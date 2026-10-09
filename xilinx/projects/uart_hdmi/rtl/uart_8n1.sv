module uart_rx_8n1 #(
    parameter integer CLOCK_HZ = 200000000,
    parameter integer BAUD = 115200
)(input wire clk, reset, rx,
  output reg [7:0] data, output reg valid, output reg framing_error);
    localparam integer DIV = (CLOCK_HZ + BAUD/2)/BAUD;
    (* ASYNC_REG = "TRUE" *) reg [2:0] sync_rx = 3'b111;
    reg [31:0] timer;
    reg [3:0] state;
    reg [7:0] shift;
    always @(posedge clk) begin
        if (reset) sync_rx <= 3'b111;
        else sync_rx <= {sync_rx[1:0], rx};
    end
    always @(posedge clk) begin
        valid <= 0;
        framing_error <= 0;
        if (reset) begin state <= 0; timer <= 0; shift <= 0; data <= 0; end
        else if (state == 0) begin
            if (!sync_rx[2]) begin state <= 1; timer <= DIV/2-1; end
        end else if (timer != 0) timer <= timer-1;
        else if (state == 1) begin
            if (sync_rx[2]) state <= 0;
            else begin state <= 2; timer <= DIV-1; end
        end else if (state <= 9) begin
            shift[state-2] <= sync_rx[2];
            timer <= DIV-1;
            state <= state+1;
        end else if (state == 10) begin
            if (sync_rx[2]) begin data <= shift; valid <= 1; state <= 0; end
            else begin framing_error <= 1; state <= 11; end
        end else if (sync_rx[2]) state <= 0; // Break recovery waits for idle.
    end
endmodule

module uart_tx_8n1 #(
    parameter integer CLOCK_HZ = 200000000,
    parameter integer BAUD = 115200
)(input wire clk, reset, input wire [7:0] data,
  input wire valid, output wire ready, output wire tx);
    localparam integer DIV = (CLOCK_HZ + BAUD/2)/BAUD;
    reg [9:0] shift;
    reg [31:0] timer;
    reg [3:0] remaining;
    assign ready = remaining == 0;
    assign tx = ready ? 1'b1 : shift[0];
    always @(posedge clk) begin
        if (reset) begin shift <= 10'h3FF; timer <= 0; remaining <= 0; end
        else if (ready) begin
            if (valid) begin shift <= {1'b1, data, 1'b0}; timer <= DIV-1; remaining <= 10; end
        end else if (timer != 0) timer <= timer-1;
        else begin shift <= {1'b1, shift[9:1]}; timer <= DIV-1; remaining <= remaining-1; end
    end
endmodule
