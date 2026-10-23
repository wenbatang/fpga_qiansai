// PC requests use COBS with 00 delimiters. Unlike SLIP, payload-dependent
// escaping is bounded to one code byte per 254 bytes. ACKs remain SLIP.
module packet_rx_cobs #(
    parameter integer MAX_BYTES=16408,TIMEOUT_CYCLES=100000000,
    parameter integer ADDRESS_BITS=$clog2(MAX_BYTES+1)
)(input wire clk,reset,input wire [7:0] byte_data,input wire byte_valid,framing_error,
  input wire consume,input wire [ADDRESS_BITS-1:0] read_address,output reg [7:0] read_data,
  output reg packet_valid,output reg [ADDRESS_BITS-1:0] packet_length,
  output reg [31:0] packet_crc,output reg bad_packet,output reg [31:0] error_count);
    `include "crc32_byte.svh"
    (* ram_style="block" *) reg [7:0] memory[0:MAX_BYTES-1];
    reg started,pending_zero,seen_code,overflow;
    reg [7:0] remaining;
    reg [ADDRESS_BITS-1:0] count;
    reg [31:0] crc,tail,timer;
    wire insert_zero=remaining==0 && pending_zero;
    wire store_byte=remaining!=0 || insert_zero;
    wire [7:0] decoded=insert_zero ? 8'd0 : byte_data;
    always @(posedge clk) read_data<=read_address<MAX_BYTES ? memory[read_address] : 0;
    always @(posedge clk) begin
        bad_packet<=0;
        if(reset) begin
            started<=0;pending_zero<=0;seen_code<=0;overflow<=0;remaining<=0;count<=0;
            crc<=32'hffffffff;tail<=0;timer<=0;packet_valid<=0;packet_length<=0;packet_crc<=0;error_count<=0;
        end else if(consume) begin
            packet_valid<=0;started<=1;pending_zero<=0;seen_code<=0;overflow<=0;remaining<=0;count<=0;
            crc<=32'hffffffff;tail<=0;timer<=0;
        end else if(!packet_valid) begin
            if(framing_error || (started && seen_code && timer>=TIMEOUT_CYCLES-1)) begin
                started<=0;pending_zero<=0;seen_code<=0;overflow<=0;remaining<=0;count<=0;
                crc<=32'hffffffff;timer<=0;bad_packet<=1;error_count<=error_count+1;
            end else if(byte_valid) begin
                timer<=0;
                if(byte_data==0) begin
                    if(started && seen_code) begin
                        if(!overflow && remaining==0 && count>=24 && crc==32'hdebb20e3) begin
                            packet_valid<=1;packet_length<=count;packet_crc<=tail;
                        end else begin bad_packet<=1;error_count<=error_count+1;end
                    end
                    started<=1;pending_zero<=0;seen_code<=0;overflow<=0;remaining<=0;count<=0;crc<=32'hffffffff;
                end else if(started && !overflow) begin
                    if(remaining==0) begin
                        seen_code<=1;remaining<=byte_data-1;pending_zero<=byte_data!=8'hff;
                    end else remaining<=remaining-1;
                    if(store_byte) begin
                        if(count<MAX_BYTES) begin
                            memory[count]<=decoded;count<=count+1;crc<=crc32_byte(crc,decoded);tail<={decoded,tail[31:8]};
                        end else overflow<=1;
                    end
                end
            end else if(started && seen_code) timer<=timer+1;
        end
    end
endmodule
