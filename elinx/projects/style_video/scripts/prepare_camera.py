"""Prepare isolated Ti60 V4 camera + Sapphire + runtime CNN + DDR/720p30."""
from pathlib import Path
import copy,hashlib,json,re,shutil,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];WS=ROOT.parents[2]
BASE=WS/'elinx/projects/uart_style_tiles'
REF=WS/'elinx/elinxdemo/Ti60F225_DemoBoard_v4/10_Ti60f225_sc431hai2hdmi_demo/Ti60f225_sc431hai2hdmi_v7/Ti60f225_sc431hai2hdmi_v7'
BUILD=ROOT/'build/camera_vga';NS='http://www.efinixinc.com/enf_proj';PN='http://www.efinixinc.com/peri_design_db'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 BUILD.mkdir(parents=True,exist_ok=True);rtl=ROOT/'rtl';rtl.mkdir(exist_ok=True)
 reused={}
 for name in ('board_boot.sv','reset_sync.sv','style_keys.sv','frame_reader.sv','style_read_arbiter.sv','pixel_fifo_efx.sv','hdmi_encoder.sv','tmds_efx.sv'):
  src=BASE/'rtl'/name;target=rtl/name
  if target.exists() and target.read_bytes()!=src.read_bytes():raise RuntimeError('Private reusable file changed: '+name)
  shutil.copyfile(src,target);reused[str(src.relative_to(WS))]=sha(src)
 src=BASE/'rtl/video_720p.sv'
 text=src.read_text(encoding='utf-8').replace('module video_720p #(','module video_raster #(')
 text=text.replace('output reg [31:0] underflow_frames);','output reg [31:0] underflow_frames,output reg[11:0] x,y);')
 text=text.replace('hsync<=0; vsync<=0; de<=0; rgb<=0;', 'hsync<=0; vsync<=0; de<=0; rgb<=0;x<=0;y<=0;')
 text=text.replace('hsync<=h<H_SYNC;', 'x<=h-H_START;y<=v-V_START;hsync<=h<H_SYNC;')
 (rtl/'video_raster.sv').write_text(text,encoding='utf-8')
 # Preserve encrypted V7 CSI implementation and all original copyright text.
 vendor=ROOT/'vendor';vendor.mkdir(exist_ok=True)
 shutil.copytree(BASE/'vendor',vendor,dirs_exist_ok=True)
 original_csi=(REF/'rtl/csi_rx_controller.sv').read_bytes()
 (vendor/'csi_rx_controller.sv').write_bytes(original_csi)
 # Same IP 5.15, separately generated RAW10-only + pixel sideband instance.
 # Original V7 file stays untouched for provenance; only one instance is built.
 generated=ROOT/'build/csi515_probe/ip/camera_csi/camera_csi.sv'
 assert generated.exists(),'Run generate_csi_probe.py first'
 assert b'IP Version: 5.15' in generated.read_bytes()[:200]
 shutil.copyfile(generated,vendor/'camera_csi.sv')
 csi=(REF/'rtl/ti60f225_oob_top.v').read_text(encoding='utf-8',errors='replace')
 p=csi.index('csi_rx_controller inst_efx_csi2_rx');q=csi.index('\n\t\t);',p)+len('\n\t\t);')
 csi_instance=csi[p:q]
 csi_instance=csi_instance.replace('csi_rx_controller inst_efx_csi2_rx','camera_csi inst_efx_csi2_rx')
 csi_instance=csi_instance.replace('.irq', '.pixel_datatype(cam_pixel_datatype),.pixel_wordcount(cam_pixel_wordcount),\n              .pixel_line_num(),.pixel_frame_num(),.pixel_vc(),.pixel_vcx(),\n              .irq')
 csi_instance=csi_instance.replace('(i_arstn)','(!reset_ui)').replace('(i_mipi_clk)','(core_clk)').replace('(w_mipi_rx_pclk_arstn)','(!reset_ui)').replace('(i_mipi_rx_pclk)','(core_clk)')
 csi_instance=csi_instance.replace('.reset_byte_HS_n\t(i_arstn)', '.reset_byte_HS_n\t(!reset_byte)')
 csi_instance=re.sub(r'\.reset_byte_HS_n\s*\([^)]*\)', '.reset_byte_HS_n(!reset_byte)',csi_instance)
 csi_instance=csi_instance.replace('w_mipi_rx_hs','cam_hs').replace('w_mipi_rx_vs','cam_vs').replace('w_mipi_rx_data','cam_pixels').replace('w_mipi_rx_de','cam_valid')
 csi_instance=csi_instance.replace('mipi_debug_out(mipi_debug_out)','mipi_debug_out(cam_debug)')
 csi_instance=re.sub(r'\.datatype\s*\(\s*\)', '.datatype(cam_datatype)',csi_instance)
 csi_instance=re.sub(r'\.pixel_per_clk\s*\(\s*\)', '.pixel_per_clk(cam_ppc)',csi_instance)
 # Unlike the original display-only demo, error status must actually run:
 # debug ports are clocked by AXI, not the byte/pixel output clock.
 for port,signal in {'axi_clk':'core_clk','axi_reset_n':'!reset_ui',
  'axi_awvalid':'csi_awvalid','axi_awready':'csi_awready','axi_wvalid':'csi_wvalid',
  'axi_wready':'csi_wready','axi_bvalid':'csi_bvalid','axi_bready':'csi_bready',
  'axi_wdata':"32'h00007ffc"}.items():
  csi_instance=re.sub(r'\.'+port+r'\s*\([^)]*\)', '.'+port+'('+signal+')',csi_instance)
 # All unused *input* ports tied to known constants, not floating X values.
 for name in ('Rx_HS_D_4','Rx_HS_D_5','Rx_HS_D_6','Rx_HS_D_7','u_dly_enable_D','u_dly_inc_D'):
  csi_instance=re.sub(r'\.'+name+r'\s*\(\s*\)', '.'+name+"(8'd0)" if name.startswith('Rx_HS') else '.'+name+"(4'd0)",csi_instance)
 base_top=(BASE/'rtl/ti60_style_top.sv').read_text(encoding='utf-8')
 header=base_top[base_top.index('module ti60_style_top'):base_top.index(' wire ui_clk=')]
 header=header.replace('module ti60_style_top','module ti60_camera_top').replace('`STYLE_PROC_WIDTH','640').replace('`STYLE_PROC_HEIGHT','480')
 cam_ports=''' input wire io_cam_sda_IN,io_cam_scl_IN,
 output wire io_cam_sda_OUT,io_cam_sda_OE,io_cam_scl_OUT,io_cam_scl_OE,o_cam_rst_p,
 input wire i_cam_ck_LP_P_IN,i_cam_ck_LP_N_IN,i_cam_ck_CLKOUT,
 output wire o_cam_ck_HS_TERM,o_cam_ck_HS_ENA,
'''
 for i in range(4):cam_ports+=f''' input wire[7:0] cam_d{i}_HS_IN,
 input wire cam_d{i}_LP_P_IN,cam_d{i}_LP_N_IN,cam_d{i}_FIFO_EMPTY,
 output wire cam_d{i}_HS_TERM,cam_d{i}_HS_ENA,cam_d{i}_RST,cam_d{i}_FIFO_RD,
'''
 header=header.replace(' output wire DDR3_PLL_RSTN',cam_ports+' output wire DDR3_PLL_RSTN')
 reset=''' wire ui_clk=core_clk,pixel_clk=hdmi_tx_slow_clk;
 wire sys_rst_n,ddr_reset,reset_ui,reset_pixel,calibrated,soc_reset,reset_byte;
 board_boot boot(.clk(CLK_25M),.keys_n(style_keys_n),.reset_n(sys_rst_n));
 assign DDR3_PLL_RSTN=sys_rst_n;assign USER_PLL_RSTN=sys_rst_n;assign CORE_PLL_RSTN=sys_rst_n;
 reset_sync ddr_rst(.clk(ui_clk),.async_reset(!sys_rst_n || !pll_locked || !core_pll_locked || !user_pll_locked),.reset(ddr_reset));
 reset_sync rst_ui(.clk(ui_clk),.async_reset(ddr_reset || !calibrated),.reset(reset_ui));
 reset_sync rst_pixel(.clk(pixel_clk),.async_reset(!sys_rst_n || !pll_locked || !core_pll_locked || !user_pll_locked || !calibrated),.reset(reset_pixel));
 reset_sync rst_byte(.clk(i_cam_ck_CLKOUT),.async_reset(reset_ui),.reset(reset_byte));
 assign cam_d0_RST=reset_byte;assign cam_d1_RST=reset_byte;assign cam_d2_RST=reset_byte;assign cam_d3_RST=reset_byte;
 wire cam_vs,cam_hs,cam_valid;wire[63:0] cam_pixels;wire[31:0] cam_debug;wire[5:0] cam_datatype;wire[3:0] cam_ppc;
 wire[5:0] cam_pixel_datatype;wire[15:0] cam_pixel_wordcount;
 wire cam_format_fault;
 wire csi_awvalid,csi_awready,csi_wvalid,csi_wready,csi_bvalid,csi_bready;
 csi_status_clear clear_status(.clk(core_clk),.reset(reset_ui),.vs(cam_vs),
  .awvalid(csi_awvalid),.awready(csi_awready),.wvalid(csi_wvalid),.wready(csi_wready),
  .bvalid(csi_bvalid),.bready(csi_bready));
 camera_format_guard format_guard(.byte_clk(i_cam_ck_CLKOUT),.byte_reset(reset_byte),.datatype(cam_datatype),
  .ui_clk(core_clk),.ui_reset(reset_ui),.fault(cam_format_fault));
 assign uart_tx=1'b1; // Image input is MIPI; inherited UART pad remains idle.
'''
 system=''' wire[15:0] paddr;wire psel,penable,pwrite,pready,pslverror,irq;
 wire[31:0] pwdata,prdata;wire scl_release,sda_release,sensor_reset_n;
 // V7 active-high module reset, not the bare sensor's XSHUTDN polarity.
 assign o_cam_rst_p=reset_ui || !sensor_reset_n;
 assign io_cam_scl_OUT=1'b0;assign io_cam_sda_OUT=1'b0;
 assign io_cam_scl_OE=!reset_ui && !scl_release;assign io_cam_sda_OE=!reset_ui && !sda_release;
 control_soc cpu(.io_systemClk(ui_clk),.io_asyncReset(reset_ui),.io_systemReset(soc_reset),
  .jtagCtrl_enable(1'b0),.jtagCtrl_tdi(1'b0),.jtagCtrl_capture(1'b0),.jtagCtrl_shift(1'b0),
  .jtagCtrl_update(1'b0),.jtagCtrl_reset(1'b1),.jtagCtrl_tdo(),.jtagCtrl_tck(1'b0),
  .userInterruptA(irq),.io_apbSlave_0_PADDR(paddr),.io_apbSlave_0_PENABLE(penable),
  .io_apbSlave_0_PRDATA(prdata),.io_apbSlave_0_PREADY(pready),.io_apbSlave_0_PSEL(psel),
  .io_apbSlave_0_PSLVERROR(pslverror),.io_apbSlave_0_PWDATA(pwdata),.io_apbSlave_0_PWRITE(pwrite));
 wire[29:0] awaddr,araddr;wire awvalid,awready,wvalid,wready,bvalid,bready,arvalid,arready,rvalid,rlast,rready;
 wire[127:0] wdata,rdata;wire[1:0] bresp,rresp;
 wire[23:0] rgb;wire hsync,vsync,de;
 video_system #(.WIDTH(PROC_WIDTH),.HEIGHT(PROC_HEIGHT)) system(.clk(ui_clk),.reset(reset_ui || soc_reset),
  .pixel_clk(pixel_clk),.pixel_reset(reset_pixel),.calibrated(calibrated),
  .paddr(paddr),.psel(psel),.penable(penable),.pwrite(pwrite),.pwdata(pwdata),.prdata(prdata),.pready(pready),.pslverror(pslverror),.irq(irq),
  .keys_n(style_keys_n),.scl_in(io_cam_scl_IN),.sda_in(io_cam_sda_IN),.scl_release(scl_release),.sda_release(sda_release),.sensor_reset_n(sensor_reset_n),
  .cam_vs(cam_vs),.cam_hs(cam_hs),.cam_valid(cam_valid),.cam_raw(cam_pixels[39:0]),
  .cam_error(cam_format_fault || |(cam_debug & 32'h00004475) || (cam_valid && (cam_ppc!=4 || cam_pixel_datatype!=6'h2b || cam_pixel_wordcount!=2400))),
  .awaddr(awaddr),.awvalid(awvalid),.awready(awready),.wdata(wdata),.wvalid(wvalid),.wready(wready),.bresp(bresp),.bvalid(bvalid),.bready(bready),
  .araddr(araddr),.arvalid(arvalid),.arready(arready),.rdata(rdata),.rresp(rresp),.rvalid(rvalid),.rlast(rlast),.rready(rready),
  .display_rgb(rgb),.hsync(hsync),.vsync(vsync),.de(de));
'''
 tail=base_top[base_top.index('tmds_efx display'):]
 tail=tail.replace('.app_sr_active                  (app_sr_active)', '.app_sr_active                  ()').replace('.app_ref_ack                    (app_ref_ack)', '.app_ref_ack                    ()').replace('.app_zq_ack                     (app_zq_ack)', '.app_zq_ack                     ()')
 (rtl/'ti60_camera_top.sv').write_text(header+reset+csi_instance+'\n'+system+tail,encoding='utf-8')
 # Start from the SIGNED DDR/HDMI/keys layout and add the FIVE factory RX
 # lanes + THREE factory camera GPIOs. No DSI transmitter is instantiated.
 peri=ET.parse(BASE/'build/vga/ti60_style.peri.xml');pt=peri.getroot();pt.set('name','ti60_camera')
 factory=ET.parse(REF/'ti60f225_oob.peri.xml').getroot()
 gpio=pt.find('{'+PN+'}gpio_info')
 for name in ('io_cam_scl','io_cam_sda','o_cam_rst_p'):
  node=factory.find('{'+PN+'}gpio_info/{'+PN+'}comp_gpio[@name="'+name+'"]')
  if node is None:raise RuntimeError('Missing factory camera GPIO '+name)
  node=copy.deepcopy(node)
  for child in node:
   if child.tag.endswith('input_config'):child.set('pull_option','none') # External module pullups only.
  index=next((i for i,n in enumerate(gpio) if not n.tag.endswith('comp_gpio')),len(gpio))
  gpio.insert(index,node)
 mipi=pt.find('{'+PN+'}mipi_dphy_info')
 for child in list(mipi):mipi.remove(child)
 for child in factory.find('{'+PN+'}mipi_dphy_info'):
  if child.get('ops_type')=='rx':mipi.append(copy.deepcopy(child))
 ET.register_namespace('efxpt',PN);peri.write(BUILD/'ti60_camera.peri.xml',encoding='utf-8',xml_declaration=True)
 from lxml import etree as LE
 schema=LE.XMLSchema(LE.parse('E:/software/efinity/pt/bin/schema/peri_design_db.xsd'));schema.assertValid(LE.parse(str(BUILD/'ti60_camera.peri.xml')))
 design=ET.parse(BASE/'build/vga/ti60_style.xml');tree=design.getroot();tree.set('name','ti60_camera')
 info=tree.find('{'+NS+'}design_info');info.find('{'+NS+'}top_module').set('name','ti60_camera_top')
 for node in list(info.findall('{'+NS+'}design_file')):info.remove(node)
 files=[*sorted(rtl.glob('*.sv')),WS/'common/rtl/style_line_ram.sv',*sorted(vendor.rglob('*.v')),*[p for p in sorted(vendor.glob('*.sv')) if p.name!='csi_rx_controller.sv'],BUILD/'ip/control_soc/control_soc.v']
 for i,p in enumerate(files,1):info.insert(i,ET.Element('{'+NS+'}design_file',name=p.as_posix(),version='default',library='default'))
 for node in tree.find('{'+NS+'}interface_info'):node.set('name','ti60_camera.peri.xml')
 for node in tree.find('{'+NS+'}constraint_info'):
  if node.tag.endswith('sdc_file'):node.set('name','ti60_camera.sdc')
 for node in list(tree.find('{'+NS+'}ip_info')):tree.find('{'+NS+'}ip_info').remove(node)
 ET.register_namespace('efx',NS);design.write(BUILD/'ti60_camera.xml',encoding='utf-8',xml_declaration=True)
 shutil.copyfile(vendor/'rtl/ddr3_controller/ddr3_parameter.vh',BUILD/'ddr3_parameter.vh')
 # $readmemb uses basenames in the generated netlist. Make the build cwd
 # self-contained and independently check all four little-endian byte lanes.
 boot_files=sorted((BUILD/'ip/control_soc').glob('EfxSapphireSoc.v_toplevel_system_ramA_logic_ram_symbol*.bin'))
 assert len(boot_files)==4,'Missing Sapphire firmware RAM byte lanes'
 lanes=[[int(x,2) for x in p.read_text().split()] for p in boot_files]
 image=bytes(lanes[i%4][i//4] for i in range((BUILD/'firmware.bin').stat().st_size))
 assert image==(BUILD/'firmware.bin').read_bytes(),'Generated CPU RAM does not contain current firmware'
 for p in boot_files:shutil.copyfile(p,BUILD/p.name)
 (BUILD/'ti60_camera.sdc').write_text('create_clock -name CLK_25M -period 40 [get_ports CLK_25M]\ncreate_clock -name CLK_27M -period 37.037037 [get_ports CLK_27M]\ncreate_clock -name i_cam_ck_CLKOUT -period 14.285714 [get_ports i_cam_ck_CLKOUT]\n',encoding='utf-8')
 manifest={'platform':'Ti60F225 I3 DemoBoard V4','sensor':'SC431HAI demo10 matching module confirmed by user','camera':[1920,1080],'process':[640,480],
  'preprocess':'2x2 Bayer block -> RGB565, center crop from 960x540','bayer':'BGGR initial; real chart verification required',
  'display':'1280x720p30, 74.25MHz, 3300x750, centered VGA + C/I/H overlay','cpu':'Sapphire 3.4.0 new minimal instance; existing 3.3.0 reference untouched',
  'source_banks':['0x00400000','0x00600000','0x00800000'],'style_banks':['0x00000000','0x00200000'],
  'sources':{str(p.relative_to(WS)):sha(p) for p in files},'reused':reused,'firmware_manifest':sha(BUILD/'firmware_manifest.json'),
  'boot_ram':{p.name:sha(p) for p in boot_files},'boot_ram_matches_firmware':True,
  'cpu_generated':{p.relative_to(BUILD).as_posix():sha(p) for p in sorted((BUILD/'ip/control_soc/source/hardware/netlist').glob('*')) if p.is_file()},
  'camera_ip_original':sha(REF/'rtl/csi_rx_controller.sv'),'csi_attribute_patch':'none; complete V7 file byte-identical',
  'csi_active':{'version':'5.15','pack_type':1,'pixel_sideband':True,'frame_mode':'GENERIC','sha256':sha(generated),'settings_sha256':sha(generated.parent/'settings.json')},
  'interface':sha(BUILD/'ti60_camera.peri.xml'),'status':'candidate; no hardware access'}
 (BUILD/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
 print('Prepared camera_vga:',len(files),'files, 5 DDR frame banks, APB control, runtime CNN, V7 four-lane CSI')
if __name__=='__main__':main()
