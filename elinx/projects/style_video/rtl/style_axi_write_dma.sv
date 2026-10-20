// Portable AXI4 frame writer. One outstanding burst; no vendor primitives.
// A command is DATA_WIDTH/8-byte aligned and contains whole, fully strobed beats.
// Invalid/aborted frames must not be published by the caller.
module style_axi_write_dma #(
    parameter integer ADDR_WIDTH = 32,
    parameter integer DATA_WIDTH = 128,
    parameter integer ID_WIDTH = 6,
    parameter integer BURST_BEATS = 16,
    parameter integer AXI_ID = 0,
    parameter integer TIMEOUT_CYCLES = 1000000
) (
    input wire clk, input wire rst_n,
    input wire cmd_valid, output wire cmd_ready,
    input wire [ADDR_WIDTH-1:0] cmd_addr,
    input wire [31:0] cmd_beats,
    input wire abort,
    output wire busy, output reg done, output reg error,
    output reg [7:0] error_code, output reg sticky_fault,
    input wire [DATA_WIDTH-1:0] s_data,
    input wire s_valid, output wire s_ready, input wire s_last,
    output wire [ID_WIDTH-1:0] m_axi_awid,
    output wire [ADDR_WIDTH-1:0] m_axi_awaddr,
    output wire [7:0] m_axi_awlen,
    output wire [2:0] m_axi_awsize,
    output wire [1:0] m_axi_awburst,
    output wire m_axi_awvalid, input wire m_axi_awready,
    output wire [DATA_WIDTH-1:0] m_axi_wdata,
    output wire [DATA_WIDTH/8-1:0] m_axi_wstrb,
    output wire m_axi_wlast, output wire m_axi_wvalid,
    input wire m_axi_wready,
    input wire [ID_WIDTH-1:0] m_axi_bid,
    input wire [1:0] m_axi_bresp,
    input wire m_axi_bvalid, output wire m_axi_bready
);
    localparam integer BYTES = DATA_WIDTH / 8;
    localparam integer SIZE = $clog2(BYTES);
    localparam [7:0] E_COMMAND = 8'h01, E_ABORT = 8'h02,
                     E_LAST = 8'h03, E_RESPONSE = 8'h04,
                     E_ID = 8'h05, E_TIMEOUT = 8'h06;
    localparam [2:0] IDLE = 0, FILL = 1, ISSUE = 2, RESPONSE = 3;
    reg [2:0] state;
    reg [DATA_WIDTH-1:0] buffer [0:BURST_BEATS-1];
    reg [ADDR_WIDTH-1:0] addr;
    reg [31:0] remaining, burst_count, fill_count, send_count;
    reg aw_accepted, w_finished, task_failed;
    reg [7:0] task_code;
    reg [31:0] watchdog;
    wire aw_fire = m_axi_awvalid && m_axi_awready;
    wire w_fire = m_axi_wvalid && m_axi_wready;
    wire b_fire = m_axi_bvalid && m_axi_bready;
    wire stream_fire = s_valid && s_ready;
    wire progress = aw_fire || w_fire || b_fire || stream_fire;
    wire timeout_now = (TIMEOUT_CYCLES > 0) && state != IDLE &&
                       !progress && watchdog >= TIMEOUT_CYCLES-1;
    wire stop_now = task_failed || abort || timeout_now;

    // Compute this at burst boundaries only. AXI bursts never cross 4 KiB.
    function [31:0] choose_burst;
        input [ADDR_WIDTH-1:0] address;
        input [31:0] beats;
        reg [31:0] boundary_beats;
        reg [31:0] n;
        begin
            boundary_beats = (4096 - {20'b0, address[11:0]}) / BYTES;
            n = beats < BURST_BEATS ? beats : BURST_BEATS;
            choose_burst = n < boundary_beats ? n : boundary_beats;
        end
    endfunction

    assign cmd_ready = state == IDLE && !sticky_fault;
    assign busy = state != IDLE;
    assign s_ready = state == FILL && !task_failed && !abort;
    assign m_axi_awid = AXI_ID;
    assign m_axi_awaddr = addr;
    assign m_axi_awlen = burst_count[7:0] - 1'b1;
    assign m_axi_awsize = SIZE;
    assign m_axi_awburst = 2'b01;
    assign m_axi_awvalid = state == ISSUE && !aw_accepted;
    assign m_axi_wdata = buffer[send_count];
    assign m_axi_wstrb = {BYTES{1'b1}};
    assign m_axi_wlast = send_count == burst_count-1;
    assign m_axi_wvalid = state == ISSUE && !w_finished;
    assign m_axi_bready = state == RESPONSE;

    always @(posedge clk) begin
        if (!rst_n) begin
            state <= IDLE;
            addr <= 0; remaining <= 0; burst_count <= 1;
            fill_count <= 0; send_count <= 0;
            aw_accepted <= 0; w_finished <= 0;
            task_failed <= 0; task_code <= 0; watchdog <= 0;
            done <= 0; error <= 0; error_code <= 0; sticky_fault <= 0;
        end else begin
            done <= 0;
            error <= 0;
            if (state == IDLE || progress) watchdog <= 0;
            else if (!timeout_now) watchdog <= watchdog + 1'b1;
            if (abort && state != IDLE && !task_failed) begin
                task_failed <= 1;
                task_code <= E_ABORT;
            end
            if (timeout_now) begin
                sticky_fault <= 1;
                task_failed <= 1;
                task_code <= E_TIMEOUT;
            end
            case (state)
                IDLE: if (cmd_valid && cmd_ready) begin
                    task_failed <= 0; task_code <= 0; error_code <= 0;
                    if (cmd_beats == 0 || (cmd_addr & (BYTES-1)) != 0) begin
                        done <= 1; error <= 1; error_code <= E_COMMAND;
                    end else if (abort) begin
                        done <= 1; error <= 1; error_code <= E_ABORT;
                    end else begin
                        addr <= cmd_addr; remaining <= cmd_beats;
                        burst_count <= choose_burst(cmd_addr, cmd_beats);
                        fill_count <= 0; state <= FILL;
                    end
                end
                FILL: begin
                    if (stop_now) begin
                        state <= IDLE; done <= 1; error <= 1;
                        error_code <= timeout_now ? E_TIMEOUT :
                                      task_failed ? task_code : E_ABORT;
                    end else if (stream_fire) begin
                        if (s_last != (remaining == fill_count+1)) begin
                            state <= IDLE; done <= 1; error <= 1;
                            error_code <= E_LAST;
                        end else begin
                            buffer[fill_count] <= s_data;
                            if (fill_count == burst_count-1) begin
                                send_count <= 0;
                                aw_accepted <= 0; w_finished <= 0;
                                state <= ISSUE;
                            end else fill_count <= fill_count + 1'b1;
                        end
                    end
                end
                ISSUE: begin
                    // Abort/timeouts do not revoke AWVALID or any part of W.
                    if (aw_fire) aw_accepted <= 1;
                    if (w_fire) begin
                        if (send_count == burst_count-1) w_finished <= 1;
                        else send_count <= send_count + 1'b1;
                    end
                    if ((aw_accepted || aw_fire) &&
                        (w_finished || (w_fire && m_axi_wlast))) state <= RESPONSE;
                end
                RESPONSE: if (b_fire) begin
                    if (stop_now || m_axi_bresp != 0 || m_axi_bid != AXI_ID) begin
                        state <= IDLE; done <= 1; error <= 1;
                        error_code <= timeout_now ? E_TIMEOUT :
                                      task_failed ? task_code : abort ? E_ABORT :
                                      m_axi_bid != AXI_ID ? E_ID : E_RESPONSE;
                    end else if (remaining == burst_count) begin
                        state <= IDLE; done <= 1; error <= 0; error_code <= 0;
                    end else begin
                        addr <= addr + burst_count*BYTES;
                        remaining <= remaining - burst_count;
                        burst_count <= choose_burst(addr + burst_count*BYTES,
                                                    remaining - burst_count);
                        fill_count <= 0; state <= FILL;
                    end
                end
                default: state <= IDLE;
            endcase
        end
    end
endmodule
