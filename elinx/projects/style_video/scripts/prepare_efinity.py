"""Create the independent Efinity project from the verified V4/J5 input bundle.

Only inputs are copied. Reference tools, source projects and known-good images
are never edited. All generated files remain inside style_video.
"""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,sys,xml.etree.ElementTree as ET
from camera_capture_shell import encapsulate
from video_module_shell import encapsulate_video
from generate_ddr_wrapper import generate as generate_ddr_wrapper
ROOT=Path(__file__).resolve().parent.parent
DEFAULT_REFERENCE=ROOT.parent/'demo10_official/build/run_v6_v4_j5_keys_reset'
NS={'e':'http://www.efinixinc.com/enf_proj','p':'http://www.efinixinc.com/peri_design_db'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
OFFICIAL_V1=ROOT.parent.parent/'elinxdemo/Ti60F225_DemoBoard_v4/10_Ti60f225_sc431hai2hdmi_demo/Ti60f225_sc431hai2hdmi_v1/rtl/cam_i2c_ctrl/i2c/i2c_master_reg_rom.v'
# Covered-lens RAW10 site means supplied by the user for this J5/BGGR3 mode.
# Physical sites: even-row/even-column A, even/odd B, odd/even C, odd/odd D.
MEASURED_BLACK_LEVELS=(65,66,66,67)
# User-observed white-paper RAW10 means in the same physical site order.
MEASURED_WHITE_RAW=(156,245,245,160)
MEASURED_WHITE_RGB={'R':93,'G':179,'B':91}
MEASURED_WB_GAINS_Q8=(493,256,504)

def active_rom_entries(source):
    """Read literal active sensor writes, never commented IMX examples."""
    active=re.sub(r'/\*.*?\*/|//[^\n]*','',source,flags=re.S)
    rows=re.findall(r"ROM\[8'h([0-9a-f]+)\]\s*=\s*\{\s*16'h([0-9a-f]+)\s*,\s*8'h([0-9a-f]+)\s*,\s*1'b([01])\s*\}",active,flags=re.I)
    entries={int(i,16):(int(a,16),int(d,16),int(rw)) for i,a,d,rw in rows}
    assert len(entries)==len(rows), 'Duplicate active ROM index'
    return entries

def prepare_sensor_profile(reference,profile):
    """Keep vendor inputs intact; replace only three exposure bytes in own ROM."""
    assert profile in ('verified','short_exposure')
    folder=reference/'rtl/cam_i2c_ctrl/i2c'
    source=folder/'i2c_master_reg_rom.v'
    text=source.read_text(encoding='utf-8')
    original=active_rom_entries(text)
    assert sorted(original)==list(range(164)), 'Expected verified 164-write SC431HAI ROM'
    shorter={0x73:(0x3e00,0x00,0),0x74:(0x3e01,0xba,0),0x75:(0x3e02,0xd0,0)}
    assert [original[i] for i in shorter]==[(0x3e00,0x01,0),(0x3e01,0xbb,0),(0x3e02,0xf0,0)]
    v1=active_rom_entries(OFFICIAL_V1.read_text(encoding='utf-8'))
    assert sorted(v1)==list(range(161))
    assert all(v1[i]==(shorter[i] if i in shorter else original[i]) for i in v1), 'Official v1 differs outside the exposure triplet'
    patched=text
    if profile=='short_exposure':
        for index,(address,data,rw) in shorter.items():
            pattern=r"(ROM\[8'h"+f'{index:02x}'+r"\]\s*=\s*\{\s*16'h"+f'{address:04x}'+r"\s*,\s*8'h)[0-9a-f]+"
            patched,count=re.subn(pattern,lambda m:m.group(1)+f'{data:02x}',patched,flags=re.I)
            assert count==1, 'Exposure register must appear exactly once'
    current=active_rom_entries(patched)
    changed=[i for i in original if original[i]!=current[i]]
    assert changed==(list(shorter) if profile=='short_exposure' else [])
    assert all(current[i]==original[i] for i in original if i not in shorter)
    patched=patched.replace('module i2c_master_reg_rom #(','module style_camera_reg_rom #(',1)
    assert 'module style_camera_reg_rom #(' in patched
    note='// Generated from the retained official ROM; vendor files remain untouched.\n'
    note+='// Profile '+profile+': '+('v1 exposure 00/BA/D0; all 164 entries and other settings retained.\n' if profile=='short_exposure' else 'original verified v6 exposure 01/BB/F0.\n')
    rom_target=ROOT/'rtl/style_camera_reg_rom.v'
    rom_target.write_text(note+patched,encoding='utf-8')
    sequence=(folder/'i2c_master_reg_set.v').read_text(encoding='utf-8')
    sequence=sequence.replace('module i2c_master_reg_set #(','module style_camera_reg_set #(',1)
    sequence=sequence.replace('i2c_master_reg_rom #(','style_camera_reg_rom #(',1)
    assert 'module style_camera_reg_set #(' in sequence and 'style_camera_reg_rom #(' in sequence
    sequence_target=ROOT/'rtl/style_camera_reg_set.v'
    sequence_target.write_text('// Generated adapter of the official sequencer; command timing is unchanged.\n'+sequence,encoding='utf-8')
    exposure=((current[0x73][1]&15)<<12)|(current[0x74][1]<<4)|(current[0x75][1]>>4)
    record={'profile':profile,'sensor':'SC431HAI register convention; sensor ID not read back',
      'baseline_rom':str(source),'baseline_sha256':sha(source),'official_v1_rom':str(OFFICIAL_V1),'official_v1_sha256':sha(OFFICIAL_V1),
      'entry_count':len(current),'exposure_half_lines':exposure,'datasheet_default_vts':1500,
      'linear_exposure_max_at_default_vts':2*1500-11,'actual_vts_read_back':False,'actual_fps_verified':False,
      'changed_registers':[{'index':i,'address':f'{original[i][0]:04X}','from':f'{original[i][1]:02X}','to':f'{current[i][1]:02X}'} for i in changed],
      'all_other_entries_unchanged':True,'vendor_inputs_modified':False,
      'generated_sources':{p.relative_to(ROOT).as_posix():sha(p) for p in [rom_target,sequence_target]}}
    (ROOT/'build').mkdir(exist_ok=True)
    (ROOT/'build/camera_profile_receipt.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    return record

def prepare(reference=DEFAULT_REFERENCE,camera_profile='short_exposure',bayer_pattern=3,color_probe=False,tone_profile=None,contrast_probe=False,black_level_profile=None,contrast_initial_level=None,white_balance_profile=None,wb_calibration=False,performance_monitor=False,reserve_cnn=True):
    tone_profile=tone_profile or ('linear' if color_probe else 'gamma18')
    black_level_profile=black_level_profile or ('none' if color_probe else 'measured')
    white_balance_profile=white_balance_profile or ('measured' if black_level_profile=='measured' and not color_probe else 'none')
    if black_level_profile not in ('none','measured'):raise ValueError('Black level profile must be none or measured')
    if white_balance_profile not in ('none','measured'):raise ValueError('White balance profile must be none or measured')
    if wb_calibration and (white_balance_profile!='measured' or not contrast_probe):
        raise ValueError('WB calibration requires measured white balance and contrast probe')
    if tone_profile not in ('linear','gamma18','gamma22'):raise ValueError('Tone profile must be linear, gamma18 or gamma22')
    if bayer_pattern not in range(4):raise ValueError('Bayer pattern must be 0..3')
    if color_probe and contrast_probe:raise ValueError('Color and contrast diagnostics are mutually exclusive')
    if color_probe and bayer_pattern!=0:raise ValueError('COLOR PROBE 01 requires RGGB0 capture for the labeled 0/3 comparison')
    if color_probe and tone_profile!='linear':raise ValueError('COLOR PROBE 01 uses linear RGB for the labeled comparison')
    if color_probe and black_level_profile!='none':raise ValueError('COLOR PROBE 01 retains uncorrected RAW interpretation')
    if color_probe and white_balance_profile!='none':raise ValueError('COLOR PROBE 01 retains uncorrected white balance')
    if black_level_profile=='measured' and (bayer_pattern!=3 or camera_profile!='short_exposure'):
        raise ValueError('Measured black levels apply only to the current BGGR3 / short_exposure mode')
    if white_balance_profile=='measured' and (black_level_profile!='measured' or bayer_pattern!=3 or camera_profile!='short_exposure'):
        raise ValueError('Measured white balance requires measured black levels / BGGR3 / short_exposure')
    if contrast_probe and (bayer_pattern!=3 or tone_profile!='gamma18'):
        raise ValueError('CONTRAST PROBE 01 requires the measured BGGR3 / gamma18 baseline')
    if contrast_initial_level is not None and (type(contrast_initial_level) is not int or contrast_initial_level not in range(5)):
        raise ValueError('Contrast initial level must be an integer from 0 to 4')
    if contrast_initial_level is not None and not contrast_probe:
        raise ValueError('Contrast initial level requires --contrast-probe')
    if contrast_probe and contrast_initial_level is None:
        contrast_initial_level=0 if black_level_profile=='measured' else 2
    diagnostic_stats=color_probe or contrast_probe
    black_levels=MEASURED_BLACK_LEVELS if black_level_profile=='measured' else (0,0,0,0)
    wb_gains=MEASURED_WB_GAINS_Q8 if white_balance_profile=='measured' else (256,256,256)
    gamma_tenths=22 if tone_profile=='gamma22' else 18
    # Fail before modifying the prepared project if either retained LUT is stale.
    subprocess.run([sys.executable,str(ROOT/'scripts/generate_gamma.py'),'--check'],check=True)
    generate_ddr_wrapper()
    reference=Path(reference).resolve()
    if not (reference/'ti60f225_oob.xml').is_file():raise FileNotFoundError('Complete verified V4/J5 reference XML required')
    target=ROOT/'efinity';target.mkdir(exist_ok=True)
    vendor=target/'vendor';vendor.mkdir(exist_ok=True)
    sources=[]
    # Preserve the full source/IP/memory inputs, excluding any generated flow.
    for sub in ['rtl','ip']:
        for p in sorted((reference/sub).rglob('*')):
            if not p.is_file():continue
            q=vendor/p.relative_to(reference);q.parent.mkdir(parents=True,exist_ok=True)
            if not q.exists() or sha(q)!=sha(p):shutil.copy2(p,q)
            sources.append({'path':q.relative_to(ROOT).as_posix(),'source':p.as_posix(),'sha256':sha(q)})
    for p in sorted(reference.glob('*.mem*')):
        q=target/p.name;shutil.copy2(p,q)
        sources.append({'path':q.relative_to(ROOT).as_posix(),'source':p.as_posix(),'sha256':sha(q)})
    prepare_sensor_profile(reference,camera_profile)
    orig=(reference/'rtl/ti60f225_oob_top.v').read_text(encoding='utf-8')
    header=orig[:orig.index('function integer log2;')]
    header=header.replace('module ti60f225_oob_top #(', 'module style_ti60_top #(')
    header=header.replace('`include "ddr3_controller/ddr3_parameter.vh"','`include "../efinity/vendor/rtl/ddr3_controller/ddr3_parameter.vh"')
    header='\n'.join(line for line in header.split('\n') if 'jtag_inst1_' not in line)
    initializer=(reference/'rtl/cam_i2c_ctrl/i2c/i2c_master_ctrl_top.v').read_text(encoding='utf-8')
    initializer=initializer.replace('module i2c_master_ctrl_top #(','module style_camera_initializer #(',1)
    initializer=initializer.replace('i2c_master_reg_set #(','style_camera_reg_set #(',1)
    initializer=initializer.replace('output sda_padoen_o    //', 'output sda_padoen_o,   //',1)
    initializer=initializer.replace('    \n);','    \noutput reg config_done\n);',1)
    assert 'output reg config_done' in initializer
    initializer=initializer.replace('wire\tinit_done;','''// Completion means all ROM transactions finished. The inherited controller
// does not expose a NACK status; this is not a sensor identity/readback check.
localparam integer DONE_BITS=$clog2(DATA_LENGTH+1);
reg [DONE_BITS-1:0] completed_transactions;
always @(posedge clk or negedge rst_n) begin
    if(!rst_n) begin completed_transactions<=0;config_done<=0;end
    else if(!config_done && (wr_done || rd_done)) begin
        completed_transactions<=completed_transactions+1'b1;
        if(completed_transactions==DATA_LENGTH-1) config_done<=1;
    end
end
wire tx_i2c_irq;
wire init_done;''',1)
    (ROOT/'rtl/style_camera_initializer.v').write_text('// Adapted from the verified official V4/J5 i2c_master_ctrl_top.v.\n'+initializer,encoding='utf-8')
    csi=orig[orig.index('csi_rx_controller inst_efx_csi2_rx'):orig.index('//     wire',orig.index('csi_rx_controller inst_efx_csi2_rx'))]
    csi=csi[:csi.index(');')+2]
    ddr=orig[orig.index('ddr3_top                 u_ddr3_top'):orig.index('// debayer')]
    ddr=ddr[:ddr.index(');')+2]
    board=header+'''
// Verified V4/J5 peripheral shell. Keep D-PHY/DDR electrical settings isolated
// from the portable platform core; no Xilinx primitive is used in this project.
wire w_arstn=i_arstn & i_pll_locked & pll_locked & user_pll_locked & pll_inst4_LOCKED;
wire core_rst_n,camera_rst_n,pixel_rst_n,mipi_core_reset_n,mipi_byte_reset_n;
wire w_mipi_rx_pclk_arstn;
style_reset_sync r_core(core_clk,w_arstn,core_rst_n);
style_reset_sync r_camera(i_mipi_rx_pclk,w_arstn,camera_rst_n);
style_reset_sync r_video(hdmi_tx_slow_clk,w_arstn,pixel_rst_n);
style_reset_sync r_mipi(core_clk,w_arstn,mipi_core_reset_n);
style_reset_sync r_byte(i_cam_ck_CLKOUT,w_arstn,mipi_byte_reset_n);
assign w_mipi_rx_pclk_arstn=camera_rst_n;
assign pll_inst1_RSTN=i_arstn;
assign USER_PLL_RSTN=i_arstn;
assign DDR3_PLL_RSTN=i_arstn;
assign pll_inst4_RSTN=i_arstn;
assign cam_d0_RST=~mipi_core_reset_n;assign cam_d1_RST=~mipi_core_reset_n;
assign cam_d2_RST=~mipi_core_reset_n;assign cam_d3_RST=~mipi_core_reset_n;
wire i_mipi_clk=core_clk;
wire w_mipi_rx_vs,w_mipi_rx_hs,w_mipi_rx_de;
wire [63:0] w_mipi_rx_data;
wire [15:0] mipi_debug_out;
'''+csi+'''
// Standalone initializer is retained only until the teammate's I2C driver is
// connected. Future integration must choose ONE I2C owner, never both at once.
wire scl_padoen_o,sda_padoen_o;
reg [12:0] i2c_rst_cnt;
wire i2c_reset_n;
style_reset_sync r_i2c(CLK_5M,w_arstn,i2c_reset_n);
always @(posedge CLK_5M or negedge i2c_reset_n)
    if(!i2c_reset_n)i2c_rst_cnt<=0;
    else if(!i2c_rst_cnt[12])i2c_rst_cnt<=i2c_rst_cnt+1'b1;
wire camera_config_done;
(* async_reg="true" *) reg [1:0] config_done_sync;
always @(posedge core_clk or negedge core_rst_n)
    if(!core_rst_n)config_done_sync<=0;else config_done_sync<={config_done_sync[0],camera_config_done};
style_camera_initializer camera_initializer(.clk(CLK_5M),.rst_n(i2c_rst_cnt[12]),.config_done(camera_config_done),
    .scl_pad_i(io_cam_scl_IN),.scl_pad_o(io_cam_scl_OUT),.scl_padoen_o(scl_padoen_o),
    .sda_pad_i(io_cam_sda_IN),.sda_pad_o(io_cam_sda_OUT),.sda_padoen_o(sda_padoen_o));
assign io_cam_scl_OE=~scl_padoen_o;assign io_cam_sda_OE=~sda_padoen_o;
assign o_cam_rst_p=~w_arstn;
wire cam_rgb_valid,cam_rgb_ready,cam_sof,cam_eol,cam_eof,cam_abort;
wire [23:0] cam_rgb;
wire [31:0] cam_id,cam_abort_id,camera_frames,camera_drops,camera_errors;
// Efinix CSI Generic interface asserts VS/HS high during active frame/line.
// COLOR PROBE 01: retain RGGB0 capture, compare BGGR3 by swapping R/B only
// in the right display pane. Independent raw A/B/C/D means identify the
// physical CFA sites without assigning sensor colors from register guesses.
style_camera_preprocess #(.BAYER_PATTERN(0),.VS_ACTIVE(1)) camera_preprocess(.clk(i_mipi_rx_pclk),.rst_n(camera_rst_n),
    .s_vs(w_mipi_rx_vs),.s_hs(w_mipi_rx_hs),.s_valid(w_mipi_rx_de & w_mipi_rx_hs),.s_raw(w_mipi_rx_data[39:0]),
    .m_valid(cam_rgb_valid),.m_ready(cam_rgb_ready),.m_rgb(cam_rgb),.m_sof(cam_sof),.m_eol(cam_eol),
    .m_eof(cam_eof),.m_frame_id(cam_id),.m_abort(cam_abort),.m_abort_frame_id(cam_abort_id),
    .input_frames(camera_frames),.drop_frames(camera_drops),.error_frames(camera_errors));
// Display-encoding approximation applies identically to all three channels.
// Pure combinational lookup: valid/ready/markers retain their original timing.
wire [23:0] cam_rgb_tone;
style_rgb_gamma #(.ENABLE(1)) camera_tone(.s_rgb(cam_rgb),.m_rgb(cam_rgb_tone));
wire core_cam_valid,core_cam_ready,core_cam_sof,core_cam_eol,core_cam_eof;
wire [23:0] core_cam_rgb;
wire [31:0] core_cam_id;
wire [10:0] cam_wr_level,cam_rd_level;
style_async_fifo #(.WIDTH(59),.ADDR_BITS(10)) camera_cdc(
    .wr_clk(i_mipi_rx_pclk),.rd_clk(core_clk),.async_rst_n(w_arstn),
    .s_data({cam_id,cam_eof,cam_eol,cam_sof,cam_rgb_tone}),.s_valid(cam_rgb_valid),.s_ready(cam_rgb_ready),
    .m_data({core_cam_id,core_cam_eof,core_cam_eol,core_cam_sof,core_cam_rgb}),
    .m_valid(core_cam_valid),.m_ready(core_cam_ready),.wr_level(cam_wr_level),.rd_level(cam_rd_level));
wire core_abort_valid,abort_ready;
wire [31:0] core_abort_id;
wire [4:0] abort_wr_level,abort_rd_level;
style_async_fifo #(.WIDTH(32),.ADDR_BITS(4)) abort_cdc(
    .wr_clk(i_mipi_rx_pclk),.rd_clk(core_clk),.async_rst_n(w_arstn),
    .s_data(cam_abort_id),.s_valid(cam_abort),.s_ready(abort_ready),
    .m_data(core_abort_id),.m_valid(core_abort_valid),.m_ready(1'b1),
    .wr_level(abort_wr_level),.rd_level(abort_rd_level));
wire [31:0] camera_frames_core,camera_drops_core,camera_errors_core;
style_cdc_counter stat_camera(i_mipi_rx_pclk,camera_rst_n,camera_frames,core_clk,core_rst_n,camera_frames_core);
style_cdc_counter stat_drops(i_mipi_rx_pclk,camera_rst_n,camera_drops,core_clk,core_rst_n,camera_drops_core);
style_cdc_counter stat_errors(i_mipi_rx_pclk,camera_rst_n,camera_errors,core_clk,core_rst_n,camera_errors_core);
reg abort_queue_fault;
(* async_reg="true" *) reg [1:0] abort_fault_sync;
always @(posedge i_mipi_rx_pclk or negedge camera_rst_n)
    if(!camera_rst_n)abort_queue_fault<=0;else if(cam_abort && !abort_ready)abort_queue_fault<=1;
always @(posedge core_clk or negedge core_rst_n)
    if(!core_rst_n)abort_fault_sync<=0;else abort_fault_sync<={abort_fault_sync[0],abort_queue_fault};
wire cal_done,app_sr_active,app_ref_ack,app_zq_ack;
'''
    # The verified DDR interface bus is copied verbatim in width/connection.
    fields={'awid':'AXI_ID_WIDTH','awaddr':'AXI_ADDR_WIDTH','awlen':'8','awsize':'3','awburst':'2','awlock':'1','awcache':'4','awprot':'3',
       'awvalid':'1','awready':'1','wdata':'AXI_DATA_WIDTH','wstrb':'AXI_DATA_WIDTH/8','wlast':'1','wvalid':'1','wready':'1',
       'bid':'AXI_ID_WIDTH','bresp':'2','bvalid':'1','bready':'1','arid':'AXI_ID_WIDTH','araddr':'AXI_ADDR_WIDTH','arlen':'8','arsize':'3',
       'arburst':'2','arlock':'1','arcache':'4','arprot':'3','arvalid':'1','arready':'1','rid':'AXI_ID_WIDTH','rdata':'AXI_DATA_WIDTH',
       'rresp':'2','rlast':'1','rvalid':'1','rready':'1'}
    board+=''.join(f"wire {'['+w+'-1:0] ' if w!='1' else ''}s_axi_{n};\n" for n,w in fields.items())
    board+='''assign s_axi_awlock=0;assign s_axi_arlock=0;
assign s_axi_awcache=0;assign s_axi_arcache=0;assign s_axi_awprot=0;assign s_axi_arprot=0;
'''+ddr+'''
wire [23:0] display_rgb,video_rgb;
wire display_valid,display_ready,display_ack,display_flush,front_valid,refresh_request,safe_window;
wire [31:0] front_id,underflows,underflows_core,captured_count,processed_count,displayed_count,drop_count,error_count;
wire [15:0] capture_fps,process_fps,video_x,video_y;
wire [1:0] mode;
wire bypass_active,fatal_fault,irq;
wire video_de,video_hs,video_vs;
// Diagnostic measurements never gate the camera stream or alter DMA payloads.
wire cfa_mean_valid,cfa_stats_ready,cfa_pixel_valid;
wire [39:0] cfa_mean_data,cfa_pixel_data;
wire [2:0] cfa_wr_level,cfa_rd_level;
style_cfa_stats raw_cfa_stats(.clk(i_mipi_rx_pclk),.rst_n(camera_rst_n),
    .s_vs(w_mipi_rx_vs),.s_hs(w_mipi_rx_hs),.s_valid(w_mipi_rx_de & w_mipi_rx_hs),
    .s_raw(w_mipi_rx_data[39:0]),.mean_valid(cfa_mean_valid),.mean_data(cfa_mean_data));
style_async_fifo #(.WIDTH(40),.ADDR_BITS(2)) color_stats_cdc(
    .wr_clk(i_mipi_rx_pclk),.rd_clk(hdmi_tx_slow_clk),.async_rst_n(w_arstn),
    .s_data(cfa_mean_data),.s_valid(cfa_mean_valid),.s_ready(cfa_stats_ready),
    .m_data(cfa_pixel_data),.m_valid(cfa_pixel_valid),.m_ready(1'b1),
    .wr_level(cfa_wr_level),.rd_level(cfa_rd_level));
reg cfa_stats_overflow;
(* async_reg="true" *) reg [1:0] cfa_overflow_sync;
reg [39:0] cfa_latest,cfa_overlay;
reg cfa_seen,cfa_overlay_valid;
always @(posedge i_mipi_rx_pclk or negedge camera_rst_n)
    if(!camera_rst_n)cfa_stats_overflow<=0;
    else if(cfa_mean_valid && !cfa_stats_ready)cfa_stats_overflow<=1;
always @(posedge hdmi_tx_slow_clk or negedge pixel_rst_n) begin
    if(!pixel_rst_n) begin
        cfa_overflow_sync<=0;cfa_latest<=0;cfa_overlay<=0;
        cfa_seen<=0;cfa_overlay_valid<=0;
    end else begin
        cfa_overflow_sync<={cfa_overflow_sync[0],cfa_stats_overflow};
        if(cfa_pixel_valid) begin cfa_latest<=cfa_pixel_data;cfa_seen<=1;end
        // Latch the whole display bundle before the diagnostic text lines.
        if(video_x==0 && video_y==640) begin
            cfa_overlay<=cfa_latest;cfa_overlay_valid<=cfa_seen && !cfa_overflow_sync[1];
        end
    end
end
style_cdc_counter stat_underflow(hdmi_tx_slow_clk,pixel_rst_n,underflows,core_clk,core_rst_n,underflows_core);
style_display_sink display_sink(.core_clk(core_clk),.core_rst_n(core_rst_n),
    .pixel_clk(hdmi_tx_slow_clk),.pixel_rst_n(pixel_rst_n),.core_flush(display_flush),
    .core_front_valid(front_valid),.core_frame_id(front_id),.core_mode(mode),
    .capture_fps(capture_fps),.process_fps(process_fps),.bypass_active(bypass_active),
    .core_camera_frames(camera_frames_core),.core_drop_count(drop_count),.core_error_count(error_count),
    .s_rgb(display_rgb),.s_valid(display_valid),.s_ready(display_ready),
    .refresh_request(refresh_request),.refresh_ack(display_ack),.safe_window(safe_window),
    .video_rgb(video_rgb),.video_de(video_de),.video_hs(video_hs),.video_vs(video_vs),
    .video_x(video_x),.video_y(video_y),.underflow_count(underflows));
style_platform_core #(.ID_WIDTH(AXI_ID_WIDTH),.FORCE_BYPASS(1)) platform(
    .clk(core_clk),.rst_n(core_rst_n),.cal_ready(cal_done && config_done_sync[1] && !abort_fault_sync[1]),
    .cam_rgb(core_cam_rgb),.cam_valid(core_cam_valid),.cam_ready(core_cam_ready),
    .cam_sof(core_cam_sof),.cam_eol(core_cam_eol),.cam_eof(core_cam_eof),.cam_frame_id(core_cam_id),
    .cam_abort(core_abort_valid),.cam_abort_id(core_abort_id),
    .camera_frames(camera_frames_core),.camera_drops(camera_drops_core),.camera_errors(camera_errors_core),
    .display_refresh_request(refresh_request),.display_safe_window(safe_window),
    .display_refresh_ack(display_ack),.display_flush(display_flush),
    .display_rgb(display_rgb),.display_valid(display_valid),.display_ready(display_ready),
    .front_valid(front_valid),.front_frame_id(front_id),.display_mode(mode),
    .capture_fps(capture_fps),.process_fps(process_fps),.underflow_count(underflows_core),.bypass_active(bypass_active),
    .paddr(12'b0),.psel(1'b0),.penable(1'b0),.pwrite(1'b0),.pwdata(32'b0),.prdata(),.pready(),.pslverr(),.irq(irq),
    .accel_input_rgb(),.accel_input_valid(),.accel_input_ready(1'b0),
    .accel_input_sof(),.accel_input_eol(),.accel_input_eof(),.accel_input_frame_id(),
    .accel_output_rgb(24'b0),.accel_output_valid(1'b0),.accel_output_ready(),
    .accel_output_sof(1'b0),.accel_output_eol(1'b0),.accel_output_eof(1'b0),.accel_output_frame_id(32'b0),.accel_start(),.accel_abort(),
    .captured_count(captured_count),.processed_count(processed_count),.displayed_count(displayed_count),
    .drop_count(drop_count),.error_count(error_count),.fatal_fault(fatal_fault),
'''
    keys=[n for n in fields if n not in {'awlock','arlock','awcache','arcache','awprot','arprot'}]
    board+=',\n'.join('    .m_axi_'+n+'(s_axi_'+n+')' for n in keys)+'\n);\n'
    board+='''
// Existing licensed HDMI encoder, driven with TRUE R/G/B order and VIC=4.
wire [23:0] probe_rgb;
style_color_probe_overlay color_probe_overlay(.x(video_x),.y(video_y),.input_rgb(video_rgb),
    .cfa_means(cfa_overlay),.sample_valid(cfa_overlay_valid),.rgb(probe_rgb));
wire [9:0] tmds_data0,tmds_data1,tmds_data2,tmds_clk;
dvi_encoder hdmi_encoder(.pixelclk(hdmi_tx_slow_clk),.rst_p(~pixel_rst_n),
    .i_rdata(probe_rgb[23:16]),.i_gdata(probe_rgb[15:8]),.i_bdata(probe_rgb[7:0]),
    .i_de(video_de),.i_hs(video_hs),.i_vs(video_vs),.video_format(2'b00),.video_VIC(8'd4),
    .audio_L(24'b0),.audio_R(24'b0),.audio_valid(1'b0),.audio_N(20'd6144),.audio_CTS(20'd74250),
    .audio_sample_frequency(3'b010),.audio_word_length(4'b1011),
    .tmds_data0(tmds_data0),.tmds_data1(tmds_data1),.tmds_data2(tmds_data2),.tmds_clk(tmds_clk));
assign tmds_tx_clk_TX_DATA=~tmds_clk;
assign tmds_tx_data0_TX_DATA=~tmds_data0;
assign tmds_tx_data1_TX_DATA=~tmds_data1;
assign tmds_tx_data2_TX_DATA=~tmds_data2;
assign tmds_tx_clk_TX_OE=1'b1;assign tmds_tx_data0_TX_OE=1'b1;
assign tmds_tx_data1_TX_OE=1'b1;assign tmds_tx_data2_TX_OE=1'b1;
assign tmds_tx_clk_TX_RST=~pixel_rst_n;assign tmds_tx_data0_TX_RST=~pixel_rst_n;
assign tmds_tx_data1_TX_RST=~pixel_rst_n;assign tmds_tx_data2_TX_RST=~pixel_rst_n;
reg [25:0] heartbeat;
always @(posedge core_clk or negedge core_rst_n)
    if(!core_rst_n)heartbeat<=0;else heartbeat<=heartbeat+1'b1;
assign led={fatal_fault|abort_fault_sync[1],|error_count,front_valid,cal_done & heartbeat[24]};
// Unused DSI outputs are explicitly disabled; camera uses J5, monitor HDMI TX.
assign LCD_RST_P=1'b0;assign LCD_POWER=1'b0;
'''
    for p in re.findall(r'output\s+(?:wire\s+)?(?:\[[^\]]+\]\s*)?(mipi_dp_\w+)',header):
        board+='assign '+p+('=1\'b1;\n' if p.endswith('_RST') else '=0;\n')
    board+='endmodule\n'
    if not diagnostic_stats:
        start=board.index('// Diagnostic measurements never gate')
        end=board.index('style_cdc_counter stat_underflow',start)
        board=board[:start]+board[end:]
    if not color_probe:
        start=board.index('wire [23:0] probe_rgb;')
        end=board.index('wire [9:0] tmds_data0',start)
        board=board[:start]+board[end:]
        board=board.replace('probe_rgb[','video_rgb[')
        board=board.replace('// COLOR PROBE 01: retain RGGB0 capture, compare BGGR3 by swapping R/B only\n// in the right display pane. Independent raw A/B/C/D means identify the\n// physical CFA sites without assigning sensor colors from register guesses.\n',
            '// Explicit camera Bayer interpretation; select from measured physical CFA sites.\n')
    if contrast_probe:
        anchor='wire [9:0] tmds_data0,tmds_data1,tmds_data2,tmds_clk;'
        contrast='''// Display-only contrast diagnostic; DDR and camera RGB remain gamma18.
wire [23:0] contrast_rgb;
wire [2:0] contrast_level;
style_contrast_probe contrast_probe(.clk(hdmi_tx_slow_clk),.rst_n(pixel_rst_n),.key1_n(key1_n),
    .x(video_x),.y(video_y),.input_rgb(video_rgb),.cfa_means(cfa_overlay),
    .sample_valid(cfa_overlay_valid),.rgb(contrast_rgb),.level(contrast_level));
'''
        # Preserve the historical none/level2 top byte-for-byte. Other levels
        # override only the display diagnostic's existing reset parameter.
        if contrast_initial_level!=2:
            contrast=contrast.replace('style_contrast_probe contrast_probe(',f'style_contrast_probe #(.INITIAL_LEVEL({contrast_initial_level})) contrast_probe(',1)
        assert board.count(anchor)==1
        board=board.replace(anchor,contrast+anchor,1)
        encoder_input='.i_rdata(video_rgb[23:16]),.i_gdata(video_rgb[15:8]),.i_bdata(video_rgb[7:0])'
        assert board.count(encoder_input)==1
        board=board.replace(encoder_input,encoder_input.replace('video_rgb[','contrast_rgb['),1)
    board=board.replace('.BAYER_PATTERN(0),.VS_ACTIVE(1)',f'.BAYER_PATTERN({bayer_pattern}),.VS_ACTIVE(1)',1)
    camera_parameters=f'.BAYER_PATTERN({bayer_pattern}),.VS_ACTIVE(1)'
    black_parameters=','.join(f'.BLACK_LEVEL_{site}({value})' for site,value in zip('ABCD',black_levels))
    assert board.count(camera_parameters)==1
    board=board.replace(camera_parameters,camera_parameters+','+black_parameters,1)
    if white_balance_profile=='measured':
        # None uses the identity defaults, retaining the earlier top verbatim.
        wb_parameters=','.join(f'.WB_GAIN_{color}_Q8({value})' for color,value in zip('RGB',wb_gains))
        board=board.replace(camera_parameters+','+black_parameters,camera_parameters+','+black_parameters+','+wb_parameters,1)
    if wb_calibration:
        anchor='wire [9:0] tmds_data0,tmds_data1,tmds_data2,tmds_clk;'
        shell=(ROOT/'scripts/wb_calibration_shell.vh').read_text(encoding='utf-8')
        board=board.replace(anchor,shell+'\n'+anchor,1)
        board=board.replace(camera_parameters,camera_parameters+',.DYNAMIC_WB(1)',1)
        anchor='.s_vs(w_mipi_rx_vs),.s_hs(w_mipi_rx_hs),.s_valid(w_mipi_rx_de & w_mipi_rx_hs),.s_raw(w_mipi_rx_data[39:0]),'
        assert board.count(anchor)==1
        board=board.replace(anchor,anchor+'\n    .wb_r_q8(wb_request_r),.wb_g_q8(11\'d256),.wb_b_q8(wb_request_b),',1)
        board=board.replace('.i_rdata(contrast_rgb[23:16]),.i_gdata(contrast_rgb[15:8]),.i_bdata(contrast_rgb[7:0])',
            '.i_rdata(wb_rgb[23:16]),.i_gdata(wb_rgb[15:8]),.i_bdata(wb_rgb[7:0])',1)
    board=board.replace('style_rgb_gamma #(.ENABLE(1))',f'style_rgb_gamma #(.ENABLE({int(tone_profile!="linear")}), .GAMMA_TENTHS({gamma_tenths}))',1)
    if performance_monitor:
        anchor='style_platform_core #(.ID_WIDTH(AXI_ID_WIDTH),.FORCE_BYPASS(1))'
        assert board.count(anchor)==1
        board=board.replace(anchor,anchor.replace('.FORCE_BYPASS(1)','.FORCE_BYPASS(1),.PERF_ENABLE(1)'),1)
        anchor='.drop_count(drop_count),.error_count(error_count),.fatal_fault(fatal_fault),'
        assert board.count(anchor)==1
        board=board.replace(anchor,anchor+'''\n    .perf_camera_level({5'd0,cam_rd_level}),.perf_display_level({3'd0,display_fifo_level}),
    .perf_snapshot(perf_snapshot),.perf_snapshot_valid(perf_snapshot_valid),''',1)
        board=board.replace('.video_x(video_x),.video_y(video_y),.underflow_count(underflows));',
            '.video_x(video_x),.video_y(video_y),.underflow_count(underflows),.monitor_fifo_level(display_fifo_level));',1)
        anchor='wire [9:0] tmds_data0,tmds_data1,tmds_data2,tmds_clk;'
        source='wb_rgb' if wb_calibration else ('contrast_rgb' if contrast_probe else ('probe_rgb' if color_probe else 'video_rgb'))
        shell='''wire [1023:0] perf_snapshot;
wire perf_snapshot_valid;
wire [12:0] display_fifo_level;
wire [23:0] perf_rgb;
style_perf_overlay perf_ui(.core_clk(core_clk),.core_rst_n(core_rst_n),
    .pixel_clk(hdmi_tx_slow_clk),.pixel_rst_n(pixel_rst_n),.async_rst_n(w_arstn),
    .snapshot(perf_snapshot),.snapshot_valid(perf_snapshot_valid),.x(video_x),.y(video_y),
    .input_rgb(SOURCE_RGB),.rgb(perf_rgb));
'''.replace('SOURCE_RGB',source)
        board=board.replace(anchor,shell+anchor,1)
        connection=f'.i_rdata({source}[23:16]),.i_gdata({source}[15:8]),.i_bdata({source}[7:0])'
        assert board.count(connection)==1
        board=board.replace(connection,'.i_rdata(perf_rgb[23:16]),.i_gdata(perf_rgb[15:8]),.i_bdata(perf_rgb[7:0])',1)
    board=board.replace(".video_VIC(8'd4)",".video_VIC(7'd4)")
    board=board.replace(".audio_sample_frequency(3'b010)",".audio_sample_frequency(4'b0010)")
    board=encapsulate(board,bayer=bayer_pattern,black=black_levels,gains=wb_gains,
        dynamic_wb=wb_calibration,tone_enable=tone_profile!='linear',gamma=gamma_tenths,stats=diagnostic_stats)
    board=encapsulate_video(board,color=color_probe,contrast=contrast_probe,contrast_level=contrast_initial_level,
        wb=wb_calibration,perf=performance_monitor,reserve_cnn=reserve_cnn)
    (ROOT/'rtl/style_ti60_top.v').write_text(board,encoding='utf-8')
    ET.register_namespace('efx',NS['e']);tree=ET.parse(reference/'ti60f225_oob.xml');root=tree.getroot()
    root.set('name','style_video');root.set('description','Independent camera/RGB DDR/display platform, V4 J5, COPY placeholder')
    design=root.find('e:design_info',NS);design.find('e:top_module',NS).set('name','style_ti60_top')
    for e in list(design.findall('e:design_file',NS)):design.remove(e)
    old=ET.parse(reference/'ti60f225_oob.xml').getroot()
    for e in old.findall('e:design_info/e:design_file',NS):
        name=e.get('name')
        if name=='debug_top.v' or name in ['rtl/ti60f225_oob_top.v','rtl/board_image_controls.sv','rtl/reset_release_sync.sv']:continue
        e.set('name','vendor/'+name);design.append(e)
    for p in sorted((ROOT/'rtl').glob('*')):
        if p.suffix not in ['.sv','.v']:continue
        ET.SubElement(design,'{'+NS['e']+'}design_file',{'name':'../rtl/'+p.name,'version':'default','library':'default'})
    for e in root.findall('e:interface_info/*',NS):e.set('name','style_video.peri.xml')
    root.find('e:constraint_info/e:sdc_file',NS).set('name','style_video.sdc')
    for e in root.findall('e:debugger/e:param',NS):
        if e.get('name')=='auto_instantiation':e.set('value','off')
        if e.get('name')=='profile':e.set('value','')
    for e in root.findall('e:synthesis/e:param',NS):
        if e.get('name')=='enable-mark-debug':e.set('value','0')
    # Keep the vendor project's native lexical layout. Some Efinity native
    # readers do not accept ElementTree's reordered namespace attributes.
    xml_text=(reference/'ti60f225_oob.xml').read_text(encoding='utf-8')
    xml_text=xml_text.replace('name="ti60f225_oob"','name="style_video"',1)
    xml_text=xml_text.replace('name="ti60f225_oob_top"','name="style_ti60_top"',1)
    xml_text=re.sub(r'^\s*<efx:design_file[^\n]*\n','',xml_text,flags=re.M)
    file_lines='\n'.join('        <efx:design_file name="'+e.get('name')+'" version="default" library="default"/>'
                         for e in design.findall('e:design_file',NS))
    # The project schema is ordered: files follow top_module and precede
    # top_vhdl_arch. Appending files at the end is not schema-valid.
    top_anchor='        <efx:top_module name="style_ti60_top"/>'
    xml_text=xml_text.replace(top_anchor,top_anchor+'\n'+file_lines)
    xml_text=xml_text.replace('ti60f225_oob.peri.xml','style_video.peri.xml').replace('ti60f225_oob.sdc','style_video.sdc')
    xml_text=xml_text.replace('name="auto_instantiation" value="on"','name="auto_instantiation" value="off"')
    xml_text=xml_text.replace('name="profile" value="debug_profile.wizard.json"','name="profile" value=""')
    xml_text=xml_text.replace('name="enable-mark-debug" value="1"','name="enable-mark-debug" value="0"')
    (target/'style_video.xml').write_text(xml_text,encoding='utf-8')
    # Only HDMI output dividers change. DDR and MIPI parameters and ALL pin
    # assignments are preserved, including verified V4 keys and J5 lanes.
    pt=ET.parse(reference/'ti60f225_oob.peri.xml')
    for pll in pt.findall('.//p:pll',NS):
        if pll.get('name')=='USER_PLL':
            for c in pll.findall('p:comp_output_clock',NS):
                if c.get('name')=='hdmi_tx_slow_clk':c.set('out_divider','40')
                if c.get('name')=='hdmi_tx_fast_clk':c.set('out_divider','8')
        if pll.get('name')=='pll_inst4':
            pll.set('reset_name','pll_inst4_RSTN');pll.set('locked_name','pll_inst4_LOCKED')
    pt.getroot().set('name','style_video')
    # There is no fabric debugger in this standalone build. Removing its
    # USER1 instance avoids required internal JTAG pins optimized out by map.
    jtag_info=pt.getroot().find('p:jtag_info',NS)
    if jtag_info is not None:
        for child in list(jtag_info):jtag_info.remove(child)
    ET.register_namespace('efxpt',NS['p']);ET.indent(pt)
    pt.write(target/'style_video.peri.xml',encoding='utf-8',xml_declaration=True)
    sdc=(reference/'ti60f225_oob.sdc').read_text(encoding='utf-8')
    # Preserve the verified DDR/MIPI pin delay values; remove references to the
    # old debug core and unresolved placeholder clock declarations.
    lines=[]
    for line in sdc.splitlines():
        if 'jtag_inst' in line or '<USER_PERIOD>' in line:continue
        if 'create_clock' in line and 'hdmi_tx_slow_clk' in line:line='create_clock -period 13.468013 -name hdmi_tx_slow_clk [get_ports {hdmi_tx_slow_clk}]'
        if 'create_clock' in line and 'hdmi_tx_fast_clk' in line:line='create_clock -waveform {0.336700 1.683502} -period 2.693603 -name hdmi_tx_fast_clk [get_ports {hdmi_tx_fast_clk}]'
        # Clock grouping is rebuilt explicitly below; no broad false path
        # between unrelated core registers is inserted.
        if line.strip().startswith('set_clock_groups'):continue
        lines.append(line)
    lines+=['','create_clock -period 40.000 -name CLK_25M [get_ports {CLK_25M}]',
      'set_clock_groups -asynchronous -group {core_clk} -group {i_mipi_rx_pclk} -group {hdmi_tx_slow_clk vid_clk_dvi2 hdmi_tx_fast_clk} -group {CLK_5M} -group {i_cam_ck_CLKOUT} -group {i_mipi_tx_pclk i_mipi_txc_sclk i_mipi_txd_sclk} -group {sdram_clk tx_cal_clk tx_cal_clk_90edge rx_cal_clk clk_100m}',
      'set_false_path -from [get_ports {i_arstn key1_n key2_n key3_n i_pll_locked pll_locked user_pll_locked pll_inst4_LOCKED}]',
      '# Efinity-native bus-skew constraint; async clock groups remain cut.',
      '# Remaining async input pin delay constraints are inherited from verified J5 example.']
    # Efinity flattens a generate scope and child instance with '.', not '/'.
    fifo_names=['camera_capture/camera_cdc','camera_capture/abort_cdc','hdmi_display/sink/fifo']+(['hdmi_display/raw_diagnostics.color_stats_cdc'] if diagnostic_stats else [])
    if wb_calibration:fifo_names+=['hdmi_display/white_balance_diagnostic.wb_status_cdc']
    for fifo in fifo_names:
        for source,dest in [('wgray','wgray_r1'),('rgray','rgray_w1')]:
            lines.append('set_bus_skew -from [get_cells {'+fifo+'/'+source+'[*]~FF}] -to [get_cells {'+fifo+'/'+dest+'[*]~FF}] 10.000')
    for stat in ['camera_capture/stat_camera','camera_capture/stat_drops','camera_capture/stat_errors','hdmi_display/stat_underflow']:
        lines.append('set_bus_skew -from [get_cells {'+stat+'/gray[*]~FF}] -to [get_cells {'+stat+'/sync1[*]~FF}] 10.000')
    (target/'style_video.sdc').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    receipt={'reference':reference.as_posix(),'files':sources,'pin_profile':'Ti60F225I3 DemoBoard V4, camera J5',
      'HDMI_pixel_MHz':74.25,'HDMI_fast_MHz':371.25,'camera_width':1920,'camera_height':1080,
      'reference_project_sha256':sha(reference/'ti60f225_oob.xml'),
      'reference_peripheral_sha256':sha(reference/'ti60f225_oob.peri.xml'),
      'DDR_parameter_sha256':sha(vendor/'rtl/ddr3_controller/ddr3_parameter.vh'),
      'camera_profile':camera_profile,'camera_profile_receipt':'build/camera_profile_receipt.json',
      'bayer_pattern':bayer_pattern,'color_probe_enabled':color_probe,
      'contrast_probe_enabled':contrast_probe,'raw_stats_enabled':diagnostic_stats,
      'display_contrast_gain_quarters':[4,5,6,7,8] if contrast_probe else None,
      'display_contrast_initial_level':contrast_initial_level if contrast_probe else None,
      'display_contrast_initial_gain_quarters':4+contrast_initial_level if contrast_probe else None,
      'display_contrast_initial_multiplier':(4+contrast_initial_level)/4 if contrast_probe else None,
      'tone_profile':tone_profile,'gamma_profile_receipt':'build/gamma_profile.json',
      'black_level_profile':black_level_profile,'raw_black_levels':dict(zip('ABCD',black_levels)),
      'black_level_measurement_receipt':'build/contrast_probe_receipt.json' if black_level_profile=='measured' else None,
      'black_level_operation':'per physical CFA site clamp(raw10-offset,0), before Bayer reconstruction/G averaging/RGB8/gamma',
      'performance_monitor_enabled':performance_monitor,
      'camera_capture_module':'style_camera_capture',
      'ddr_framebuffer_module':'style_ddr_framebuffer',
      'hdmi_display_module':'style_hdmi_display',
      'cnn_right_pane_reserved':reserve_cnn,
      'display_layout':'left original / right black reserved for CNN' if reserve_cnn else 'APB display_mode controls original/result; standalone result is COPY',
      'camera_capture_interface':'RAW10 x4 camera-domain input -> RGB888 core-domain ready/valid with abort/counters; sensor I2C and PHY remain board-owned',
      'wb_calibration_enabled':wb_calibration,
      'white_balance_profile':white_balance_profile,'white_balance_gains_q8':dict(zip('RGB',wb_gains)),
      'white_balance_white_raw_sites':dict(zip('ABCD',MEASURED_WHITE_RAW)),
      'white_balance_white_rgb_after_black':MEASURED_WHITE_RGB,
      'white_balance_measurement_receipt':'build/white_balance_measurement.json' if white_balance_profile=='measured' else None,
      'white_balance_gain_quantization':'Q8 half-up: floor(256*179/channel+0.5), target G=179',
      'white_balance_operation':'physical-site RAW10 black clamp -> Bayer R/B and floor((G0+G1)/2) -> clamp_0_1023((RAW10*gain_q8+128)>>8) -> RGB8[9:2] -> gamma',
      'raw_statistics_before_black_correction':True,
      'selected_gamma_tenths':gamma_tenths if tone_profile!='linear' else None,
      'camera_rgb_encoding':('approx_'+tone_profile) if tone_profile!='linear' else 'linear_RAW10_to_RGB8',
      'changes':['independent portable platform RTL','HDMI dividers 40/8','bound camera PLL reset/lock','debug disabled','explicit clock groups'],
      'programmed':False}
    (ROOT/'build').mkdir(exist_ok=True)
    (ROOT/'build/source_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(target/'style_video.xml')
    return target
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--reference',type=Path,default=DEFAULT_REFERENCE)
    p.add_argument('--camera-profile',choices=['verified','short_exposure'],default='short_exposure')
    p.add_argument('--bayer-pattern',type=int,choices=range(4),default=3)
    p.add_argument('--color-probe',action='store_true',help='Temporary COLOR PROBE 01 overlay and independent raw CFA statistics; requires Bayer0')
    p.add_argument('--contrast-probe',action='store_true',help='Display-only adjustable contrast and RAW means; requires BGGR3/gamma18, KEY1 cycles levels')
    p.add_argument('--contrast-initial-level',type=int,choices=range(5),default=None,help='Requires --contrast-probe; default level0 (1.00) with measured black levels, level2 (1.50) with none')
    p.add_argument('--black-level-profile',choices=['none','measured'],default=None,help='Normal default: measured RAW10 A/B/C/D=65/66/66/67; color probe default: none')
    p.add_argument('--white-balance-profile',choices=['none','measured'],default=None,help='Default measured with measured black levels, otherwise none; measured requires BGGR3/short_exposure/measured black levels')
    p.add_argument('--tone-profile',choices=['linear','gamma18','gamma22'],default=None,help='Default gamma18 for normal display; gamma22 restores stronger lift; linear for --color-probe')
    p.add_argument('--wb-calibration',action='store_true',help='KEY2 neutral-target calibration / KEY3 default restore; requires measured WB and contrast probe')
    p.add_argument('--performance-monitor',action='store_true',help='Passive frame timing, DDR traffic/wait, FIFO high-water bank and decimal OSD')
    p.add_argument('--show-result',action='store_true',help='Disable default black CNN reservation and display the actual result pane; still COPY until a CNN is integrated')
    a=p.parse_args();prepare(a.reference,a.camera_profile,a.bayer_pattern,a.color_probe,a.tone_profile,a.contrast_probe,a.black_level_profile,a.contrast_initial_level,a.white_balance_profile,a.wb_calibration,a.performance_monitor,not a.show_result)
