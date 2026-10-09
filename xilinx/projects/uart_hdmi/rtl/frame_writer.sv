// Stop-and-wait packet engine; only successful AXI B responses advance offset.
module frame_writer #(
    parameter integer WIDTH=1280, HEIGHT=720,
    parameter integer SESSION_TIMEOUT=1000000000,
    parameter integer MAX_PAYLOAD_BYTES=1024,
    parameter integer PACKET_ADDRESS_BITS=$clog2(MAX_PAYLOAD_BYTES+25),
    parameter [29:0] BANK_STRIDE=30'h00200000
)(input wire clk, reset, calibrated, rx_activity,
  input wire packet_valid, input wire [PACKET_ADDRESS_BITS-1:0] packet_length,
  input wire [31:0] packet_crc, input wire bad_packet,
  output reg packet_consume, output reg [PACKET_ADDRESS_BITS-1:0] packet_address,
  input wire [7:0] packet_data,
  output wire reply_valid, input wire reply_ready,
  output reg [7:0] reply_command, reply_status,
  output reg [15:0] reply_sequence,
  output reg [31:0] reply_frame, reply_offset,
  input wire front_bank,
  output reg commit_valid, commit_bank,
  output reg [31:0] commit_frame,
  input wire commit_ack,
  output wire [29:0] awaddr, output wire awvalid, input wire awready,
  output wire [127:0] wdata, output wire wvalid, input wire wready,
  input wire [1:0] bresp, input wire bvalid, output wire bready,
  output reg [31:0] accepted_frames, rejected_packets,
  output reg session_active);
    `include "crc32_byte.svh"
    localparam integer FRAME_BYTES = WIDTH*HEIGHT*2;
    localparam IDLE=0, HEADER=1, CHECK=2, BEGIN_CRC=3, LOAD=4,
               WRITE=5, RESPONSE=6, PUBLISH=7, REPLY=8;
    reg [3:0] state;
    reg [7:0] header [0:19];
    reg [4:0] header_index, word_byte;
    reg [15:0] data_index;
    reg [31:0] active_frame, next_offset, expected_crc, frame_crc, session_timer;
    reg writer_bank, aw_done, w_done;
    reg [127:0] word_data;
    reg [29:0] word_address;
    reg [7:0] last_command;
    reg [15:0] last_sequence;
    reg [31:0] last_frame, last_crc, saved_crc;
    reg have_last;
    wire [7:0] command = header[1];
    wire [15:0] sequence_id = {header[3], header[2]};
    wire [31:0] frame_id = {header[7],header[6],header[5],header[4]};
    wire [31:0] offset = {header[11],header[10],header[9],header[8]};
    wire [15:0] length = {header[13],header[12]};
    wire [15:0] width = {header[15],header[14]};
    wire [15:0] height = {header[17],header[16]};
    assign awaddr=word_address;
    assign awvalid=state == WRITE && !aw_done;
    assign wdata=word_data;
    assign wvalid=state == WRITE && !w_done;
    assign bready=state == RESPONSE;
    assign reply_valid=state == REPLY;
    task automatic respond(input [7:0] status_code);
        begin
            reply_status <= status_code; reply_offset <= next_offset; state <= REPLY;
            if (status_code != 0) rejected_packets <= rejected_packets+1;
        end
    endtask
    always @(posedge clk) begin
        packet_consume <= 0;
        if (reset) begin
            state<=IDLE; packet_address<=0; header_index<=0; word_byte<=0; data_index<=0;
            active_frame<=0; next_offset<=0; expected_crc<=0; frame_crc<=32'hFFFFFFFF;
            writer_bank<=0; aw_done<=0; w_done<=0; word_data<=0; word_address<=0;
            commit_valid<=0; commit_bank<=0; commit_frame<=0;
            reply_command<=0; reply_status<=0; reply_sequence<=0; reply_frame<=0; reply_offset<=0;
            last_command<=0; last_sequence<=0; last_frame<=0; last_crc<=0; saved_crc<=0; have_last<=0;
            accepted_frames<=0; rejected_packets<=0; session_active<=0; session_timer<=0;
        end else begin
            if (!session_active || rx_activity || state != IDLE) session_timer<=0;
            else if (session_timer < SESSION_TIMEOUT) session_timer<=session_timer+1;
            case (state)
                IDLE: begin
                    if (session_active && session_timer >= SESSION_TIMEOUT-1) begin
                        session_active<=0; have_last<=0;
                        reply_command<=0; reply_sequence<=16'hFFFF; reply_frame<=active_frame;
                        respond(7);
                    end else if (packet_valid) begin
                        packet_address<=0; header_index<=0; saved_crc<=packet_crc; state<=HEADER;
                    end else if (bad_packet) begin
                        reply_command<=0; reply_sequence<=16'hFFFF; reply_frame<=active_frame;
                        respond(2);
                    end
                end
                HEADER: begin
                    header[header_index]<=packet_data;
                    if (header_index==19) state<=CHECK;
                    else begin header_index<=header_index+1; packet_address<=packet_address+1; end
                end
                CHECK: begin
                    reply_command<=command; reply_sequence<=sequence_id; reply_frame<=frame_id;
                    if (header[0]!=1 || header[18]!=1 || header[19]!=0 || width!=WIDTH || height!=HEIGHT ||
                        length>MAX_PAYLOAD_BYTES || packet_length!=24+length) respond(1);
                    else if (!calibrated) respond(8);
                    else if (have_last && command==last_command && sequence_id==last_sequence &&
                             frame_id==last_frame && saved_crc==last_crc) respond(0);
                    else case (command)
                        1: begin // BEGIN: payload = whole-frame CRC32, little endian.
                            if (length!=4 || offset!=0) respond(1);
                            else if (session_active) respond(4);
                            else begin
                                writer_bank<=~front_bank; active_frame<=frame_id;
                                next_offset<=0; frame_crc<=32'hFFFFFFFF; expected_crc<=0;
                                packet_address<=20; word_byte<=0; state<=BEGIN_CRC;
                            end
                        end
                        2: begin // DATA: aligned RGB565 byte blocks.
                            if (!session_active || frame_id!=active_frame || offset!=next_offset) respond(3);
                            else if (length==0 || length[3:0]!=0 || length > FRAME_BYTES-next_offset) respond(1);
                            else begin
                                packet_address<=20; data_index<=0; word_byte<=0; word_data<=0; state<=LOAD;
                            end
                        end
                        3: begin // END waits for the next display-frame boundary.
                            if (!session_active || frame_id!=active_frame || offset!=FRAME_BYTES || next_offset!=FRAME_BYTES || length!=0) respond(3);
                            else if (~frame_crc!=expected_crc) begin session_active<=0; have_last<=0; respond(6); end
                            else begin
                                commit_valid<=1; commit_bank<=writer_bank; commit_frame<=active_frame; state<=PUBLISH;
                            end
                        end
                        4: begin session_active<=0; next_offset<=0; have_last<=0; respond(0); reply_offset<=0; end
                        5: begin // QUERY reports current accepted offset, no state change.
                            if (length!=0) respond(1); else respond(0);
                        end
                        default: respond(1);
                    endcase
                end
                BEGIN_CRC: begin
                    expected_crc[word_byte*8 +: 8]<=packet_data;
                    if (word_byte==3) begin session_active<=1; reply_offset<=0; reply_status<=0; state<=REPLY; end
                    else begin word_byte<=word_byte+1; packet_address<=packet_address+1; end
                end
                LOAD: begin
                    word_data[word_byte*8 +: 8]<=packet_data;
                    frame_crc<=crc32_byte(frame_crc,packet_data);
                    data_index<=data_index+1;
                    packet_address<=packet_address+1;
                    if (word_byte==15) begin
                        word_address <= (writer_bank ? BANK_STRIDE : 30'd0) + next_offset + data_index - 15;
                        aw_done<=0; w_done<=0; state<=WRITE;
                    end else word_byte<=word_byte+1;
                end
                WRITE: begin
                    if (awvalid && awready) aw_done<=1;
                    if (wvalid && wready) w_done<=1;
                    if ((aw_done || awready) && (w_done || wready)) state<=RESPONSE;
                end
                RESPONSE: if (bvalid) begin
                    if (bresp!=0) begin session_active<=0; have_last<=0; respond(5); end
                    else if (data_index==length) begin
                        next_offset<=next_offset+length; reply_offset<=next_offset+length; reply_status<=0; state<=REPLY;
                    end else begin word_byte<=0; word_data<=0; state<=LOAD; end
                end
                PUBLISH: if (commit_ack) begin
                    commit_valid<=0; session_active<=0; accepted_frames<=accepted_frames+1; respond(0);
                end
                REPLY: if (reply_ready) begin
                    if (packet_valid) begin
                        packet_consume<=1;
                        if (reply_status==0 && command!=5) begin
                            have_last<=1; last_command<=command; last_sequence<=sequence_id;
                            last_frame<=frame_id; last_crc<=saved_crc;
                        end
                    end
                    // Wait one cycle for packet_consume to reach the receiver.
                    state<=9;
                end
                9: state<=IDLE;
                default: state<=IDLE;
            endcase
        end
    end
endmodule
