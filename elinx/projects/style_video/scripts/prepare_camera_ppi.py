"""Independent D-PHY/atomic-FIFO camera build; preserves camera_vga baseline."""
from pathlib import Path
import hashlib,json,re,shutil,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];WS=ROOT.parents[2]
OLD=ROOT/'build/camera_vga';BUILD=ROOT/'build/camera_ppi'
NS='http://www.efinixinc.com/enf_proj'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 BUILD.mkdir(exist_ok=True)
 original=(ROOT/'rtl/ti60_camera_top.sv').read_text()
 top=original.replace('module ti60_camera_top #','module ti60_camera_ppi_top #')
 begin=top.index(' wire cam_vs,cam_hs,cam_valid;')
 end=top.index(' wire[15:0] paddr;')
 inst=original[original.index('camera_csi inst_efx_csi2_rx'):original.index('              .axi_clk(core_clk)')]
 inst=inst.replace('camera_csi inst_efx_csi2_rx','camera_dphy inst_camera_dphy')
 inst=re.sub(r'^\s*\.(?:reset_pixel_n|clk_pixel)\s*\([^\n]*\n','',inst,flags=re.M)
 new=''' wire cam_vs,cam_hs,cam_valid;
 wire[63:0] cam_pixels;wire[31:0] ppi_data;
 wire[3:0] ppi_valid,ppi_sync,ppi_sot_error,dphy_control_error,dphy_escape_error;
 wire bridge_error,bridge_transport_fault;
 assign uart_tx=1'b1;
'''+inst+'''
 .RxDataHS_0(ppi_data[7:0]),.RxDataHS_1(ppi_data[15:8]),.RxDataHS_2(ppi_data[23:16]),.RxDataHS_3(ppi_data[31:24]),
 .RxDataHS_4(),.RxDataHS_5(),.RxDataHS_6(),.RxDataHS_7(),.RxValidHS(ppi_valid),.RxSyncHS(ppi_sync),
 .RxErrSotSyncHS(ppi_sot_error),.RxErrControl(dphy_control_error),.RxErrEsc(dphy_escape_error),
 .RxActiveHS(),.RxStopState(),.RxUlpsEsc(),.RxUlpsActiveNot(),.RxLPDTEsc(),.RxValidEsc(),
 .RxDataEsc_0(),.RxDataEsc_1(),.RxDataEsc_2(),.RxDataEsc_3(),.RxDataEsc_4(),.RxDataEsc_5(),.RxDataEsc_6(),.RxDataEsc_7(),
 .RxSkewCalHS(),.RxUlpsClkNot(),.RxUlpsActiveClkNot());
 assign cam_pixels[63:40]=24'd0;
 csi_ppi_bridge bridge(.byte_clk(i_cam_ck_CLKOUT),.byte_reset(reset_byte),.ui_clk(core_clk),.ui_reset(reset_ui),
  .ppi_data(ppi_data),.ppi_valid(ppi_valid),.ppi_sync(ppi_sync),.ppi_sot_error(ppi_sot_error),
  .control_error(|dphy_control_error || |dphy_escape_error),
  .vs(cam_vs),.hs(cam_hs),.valid(cam_valid),.raw(cam_pixels[39:0]),.packet_error(bridge_error),
  .transport_fault(bridge_transport_fault),.good_lines(),.error_packets());
'''
 top=top[:begin]+new+top[end:]
 top=re.sub(r'^\s*\.cam_error.*$', '  .cam_error(bridge_error),',top,flags=re.M)
 assert 'cam_format_fault' not in top and 'cam_debug' not in top
 target=ROOT/'rtl/ti60_camera_ppi_top.sv';target.write_text(top)
 shutil.copytree(OLD/'ip/control_soc',BUILD/'ip/control_soc',dirs_exist_ok=True)
 for path in OLD.glob('EfxSapphireSoc*.bin'):shutil.copy2(path,BUILD/path.name)
 for name in ('ddr3_parameter.vh','firmware.bin','firmware_manifest.json','firmware_test.json'):
  shutil.copy2(OLD/name,BUILD/name)
 dphy=ROOT/'build/dphy_bridge/ip/camera_dphy/camera_dphy.sv'
 settings=dphy.parent/'settings.json'
 shutil.copyfile(dphy,ROOT/'vendor/camera_dphy.sv')
 tree=ET.parse(OLD/'ti60_camera.xml');root=tree.getroot();info=root.find('{'+NS+'}design_info')
 for node in root.iter('{'+NS+'}param'):
  if node.get('name')=='max_threads':node.set('value','4')
 info.find('{'+NS+'}top_module').set('name','ti60_camera_ppi_top')
 paths=[]
 for node in info.findall('{'+NS+'}design_file'):
  path=Path(node.get('name'))
  if path.name=='camera_csi.sv':path=ROOT/'vendor/camera_dphy.sv'
  if path.name=='ti60_camera_top.sv':path=target
  if path==OLD/'ip/control_soc/control_soc.v':path=BUILD/'ip/control_soc/control_soc.v'
  node.set('name',path.as_posix());paths.append(path)
 bridge=ROOT/'rtl/csi_ppi_bridge.sv'
 if bridge not in paths:
  info.insert(1,ET.Element('{'+NS+'}design_file',name=bridge.as_posix(),version='default',library='default'));paths.append(bridge)
 ET.register_namespace('efx',NS);tree.write(BUILD/'ti60_camera.xml',encoding='utf-8',xml_declaration=True)
 peri=ET.parse(OLD/'ti60_camera.peri.xml')
 pn='http://www.efinixinc.com/peri_design_db'
 for i,pin in enumerate(['GPIOL_07','GPIOR_22','GPIOR_21','GPIOL_03']):
  peri.find('.//{'+pn+'}comp_gpio[@name="style_keys_n['+str(i)+']"]').set('gpio_def',pin)
 ET.register_namespace('efxpt',pn);peri.write(BUILD/'ti60_camera.peri.xml',encoding='utf-8',xml_declaration=True)
 (BUILD/'ti60_camera.sdc').write_text('create_clock -name CLK_25M -period 40 [get_ports CLK_25M]\ncreate_clock -name CLK_27M -period 37.037037 [get_ports CLK_27M]\ncreate_clock -name i_cam_ck_CLKOUT -period 14.285714 [get_ports i_cam_ck_CLKOUT]\n')
 baseline=json.loads((OLD/'manifest.json').read_text())
 result={k:v for k,v in baseline.items() if k not in ('sources','csi_active','cpu_generated','interface','status')}
 result.update({'sources':{str(p.relative_to(WS)):sha(p) for p in paths},'interface':sha(BUILD/'ti60_camera.peri.xml'),
  'dphy_active':{'version':'5.8','sha256':sha(dphy),'settings_sha256':sha(settings)},
  'transport':'RAW PPI44 atomic async FIFO; all CSI header/WC/CRC/RAW10 in100MHz UI',
  'packet_scope':'VC0 RAW10, one CSI packet per HS transmission; reject ECC errors; CRC checked',
  'cpu_generated':{p.relative_to(BUILD).as_posix():sha(p) for p in sorted((BUILD/'ip/control_soc/source/hardware/netlist').glob('*')) if p.is_file()},
  'baseline_manifest_sha256':sha(OLD/'manifest.json'),'status':'candidate; no board access'})
 (BUILD/'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print('Prepared independent camera_ppi',len(paths),'sources')
if __name__=='__main__':main()
