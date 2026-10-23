// DDR source -> learned CNN -> DDR back buffer. Success is asserted only
// after the last output AXI B response, never merely after the last pixel.
module style_frame_engine #(
    parameter integer WIDTH=1280,HEIGHT=720,DEPTH=3,COORD_PHASE=0,
    parameter W0="", B0="", S0="", W1="", B1="", S1="", W2="", B2="", S2="",
    parameter W3="",B3="",S3="",W4="",B4="",S4="",
    parameter [29:0] SOURCE_BASE=30'h00400000, BANK_STRIDE=30'h00200000
)(input wire clk,reset,start,input wire [2:0] style,input wire output_bank,
  output reg busy,done,error,output reg [31:0] cycles,
  output reg [29:0] araddr,output reg arvalid,input wire arready,
  input wire [127:0] rdata,input wire [1:0] rresp,input wire rvalid,rlast,output wire rready,
  output wire [29:0] awaddr,output wire awvalid,input wire awready,
  output wire [127:0] wdata,output wire wvalid,input wire wready,
  input wire [1:0] bresp,input wire bvalid,output wire bready);
    localparam integer FRAME_BYTES=WIDTH*HEIGHT*2,PIXELS=WIDTH*HEIGHT;
    reg [127:0] fifo[0:31];
    reg [4:0] wp,rp;
    reg [5:0] word_count;
    reg [2:0] subpixel;
    reg [29:0] read_offset,write_offset,out_base;
    reg read_active;
    reg [4:0] read_beat;
    reg failed,cnn_reset;
    wire cnn_in_ready,cnn_out_valid,cnn_done;
    wire [23:0] cnn_rgb;
    wire [15:0] raw=fifo[rp][subpixel*16+:16];
    wire [23:0] input_rgb={{raw[4:0],raw[4:2]},{raw[10:5],raw[10:9]},{raw[15:11],raw[15:13]}};
    wire cnn_in_valid=busy && !failed && word_count!=0;
    wire take_pixel=cnn_in_valid && cnn_in_ready;
    wire pop_word=take_pixel && subpixel==7;
    // A full burst is reserved before issuing AR, so no accepted beat is lost.
    assign rready=busy && read_active;
    wire push_word=rvalid && rready && !failed && rresp==0 && rlast==(read_beat==15);
    reg [127:0] output_word;
    reg [2:0] output_lane;
    reg [31:0] output_pixels;
    reg [1:0] write_state;
    reg aw_done,w_done;
    wire cnn_out_ready=busy && !failed && write_state==0;
    wire take_output=cnn_out_valid && cnn_out_ready;
    wire [15:0] rgb565={cnn_rgb[7:3],cnn_rgb[15:10],cnn_rgb[23:19]};
    assign awaddr=out_base+write_offset;
    assign awvalid=write_state==1 && !aw_done;
    assign wdata=output_word;
    assign wvalid=write_state==1 && !w_done;
    assign bready=write_state==2;
    generate if(DEPTH==3) begin:g_three
    style_cnn_stream #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.W0(W0),.B0(B0),.S0(S0),
        .W1(W1),.B1(B1),.S1(S1),.W2(W2),.B2(B2),.S2(S2)) cnn(
        .clk(clk),.reset(reset || cnn_reset),.start(start && !busy),.style(style),
        .in_rgb(input_rgb),.in_valid(cnn_in_valid),.in_ready(cnn_in_ready),
        .out_rgb(cnn_rgb),.out_valid(cnn_out_valid),.out_ready(cnn_out_ready),.done(cnn_done));
    end else begin:g_five
    style_cnn_stream5 #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.COORD_PHASE(COORD_PHASE),.W0(W0),.B0(B0),.S0(S0),
        .W1(W1),.B1(B1),.S1(S1),.W2(W2),.B2(B2),.S2(S2),.W3(W3),.B3(B3),.S3(S3),.W4(W4),.B4(B4),.S4(S4)) cnn(
        .clk(clk),.reset(reset || cnn_reset),.start(start && !busy),.style(style),
        .in_rgb(input_rgb),.in_valid(cnn_in_valid),.in_ready(cnn_in_ready),
        .out_rgb(cnn_rgb),.out_valid(cnn_out_valid),.out_ready(cnn_out_ready),.done(cnn_done));
    end endgenerate
    always @(posedge clk) begin
        done<=0; error<=0; cnn_reset<=0;
        if(reset) begin
            busy<=0;cycles<=0;araddr<=0;arvalid<=0;read_active<=0;
            read_offset<=0;write_offset<=0;out_base<=0;read_beat<=0;
            wp<=0;rp<=0;word_count<=0;subpixel<=0;failed<=0;
            output_word<=0;output_lane<=0;output_pixels<=0;write_state<=0;aw_done<=0;w_done<=0;
        end else if(start && !busy) begin
            busy<=1;cycles<=0;read_offset<=0;write_offset<=0;out_base<=output_bank ? BANK_STRIDE : 0;
            wp<=0;rp<=0;word_count<=0;subpixel<=0;failed<=0;read_active<=0;read_beat<=0;arvalid<=0;
            output_word<=0;output_lane<=0;output_pixels<=0;write_state<=0;aw_done<=0;w_done<=0;
        end else if(busy) begin
            cycles<=cycles+1;
            if(!read_active && !arvalid && !failed && read_offset<FRAME_BYTES && word_count<=16) begin
                araddr<=SOURCE_BASE+read_offset;arvalid<=1;
            end
            if(arvalid && arready) begin arvalid<=0;read_active<=1;read_beat<=0;end
            if(rvalid && rready) begin
                if(rresp!=0 || rlast!=(read_beat==15)) failed<=1;
                if(push_word) begin fifo[wp]<=rdata;wp<=wp+1;end
                if(rlast) begin read_active<=0;read_offset<=read_offset+256;end
                else read_beat<=read_beat+1;
            end
            case({push_word,pop_word})
                2'b10: word_count<=word_count+1;
                2'b01: word_count<=word_count-1;
                default: ;
            endcase
            if(take_pixel) begin
                subpixel<=subpixel+1;
                if(pop_word) rp<=rp+1;
            end
            if(take_output) begin
                output_word[output_lane*16+:16]<=rgb565;
                output_lane<=output_lane+1;output_pixels<=output_pixels+1;
                if(output_lane==7) begin write_state<=1;aw_done<=0;w_done<=0;end
            end
            if(write_state==1) begin
                if(awvalid && awready) aw_done<=1;
                if(wvalid && wready) w_done<=1;
                if((aw_done || awready) && (w_done || wready)) write_state<=2;
            end
            if(bvalid && bready) begin
                write_state<=0;output_word<=0;
                if(bresp!=0) failed<=1;
                else if(write_offset==FRAME_BYTES-16 && !failed) begin
                    if(read_offset==FRAME_BYTES && !read_active && !arvalid && output_pixels==PIXELS) begin
                        busy<=0;done<=1;
                    end else failed<=1;
                end else write_offset<=write_offset+16;
            end
            // Do not withdraw VALID under backpressure: drain all outstanding
            // AXI transactions before returning an error and resetting CNN.
            if(failed && !read_active && !arvalid && write_state==0) begin
                busy<=0;error<=1;cnn_reset<=1;
            end
        end
    end
endmodule
