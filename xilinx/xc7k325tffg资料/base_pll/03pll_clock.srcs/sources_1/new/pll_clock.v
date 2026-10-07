    module pll_clock(
        output wire [7:0] led, 
        input  wire       clk, 
        input  wire       rst_n 
    );

    assign led=led_reg;

    reg [31:0] cnt;
    reg [2:0]  led_on_number;
    
    reg [7:0]led_reg;
    wire clk_100m;
    parameter CLOCK_FREQ  =50000000;
    parameter COUNTER_MAX_CNT=CLOCK_FREQ/2-1;//count time 0.5s
    
    
    clk_wiz_0 clk_wiz_0_inst
     (
     .clk_out1(clk_100m),
     .reset(~rst_n),
     .locked(),
    .clk_in1(clk)
    ); 
    //counter 1s
    always @(posedge clk_100m, negedge rst_n) begin
        if(!rst_n) begin
            cnt <= 'd0;
            led_on_number <= 'd0;
        end
        else begin
            cnt <= cnt + 1'b1;
            if(cnt == COUNTER_MAX_CNT) begin//¼ÆÊý0.5s
                cnt <= 'd0;
                led_on_number <= led_on_number + 1'b1;
            end
        end
    end
//indicate whitch led on
    always @(posedge clk_100m, negedge rst_n) begin
        if(!rst_n) begin
            led_reg <= 'd0;
        end
        else begin        
            case(led_on_number)
                0: led_reg <= 8'b00000001;
                1: led_reg <= 8'b00000010;
                2: led_reg <= 8'b00000100;
                3: led_reg <= 8'b00001000;
                4: led_reg <= 8'b00010000;
                5: led_reg <= 8'b00100000;
                6: led_reg <= 8'b01000000;
                7: led_reg <= 8'b10000000;
            endcase
        end
    end
    
    
endmodule


