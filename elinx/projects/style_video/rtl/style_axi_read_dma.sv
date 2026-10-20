// Portable AXI4 frame reader, one outstanding burst. Each <=BURST_BEATS
// burst is checked completely before any of its data is made available.
module style_axi_read_dma #(
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
    output wire [DATA_WIDTH-1:0] m_data,
    output wire m_valid, input wire m_ready, output wire m_last,
    output wire [ID_WIDTH-1:0] m_axi_arid,
    output wire [ADDR_WIDTH-1:0] m_axi_araddr,
    output wire [7:0] m_axi_arlen,
    output wire [2:0] m_axi_arsize,
    output wire [1:0] m_axi_arburst,
    output wire m_axi_arvalid, input wire m_axi_arready,
    input wire [ID_WIDTH-1:0] m_axi_rid,
    input wire [DATA_WIDTH-1:0] m_axi_rdata,
    input wire [1:0] m_axi_rresp,
    input wire m_axi_rlast, input wire m_axi_rvalid,
    output wire m_axi_rready
);
    localparam integer BYTES = DATA_WIDTH / 8;
    localparam integer SIZE = $clog2(BYTES);
    localparam [7:0] E_COMMAND = 8'h01, E_ABORT = 8'h02,
                     E_LAST = 8'h03, E_RESPONSE = 8'h04,
                     E_ID = 8'h05, E_TIMEOUT = 8'h06;
    localparam [2:0] IDLE = 0, ADDRESS = 1, RECEIVE = 2, OUTPUT = 3;
    reg [2:0] state;
    reg [DATA_WIDTH-1:0] buffer [0:BURST_BEATS-1];
    reg [ADDR_WIDTH-1:0] addr;
    reg [31:0] remaining, burst_count, receive_count, output_count;
    reg task_failed;
    reg [7:0] task_code;
    reg [31:0] watchdog;
    wire ar_fire = m_axi_arvalid && m_axi_arready;
    wire r_fire = m_axi_rvalid && m_axi_rready;
    wire output_fire = m_valid && m_ready;
    wire progress = ar_fire || r_fire || output_fire;
    wire timeout_now = (TIMEOUT_CYCLES > 0) && state != IDLE &&
                       !progress && watchdog >= TIMEOUT_CYCLES-1;
    wire stop_now = task_failed || abort || timeout_now;
    wire beat_error = m_axi_rresp != 0 || m_axi_rid != AXI_ID ||
                      m_axi_rlast != (receive_count == burst_count-1) ||
                      receive_count >= burst_count;
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
    assign m_axi_arid = AXI_ID;
    assign m_axi_araddr = addr;
    assign m_axi_arlen = burst_count[7:0] - 1'b1;
    assign m_axi_arsize = SIZE;
    assign m_axi_arburst = 2'b01;
    assign m_axi_arvalid = state == ADDRESS;
    assign m_axi_rready = state == RECEIVE;
    assign m_data = buffer[output_count];
    assign m_valid = state == OUTPUT;
    assign m_last = remaining == burst_count && output_count == burst_count-1;

    always @(posedge clk) begin
        if (!rst_n) begin
            state <= IDLE; addr <= 0; remaining <= 0; burst_count <= 1;
            receive_count <= 0; output_count <= 0;
            task_failed <= 0; task_code <= 0; watchdog <= 0;
            done <= 0; error <= 0; error_code <= 0; sticky_fault <= 0;
        end else begin
            done <= 0; error <= 0;
            if (state == IDLE || progress) watchdog <= 0;
            else if (!timeout_now) watchdog <= watchdog + 1'b1;
            if (abort && state != IDLE && !task_failed) begin
                task_failed <= 1; task_code <= E_ABORT;
            end
            if (timeout_now) begin
                sticky_fault <= 1; task_failed <= 1; task_code <= E_TIMEOUT;
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
                        receive_count <= 0; state <= ADDRESS;
                    end
                end
                ADDRESS: if (ar_fire) begin
                    // Once ARVALID has been asserted it is held until acceptance.
                    receive_count <= 0; state <= RECEIVE;
                end
                RECEIVE: if (r_fire) begin
                    if (beat_error && !task_failed) begin
                        task_failed <= 1;
                        task_code <= m_axi_rid != AXI_ID ? E_ID :
                                     m_axi_rresp != 0 ? E_RESPONSE : E_LAST;
                    end
                    if (!stop_now && !beat_error)
                        buffer[receive_count] <= m_axi_rdata;
                    // Even on faults, drain through the actual RLAST. Timeout
                    // latches sticky_fault; it is not permission to reuse AXI.
                    if (m_axi_rlast) begin
                        if (stop_now || beat_error) begin
                            state <= IDLE; done <= 1; error <= 1;
                            error_code <= timeout_now ? E_TIMEOUT :
                                          task_failed ? task_code : abort ? E_ABORT :
                                          m_axi_rid != AXI_ID ? E_ID :
                                          m_axi_rresp != 0 ? E_RESPONSE : E_LAST;
                        end else begin
                            output_count <= 0; state <= OUTPUT;
                        end
                    end else if (receive_count != 32'hffffffff)
                        receive_count <= receive_count + 1'b1;
                end
                OUTPUT: if (output_fire) begin
                    // Do not revoke an already offered, stalled output beat.
                    if (stop_now) begin
                        state <= IDLE; done <= 1; error <= 1;
                        error_code <= timeout_now ? E_TIMEOUT :
                                      task_failed ? task_code : E_ABORT;
                    end else if (output_count == burst_count-1) begin
                        if (remaining == burst_count) begin
                            state <= IDLE; done <= 1; error <= 0; error_code <= 0;
                        end else begin
                            addr <= addr + burst_count*BYTES;
                            remaining <= remaining - burst_count;
                            burst_count <= choose_burst(addr + burst_count*BYTES,
                                                        remaining - burst_count);
                            receive_count <= 0; state <= ADDRESS;
                        end
                    end else output_count <= output_count + 1'b1;
                end
                default: state <= IDLE;
            endcase
        end
    end
endmodule
