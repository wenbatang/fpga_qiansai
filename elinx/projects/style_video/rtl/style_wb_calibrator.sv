// One-shot neutral-target calibration, BGGR / measured black levels only.
// No automatic scene assumptions: the operator must fill the central ROI with white/gray.
module style_wb_calibrator #(
    parameter integer DEBOUNCE_CYCLES=1000000,
    parameter integer TIMEOUT_CYCLES=100000000,
    parameter integer DEFAULT_R=493,
    parameter integer DEFAULT_B=504
)(
    input wire clk, rst_n,
    input wire key_cal_n, key_restore_n,
    input wire s_vs,
    input wire mean_valid,
    input wire [39:0] mean_data,
    output reg [10:0] request_r, request_b,
    output reg [10:0] active_r, active_b,
    // 0 DEFAULT, 1 ARM, 2 SAMPLE, 3/4 DIVIDE, 5 APPLY, 6 LOCKED, 7 REJECT, 8 CALC.
    output reg [3:0] state
);
    localparam integer DW=DEBOUNCE_CYCLES>1?$clog2(DEBOUNCE_CYCLES):1;
    localparam integer TW=TIMEOUT_CYCLES>1?$clog2(TIMEOUT_CYCLES):1;
    (* async_reg="true" *) reg [1:0] key_meta,key_sync;
    reg [1:0] stable_key, press;
    reg [DW-1:0] debounce[0:1];
    reg vs_q, restore_pending;
    wire sof=s_vs && !vs_q;
    integer k;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin key_meta<=3;key_sync<=3; end
        else begin key_meta<={key_restore_n,key_cal_n};key_sync<=key_meta;end
    end
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin stable_key<=3;press<=0;debounce[0]<=0;debounce[1]<=0;end
        else begin
            press<=0;
            for(k=0;k<2;k=k+1) begin
                if(key_sync[k]==stable_key[k]) debounce[k]<=0;
                else if(debounce[k]==DEBOUNCE_CYCLES-1) begin
                    stable_key[k]<=key_sync[k];debounce[k]<=0;
                    if(!key_sync[k]) press[k]<=1;
                end else debounce[k]<=debounce[k]+1'b1;
            end
        end
    end
    wire [9:0] a=mean_data[9:0],b=mean_data[19:10],c=mean_data[29:20],d=mean_data[39:30];
    wire [9:0] r=d>67?d-10'd67:10'd0;
    wire [9:0] bl=a>65?a-10'd65:10'd0;
    wire [9:0] gb=b>66?b-10'd66:10'd0, gc=c>66?c-10'd66:10'd0;
    wire [10:0] gs={1'b0,gb}+{1'b0,gc};
    wire [9:0] g=gs[10:1];
    wire acceptable=r>=32 && bl>=32 && gb>=32 && gc>=32 &&
                    a<960 && b<960 && c<960 && d<960;
    reg [11:0] sum_r,sum_g,sum_b;
    reg [1:0] samples;
    wire [9:0] avg_r=sum_r[11:2],avg_g=sum_g[11:2],avg_b=sum_b[11:2];
    reg [TW-1:0] timeout_count;
    // Restoring division: 19 clocks per ratio, no combinational variable divider.
    reg [18:0] numerator,quotient;
    reg [10:0] remainder;
    reg [9:0] divisor;
    reg [4:0] bit_count;
    reg [10:0] candidate_r;
    wire [11:0] trial={remainder,numerator[18]};
    wire take=trial>={2'b0,divisor};
    wire [18:0] next_q={quotient[17:0],take};
    wire [11:0] next_rem=take?trial-{2'b0,divisor}:trial;
    wire busy=state!=0 && state!=6 && state!=7;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            vs_q<=0;state<=0;restore_pending<=0;timeout_count<=0;
            request_r<=DEFAULT_R;request_b<=DEFAULT_B;active_r<=DEFAULT_R;active_b<=DEFAULT_B;
            sum_r<=0;sum_g<=0;sum_b<=0;samples<=0;
            numerator<=0;quotient<=0;remainder<=0;divisor<=1;bit_count<=0;candidate_r<=0;
        end else begin
            vs_q<=s_vs;
            if(busy) timeout_count<=timeout_count+1'b1;else timeout_count<=0;
            // Requests and capture latch on the same SOF; report the applied tuple.
            if(sof) begin active_r<=request_r;active_b<=request_b;end
            if(press[1]) begin
                request_r<=DEFAULT_R;request_b<=DEFAULT_B;state<=5;
                restore_pending<=1;timeout_count<=0;
            end else if(press[0] && !busy) begin
                // Ignore extra calibration presses while a request is busy.
                state<=1;restore_pending<=0;timeout_count<=0;
                sum_r<=0;sum_g<=0;sum_b<=0;samples<=0;
            end else if(busy && timeout_count==TIMEOUT_CYCLES-1 && !(state==5 && sof)) begin
                state<=7;request_r<=active_r;request_b<=active_b;
            end else case(state)
                1:if(sof) state<=2; // Ignore the frame already in flight at the key press.
                2:if(mean_valid) begin
                    if(!acceptable) state<=7;
                    else begin
                        sum_r<=sum_r+r;sum_g<=sum_g+g;sum_b<=sum_b+bl;
                        if(samples==3) state<=8;else samples<=samples+1'b1;
                    end
                end
                8:begin
                    numerator<={1'b0,avg_g,8'b0}+{10'b0,avg_r[9:1]};
                    divisor<=avg_r;quotient<=0;remainder<=0;bit_count<=0;state<=3;
                end
                3,4:begin
                    numerator<={numerator[17:0],1'b0};quotient<=next_q;
                    remainder<=next_rem[10:0];bit_count<=bit_count+1'b1;
                    if(bit_count==18) begin
                        if(next_q<64 || next_q>1024) state<=7;
                        else if(state==3) begin
                            candidate_r<=next_q[10:0];
                            numerator<={1'b0,avg_g,8'b0}+{10'b0,avg_b[9:1]};
                            divisor<=avg_b;quotient<=0;remainder<=0;bit_count<=0;state<=4;
                        end else begin
                            request_r<=candidate_r;request_b<=next_q[10:0];state<=5;
                        end
                    end
                end
                5:if(sof) state<=restore_pending?0:6;
                default:;
            endcase
        end
    end
endmodule
