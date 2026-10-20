// Passive instrumentation bank 0x100..0x17f, enabled explicitly by the shell.
wire [31:0] regs_prdata,perf_prdata;
wire regs_pready,regs_pslverr,perf_pslverr;
wire perf_select=PERF_ENABLE && paddr[11:7]==5'd2;
assign prdata=perf_select?perf_prdata:regs_prdata;
assign pready=perf_select?1'b1:regs_pready;
assign pslverr=perf_select?perf_pslverr:regs_pslverr;
generate if(PERF_ENABLE) begin:performance
    style_perf_monitor #(.CORE_HZ(CORE_HZ)) monitor(
        .clk(clk),.rst_n(rst_n),.second_tick(fps_tick),
        .cap_start(cap_take),.cap_done(cap_done),.cap_ok(cap_ok),.cap_slot(captured_slot),.cap_id(captured_id),
        .job_start(job_take),.job_done(job_done),.job_ok(job_ok),.job_slot(work_input),.job_id(work_id),
        .publish(display_switch && pending_valid),
        .arvalid(m_axi_arvalid),.arready(m_axi_arready),.rvalid(m_axi_rvalid),.rready(m_axi_rready),.rlast(m_axi_rlast),
        .awvalid(m_axi_awvalid),.awready(m_axi_awready),.wvalid(m_axi_wvalid),.wready(m_axi_wready),
        .wlast(m_axi_wlast),.wstrb(m_axi_wstrb),.bvalid(m_axi_bvalid),.bready(m_axi_bready),
        .camera_level(perf_camera_level),.display_level(perf_display_level),
        .paddr(paddr[6:0]),.psel(psel && perf_select),.penable(penable),.pwrite(pwrite),.pwdata(pwdata),
        .prdata(perf_prdata),.pslverr(perf_pslverr),.snapshot(perf_snapshot),.snapshot_valid(perf_snapshot_valid));
end else begin:no_performance
    assign perf_prdata=0;assign perf_pslverr=0;assign perf_snapshot=0;assign perf_snapshot_valid=0;
end endgenerate
