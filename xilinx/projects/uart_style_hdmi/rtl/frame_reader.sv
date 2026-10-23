// UI-clock AXI reader. FIFO is flushed during vertical blank on every frame.
module frame_reader #(
    parameter integer WIDTH=1280, HEIGHT=720,
    parameter integer FIFO_WORDS=1024,
    parameter [29:0] BANK_STRIDE=30'h00200000
)(input wire clk, reset, calibrated,
  input wire refresh_request,
  input wire refresh_window,
  output reg refresh_ack,
  input wire commit_valid, commit_bank, input wire [31:0] commit_frame,
  output reg commit_ack, front_bank, front_valid,
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
    reg frame_fault;
    (* ASYNC_REG="TRUE" *) reg [1:0] request_sync, window_sync, rd_busy_sync;
    wire refresh_pending=request_sync[1]!=refresh_ack;
    assign araddr=(front_bank ? BANK_STRIDE : 30'd0)+offset;
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
            state<=RUN; offset<=0; beat<=0; reset_count<=0; frame_fault<=0;
            refresh_ack<=0; fifo_reset<=1; front_bank<=0; front_valid<=0; front_frame<=0; read_errors<=0;
        end else case (state)
            RUN: begin
                // A request can outlive blanking under long AXI backpressure.
                // Wait for the next guarded blank; never publish during active video.
                if (refresh_pending && window_sync[1] && calibrated) begin
                    if (commit_valid) begin
                        front_bank<=commit_bank; front_frame<=commit_frame; front_valid<=1; commit_ack<=1;
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
            WAIT_FIFO: if (!fifo_wr_busy && !rd_busy_sync[1]) begin
                refresh_ack<=request_sync[1]; state<=RUN;
            end
            default: state<=RUN;
        endcase
    end
endmodule
