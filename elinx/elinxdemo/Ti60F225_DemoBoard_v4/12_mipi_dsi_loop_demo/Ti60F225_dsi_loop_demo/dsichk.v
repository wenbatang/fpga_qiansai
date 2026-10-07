
module dsichk # (

parameter MAX_HRES = 11'd1080,
parameter MAX_VRES = 11'd1920,
parameter HSP = 10'd100,
parameter HBP = 10'd100,
parameter HFP = 10'd250,
parameter VSP = 10'd3,
parameter VBP = 10'd5,
parameter VFP = 11'd6

) 
(
    input               i_arstn,
    input               pll_locked,
    output              o_pixel_rstn,
    output              o_global_rstn,

    input               i_fb_clk,
    input               i_sysclk,

    output              o_vsync,
    output              o_hsync,
    output              o_valid,
    output [9:0]        o_out_x,
    output [9:0]        o_out_y,

    input               i_inject_err1,
    input               i_inject_err2,
    output              o_hsync_match,
    output              o_vsync_match,
    output              o_pdata_match,
    output [ 8:0]       o_frame_cnt,

    input               i_vsync,
    input               i_hsync,
    input               i_valid,
    input [63:0]        i_pdata,

    input               i_clr_cnt,
    
// axi 
	input		        i_axi_awready,
	input		        i_axi_wready,
	input		        i_axi_bvalid,
	output [6:0]        o_axi_awaddr,
	output              o_axi_awvalid,
	output [31:0]       o_axi_wdata,
	output   	        o_axi_wvalid,
	output   	        o_axi_bready,
	
	input		        i_axi_arready,
	input		[31:0]  i_axi_rdata,
	input		        i_axi_rvalid,
	output 	[6:0]       o_axi_araddr,
	output 	            o_axi_arvalid,
	output 	            o_axi_rready
    
    
);

localparam RESET_COUNT          = 26;
localparam RELEASE_RESET_ALL    = 26'd1500;


reg         r_rstn_video = 0;
reg  [10:0] r_hs_cnt = 0;
reg  [ 8:0] r_frame_cnt = 0;
reg  [25:0] r_rst_cnt = 0;
reg         r_lcd_rstn = 1;
reg         r_cam_rstn = 1;
reg         r_lcd_init = 0;
reg         global_rstn = 0;
wire        w_confdone;

////////////////////////////////////////////////////////////////
// System & Debugger
wire        w_cam_arstn;
wire        w_cam_arst;
wire        w_sysclk_arstn;
wire        w_sysclk_arst;
wire        w_sysclkdiv2_arstn;
wire        w_sysclkdiv2_arst;
wire        w_fb_clk_arstn;
wire        w_fb_clk_arst;
////////////////////////////////////////////////////////////////
reg         r_vs_p1 = 0;
reg         r_hs_p1 = 0;
reg         r_de_p1;
reg [63:0]  r_pdata_p1, r_pdata_p2;

assign o_frame_cnt = r_frame_cnt;
assign o_global_rstn = global_rstn;
assign o_pixel_rstn = r_rstn_video;

reset_ctrl #(
    .NUM_RST       (4),
    .CYCLE         (4),
    .IN_RST_ACTIVE (4'b0000),
    .OUT_RST_ACTIVE(4'b1010)
) inst_reset_ctrl (
    .i_arst({4{global_rstn}}),
    .i_clk({
        {2{i_sysclk}}, {2{i_fb_clk}}
    }),
    .o_srst({
        w_sysclk_arst,
        w_sysclk_arstn,
        w_fb_clk_arst,
        w_fb_clk_arstn
    })
);

////////////////////////////////////////////////////////////////
// vga_gen for DSI TX
////////////////////////////////////////////////////////////////
vga_gen #(
    .H_SyncPulse (HSP),
    .H_BackPorch (HBP),
    .H_ActivePix (MAX_HRES/2),
    .H_FrontPorch(HFP+MAX_HRES/2),
    .V_SyncPulse (VSP),
    .V_BackPorch (VBP),
    .V_ActivePix (MAX_VRES),
    .V_FrontPorch(VFP),
    .P_Cnt       (3'd1)
) vga_gen_inst (
    .in_pclk  (i_sysclk),
    .in_rstn  (w_confdone & w_sysclk_arstn),

    .out_x    (o_out_x),
    .out_y    (o_out_y),
    .out_de   (),
    .out_valid(o_valid),
    .out_hs   (o_hsync),
    .out_vs   (o_vsync)
);


always @(negedge w_sysclk_arstn or posedge i_sysclk) begin
    if (~w_sysclk_arstn) begin
        r_vs_p1         <= 1'b0;
        r_hs_p1         <= 1'b0;
        r_de_p1         <= 1'b0;

        r_rstn_video    <= 1'b0;
        r_hs_cnt        <= {11{1'b0}};
        r_frame_cnt     <= {9{1'b0}};
    end else if (w_confdone) begin
        r_vs_p1         <= o_vsync;
        r_hs_p1         <= o_hsync;
        r_de_p1         <= o_valid;

        if (r_vs_p1 && ~o_vsync)    r_frame_cnt <= r_frame_cnt + 1'b1;

        if (~o_hsync && r_hs_p1)    r_hs_cnt <= r_hs_cnt + 1'b1;

        if (r_frame_cnt == 1'b1)    r_rstn_video <= 1'b1;
    end
end


////////////////////////////////////////////////////////////////
// vga_gen comparator for DSI RX
////////////////////////////////////////////////////////////////

wire        w_vsync;
wire        w_hsync;
wire        w_valid;
wire [9:0]  w_out_x;
wire [9:0]  w_out_y;


reg r_vcomp_start;
reg r_hsync_match;
reg r_vsync_match;
reg r_pdata_match;

wire [63:0] w_pdata;

assign w_pdata =( {4'b0, {3{w_out_y,w_out_x}}} ) & ( { {16{1'h0}},{48{1'h1}} } ) ;

assign o_hsync_match = r_hsync_match ;
assign o_vsync_match = r_vsync_match ;
assign o_pdata_match = r_pdata_match ;

always @(negedge w_sysclk_arstn or posedge i_sysclk) begin
    if (~w_sysclk_arstn) begin
        r_vcomp_start   <= 1'b0;
    end else if (i_hsync) begin
        r_vcomp_start   <= 1'b1;
    end
    
    if (~w_sysclk_arstn) begin
        r_pdata_match   <= 1'b0;
    end else if (w_valid) begin
        if (r_pdata_p2 == w_pdata) begin
            r_pdata_match   <= 1'b1;
        end else begin
            r_pdata_match   <= 1'b0;
        end
    end
    
end

vga_chk #(
    .H_SyncPulse (HSP),
    .H_BackPorch (HBP),
    .H_ActivePix (MAX_HRES/2),
    .H_FrontPorch(HFP+MAX_HRES/2),
    .V_SyncPulse (VSP),
    .V_BackPorch (VBP),
    .V_ActivePix (MAX_VRES),
    .V_FrontPorch(VFP),
    .P_Cnt       (3'd1)
) vga_chk_inst (
    .in_pclk  (i_sysclk),
    .in_rstn  (r_vcomp_start),
    .in_datavalid  (i_valid),

    .out_x    (w_out_x),
    .out_y    (w_out_y),
    .out_de   (),
    .out_valid(w_valid),
    .out_hs   (w_hsync),
    .out_vs   (w_vsync)
);

/// hsync and vsync counter compare:

reg [11:0]    r_tx_hsync_cnt;
reg [11:0]    r_tx_vsync_cnt;
reg [11:0]    r_rx_hsync_cnt;
reg [11:0]    r_rx_vsync_cnt;


always @(negedge w_sysclk_arstn or posedge i_hsync) begin
    if (~w_sysclk_arstn)    r_rx_hsync_cnt  <= 1'b0;
    else                    r_rx_hsync_cnt  <= r_rx_hsync_cnt + 1;
end

always @(negedge w_sysclk_arstn or negedge w_hsync) begin
    if (~w_sysclk_arstn)     r_tx_hsync_cnt  <= 1'b1;
    else if (~i_inject_err1) r_tx_hsync_cnt  <= 1'b1;
    else                     r_tx_hsync_cnt  <= r_tx_hsync_cnt + 1;
end


always @(negedge w_sysclk_arstn or posedge i_vsync) begin
    if (~w_sysclk_arstn)    r_rx_vsync_cnt  <= 1'b0;
    else                    r_rx_vsync_cnt  <= r_rx_vsync_cnt + 1;
end

always @(negedge w_sysclk_arstn or posedge w_vsync) begin
    if (~w_sysclk_arstn)     r_tx_vsync_cnt  <= 1'b0;
    else if (~i_inject_err2) r_tx_vsync_cnt  <= 1'b1;
    else                     r_tx_vsync_cnt  <= r_tx_vsync_cnt + 1;
end

always @(negedge w_sysclk_arstn or posedge i_sysclk) begin
    if (~w_sysclk_arstn)    r_pdata_p1  <= 1'b0;
    else                    r_pdata_p1  <= i_pdata;
    if (~w_sysclk_arstn)    r_pdata_p2  <= 1'b0;
    else                    r_pdata_p2  <= r_pdata_p1;
end


always @(negedge w_sysclk_arstn or posedge i_sysclk) begin
    if (~w_sysclk_arstn) begin
        r_vsync_match   <= 1'b0;
    end else if (w_valid) begin
        if (r_tx_vsync_cnt == r_rx_vsync_cnt) begin
            r_vsync_match   <= 1'b1;
        end else begin
            r_vsync_match   <= 1'b0;
        end
    end
    if (~w_sysclk_arstn) begin
        r_hsync_match   <= 1'b0;
    end else if (w_valid) begin
        if (r_tx_hsync_cnt == r_rx_hsync_cnt) begin
            r_hsync_match   <= 1'b1;
        end else begin
            r_hsync_match   <= 1'b0;
        end
    end
end

/// reset release control.. 

always @(negedge i_arstn or posedge i_fb_clk) begin
    if (~i_arstn) begin
        r_rst_cnt   <= {RESET_COUNT{1'b0}};
        global_rstn <= 1'b0;
    end else begin
        if (pll_locked) begin
            if (r_rst_cnt != {RESET_COUNT{1'b1}}) begin
                r_rst_cnt <= r_rst_cnt + 1'b1;
                if (r_rst_cnt == RELEASE_RESET_ALL) begin
                    global_rstn <= 1'b1;
                end
            end
        end else begin
            r_rst_cnt   <= {RESET_COUNT{1'b0}};
            global_rstn <= 1'b0;
        end
    end
end


// Panel driver initialization
panel_config #(
    .INITIAL_CODE("./IPhone_7p_1080p_reg.mem"),
    .REG_DEPTH   (9'd15)
) inst_panel_config (
    .i_axi_clk(i_fb_clk),
    .i_restn  (w_fb_clk_arstn),

    .i_axi_awready(i_axi_awready),
    .i_axi_wready (i_axi_wready),
    .i_axi_bvalid (i_axi_bvalid),
    .o_axi_awaddr (o_axi_awaddr),
    .o_axi_awvalid(o_axi_awvalid),
    .o_axi_wdata  (o_axi_wdata),
    .o_axi_wvalid (o_axi_wvalid),
    .o_axi_bready (o_axi_bready),

    .i_axi_arready(i_axi_arready),
    .i_axi_rdata  (i_axi_rdata),
    .i_axi_rvalid (i_axi_rvalid),
    .o_axi_araddr (o_axi_araddr),
    .o_axi_arvalid(o_axi_arvalid),
    .o_axi_rready (o_axi_rready),

    .o_addr_cnt(),
    .o_state   (),
    .o_confdone(w_confdone),

    .i_dbg_we      (0),
    .i_dbg_din     (0),
    .i_dbg_addr    (0),
    .o_dbg_dout    (),
    .i_dbg_reconfig(0)
);


endmodule
