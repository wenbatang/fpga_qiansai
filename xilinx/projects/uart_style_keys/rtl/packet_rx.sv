// SLIP-style framing: 7E delimiters, 7D escape, XOR 20. One held packet.
module packet_rx #(
    parameter integer MAX_BYTES = 1048,
    parameter integer TIMEOUT_CYCLES = 200000000,
    parameter integer ADDRESS_BITS = $clog2(MAX_BYTES+1)
)(input wire clk, reset,
  input wire [7:0] byte_data, input wire byte_valid, framing_error,
  input wire consume, input wire [ADDRESS_BITS-1:0] read_address,
  output wire [7:0] read_data,
  output reg packet_valid, output reg [ADDRESS_BITS-1:0] packet_length,
  output reg [31:0] packet_crc, output reg bad_packet,
  output reg [31:0] error_count);
    `include "crc32_byte.svh"
    (* ram_style = "distributed" *) reg [7:0] memory [0:MAX_BYTES-1];
    reg started, escaped, overflow;
    reg [ADDRESS_BITS-1:0] count;
    reg [31:0] crc, tail, timer;
    wire [7:0] decoded = escaped ? byte_data ^ 8'h20 : byte_data;
    assign read_data = read_address < MAX_BYTES ? memory[read_address] : 8'd0;
    always @(posedge clk) begin
        bad_packet <= 0;
        if (reset) begin
            started <= 0; escaped <= 0; overflow <= 0; count <= 0;
            crc <= 32'hFFFFFFFF; tail <= 0; timer <= 0;
            packet_valid <= 0; packet_length <= 0; packet_crc <= 0; error_count <= 0;
        end else if (consume) begin
            packet_valid <= 0; started <= 1; count <= 0; escaped <= 0;
            overflow <= 0; crc <= 32'hFFFFFFFF; timer <= 0;
        end else if (!packet_valid) begin
            if (framing_error || (started && (count != 0 || escaped) && timer >= TIMEOUT_CYCLES-1)) begin
                started <= 0; count <= 0; escaped <= 0; overflow <= 0;
                crc <= 32'hFFFFFFFF; timer <= 0;
                bad_packet <= 1; error_count <= error_count+1;
            end else if (byte_valid) begin
                timer <= 0;
                if (byte_data == 8'h7E) begin
                    if (started && (count != 0 || escaped || overflow)) begin
                        if (!overflow && !escaped && count >= 24 && crc == 32'hDEBB20E3) begin
                            packet_valid <= 1; packet_length <= count; packet_crc <= tail;
                        end else begin bad_packet <= 1; error_count <= error_count+1; end
                    end
                    started <= 1; count <= 0; escaped <= 0;
                    overflow <= 0; crc <= 32'hFFFFFFFF;
                end else if (started && !overflow) begin
                    if (!escaped && byte_data == 8'h7D) escaped <= 1;
                    else if (count < MAX_BYTES) begin
                        memory[count] <= decoded; count <= count+1;
                        crc <= crc32_byte(crc, decoded);
                        tail <= {decoded, tail[31:8]}; escaped <= 0;
                    end else overflow <= 1;
                end
            end else if (started && (count != 0 || escaped)) timer <= timer+1;
        end
    end
endmodule
