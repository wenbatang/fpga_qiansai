// Passive core-domain observer. No output participates in video/AXI flow control.
// Frame timing begins at core capture-slot allocation, NOT sensor exposure.
module style_perf_monitor #(
    parameter integer CORE_HZ=100000000
)(
    input wire clk,rst_n,second_tick,
    input wire cap_start,cap_done,cap_ok,
    input wire [1:0] cap_slot,
    input wire [31:0] cap_id,
    input wire job_start,job_done,job_ok,
    input wire [1:0] job_slot,
    input wire [31:0] job_id,
    input wire publish,
    input wire arvalid,arready,rvalid,rready,rlast,
    input wire awvalid,awready,wvalid,wready,wlast,bvalid,bready,
    input wire [15:0] wstrb,
    input wire [15:0] camera_level,display_level,
    input wire [6:0] paddr,
    input wire psel,penable,pwrite,
    input wire [31:0] pwdata,
    output wire [31:0] prdata,
    output wire pslverr,
    output reg [1023:0] snapshot,
    output reg snapshot_valid
);
    localparam integer DIV=CORE_HZ>=1000000?CORE_HZ/1000000:1;
    localparam integer DW=DIV>1?$clog2(DIV):1;
    localparam integer TICK_HZ=CORE_HZ/DIV;
    reg [DW-1:0] prescale;
    reg [63:0] ticks,cycles,rd_bytes,wr_bytes;
    reg [63:0] previous_cycles,previous_rd,previous_wr;
    reg automatic_snapshot;
    reg [31:0] snapshot_sequence;
    wire access=psel && penable;
    wire control_write=access && pwrite && paddr==0;
    wire clear=control_write && pwdata[2];
    wire take_snapshot=(automatic_snapshot && second_tick) || (control_write && pwdata[1]);
    assign prdata=paddr[6:2]==0?{31'b0,automatic_snapshot}:snapshot[paddr[6:2]*32+:32];
    assign pslverr=access && (paddr[1:0]!=0 || (pwrite && paddr!=0));

    reg [63:0] began[0:3],captured[0:3];
    reg [31:0] tag[0:3],capture_time[0:3],queue_time[0:3],job_time[0:3];
    reg [3:0] tag_valid,capture_valid,job_valid;
    reg working_valid,pending_valid;
    reg [1:0] working_slot,pending_slot;
    reg [31:0] working_id,pending_id;
    reg [63:0] working_began;
    reg [31:0] last_id,last_cap,last_job,last_queue,last_total;
    reg [31:0] max_cap,max_job,max_total,cap_count,job_count,publish_count,tag_misses;
    reg last_valid,latency_overflow;
    wire cap_match=tag_valid[cap_slot] && tag[cap_slot]==cap_id;
    wire start_match=tag_valid[job_slot] && capture_valid[job_slot] && tag[job_slot]==job_id;
    wire job_match=working_valid && working_id==job_id && working_slot==job_slot &&
        tag_valid[job_slot] && tag[job_slot]==job_id;
    wire pub_match=pending_valid && tag_valid[pending_slot] && job_valid[pending_slot] &&
        tag[pending_slot]==pending_id;
    wire [2:0] misses={2'b0,cap_done && cap_ok && !cap_match}+
        {2'b0,job_start && !start_match}+{2'b0,job_done && job_ok && !job_match}+
        {2'b0,publish && !pub_match};
    wire [63:0] cap_elapsed=ticks-began[cap_slot];
    wire [63:0] queue_elapsed=ticks-captured[job_slot];
    wire [63:0] job_elapsed=ticks-working_began;
    wire [63:0] total_elapsed=ticks-began[pending_slot];
    function [31:0] clip32(input [63:0] value);
        clip32=|value[63:32]?32'hffffffff:value[31:0];
    endfunction
    function [31:0] inc(input [31:0] value,input enable);
        inc=(enable && value!=32'hffffffff)?value+1'b1:value;
    endfunction
    // AXI4 is 128-bit, one outstanding transaction per direction in this platform.
    reg read_pending,write_pending,write_last_seen;
    wire ar=arvalid && arready,rr=rvalid && rready;
    wire aw=awvalid && awready,ww=wvalid && wready,br=bvalid && bready;
    wire ar_stall=arvalid && !arready;
    wire read_wait=read_pending && rready && !rvalid;
    wire read_backpressure=rvalid && !rready;
    wire aw_stall=awvalid && !awready;
    wire write_stall=wvalid && !wready;
    wire response_wait=write_pending && write_last_seen && bready && !bvalid;
    reg [31:0] ars,rwait,rbp,aws,wstall,bwait,read_run,write_run,max_read_run,max_write_run;
    reg [15:0] cam_high,display_high;
    reg [4:0] bytes_this_write;
    integer i;
    always @* begin
        bytes_this_write=0;
        for(integer lane=0;lane<16;lane=lane+1) bytes_this_write=bytes_this_write+wstrb[lane];
    end
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            prescale<=0;ticks<=0;cycles<=0;rd_bytes<=0;wr_bytes<=0;
            previous_cycles<=0;previous_rd<=0;previous_wr<=0;
            automatic_snapshot<=1;snapshot_sequence<=0;snapshot<=0;snapshot_valid<=0;
            tag_valid<=0;capture_valid<=0;job_valid<=0;working_valid<=0;pending_valid<=0;
            working_slot<=0;pending_slot<=0;working_id<=0;pending_id<=0;working_began<=0;
            last_id<=0;last_cap<=0;last_job<=0;last_queue<=0;last_total<=0;
            max_cap<=0;max_job<=0;max_total<=0;cap_count<=0;job_count<=0;publish_count<=0;
            tag_misses<=0;last_valid<=0;latency_overflow<=0;
            read_pending<=0;write_pending<=0;write_last_seen<=0;
            ars<=0;rwait<=0;rbp<=0;aws<=0;wstall<=0;bwait<=0;
            read_run<=0;write_run<=0;max_read_run<=0;max_write_run<=0;cam_high<=0;display_high<=0;
            for(i=0;i<4;i=i+1) begin
                began[i]<=0;captured[i]<=0;tag[i]<=0;capture_time[i]<=0;queue_time[i]<=0;job_time[i]<=0;
            end
        end else begin
            cycles<=cycles+1'b1;snapshot_valid<=0;
            if(prescale==DIV-1) begin prescale<=0;ticks<=ticks+1'b1;end
            else prescale<=prescale+1'b1;
            if(control_write) automatic_snapshot<=pwdata[0];
            if(rr) rd_bytes<=rd_bytes+64'd16;
            if(ww) wr_bytes<=wr_bytes+bytes_this_write;
            if(ar) read_pending<=1;
            if(rr && rlast) read_pending<=0;
            if(aw) write_pending<=1;
            if(ww && wlast) write_last_seen<=1;
            if(br) begin write_pending<=0;write_last_seen<=0;end
            ars<=inc(ars,ar_stall);rwait<=inc(rwait,read_wait);rbp<=inc(rbp,read_backpressure);
            aws<=inc(aws,aw_stall);wstall<=inc(wstall,write_stall);bwait<=inc(bwait,response_wait);
            read_run<=read_wait?inc(read_run,1'b1):0;
            write_run<=write_stall?inc(write_run,1'b1):0;
            if(read_wait && inc(read_run,1'b1)>max_read_run) max_read_run<=inc(read_run,1'b1);
            if(write_stall && inc(write_run,1'b1)>max_write_run) max_write_run<=inc(write_run,1'b1);
            if(camera_level>cam_high) cam_high<=camera_level;
            if(display_level>display_high) display_high<=display_level;
            if(misses!=0) begin
                tag_misses<=tag_misses>32'hffffffff-misses?32'hffffffff:tag_misses+misses;
            end
            if(cap_start) begin
                began[cap_slot]<=ticks;tag[cap_slot]<=cap_id;tag_valid[cap_slot]<=1;
                capture_valid[cap_slot]<=0;job_valid[cap_slot]<=0;
            end
            if(cap_done) begin
                if(cap_ok && cap_match) begin
                    captured[cap_slot]<=ticks;capture_time[cap_slot]<=clip32(cap_elapsed);
                    capture_valid[cap_slot]<=1;cap_count<=inc(cap_count,1'b1);
                    if(clip32(cap_elapsed)>max_cap)max_cap<=clip32(cap_elapsed);
                    if(|cap_elapsed[63:32])latency_overflow<=1;
                end else begin tag_valid[cap_slot]<=0;capture_valid[cap_slot]<=0;end
            end
            if(job_start) begin
                working_valid<=start_match;working_slot<=job_slot;working_id<=job_id;working_began<=ticks;
                if(start_match) begin
                    queue_time[job_slot]<=clip32(queue_elapsed);
                    if(|queue_elapsed[63:32])latency_overflow<=1;
                end
            end
            if(job_done) begin
                working_valid<=0;
                if(job_ok && job_match) begin
                    job_time[job_slot]<=clip32(job_elapsed);job_valid[job_slot]<=1;
                    pending_valid<=1;pending_slot<=job_slot;pending_id<=job_id;
                    job_count<=inc(job_count,1'b1);
                    if(clip32(job_elapsed)>max_job)max_job<=clip32(job_elapsed);
                    if(|job_elapsed[63:32])latency_overflow<=1;
                end else begin tag_valid[job_slot]<=0;job_valid[job_slot]<=0;end
            end
            if(publish) begin
                pending_valid<=0;
                if(pub_match) begin
                    last_id<=pending_id;last_cap<=capture_time[pending_slot];last_job<=job_time[pending_slot];
                    last_queue<=queue_time[pending_slot];last_total<=clip32(total_elapsed);last_valid<=1;
                    publish_count<=inc(publish_count,1'b1);
                    if(clip32(total_elapsed)>max_total)max_total<=clip32(total_elapsed);
                    if(|total_elapsed[63:32])latency_overflow<=1;
                end
            end
            if(take_snapshot) begin
                snapshot_sequence<=snapshot_sequence+1'b1;snapshot_valid<=1;
                snapshot[0*32+:32]<=0;snapshot[1*32+:32]<=snapshot_sequence+1'b1;
                snapshot[2*32+:32]<=TICK_HZ;
                snapshot[3*32+:32]<={29'b0,tag_misses!=0,latency_overflow,last_valid};
                snapshot[4*32+:32]<=last_id;snapshot[5*32+:32]<=last_cap;snapshot[6*32+:32]<=max_cap;
                snapshot[7*32+:32]<=last_job;snapshot[8*32+:32]<=max_job;snapshot[9*32+:32]<=last_queue;
                snapshot[10*32+:32]<=last_total;snapshot[11*32+:32]<=max_total;
                snapshot[12*32+:32]<=cap_count;snapshot[13*32+:32]<=job_count;
                snapshot[14*32+:32]<=publish_count;snapshot[15*32+:32]<=tag_misses;
                snapshot[16*32+:64]<=cycles-previous_cycles;
                snapshot[18*32+:64]<=rd_bytes-previous_rd;
                snapshot[20*32+:64]<=wr_bytes-previous_wr;
                snapshot[22*32+:32]<=ars;snapshot[23*32+:32]<=rwait;snapshot[24*32+:32]<=rbp;
                snapshot[25*32+:32]<=aws;snapshot[26*32+:32]<=wstall;snapshot[27*32+:32]<=bwait;
                snapshot[28*32+:32]<=max_read_run;snapshot[29*32+:32]<=max_write_run;
                snapshot[30*32+:32]<={display_high,cam_high};snapshot[31*32+:32]<=CORE_HZ;
                previous_cycles<=cycles;previous_rd<=rd_bytes;previous_wr<=wr_bytes;
            end
            // Start a new interval with THIS edge's observations; the snapshot
            // above includes observations strictly before this clock edge.
            if(take_snapshot || clear) begin
                ars<={31'b0,ar_stall};rwait<={31'b0,read_wait};rbp<={31'b0,read_backpressure};
                aws<={31'b0,aw_stall};wstall<={31'b0,write_stall};bwait<={31'b0,response_wait};
                read_run<={31'b0,read_wait};write_run<={31'b0,write_stall};
                max_read_run<={31'b0,read_wait};max_write_run<={31'b0,write_stall};
                cam_high<=camera_level;display_high<=display_level;
            end
            if(clear) begin
                previous_cycles<=cycles;previous_rd<=rd_bytes;previous_wr<=wr_bytes;
                max_cap<=0;max_job<=0;max_total<=0;cap_count<=0;job_count<=0;publish_count<=0;tag_misses<=0;
                last_valid<=0;latency_overflow<=0;
                // In-flight frame timestamps and AXI ownership deliberately survive clear.
            end
        end
    end
endmodule
