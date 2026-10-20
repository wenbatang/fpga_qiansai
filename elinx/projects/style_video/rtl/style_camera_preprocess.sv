// Independent camera adapter for Efinity SystemVerilog (sv_09).
// Four RAW10 pixels per input beat, x0 in bits [9:0].
// 2x2 Bayer-cell reconstruction, then floor-coordinate nearest-neighbour resize.
// This is HALF-resolution Debayer, not full-resolution bilinear interpolation.
module style_camera_preprocess #(
    parameter integer CAM_WIDTH = 1920,
    parameter integer CAM_HEIGHT = 1080,
    parameter integer OUT_WIDTH = 640,
    parameter integer OUT_HEIGHT = 480,
    parameter integer BAYER_PATTERN = 0, // 0 RGGB, 1 GRBG, 2 GBRG, 3 BGGR
    parameter integer VS_ACTIVE = 1,     // Efinix CSI generic output: VS active high
    parameter integer QUEUE_DEPTH = 256, // packets; each holds one or two pixels
    // Physical 2x2 RAW sites, independent of the Bayer color interpretation.
    parameter integer BLACK_LEVEL_A = 0, // top-left
    parameter integer BLACK_LEVEL_B = 0, // top-right
    parameter integer BLACK_LEVEL_C = 0, // bottom-left
    parameter integer BLACK_LEVEL_D = 0, // bottom-right
    // Per-color RAW10 white balance, unsigned Q8 (256 = exact identity).
    parameter integer WB_GAIN_R_Q8 = 256,
    parameter integer WB_GAIN_G_Q8 = 256,
    parameter integer WB_GAIN_B_Q8 = 256,
    parameter integer DYNAMIC_WB = 0
) (
    input wire clk,
    input wire rst_n,
    input wire s_vs,
    input wire s_hs,
    input wire s_valid,
    input wire [39:0] s_raw,
    output wire m_valid,
    input wire m_ready,
    output wire [23:0] m_rgb,
    output wire m_sof,
    output wire m_eol,
    output wire m_eof,
    output wire [31:0] m_frame_id,
    output reg m_abort,
    output reg [31:0] m_abort_frame_id,
    output reg [31:0] input_frames,
    output reg [31:0] drop_frames,
    output reg [31:0] error_frames,
    // Camera-domain requests; latched together only on input SOF.
    // Unconnected inputs are ignored when DYNAMIC_WB=0 (historical behavior).
    input wire [10:0] wb_r_q8, wb_g_q8, wb_b_q8
);
    localparam integer GROUPS = CAM_WIDTH / 4;
    localparam integer HALF_WIDTH = CAM_WIDTH / 2;
    localparam integer HALF_HEIGHT = CAM_HEIGHT / 2;
    localparam integer X_STEP = HALF_WIDTH / OUT_WIDTH;
    localparam integer X_REM = HALF_WIDTH % OUT_WIDTH;
    localparam integer Y_STEP = HALF_HEIGHT / OUT_HEIGHT;
    localparam integer Y_REM = HALF_HEIGHT % OUT_HEIGHT;
    localparam integer QAW = (QUEUE_DEPTH < 2) ? 1 : $clog2(QUEUE_DEPTH);
    localparam integer QCW = $clog2(QUEUE_DEPTH + 1);
    reg [10:0] active_wb_r, active_wb_g, active_wb_b;
    always @(posedge clk) begin
        if (!rst_n) begin
            active_wb_r<=WB_GAIN_R_Q8; active_wb_g<=WB_GAIN_G_Q8; active_wb_b<=WB_GAIN_B_Q8;
        end else if (DYNAMIC_WB && sof_in) begin
            active_wb_r<=wb_r_q8; active_wb_g<=wb_g_q8; active_wb_b<=wb_b_q8;
        end
    end

    // A packed source line is only CAM_WIDTH*10 bits, not a frame store.
    // No reset on either RAM: their contents are read only after being written.
    reg [39:0] even_line [0:GROUPS-1];
    reg [86:0] packet_mem [0:QUEUE_DEPTH-1];
    reg [QAW-1:0] write_ptr, read_ptr;
    reg [QCW-1:0] ram_count;
    reg [86:0] out_packet;
    reg out_valid, out_second;

    wire out_last = out_second || !out_packet[54];
    wire out_take = out_valid && m_ready;
    wire packet_take = out_take && out_last;
    wire fetch = (ram_count != 0) && (!out_valid || packet_take);
    wire room = (ram_count < QUEUE_DEPTH) || fetch;

    assign m_valid = out_valid;
    assign m_rgb = out_second ? out_packet[50:27] : out_packet[23:0];
    assign m_sof = out_second ? out_packet[51] : out_packet[24];
    assign m_eol = out_second ? out_packet[52] : out_packet[25];
    assign m_eof = out_second ? out_packet[53] : out_packet[26];
    assign m_frame_id = out_packet[86:55];

    function [QAW-1:0] next_pointer;
        input [QAW-1:0] p;
        begin
            if (p == QUEUE_DEPTH-1) next_pointer = 0;
            else next_pointer = p + 1'b1;
        end
    endfunction

    function [9:0] subtract_black;
        input [9:0] sample;
        input [9:0] offset;
        begin
            // Unsigned compare before the explicitly 10-bit subtraction:
            // samples below the measured RAW black level never wrap around.
            subtract_black = sample > offset ? sample - offset : 10'd0;
        end
    endfunction

    function [9:0] white_balance;
        input [9:0] sample;
        input [10:0] gain_q8;
        reg [20:0] scaled;
        begin
            // 10-bit sample * 11-bit gain plus half-up Q8 rounding.
            // Explicit unsigned width retains the full product at gain 4x.
            scaled=({11'd0,sample} * {10'd0,gain_q8}) + 21'd128;
            if (scaled[20:8] > 13'd1023) white_balance=10'd1023;
            else white_balance=scaled[17:8];
        end
    endfunction

    function [23:0] cell_rgb;
        input [19:0] top;
        input [19:0] bottom;
        input [10:0] gain_r, gain_g, gain_b;
        reg [9:0] red, green, blue;
        reg [9:0] site_a, site_b, site_c, site_d;
        reg [10:0] green_sum;
        begin
            // Clamp each physical RAW10 site before either Bayer selection
            // or G averaging. No white-level rescale or early RGB8 cut.
            site_a = subtract_black(top[9:0], BLACK_LEVEL_A[9:0]);
            site_b = subtract_black(top[19:10], BLACK_LEVEL_B[9:0]);
            site_c = subtract_black(bottom[9:0], BLACK_LEVEL_C[9:0]);
            site_d = subtract_black(bottom[19:10], BLACK_LEVEL_D[9:0]);
            case (BAYER_PATTERN)
                0: begin
                    red=site_a; blue=site_d;
                    green_sum={1'b0,site_b}+{1'b0,site_c};
                end
                1: begin
                    red=site_b; blue=site_c;
                    green_sum={1'b0,site_a}+{1'b0,site_d};
                end
                2: begin
                    red=site_c; blue=site_b;
                    green_sum={1'b0,site_a}+{1'b0,site_d};
                end
                default: begin
                    red=site_d; blue=site_a;
                    green_sum={1'b0,site_b}+{1'b0,site_c};
                end
            endcase
            // Keep the old identity path exactly bit-equivalent, without
            // extra function calls in uncalibrated generic simulations.
            if (!DYNAMIC_WB && WB_GAIN_R_Q8==256 && WB_GAIN_G_Q8==256 && WB_GAIN_B_Q8==256)
                cell_rgb={red[9:2],green_sum[10:3],blue[9:2]};
            else begin
                // Average G in RAW10 first (floor), then round/saturate each
                // color's Q8 gain before the final RAW10->RGB8 truncation.
                green=green_sum[10:1];
                if (DYNAMIC_WB) begin
                    red=white_balance(red,gain_r);
                    green=white_balance(green,gain_g);
                    blue=white_balance(blue,gain_b);
                end else begin
                    if (WB_GAIN_R_Q8!=256) red=white_balance(red,WB_GAIN_R_Q8[10:0]);
                    if (WB_GAIN_G_Q8!=256) green=white_balance(green,WB_GAIN_G_Q8[10:0]);
                    if (WB_GAIN_B_Q8!=256) blue=white_balance(blue,WB_GAIN_B_Q8[10:0]);
                end
                cell_rgb={red[9:2],green[9:2],blue[9:2]};
            end
        end
    endfunction

    reg vs_q, hs_q;
    wire sof_in = (s_vs == VS_ACTIVE) && (vs_q != VS_ACTIVE);
    wire eof_in = (s_vs != VS_ACTIVE) && (vs_q == VS_ACTIVE);
    wire line_start = s_hs && !hs_q;
    wire line_end = !s_hs && hs_q;
    reg frame_open, frame_bad;
    reg [31:0] frame_id;
    integer groups_seen, rows_seen;
    integer next_x, frac_x, out_x;
    integer next_y, frac_y, out_y;

    // Synchronous even-line RAM read. A selected odd-row beat becomes p_*
    // one cycle later; two selected pixels enter the packet RAM together.
    reg p_valid, p_keep0, p_keep1;
    reg [39:0] p_top, p_bottom;
    reg p_sof0, p_sof1, p_eol0, p_eol1, p_last0, p_last1;
    reg [31:0] p_frame_id;
    wire [23:0] rgb0 = cell_rgb(p_top[19:0],p_bottom[19:0],active_wb_r,active_wb_g,active_wb_b);
    wire [23:0] rgb1 = cell_rgb(p_top[39:20],p_bottom[39:20],active_wb_r,active_wb_g,active_wb_b);

    // The last output pixel is withheld until the REAL VS end validates all
    // input lines. A short frame / extra line can never publish a valid EOF.
    reg tail_pending, tail_good;
    reg [23:0] tail_rgb;
    reg tail_sof;
    reg [31:0] tail_id;

    integer dx, fx, ox, source_x;
    integer completed_rows;
    reg keep0, keep1, sf0, sf1, el0, el1, last0, last1;
    reg protocol_error;
    reg normal_push, final_push;
    reg [86:0] normal_word, push_word;
    wire push = (normal_push || final_push) && room && !protocol_error;
    wire queue_overflow = normal_push && (!room || final_push);
    wire fail_current = protocol_error || queue_overflow;

    always @* begin
        dx=next_x; fx=frac_x; ox=out_x;
        keep0=0; keep1=0; sf0=0; sf1=0;
        el0=0; el1=0; last0=0; last1=0;
        if (groups_seen == 0) begin dx=0; fx=0; ox=0; end
        source_x=groups_seen*2;
        if (rows_seen[0] && ((rows_seen/2) == next_y) && out_y < OUT_HEIGHT) begin
            if (source_x == dx && ox < OUT_WIDTH) begin
                keep0=1; sf0=(ox==0 && out_y==0); el0=(ox==OUT_WIDTH-1);
                last0=el0 && (out_y==OUT_HEIGHT-1);
                ox=ox+1; dx=dx+X_STEP; fx=fx+X_REM;
                if (fx >= OUT_WIDTH) begin dx=dx+1; fx=fx-OUT_WIDTH; end
            end
            if (source_x+1 == dx && ox < OUT_WIDTH) begin
                keep1=1; sf1=(ox==0 && out_y==0); el1=(ox==OUT_WIDTH-1);
                last1=el1 && (out_y==OUT_HEIGHT-1);
                ox=ox+1; dx=dx+X_STEP; fx=fx+X_REM;
                if (fx >= OUT_WIDTH) begin dx=dx+1; fx=fx-OUT_WIDTH; end
            end
        end

        normal_push=0; normal_word=0;
        if (p_valid && !(frame_bad && p_frame_id==frame_id)) begin
            if (p_keep0 && !p_last0) begin
                normal_push=1;
                normal_word={p_frame_id,1'b0,3'b000,24'b0,1'b0,p_eol0,p_sof0,rgb0};
                if (p_keep1 && !p_last1) begin
                    normal_word[54]=1'b1;
                    normal_word[50:27]=rgb1;
                    normal_word[51]=p_sof1; normal_word[52]=p_eol1;
                end
            end else if (p_keep1 && !p_last1) begin
                normal_push=1;
                normal_word={p_frame_id,1'b0,3'b000,24'b0,1'b0,p_eol1,p_sof1,rgb1};
            end
        end
        final_push=tail_pending && tail_good;
        push_word=normal_word;
        if (final_push)
            push_word={tail_id,1'b0,3'b000,24'b0,1'b1,1'b1,tail_sof,tail_rgb};

        completed_rows=rows_seen;
        if (line_end && frame_open && !frame_bad && groups_seen==GROUPS)
            completed_rows=rows_seen+1;
        protocol_error=0;
        if (frame_open && !frame_bad) begin
            if (s_valid && (!s_hs || s_vs!=VS_ACTIVE)) protocol_error=1;
            if (line_start && rows_seen>=CAM_HEIGHT) protocol_error=1;
            if (s_valid && s_hs && groups_seen>=GROUPS) protocol_error=1;
            if (line_end && groups_seen!=GROUPS) protocol_error=1;
            if (eof_in && (completed_rows!=CAM_HEIGHT || s_hs)) protocol_error=1;
        end
    end

    // Paired synchronous FIFO. A held output packet is never flushed or
    // changed by an incoming SOF, protocol error or overflow.
    always @(posedge clk) begin
        if (!rst_n) begin
            write_ptr<=0; read_ptr<=0; ram_count<=0;
            out_valid<=0; out_second<=0; out_packet<=0;
        end else begin
            if (push) begin
                packet_mem[write_ptr]<=push_word;
                write_ptr<=next_pointer(write_ptr);
            end
            if (fetch) begin
                out_packet<=packet_mem[read_ptr];
                read_ptr<=next_pointer(read_ptr);
                out_valid<=1; out_second<=0;
            end else if (packet_take) begin
                out_valid<=0; out_second<=0;
            end else if (out_take) out_second<=1;
            case ({push,fetch})
                2'b10: ram_count<=ram_count+1'b1;
                2'b01: ram_count<=ram_count-1'b1;
                default: ram_count<=ram_count;
            endcase
        end
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            vs_q<=!VS_ACTIVE; hs_q<=0;
            frame_open<=0; frame_bad<=0; frame_id<=0;
            groups_seen<=0; rows_seen<=0;
            next_x<=0; frac_x<=0; out_x<=0;
            next_y<=0; frac_y<=0; out_y<=0;
            p_valid<=0; p_top<=0; p_bottom<=0; p_frame_id<=0;
            p_keep0<=0; p_keep1<=0; p_sof0<=0; p_sof1<=0;
            p_eol0<=0; p_eol1<=0; p_last0<=0; p_last1<=0;
            tail_pending<=0; tail_good<=0; tail_rgb<=0; tail_sof<=0; tail_id<=0;
            m_abort<=0; m_abort_frame_id<=0;
            input_frames<=0; drop_frames<=0; error_frames<=0;
        end else begin
            vs_q<=s_vs; hs_q<=s_hs;
            p_valid<=0; m_abort<=0;
            if (final_push && room && !protocol_error) begin
                tail_pending<=0; tail_good<=0;
            end
            if (p_valid && !(frame_bad && p_frame_id==frame_id)) begin
                if ((p_keep0 && p_last0) || (p_keep1 && p_last1)) begin
                    tail_pending<=1;
                    tail_rgb<=p_last0 ? rgb0 : rgb1;
                    tail_sof<=p_last0 ? p_sof0 : p_sof1;
                    tail_id<=p_frame_id;
                end
            end
            if (sof_in) begin
                input_frames<=input_frames+1'b1;
                frame_id<=input_frames+1'b1;
                frame_open<=1;
                groups_seen<=0; rows_seen<=0;
                next_x<=0; frac_x<=0; out_x<=0;
                next_y<=0; frac_y<=0; out_y<=0;
                // Previous validated tail must be queued before the next
                // input frame is accepted; otherwise drop this new frame.
                if ((tail_pending && !(final_push && room)) || s_valid) begin
                    frame_bad<=1;
                    drop_frames<=drop_frames+1'b1;
                    error_frames<=error_frames+1'b1;
                    m_abort<=1; m_abort_frame_id<=input_frames+1'b1;
                end else begin
                    frame_bad<=0;
                    tail_good<=0;
                end
            end else if (frame_open && !frame_bad) begin
                if (s_valid && s_hs && s_vs==VS_ACTIVE && groups_seen<GROUPS && rows_seen<CAM_HEIGHT) begin
                    groups_seen<=groups_seen+1;
                    if (!rows_seen[0]) even_line[groups_seen]<=s_raw;
                    else begin
                        p_valid<=1; p_top<=even_line[groups_seen]; p_bottom<=s_raw;
                        p_keep0<=keep0; p_keep1<=keep1;
                        p_sof0<=sf0; p_sof1<=sf1;
                        p_eol0<=el0; p_eol1<=el1;
                        p_last0<=last0; p_last1<=last1; p_frame_id<=frame_id;
                        next_x<=dx; frac_x<=fx; out_x<=ox;
                    end
                end
                if (line_end) begin
                    groups_seen<=0;
                    rows_seen<=rows_seen+1;
                    if (rows_seen[0] && rows_seen/2==next_y && out_y<OUT_HEIGHT) begin
                        out_y<=out_y+1;
                        if (frac_y+Y_REM>=OUT_HEIGHT) begin
                            next_y<=next_y+Y_STEP+1; frac_y<=frac_y+Y_REM-OUT_HEIGHT;
                        end else begin
                            next_y<=next_y+Y_STEP; frac_y<=frac_y+Y_REM;
                        end
                    end
                end
                if (eof_in) begin
                    frame_open<=0;
                    if (!fail_current) tail_good<=1;
                end
                if (fail_current) begin
                    frame_bad<=1; p_valid<=0;
                    drop_frames<=drop_frames+1'b1;
                    error_frames<=error_frames+1'b1;
                    m_abort<=1; m_abort_frame_id<=frame_id;
                    if (tail_id==frame_id || (p_valid && p_frame_id==frame_id &&
                        ((p_keep0 && p_last0) || (p_keep1 && p_last1)))) begin
                        tail_pending<=0; tail_good<=0;
                    end
                end
            end else if (eof_in) frame_open<=0;
        end
    end

    // Configuration assertions are deliberately simulation-only.
    // All resize divisions/moduli above are elaboration-time constants.
    // synthesis translate_off
    initial begin
        if (CAM_WIDTH<4 || CAM_WIDTH%4!=0 || CAM_HEIGHT<2 || CAM_HEIGHT%2!=0)
            $fatal(1,"camera dimensions require width multiple of 4 and even height");
        if (OUT_WIDTH<1 || OUT_HEIGHT<1 || OUT_WIDTH>HALF_WIDTH || OUT_HEIGHT>HALF_HEIGHT)
            $fatal(1,"only downscale from half-resolution Bayer cells is supported");
        if (QUEUE_DEPTH<2 || BAYER_PATTERN<0 || BAYER_PATTERN>3)
            $fatal(1,"invalid camera queue or Bayer pattern");
        if (BLACK_LEVEL_A<0 || BLACK_LEVEL_A>1023 || BLACK_LEVEL_B<0 || BLACK_LEVEL_B>1023 ||
            BLACK_LEVEL_C<0 || BLACK_LEVEL_C>1023 || BLACK_LEVEL_D<0 || BLACK_LEVEL_D>1023)
            $fatal(1,"RAW10 black levels must be 0..1023");
        if (WB_GAIN_R_Q8<0 || WB_GAIN_R_Q8>1024 || WB_GAIN_G_Q8<0 || WB_GAIN_G_Q8>1024 ||
            WB_GAIN_B_Q8<0 || WB_GAIN_B_Q8>1024)
            $fatal(1,"RAW10 white balance Q8 gains must be 0..1024");
    end
    // synthesis translate_on
endmodule
