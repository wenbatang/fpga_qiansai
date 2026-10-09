module ddr3_read_write
       (
        input wire sys_clk,
        output wire calib_done,
        input wire rst_n,
        output wire  locked,
        inout [31:0]       ddr3_dq,
        inout [3:0]        ddr3_dqs_n,
        inout [3:0]        ddr3_dqs_p,
        output [14:0]      ddr3_addr,
        output [2:0]       ddr3_ba,
        output             ddr3_ras_n,
        output             ddr3_cas_n,
        output             ddr3_we_n,
        output             ddr3_reset_n,
        output [0:0]       ddr3_ck_p,
        output [0:0]       ddr3_ck_n,
        output [0:0]       ddr3_cke,
        output [0:0]       ddr3_cs_n,
        output [3:0]       ddr3_dm,
        output [0:0]       ddr3_odt
        );
    (*mark_debug="true"*) wire[28:0]        app_addr;
    (*mark_debug="true"*)  wire[2:0]        app_cmd;
    (*mark_debug="true"*)  wire             app_en;
    (*mark_debug="true"*)  wire[255:0]      app_wdf_data;
    (*mark_debug="true"*)  wire             app_wdf_end;
    (*mark_debug="true"*) wire             app_wdf_wren;
    (*mark_debug="true"*) wire [255:0]     app_rd_data;
    (*mark_debug="true"*) wire             app_rd_data_end;
    (*mark_debug="true"*) wire             app_rd_data_valid;
    (*mark_debug="true"*) wire             app_rdy;
    (*mark_debug="true"*) wire             app_wdf_rdy;
    (*mark_debug="true"*) wire             ui_clk;
    (*mark_debug="true"*)wire write_state_flag;

    
    wire ui_rst;
    wire ddr3_clk;
    wire ddr3_ref_clk;
    
    reg[28:0]       app_addr_reg;
    reg [255:0]     app_wdf_data_reg;
   (*mark_debug="true"*)  reg [255:0]app_rd_data_reg;
   
assign     app_addr=app_addr_reg;
assign     app_wdf_data=app_wdf_data_reg;
assign     app_wdf_wren=(state_reg==STATE_WRITE)&&app_rdy&&app_wdf_rdy;
assign     app_wdf_end=app_wdf_wren;        

clk_wiz_0 clk_wiz_0_inst
    (
    .clk_out1(ddr3_clk),
    .clk_out2(ddr3_ref_clk),
    .resetn(rst_n),
    .locked(locked),
    .clk_in1(sys_clk)
    );
    
reg [3:0]state_reg;
parameter STATE_IDLE='d0;
parameter STATE_WRITE='d1;
parameter STATE_WAIT='d2;
parameter STATE_READ='d3;
parameter STATE_END='d4;
parameter FSM_IDLE_TIME =256;
parameter FSM_WRITE_TIME =256;
parameter FSM_WAIT_TIME =8;
parameter FSM_READ_TIME =256;
reg [15:0]fsm_cnt_reg;

assign write_state_flag=(state_reg==STATE_WRITE)?1'b1:1'b0;
assign app_en = ((state_reg == STATE_WRITE && (app_rdy && app_wdf_rdy)) ||(state_reg == STATE_READ && app_rdy)) ? 1'b1:1'b0;
assign app_cmd = (state_reg == STATE_READ) ? 3'd1 :3'd0; 
always@(posedge ui_clk or posedge ui_rst)begin
    if(ui_rst)begin
        state_reg<='d0;
        fsm_cnt_reg<='d0; 
    end
    else begin
        case (state_reg)
            STATE_IDLE:begin
                if(calib_done=='b1)begin
                    if(fsm_cnt_reg<FSM_IDLE_TIME-1)fsm_cnt_reg<=fsm_cnt_reg+'d1;
                    else begin
                        fsm_cnt_reg<='d0;
                        state_reg<=STATE_WRITE;
                    end
                end
            end
            STATE_WRITE:begin
                if(fsm_cnt_reg<FSM_WRITE_TIME-1)fsm_cnt_reg<=fsm_cnt_reg+'d1;
                else begin
                    fsm_cnt_reg<='d0;
                    state_reg<=STATE_WAIT;
                end
            end
            STATE_WAIT:begin
                if(fsm_cnt_reg<FSM_WAIT_TIME-1)fsm_cnt_reg<=fsm_cnt_reg+'d1;
                else begin
                    fsm_cnt_reg<='d0;
                    state_reg<=STATE_READ;
                end
            end
            STATE_READ:begin
                if(fsm_cnt_reg<FSM_WRITE_TIME-1)fsm_cnt_reg<=fsm_cnt_reg+'d1;
                 else begin
                    fsm_cnt_reg<='d0;
                    state_reg<=STATE_END;
                end
            end
            STATE_END:begin
                state_reg<=STATE_IDLE;
            end
            default:state_reg<=STATE_IDLE;
            endcase
        end
    end
     
    parameter CMD_WRITE=3'b000;
    parameter CMD_READ=3'b001;
    parameter ADDR_INCREMENT='d32;
    parameter ADDR_MAX=1024*1024*1024;
    parameter databit_128=128'h00010001000100010001000100010001;
    parameter DATA_INCREMENT={databit_128,databit_128};
    always@(posedge ui_clk or posedge ui_rst)begin
        if(ui_rst)begin
            app_addr_reg<='d0;
            app_wdf_data_reg<='d0;
        end
        else begin
        case (state_reg)
            STATE_IDLE:begin
              app_addr_reg<='d0;
              app_wdf_data_reg<='d0;
            end
            STATE_WRITE:begin
                if(app_wdf_wren=='b1)begin
                    app_addr_reg<=app_addr_reg+ADDR_INCREMENT;      
                    app_wdf_data_reg<=app_wdf_data_reg+DATA_INCREMENT;
                end
            end
            STATE_WAIT:begin
                app_addr_reg<='d0;
                app_wdf_data_reg<='d0;
            end
            STATE_READ:begin
                if(app_rdy=='b1)begin
                    if(app_addr_reg<ADDR_MAX)app_addr_reg<=app_addr_reg+ADDR_INCREMENT;
                    else app_addr_reg<='d0;
                end      
            end
            STATE_END:begin
                app_addr_reg<='d0;     
                app_wdf_data_reg<='d0;
            end
            default:;
            endcase
        end
    end

    always@(posedge ui_clk ) if(app_rd_data_valid=='b1)app_rd_data_reg<=app_rd_data;
    
    mig_7series_0 mig_7series_0_inst
        (
        .ddr3_dq(ddr3_dq),
        .ddr3_dqs_n(ddr3_dqs_n),
        .ddr3_dqs_p(ddr3_dqs_p),
        .ddr3_addr(ddr3_addr),
        .ddr3_ba(ddr3_ba),
        .ddr3_ras_n(ddr3_ras_n),
        .ddr3_cas_n(ddr3_cas_n),
        .ddr3_we_n(ddr3_we_n),
        .ddr3_reset_n(ddr3_reset_n),
        .ddr3_ck_p(ddr3_ck_p),
        .ddr3_ck_n(ddr3_ck_n),
        .ddr3_cke(ddr3_cke),
        .ddr3_cs_n(ddr3_cs_n),
        .ddr3_dm(ddr3_dm),
        .ddr3_odt(ddr3_odt),
        .sys_clk_i(ddr3_clk),
        .clk_ref_i(ddr3_ref_clk),
        .app_addr(app_addr),
        .app_cmd(app_cmd),
        .app_en(app_en),
        .app_wdf_data(app_wdf_data),
        .app_wdf_end(app_wdf_end),
        .app_wdf_mask(32'd0),
        .app_wdf_wren(app_wdf_wren),
        .app_rd_data(app_rd_data),
        .app_rd_data_end(app_rd_data_end),
        .app_rd_data_valid(app_rd_data_valid),
        .app_rdy(app_rdy),
        .app_wdf_rdy(app_wdf_rdy),
        .app_sr_req('b0),
        .app_ref_req('b0),
        .app_zq_req('b0),
        .app_sr_active(app_sr_active),
        .app_ref_ack(app_ref_ack),
        .app_zq_ack(app_zq_ac),
        .ui_clk(ui_clk),
        .ui_clk_sync_rst(ui_rst),
        .init_calib_complete(calib_done),
        .device_temp(),
        .sys_rst(rst_n)
    );    
endmodule
