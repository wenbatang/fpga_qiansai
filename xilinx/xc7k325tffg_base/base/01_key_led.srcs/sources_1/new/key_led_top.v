//按键消抖控制LED
module key_led_top(
            input wire clk,
            input wire rst_n,
            input wire key,
            output wire [7:0]led
    );
    reg[7:0]led_counter_reg;
    reg [31:0]timeout_counter_reg;
    reg [2:0]state_reg;
    reg key_pre_reg;
    reg key_now_reg;
    wire negedge_key;
    
    parameter CLOCK_FRQ=50000000; 
    parameter STATE_IDLE=3'b000;
    parameter STATE_WAIT=3'b001;
    parameter STATE_DONE=3'b010;  
    parameter DEBUNCE_TIME=CLOCK_FRQ/100;//10ms消抖时间。计数器计数到CLOCK_FRQ需要1秒，除以一百就是10ms。
    
    assign led=led_counter_reg;
    
   //按钮检测下降沿。我们按钮打两拍
   //判断两拍前后跳变从1变为0即表示按钮按下 ，产生一个时钟周期拉高的  negedge_key信号
    assign negedge_key=((key_pre_reg==1'b1)&&(key_now_reg==1'b0))?1'b1:1'b0;
    always @(posedge clk, negedge rst_n) begin
        if(!rst_n) begin
            key_pre_reg<=1'b0;
            key_now_reg<=1'b0;
        end
        else begin
            key_pre_reg<=key_now_reg;
            key_now_reg<=key;
        end
    end
    //两段状态机第一段，状态转换触发。
    //按钮没有检测到下降沿，处于IDLE状态。
    //按钮下降沿检测到，则timeout_counter_reg开始计数到DEBUNCE_TIME结束
    //计数结束进入STATE_DONE状态，然后STATE_DONE直接进入IDLE
   always @(posedge clk, negedge rst_n) begin
        if(!rst_n) begin
          state_reg<=STATE_IDLE;
        end
        else begin
            case(state_reg)
            STATE_IDLE:begin
                if(negedge_key==1'b1)begin
                    timeout_counter_reg<=32'd0;
                    state_reg<=STATE_WAIT;
                end
            end
            STATE_WAIT:begin
                if(timeout_counter_reg<DEBUNCE_TIME)timeout_counter_reg<=timeout_counter_reg+'d1;
                else state_reg<=STATE_DONE;
            end
            STATE_DONE:begin
                state_reg<=STATE_IDLE;
                timeout_counter_reg<=32'd0;
            end
            default:;
            endcase
        end
    end
    //STATE_DONE状态的时候，表示离检测到按键下降沿的时刻开始持续了10ms时间了
    //也就是说按钮按下下降沿10ms后，这里判断key是否还是按下状态，是的话LED计数加1
    always @(posedge clk, negedge rst_n) begin
        if(!rst_n) begin
            led_counter_reg<=8'd0;
        end
        else if((state_reg==STATE_DONE)&&(key==1'b0))led_counter_reg<=led_counter_reg+8'd1;
    end
    
endmodule
