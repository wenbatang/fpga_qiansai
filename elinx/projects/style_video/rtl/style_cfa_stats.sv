// Read-only CSI observer. A/B/C/D name physical RAW sites, not color channels.
// VS/HS are active high; four consecutive RAW10 pixels are packed low first.
module style_cfa_stats #(
    parameter integer CAM_WIDTH = 1920,
    parameter integer CAM_HEIGHT = 1080,
    parameter integer ROI_X = 896,
    parameter integer ROI_Y = 476,
    parameter integer ROI_SIZE = 128
) (
    input wire clk,
    input wire rst_n,
    input wire s_vs,
    input wire s_hs,
    input wire s_valid,
    input wire [39:0] s_raw,
    output reg mean_valid,
    output reg [39:0] mean_data
);
    localparam integer GROUPS = CAM_WIDTH / 4;
    localparam integer SAMPLES = ROI_SIZE * ROI_SIZE / 4;
    localparam integer MEAN_SHIFT = $clog2(SAMPLES);
    localparam integer SUM_BITS = 10 + MEAN_SHIFT;
    localparam integer COUNT_BITS = $clog2(SAMPLES + 1);
    localparam integer FIRST_GROUP = ROI_X / 4;
    localparam integer LAST_GROUP = (ROI_X + ROI_SIZE) / 4;

    reg vs_q, hs_q, frame_open, frame_bad;
    integer groups_seen, rows_seen;
    reg [SUM_BITS-1:0] sum_a, sum_b, sum_c, sum_d;
    // Each eligible beat contributes two samples to each site on its row.
    // A/B and C/D therefore have identical respective sample counts.
    reg [COUNT_BITS-1:0] count_ab, count_cd;
    wire frame_start = s_vs && !vs_q;
    wire frame_end = !s_vs && vs_q;
    wire line_start = s_hs && !hs_q;
    wire line_end = !s_hs && hs_q;
    wire sample_take = s_valid && s_hs && s_vs;
    wire roi_take = rows_seen >= ROI_Y && rows_seen < ROI_Y + ROI_SIZE &&
                    groups_seen >= FIRST_GROUP && groups_seen < LAST_GROUP;
    wire protocol_error = (s_valid && (!s_hs || !s_vs || groups_seen >= GROUPS ||
                                      rows_seen >= CAM_HEIGHT)) ||
                          (line_start && rows_seen >= CAM_HEIGHT) ||
                          (line_end && groups_seen != GROUPS);
    // Account for CSI deasserting its last HS and VS on the same clock.
    wire complete_rows = (rows_seen == CAM_HEIGHT && groups_seen == 0) ||
                         (line_end && rows_seen == CAM_HEIGHT-1 && groups_seen == GROUPS);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            vs_q <= 0; hs_q <= 0; frame_open <= 0; frame_bad <= 0;
            groups_seen <= 0; rows_seen <= 0;
            sum_a <= 0; sum_b <= 0; sum_c <= 0; sum_d <= 0;
            count_ab <= 0; count_cd <= 0;
            mean_valid <= 0; mean_data <= 0;
        end else begin
            vs_q <= s_vs; hs_q <= s_hs;
            mean_valid <= 0;
            if (frame_start) begin
                frame_open <= 1;
                frame_bad <= s_valid;
                groups_seen <= 0; rows_seen <= 0;
                sum_a <= 0; sum_b <= 0; sum_c <= 0; sum_d <= 0;
                count_ab <= 0; count_cd <= 0;
            end else if (frame_open) begin
                if (protocol_error) frame_bad <= 1;
                if (sample_take) begin
                    groups_seen <= groups_seen + 1;
                    if (!frame_bad && !protocol_error && roi_take) begin
                        if (!rows_seen[0]) begin
                            sum_a <= sum_a + s_raw[9:0] + s_raw[29:20];
                            sum_b <= sum_b + s_raw[19:10] + s_raw[39:30];
                            count_ab <= count_ab + 2;
                        end else begin
                            sum_c <= sum_c + s_raw[9:0] + s_raw[29:20];
                            sum_d <= sum_d + s_raw[19:10] + s_raw[39:30];
                            count_cd <= count_cd + 2;
                        end
                    end
                end
                if (line_end) begin
                    rows_seen <= rows_seen + 1;
                    groups_seen <= 0;
                end
                if (frame_end) begin
                    frame_open <= 0;
                    if (!frame_bad && !protocol_error && !s_hs && complete_rows &&
                        count_ab == SAMPLES && count_cd == SAMPLES) begin
                        mean_valid <= 1;
                        mean_data <= {sum_d[SUM_BITS-1:MEAN_SHIFT],
                                      sum_c[SUM_BITS-1:MEAN_SHIFT],
                                      sum_b[SUM_BITS-1:MEAN_SHIFT],
                                      sum_a[SUM_BITS-1:MEAN_SHIFT]};
                    end
                end
            end
        end
    end

`ifndef SYNTHESIS
    initial begin
        if (CAM_WIDTH < 4 || CAM_WIDTH % 4 != 0 || CAM_HEIGHT < 2 ||
            CAM_HEIGHT % 2 != 0 || ROI_SIZE < 4 || (ROI_SIZE & (ROI_SIZE-1)) != 0 ||
            ROI_X < 0 || ROI_Y < 0 || ROI_X % 4 != 0 || ROI_Y % 2 != 0 ||
            ROI_X + ROI_SIZE > CAM_WIDTH || ROI_Y + ROI_SIZE > CAM_HEIGHT)
            $fatal(1, "Invalid CFA statistics camera/ROI geometry");
    end
`endif
endmodule
