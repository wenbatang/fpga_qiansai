module packet_reply #(
    parameter integer WIDTH = 1280, HEIGHT = 720
)(input wire clk, reset,
  input wire valid, output wire ready,
  input wire [7:0] command, status,
  input wire [15:0] sequence_id,
  input wire [31:0] frame_id, accepted_offset,
  output wire [7:0] tx_data, output wire tx_valid, input wire tx_ready);
    `include "crc32_byte.svh"
    reg [7:0] cmd, result;
    reg [15:0] seq;
    reg [31:0] frame, offset, crc, final_crc;
    reg [2:0] state;
    reg [5:0] index;
    reg [7:0] escaped_byte;
    reg [7:0] raw;
    localparam IDLE=0, OPEN=1, RAW=2, ESCAPE=3, CLOSE=4;
    always @* begin
        case (index)
            0: raw=1; 1: raw=cmd|8'h80;
            2: raw=seq[7:0]; 3: raw=seq[15:8];
            4: raw=frame[7:0]; 5: raw=frame[15:8]; 6: raw=frame[23:16]; 7: raw=frame[31:24];
            8: raw=offset[7:0]; 9: raw=offset[15:8]; 10: raw=offset[23:16]; 11: raw=offset[31:24];
            12: raw=1; 13: raw=0; 14: raw=WIDTH%256; 15: raw=WIDTH/256;
            16: raw=HEIGHT%256; 17: raw=HEIGHT/256; 18: raw=1; 19: raw=0;
            20: raw=result;
            21: raw=final_crc[7:0]; 22: raw=final_crc[15:8];
            23: raw=final_crc[23:16]; default: raw=final_crc[31:24];
        endcase
    end
    wire needs_escape = raw == 8'h7E || raw == 8'h7D;
    assign ready = state == IDLE;
    assign tx_valid = state != IDLE;
    assign tx_data = (state == OPEN || state == CLOSE) ? 8'h7E :
                     state == ESCAPE ? escaped_byte : needs_escape ? 8'h7D : raw;
    always @(posedge clk) begin
        if (reset) begin
            state <= IDLE; cmd <= 0; result <= 0; seq <= 0; frame <= 0;
            offset <= 0; crc <= 32'hFFFFFFFF; final_crc <= 0; index <= 0; escaped_byte <= 0;
        end else case (state)
            IDLE: if (valid) begin
                cmd <= command; result <= status; seq <= sequence_id; frame <= frame_id;
                offset <= accepted_offset; crc <= 32'hFFFFFFFF; index <= 0; state <= OPEN;
            end
            OPEN: if (tx_ready) state <= RAW;
            RAW: if (tx_ready) begin
                if (needs_escape) begin escaped_byte <= raw ^ 8'h20; state <= ESCAPE; end
                else begin
                    if (index < 21) crc <= crc32_byte(crc, raw);
                    if (index == 20) final_crc <= ~crc32_byte(crc, raw);
                    if (index == 24) state <= CLOSE;
                    else index <= index+1;
                end
            end
            ESCAPE: if (tx_ready) begin
                if (index < 21) crc <= crc32_byte(crc, raw);
                if (index == 20) final_crc <= ~crc32_byte(crc, raw);
                if (index == 24) state <= CLOSE;
                else begin index <= index+1; state <= RAW; end
            end
            CLOSE: if (tx_ready) state <= IDLE;
            default: state <= IDLE;
        endcase
    end
endmodule
