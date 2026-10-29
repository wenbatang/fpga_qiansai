// Qualification only: this module does NOT classify a camera image.
// All inputs are synchronous to clk. A report is one detector result;
// sample_valid means a confident class 1..4, sample_no_hand means confirmed
// absence. Invalid/uncertain reports clear qualification but do not rearm.
module gesture_hold_gate #(
    parameter integer WINDOW_CYCLES = 100000000,
    parameter integer MAX_REPORT_GAP_CYCLES = 100000000
)(
    input  wire       clk,
    input  wire       reset,
    input  wire       enable,
    input  wire       cancel,
    input  wire       sample_strobe,
    input  wire       sample_valid,
    input  wire       sample_no_hand,
    input  wire [2:0] sample_id,
    output reg        switch_valid,
    output reg  [1:0] switch_style,
    output reg  [2:0] candidate_id,
    output reg  [2:0] completed_windows,
    output reg        armed
);
    localparam integer WB = WINDOW_CYCLES <= 1 ? 1 : $clog2(WINDOW_CYCLES);
    localparam integer GB = MAX_REPORT_GAP_CYCLES <= 1 ? 1 : $clog2(MAX_REPORT_GAP_CYCLES);
    reg [WB-1:0] window_cycles;
    reg [GB-1:0] gap_cycles;
    reg window_has_report;
    wire usable = sample_strobe && sample_valid && !sample_no_hand &&
                  sample_id >= 1 && sample_id <= 4;
    wire released = sample_strobe && sample_no_hand && !sample_valid;

    // Candidate begins at the first usable report, not at a free-running
    // 1 Hz phase boundary. Four FULL windows must elapse after that report.
    // A report at a window boundary belongs to the ending window only.
    always @(posedge clk) begin
        switch_valid <= 0;
        if (reset) begin
            switch_style <= 0;
            candidate_id <= 0;
            completed_windows <= 0;
            window_cycles <= 0;
            gap_cycles <= 0;
            window_has_report <= 0;
            armed <= 1;
        end else if (!enable || cancel) begin
            candidate_id <= 0;
            completed_windows <= 0;
            window_cycles <= 0;
            gap_cycles <= 0;
            window_has_report <= 0;
            // Display changes and faults cannot rearm a still-held hand.
            // A new confirmed no-hand report is required after firing.
        end else if (released || (sample_strobe && !usable)) begin
            candidate_id <= 0;
            completed_windows <= 0;
            window_cycles <= 0;
            gap_cycles <= 0;
            window_has_report <= 0;
            if (released) armed <= 1;
        end else if (!armed) begin
            // Keep the confirmed class/window count available to an OSD.
            window_cycles <= 0;
            gap_cycles <= 0;
            window_has_report <= 0;
        end else if (candidate_id == 0 || (usable && sample_id != candidate_id)) begin
            completed_windows <= 0;
            window_cycles <= 0;
            gap_cycles <= 0;
            window_has_report <= usable;
            candidate_id <= usable ? sample_id : 3'd0;
        end else if (!usable && gap_cycles == MAX_REPORT_GAP_CYCLES-1) begin
            // A stalled detector must never turn one stale label into 4 s.
            candidate_id <= 0;
            completed_windows <= 0;
            window_cycles <= 0;
            gap_cycles <= 0;
            window_has_report <= 0;
        end else begin
            gap_cycles <= usable ? 0 : gap_cycles + 1'b1;
            if (window_cycles == WINDOW_CYCLES-1) begin
                window_cycles <= 0;
                window_has_report <= 0;
                if (!(window_has_report || usable)) begin
                    candidate_id <= 0;
                    completed_windows <= 0;
                    gap_cycles <= 0;
                end else if (completed_windows == 3) begin
                    completed_windows <= 4;
                    switch_valid <= 1;
                    switch_style <= candidate_id[1:0] - 2'd1;
                    armed <= 0;
                end else completed_windows <= completed_windows + 1'b1;
            end else begin
                window_cycles <= window_cycles + 1'b1;
                if (usable) window_has_report <= 1;
            end
        end
    end
endmodule
