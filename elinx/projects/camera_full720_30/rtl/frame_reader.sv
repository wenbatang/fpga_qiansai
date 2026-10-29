// Three-output-bank reader. An accepted commit is acknowledged only after
// all OLD AXI reads have drained and the pixel FIFO reset has completed.
// Commit valid/payload must remain stable until commit_ack. No other owner
// may release the old front bank merely because front_bank changes early.
module frame_reader #(
    parameter integer WIDTH=1280, HEIGHT=720,
    parameter integer FIFO_WORDS=512,
    parameter [29:0] BANK_STRIDE=30'h00200000,
    parameter [29:0] THIRD_BANK_BASE=30'h00A00000
)(input wire clk, reset, calibrated,
  input wire refresh_request,
  input wire refresh_window,
  output reg refresh_ack,
  input wire commit_valid, input wire [1:0] commit_bank,
  input wire [31:0] commit_frame,
  output reg commit_ack, output reg [1:0] front_bank, output reg front_valid,
  output reg [31:0] front_frame,
  output reg fifo_reset, output wire [127:0] fifo_data, output wire fifo_write,
  input wire fifo_full, fifo_wr_busy, fifo_rd_busy,
  input wire [10:0] fifo_word_count,
  output wire [29:0] araddr, output wire arvalid, input wire arready,
  input wire [127:0] rdata, input wire [1:0] rresp,
  input wire rvalid, rlast, output wire rready,
  output reg [31:0] read_errors);
    localparam integer FRAME_BYTES=WIDTH*HEIGHT*2;
    localparam RUN=0, ADDRESS=1, DATA=2, RESET_FIFO=3, WAIT_FIFO=4;
    reg [2:0] state;
    reg [29:0] offset;
    reg [4:0] beat;
    reg [4:0] reset_count;
    reg frame_fault, commit_wait;
    reg [29:0] front_base;
    (* async_reg="true", syn_srlstyle="registers" *) reg [1:0] request_sync, window_sync, rd_busy_sync;
    wire refresh_pending=request_sync[1]!=refresh_ack;
    // ID 3 is invalid. Ignore it without ACK and continue refreshing the
    // previous front; never alias it to a legal DDR source slot.
    wire commit_legal=commit_bank!=2'd3;
    assign araddr=front_base+offset;
    assign arvalid=state==ADDRESS;
    assign rready=state==DATA && (refresh_pending || frame_fault || (!fifo_full && !fifo_wr_busy));
    assign fifo_data=rdata;
    assign fifo_write=state==DATA && rvalid && rready && !refresh_pending && !frame_fault &&
                      rresp==0 && rlast==(beat==15);
    always @(posedge clk) begin
        if (reset) begin request_sync<=0; window_sync<=0; rd_busy_sync<=3; end
        else begin
            request_sync<={request_sync[0],refresh_request};
            window_sync<={window_sync[0],refresh_window};
            rd_busy_sync<={rd_busy_sync[0],fifo_rd_busy};
        end
    end
    always @(posedge clk) begin
        commit_ack<=0;
        if (reset) begin
            state<=RUN; offset<=0; beat<=0; reset_count<=0; frame_fault<=0; commit_wait<=0;
            refresh_ack<=0; fifo_reset<=1; front_bank<=0; front_base<=0; front_valid<=0; front_frame<=0; read_errors<=0;
        end else case (state)
            RUN: begin
                // RUN has no unaccepted AR or outstanding R burst. A refresh
                // delayed past the guard waits until a later guarded blank.
                if (refresh_pending && window_sync[1] && calibrated) begin
                    if (commit_valid && commit_legal) begin
                        front_bank<=commit_bank; front_frame<=commit_frame; front_valid<=1;
                        case (commit_bank)
                            2'd0:front_base<=30'd0;
                            2'd1:front_base<=BANK_STRIDE;
                            2'd2:front_base<=THIRD_BANK_BASE;
                            default:front_base<=30'd0;
                        endcase
                        commit_wait<=1;
                    end
                    fifo_reset<=1; reset_count<=0; offset<=0; frame_fault<=0; state<=RESET_FIFO;
                end else if (!refresh_pending && front_valid && !fifo_reset && !frame_fault && calibrated && offset<FRAME_BYTES &&
                             !fifo_wr_busy && fifo_word_count <= FIFO_WORDS-32) state<=ADDRESS;
            end
            ADDRESS: if (arready) begin beat<=0; state<=DATA; end
            DATA: if (rvalid && rready) begin
                if (rresp!=0 || rlast!=(beat==15)) begin frame_fault<=1; read_errors<=read_errors+1; end
                if (rlast) begin offset<=offset+256; state<=RUN; end
                else beat<=beat+1;
            end
            RESET_FIFO: begin
                if (reset_count==15) begin fifo_reset<=0; state<=WAIT_FIFO; end
                else reset_count<=reset_count+1;
            end
            WAIT_FIFO: if (!fifo_wr_busy && !rd_busy_sync[1] && window_sync[1] && calibrated) begin
                // Only this ACK permits the producer to reuse the old front.
                // A stopped/slow pixel clock may miss the first blank; in
                // that case keep the request pending until a later guard.
                refresh_ack<=request_sync[1];
                commit_ack<=commit_wait; commit_wait<=0; state<=RUN;
            end
            default: state<=RUN;
        endcase
    end
endmodule
