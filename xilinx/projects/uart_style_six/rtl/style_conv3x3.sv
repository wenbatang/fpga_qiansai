// Int8 dilated convolution: 9 spatial taps reused, all input/output channels
// parallel. Registered product, pair, partial and dot stages limit the adder path.
// Mirror boundaries, with edge replication on axes no longer than dilation.
// Address remapping reuses the existing history RAM; no extra pixels or crop.
module style_conv3x3 #(
    parameter integer WIDTH=1280, HEIGHT=720, CIN=3, COUT=8, DILATION=1,
    parameter integer PHASE_INPUT=0,
    parameter WEIGHT_FILE="", BIAS_FILE="", SHIFT_FILE=""
)(
    input wire clk, reset, start,
    input wire [2:0] style,
    input wire [CIN*8-1:0] in_data, input wire in_valid, output wire in_ready,
    output reg [COUT*8-1:0] out_data, output reg out_valid, input wire out_ready,
    output reg done
);
    localparam integer PW=WIDTH+2*DILATION, PH=HEIGHT+2*DILATION;
    localparam integer ROWS=2*DILATION+1;
    localparam IDLE=0, FEED=1, TAPS=2, DRAIN=3, EMIT=4;
    reg [2:0] state;
    reg [15:0] px,py;
    reg [$clog2(ROWS)-1:0] row_ptr;
    reg [3:0] tap;
    reg [2:0] style_hold;
    // Efinity: a shallow wide ROM in logic preserves scarce RAM10 blocks.
    // Xilinx may choose its own efficient memory implementation.
    (* syn_romstyle="logic" *) reg [CIN*COUT*8-1:0] weights [0:53];
    reg signed [31:0] biases [0:6*COUT-1];
    reg [7:0] shifts [0:5];
    initial begin
        if (WEIGHT_FILE!="") $readmemh(WEIGHT_FILE,weights);
        if (BIAS_FILE!="") $readmemh(BIAS_FILE,biases);
        if (SHIFT_FILE!="") $readmemh(SHIFT_FILE,shifts);
    end
    wire actual=px>=DILATION && px<WIDTH+DILATION && py>=DILATION && py<HEIGHT+DILATION;
    assign in_ready=state==FEED && actual;
    localparam integer ROW_BITS=$clog2(ROWS),COL_BITS=$clog2(PW);
    reg [1:0] kr,kc;
    reg [COL_BITS-1:0] read_x;
    reg [ROW_BITS-1:0] row_lag;
    integer raw_x,raw_y;
    always @* begin
        case(tap)
            0:begin kr=0;kc=0;end 1:begin kr=0;kc=1;end 2:begin kr=0;kc=2;end
            3:begin kr=1;kc=0;end 4:begin kr=1;kc=1;end 5:begin kr=1;kc=2;end
            6:begin kr=2;kc=0;end 7:begin kr=2;kc=1;end 8:begin kr=2;kc=2;end
            default:begin kr=0;kc=0;end
        endcase
        raw_x=0;raw_y=0;
        // Decode nine taps and retain only the bounded row/column widths.
        // Avoid a 32-bit tap-dependent subtract/compare/subtract chain.
        if(WIDTH>DILATION)case(kc)
            0:read_x=px<3*DILATION ? 4*DILATION-px : px-2*DILATION;
            1:read_x=px-DILATION;
            default:read_x=px>=WIDTH+DILATION ? 2*(WIDTH+DILATION-1)-px : px;
        endcase
        else begin
            raw_x=px-2*DILATION+kc*DILATION;
            read_x=raw_x<DILATION ? DILATION : raw_x>=WIDTH+DILATION ? WIDTH+DILATION-1:raw_x;
        end
        if(HEIGHT>DILATION)case(kr)
            0:row_lag=py<3*DILATION ? (py-2*DILATION)<<1 : 2*DILATION;
            1:row_lag=DILATION;
            default:row_lag=py>=HEIGHT+DILATION ? (py-(HEIGHT+DILATION-1))<<1 : 0;
        endcase
        else begin
            raw_y=py-2*DILATION+kr*DILATION;
            if(raw_y<DILATION)raw_y=DILATION;
            else if(raw_y>=HEIGHT+DILATION)raw_y=HEIGHT+DILATION-1;
            row_lag=py-raw_y;
        end
        // At each output every required mirrored sample has already arrived.
        // Its age is <= 2*DILATION, so it is still in the circular row RAM.
    end
    wire [CIN*8-1:0] sample;
    localparam integer RAM_ADDR_BITS=$clog2(ROWS*PW);
    wire [ROW_BITS:0] row_delta={1'b0,row_ptr}-{1'b0,row_lag};
    wire [ROW_BITS-1:0] read_row=row_delta[ROW_BITS] ? row_delta+ROWS : row_delta;
    (* use_dsp="no", syn_use_dsp="no" *) wire [RAM_ADDR_BITS-1:0] write_row_base;
    (* use_dsp="no", syn_use_dsp="no" *) wire [RAM_ADDR_BITS-1:0] read_row_base;
    assign write_row_base=row_ptr*PW;
    assign read_row_base=read_row*PW;
    wire [RAM_ADDR_BITS-1:0] write_address=write_row_base+px;
    wire [RAM_ADDR_BITS-1:0] read_address=read_row_base+read_x;
    style_line_ram #(.DATA_BITS(CIN*8),.DEPTH(ROWS*PW)) history(
        .clk(clk),.write_enable(!reset && state==FEED && (!actual || in_valid)),
        .write_address(write_address),.write_data(actual ? in_data : {CIN*8{1'b0}}),
        .read_enable(state==TAPS),.read_address(read_address),.read_data(sample));
    reg [CIN*COUT*8-1:0] weight_word;
    wire [5:0] weight_address=style_hold*9+tap;
    reg [5:0] valid_pipe,last_pipe;
    wire signed [17:0] products [0:CIN*COUT-1];
    wire signed [31:0] accum [0:COUT-1];
    integer o;
    reg signed [32:0] rounded;
    genvar lane;
    generate for(lane=0;lane<CIN*COUT;lane=lane+1) begin:g_multiply
        if(PHASE_INPUT && lane%CIN>=3)begin:g_phase
            // Coordinate values are exactly 0,85,170,255 (2-bit phase repeated
            // four times). Compute their signed product with shifts/adds so
            // the two extra inputs consume no DSP multipliers.
            wire signed [17:0] weight_extended={{10{weight_word[lane*8+7]}},weight_word[lane*8+:8]};
            (* use_dsp="no",syn_use_dsp="no" *) wire signed [17:0] times85;
            assign times85=(weight_extended<<<6)+(weight_extended<<<4)+(weight_extended<<<2)+weight_extended;
            (* use_dsp="no",syn_use_dsp="no" *) reg signed [17:0] product_reg;
            always @(posedge clk)if(valid_pipe[0])case(sample[(lane%CIN)*8+:2])
                0:product_reg<=0;
                1:product_reg<=times85;
                2:product_reg<=times85<<<1;
                3:product_reg<=times85+(times85<<<1);
            endcase
            assign products[lane]=product_reg;
        end else begin:g_general
            (* use_dsp="yes", syn_use_dsp="yes" *) reg signed [17:0] product_reg;
            always @(posedge clk) if(valid_pipe[0])
                product_reg <= $signed({1'b0,sample[(lane%CIN)*8+:8]}) *
                    $signed(weight_word[lane*8+:8]);
            assign products[lane]=product_reg;
        end
    end endgenerate
    genvar output_channel,pair_index;
    generate for(output_channel=0;output_channel<COUT;output_channel=output_channel+1) begin:g_sum
        wire signed [31:0] pairs [0:5];
        for(pair_index=0;pair_index<6;pair_index=pair_index+1) begin:g_pair
            reg signed [31:0] pair_reg;
            if(2*pair_index+1<CIN) begin:g_two
                always @(posedge clk)if(valid_pipe[1])
                    pair_reg<=$signed(products[output_channel*CIN+2*pair_index])+
                              $signed(products[output_channel*CIN+2*pair_index+1]);
            end else if(2*pair_index<CIN) begin:g_one
                always @(posedge clk)if(valid_pipe[1])pair_reg<=products[output_channel*CIN+2*pair_index];
            end else begin:g_zero
                always @(posedge clk)if(valid_pipe[1])pair_reg<=0;
            end
            assign pairs[pair_index]=pair_reg;
        end
        reg signed [31:0] partial_left,partial_right,dot_reg,accumulator;
        always @(posedge clk) begin
            if(valid_pipe[2])begin partial_left<=(pairs[0]+pairs[1])+pairs[2];partial_right<=(pairs[3]+pairs[4])+pairs[5];end
            if(valid_pipe[3])dot_reg<=partial_left+partial_right;
            if(reset)accumulator<=0;
            else if(state==FEED && (!actual || in_valid) && px>=2*DILATION && py>=2*DILATION)
                accumulator<=biases[style_hold*COUT+output_channel];
            else if(valid_pipe[4])accumulator<=accumulator+dot_reg;
        end
        assign accum[output_channel]=accumulator;
    end endgenerate
    // Pixel pointer changes only after the result has been accepted.
    task automatic advance;
        begin
            if (px==PW-1) begin
                px<=0;
                if (row_ptr==ROWS-1) row_ptr<=0; else row_ptr<=row_ptr+1;
                if (py==PH-1) begin state<=IDLE; done<=1; end
                else begin py<=py+1; state<=FEED; end
            end else begin px<=px+1; state<=FEED; end
        end
    endtask
    always @(posedge clk) begin
        done<=0;
        if (reset) begin
            state<=IDLE; px<=0; py<=0; row_ptr<=0; tap<=0;
            valid_pipe<=0; last_pipe<=0; out_valid<=0; out_data<=0;
            weight_word<=0; style_hold<=0;
        end else begin
            valid_pipe<={valid_pipe[4:0],state==TAPS};
            last_pipe<={last_pipe[4:0],state==TAPS && tap==8};
            if (state==TAPS) weight_word<=weights[weight_address];
            case(state)
                IDLE: if(start) begin
                    state<=FEED; px<=0; py<=0; row_ptr<=0; style_hold<=style<6 ? style:0; out_valid<=0;
                    valid_pipe<=0; last_pipe<=0;
                end
                FEED: if(!actual || in_valid) begin
                    if(px>=2*DILATION && py>=2*DILATION) begin
                        tap<=0; state<=TAPS;
                    end else advance();
                end
                TAPS: if(tap==8) state<=DRAIN; else tap<=tap+1;
                DRAIN: if(last_pipe[5]) begin
                    for(o=0;o<COUT;o=o+1) begin
                        if(shifts[style_hold]==0) rounded=$signed(accum[o]);
                        else rounded=($signed({accum[o][31],accum[o]})+(33'sd1 << (shifts[style_hold]-1))) >>> shifts[style_hold];
                        if(rounded<0) out_data[o*8+:8]<=0;
                        else if(rounded>255) out_data[o*8+:8]<=255;
                        else out_data[o*8+:8]<=rounded[7:0];
                    end
                    out_valid<=1; state<=EMIT;
                end
                EMIT: if(out_ready) begin out_valid<=0; advance(); end
                default: state<=IDLE;
            endcase
        end
    end
endmodule
