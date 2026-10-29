// INDEPENDENT FPS EXPERIMENT. Not used by the signed camera project.
// Full RGB565 DDR frame -> overlapping CNN strips -> full DDR frame.
// One 16-beat read burst and one single-beat write may be outstanding.
// Read addresses are 256-byte aligned, never crossing a 4KB AXI boundary.
// Completion requires all strips and the final DDR B response; no tile is
// published independently. Errors drain accepted transactions before return.
module fps_tile_engine_3bank_srl #(
    parameter integer WIDTH=1280,HEIGHT=720,DEPTH=5,COORD_PHASE=0,
    parameter integer TILE_CORE=640,HALO=16,
    parameter W0="",B0="",S0="",W1="",B1="",S1="",W2="",B2="",S2="",
    parameter W3="",B3="",S3="",W4="",B4="",S4="",
    parameter [29:0] SOURCE_BASE=30'h00400000,BANK_STRIDE=30'h00200000
)(input wire clk,fast_clk,reset,start,input wire[1:0] style,input wire raw_mode,output reg raw_active,output reg[127:0] image_stats,input wire[1:0] output_bank,input wire[29:0] source_base,
 input wire cfg_valid,input wire[15:0] cfg_address,input wire[31:0] cfg_data,output wire cfg_ready,
  output reg busy,done,error,output reg[31:0] cycles,
  output reg[29:0] araddr,output wire arvalid,input wire arready,
  input wire[127:0] rdata,input wire[1:0] rresp,input wire rvalid,rlast,output wire rready,
  output wire[29:0] awaddr,output wire awvalid,input wire awready,
  output wire[127:0] wdata,output wire wvalid,input wire wready,
  input wire[1:0] bresp,input wire bvalid,output wire bready);
    localparam integer TILE_WIDTH=TILE_CORE+2*HALO;
    localparam IDLE=0,LAUNCH=1,RUN=2,GAP=3;
    localparam RD_IDLE=0,RD_ADDRESS=1,RD_DATA=2;
    reg[1:0] state,read_state,write_state;
    reg[15:0] tile_base,in_x,in_y,out_x,out_y;
    reg signed[15:0] origin_x;
    reg[1:0] style_hold;
    reg[31:0] sum_r,sum_g,sum_b;
    reg[29:0] source_hold;
    reg[29:0] out_base,in_row_bytes,out_row_bytes,cache_address,write_address;
    reg[127:0] cache[0:15];
    reg cache_valid,failed,tile_done_seen,aw_done,w_done;
    reg[4:0] read_beat;
    reg[127:0] output_word;
    reg[2:0] output_lane;
    reg[31:0] inputs,outputs,kept_outputs;
    wire signed[16:0] global_x=$signed({origin_x[15],origin_x})+$signed({1'b0,in_x});
    wire in_frame=global_x>=0 && global_x<WIDTH;
    wire[15:0] source_x=global_x[15:0];
    wire[29:0] wanted_address=source_hold+in_row_bytes+{13'd0,source_x[15:7],8'd0};
    wire cache_hit=cache_valid && cache_address==wanted_address;
    wire[127:0] cache_word=cache[source_x[6:3]];
    wire[15:0] raw=cache_word[source_x[2:0]*16+:16];
    wire[23:0] rgb={{raw[4:0],raw[4:2]},{raw[10:5],raw[10:9]},{raw[15:11],raw[15:13]}};
    wire cnn_in_valid=state==RUN && !failed && inputs<TILE_WIDTH*HEIGHT && (!in_frame || cache_hit);
    wire cnn_in_ready,cnn_out_valid,cnn_done;
    wire[23:0] cnn_rgb;
    wire keep=out_x>=HALO && out_x<HALO+TILE_CORE && tile_base+out_x-HALO<WIDTH;
    wire cnn_out_ready=state==RUN && !failed && (!keep || write_state==0);
    wire take_input=cnn_in_valid && cnn_in_ready;
    wire take_output=cnn_out_valid && cnn_out_ready;
    wire[15:0] result565={cnn_rgb[7:3],cnn_rgb[15:10],cnn_rgb[23:19]};
    assign arvalid=read_state==RD_ADDRESS;
    assign rready=read_state==RD_DATA;
    assign awaddr=write_address;
    assign awvalid=write_state==1 && !aw_done;
    assign wdata=output_word;
    assign wvalid=write_state==1 && !w_done;
    assign bready=write_state==2;
    fps_cnn_async_srl #(.WIDTH(TILE_WIDTH),.HEIGHT(HEIGHT),.FRAME_WIDTH(WIDTH),
        .W0(W0),.B0(B0),.S0(S0),.W1(W1),.B1(B1),.S1(S1),.W2(W2),.B2(B2),.S2(S2),
        .W3(W3),.B3(B3),.S3(S3),.W4(W4),.B4(B4),.S4(S4)) cnn(
        .clk(clk),.fast_clk(fast_clk),.global_reset(reset),.reset(reset || state==IDLE || state==GAP),.start(state==LAUNCH),.raw_mode(raw_active),
        .style({1'b0,style_hold}),.origin_x(origin_x),.in_rgb(in_frame ? rgb:24'd0),
        .in_valid(cnn_in_valid),.in_ready(cnn_in_ready),.out_rgb(cnn_rgb),
        .out_valid(cnn_out_valid),.out_ready(cnn_out_ready),.done(cnn_done),.cfg_valid(cfg_valid),.cfg_address(cfg_address),.cfg_data(cfg_data),.cfg_ready(cfg_ready));
    always @(posedge clk)begin
        done<=0;error<=0;
        if(reset)begin
            raw_active<=1;image_stats<=0;sum_r<=0;sum_g<=0;sum_b<=0;
            state<=IDLE;busy<=0;cycles<=0;tile_base<=0;origin_x<=-HALO;style_hold<=0;
            in_x<=0;in_y<=0;out_x<=0;out_y<=0;in_row_bytes<=0;out_row_bytes<=0;out_base<=0;source_hold<=0;
            cache_valid<=0;cache_address<=0;read_state<=RD_IDLE;araddr<=0;read_beat<=0;
            write_state<=0;write_address<=0;output_word<=0;output_lane<=0;aw_done<=0;w_done<=0;
            failed<=0;tile_done_seen<=0;inputs<=0;outputs<=0;kept_outputs<=0;
        end else begin
            if(busy)cycles<=cycles+1;
            case(state)
            IDLE: if(start)begin
                state<=GAP;busy<=1;cycles<=0;tile_base<=0;origin_x<=-HALO;style_hold<=style;source_hold<=source_base;
                out_base<=output_bank==2'd2 ? 30'h00a00000:(output_bank==2'd1 ? BANK_STRIDE:0);failed<=0;kept_outputs<=0;
                raw_active<=raw_mode;sum_r<=0;sum_g<=0;sum_b<=0;
            end
            GAP: begin
                in_x<=0;in_y<=0;out_x<=0;out_y<=0;in_row_bytes<=0;out_row_bytes<=0;
                cache_valid<=0;inputs<=0;outputs<=0;tile_done_seen<=0;output_lane<=0;output_word<=0;
                state<=LAUNCH;
            end
            LAUNCH: state<=RUN;
            RUN: begin
                if(cnn_done)tile_done_seen<=1;
                if(read_state==RD_IDLE && inputs<TILE_WIDTH*HEIGHT && in_frame && !cache_hit && !failed)begin
                    araddr<=wanted_address;cache_address<=wanted_address;cache_valid<=0;read_state<=RD_ADDRESS;
                end
                if(take_input)begin
                    inputs<=inputs+1;
                    if(in_x==TILE_WIDTH-1)begin in_x<=0;in_y<=in_y+1;in_row_bytes<=in_row_bytes+WIDTH*2;end
                    else in_x<=in_x+1;
                end
                if(take_output)begin
                    outputs<=outputs+1;
                    if(out_x==TILE_WIDTH-1)begin out_x<=0;out_y<=out_y+1;out_row_bytes<=out_row_bytes+WIDTH*2;end
                    else out_x<=out_x+1;
                    if(keep)begin
                        kept_outputs<=kept_outputs+1;
                        sum_r<=sum_r+{24'd0,result565[15:11],result565[15:13]};
                        sum_g<=sum_g+{24'd0,result565[10:5],result565[10:9]};
                        sum_b<=sum_b+{24'd0,result565[4:0],result565[4:2]};
                        if(output_lane==0)write_address<=out_base+out_row_bytes+(tile_base+out_x-HALO)*2;
                        output_word[output_lane*16+:16]<=result565;
                        output_lane<=output_lane+1;
                        if(output_lane==7)begin write_state<=1;aw_done<=0;w_done<=0;end
                    end
                end
                if(!failed && tile_done_seen && inputs==TILE_WIDTH*HEIGHT && outputs==TILE_WIDTH*HEIGHT && read_state==RD_IDLE && write_state==0)begin
                    if(output_lane!=0)failed<=1;
                    else if(tile_base+TILE_CORE>=WIDTH)begin
                        if(kept_outputs!=WIDTH*HEIGHT)failed<=1;
                        else begin state<=IDLE;busy<=0;done<=1;image_stats<={kept_outputs,sum_r,sum_g,sum_b};end
                    end else begin tile_base<=tile_base+TILE_CORE;origin_x<=origin_x+TILE_CORE;state<=GAP;end
                end
                if(failed && read_state==RD_IDLE && write_state==0)begin state<=IDLE;busy<=0;error<=1;end
            end
            default: state<=IDLE;
            endcase
            if(arvalid && arready)begin read_state<=RD_DATA;read_beat<=0;end
            if(rvalid && rready)begin
                if(rresp!=0 || rlast!=(read_beat==15))failed<=1;
                if(!failed && rresp==0 && rlast==(read_beat==15))cache[read_beat[3:0]]<=rdata;
                if(rlast)begin read_state<=RD_IDLE;cache_valid<=!failed && rresp==0 && read_beat==15;end
                else read_beat<=read_beat+1;
            end
            if(write_state==1)begin
                if(awvalid && awready)aw_done<=1;
                if(wvalid && wready)w_done<=1;
                if((aw_done || (awvalid && awready)) && (w_done || (wvalid && wready)))write_state<=2;
            end
            if(bvalid && bready)begin
                write_state<=0;output_word<=0;
                if(bresp!=0)failed<=1;
            end
        end
    end
endmodule
