// Input and result pools have independent ownership. The displayed original is
// retained with its result until a safe display switch releases BOTH slots.
module style_frame_pool #(
    parameter integer INPUT_SLOTS=4, RESULT_SLOTS=2,
    parameter [31:0] BASE_ADDR=32'h01000000,
    parameter [31:0] SLOT_BYTES=32'h00200000
)(
    input wire clk,rst_n,
    output reg cap_available, output reg [1:0] cap_slot, output reg [31:0] cap_addr,
    input wire cap_take,cap_done,cap_ok,input wire [1:0] cap_take_slot,
    input wire [1:0] cap_done_slot,input wire [31:0] cap_done_id,
    output reg job_available,
    output reg [1:0] job_input_slot, output reg job_result_slot,
    output reg [31:0] job_input_addr,job_result_addr,job_frame_id,
    input wire job_take,job_done,job_ok,input wire [1:0] job_take_input,input wire job_take_result,
    input wire [1:0] job_done_input,input wire job_done_result,
    input wire display_switch,
    output reg front_valid,pending_valid,
    output reg [31:0] front_input_addr,front_result_addr,front_frame_id,
    output wire [3:0] ready_mask,
    output reg [31:0] captured_count,processed_count,displayed_count,error_count
);
    localparam [2:0] FREE=0,CAPTURE=1,READY=2,PROCESS=3,RETAIN=4;
    localparam [1:0] OUT_FREE=0,OUT_WRITE=1,OUT_RETAIN=2;
    reg [2:0] input_state [0:INPUT_SLOTS-1];
    reg [1:0] result_state [0:RESULT_SLOTS-1];
    reg [31:0] input_id [0:INPUT_SLOTS-1];
    reg [1:0] pending_input,front_input;
    reg pending_result,front_result;
    reg [31:0] pending_id;
    integer i;
    reg found_input,found_output;
    wire capture_failure=cap_done && input_state[cap_done_slot]==CAPTURE && !cap_ok;
    wire job_failure=job_done && input_state[job_done_input]==PROCESS &&
                     result_state[job_done_result]==OUT_WRITE && (!job_ok || pending_valid);
    always @* begin
        cap_available=0;cap_slot=0;cap_addr=BASE_ADDR;
        for(integer c=0;c<INPUT_SLOTS;c=c+1)
            if(!cap_available && input_state[c]==FREE) begin
                cap_available=1;cap_slot=c;cap_addr=BASE_ADDR+c*SLOT_BYTES;
            end
        found_input=0;found_output=0;
        job_input_slot=0;job_result_slot=0;job_frame_id=0;
        for(integer j=0;j<INPUT_SLOTS;j=j+1)
            if(input_state[j]==READY && (!found_input || $signed(input_id[j]-job_frame_id)<0)) begin
                found_input=1;job_input_slot=j;job_frame_id=input_id[j];
            end
        for(integer r=0;r<RESULT_SLOTS;r=r+1)
            if(!found_output && result_state[r]==OUT_FREE) begin found_output=1;job_result_slot=r;end
        job_available=found_input && found_output && !pending_valid;
        job_input_addr=BASE_ADDR+job_input_slot*SLOT_BYTES;
        job_result_addr=BASE_ADDR+(INPUT_SLOTS+job_result_slot)*SLOT_BYTES;
    end
    generate for(genvar k=0;k<4;k=k+1) begin:ready_bits
        if(k<INPUT_SLOTS) assign ready_mask[k]=input_state[k]==READY;
        else assign ready_mask[k]=1'b0;
    end endgenerate
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            for(i=0;i<INPUT_SLOTS;i=i+1) begin input_state[i]<=FREE;input_id[i]<=0;end
            for(i=0;i<RESULT_SLOTS;i=i+1) result_state[i]<=OUT_FREE;
            front_valid<=0;pending_valid<=0;front_input<=0;front_result<=0;
            pending_input<=0;pending_result<=0;pending_id<=0;
            front_input_addr<=BASE_ADDR;front_result_addr<=BASE_ADDR+INPUT_SLOTS*SLOT_BYTES;
            front_frame_id<=0;captured_count<=0;processed_count<=0;displayed_count<=0;error_count<=0;
        end else begin
            // Independent capture and processing pipelines can fail together.
            // Use one assignment so neither increment overwrites the other.
            if(capture_failure || job_failure)
                error_count<=error_count+{31'b0,capture_failure}+{31'b0,job_failure};
            if(cap_take && input_state[cap_take_slot]==FREE) input_state[cap_take_slot]<=CAPTURE;
            if(cap_done && input_state[cap_done_slot]==CAPTURE) begin
                if(cap_ok) begin
                    input_state[cap_done_slot]<=READY;input_id[cap_done_slot]<=cap_done_id;
                    captured_count<=captured_count+1'b1;
                end else input_state[cap_done_slot]<=FREE;
            end
            if(job_take && input_state[job_take_input]==READY && result_state[job_take_result]==OUT_FREE) begin
                input_state[job_take_input]<=PROCESS;result_state[job_take_result]<=OUT_WRITE;
            end
            if(job_done && input_state[job_done_input]==PROCESS && result_state[job_done_result]==OUT_WRITE) begin
                if(job_ok && !pending_valid) begin
                    input_state[job_done_input]<=RETAIN;result_state[job_done_result]<=OUT_RETAIN;
                    pending_valid<=1;pending_input<=job_done_input;pending_result<=job_done_result;
                    pending_id<=input_id[job_done_input];processed_count<=processed_count+1'b1;
                end else begin
                    input_state[job_done_input]<=FREE;result_state[job_done_result]<=OUT_FREE;
                end
            end
            // Caller must first drain previous AXI reads AND flush display FIFO
            // while the pixel domain is in its safe window.
            if(display_switch && pending_valid) begin
                if(front_valid) begin input_state[front_input]<=FREE;result_state[front_result]<=OUT_FREE;end
                front_valid<=1;front_input<=pending_input;front_result<=pending_result;
                front_input_addr<=BASE_ADDR+pending_input*SLOT_BYTES;
                front_result_addr<=BASE_ADDR+(INPUT_SLOTS+pending_result)*SLOT_BYTES;
                front_frame_id<=pending_id;pending_valid<=0;displayed_count<=displayed_count+1'b1;
            end
        end
    end
endmodule
