"""Fail-closed audit of current camera candidate. Never accesses a board."""
from pathlib import Path
import csv,hashlib,json,re,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];WS=ROOT.parents[2];BUILD=ROOT/'build/camera_vga'
PN='http://www.efinixinc.com/peri_design_db'
REF=WS/'elinx/elinxdemo/Ti60F225_DemoBoard_v4/10_Ti60f225_sc431hai2hdmi_demo/Ti60f225_sc431hai2hdmi_v7/Ti60f225_sc431hai2hdmi_v7'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def electrical():
 rows=list(csv.DictReader(x for x in (BUILD/'outflow/ti60_camera.pinout.csv').read_text().splitlines() if x and not x.startswith('#')))
 pins={x['Signal Name']:x for x in rows if x['Signal Name']}
 # The baseline was independently transcribed against V4 schematic pages
 # 3/7/8/9/10. Compare every field of all 66 existing physical signals.
 base=json.loads((ROOT.parent/'uart_style_tiles/build/electrical_review/vga_board_audit.json').read_text())
 for old in base['pins']:
  assert pins[old['Signal Name']]==old,'Inherited electrical binding changed: '+old['Signal Name']
 extra={'io_cam_scl':('D12','Bidirectional','TR','3.3 V'),
  'io_cam_sda':('B14','Bidirectional','TR','3.3 V'),'o_cam_rst_p':('C12','Output','TR','3.3 V')}
 for name,pp,pn,bank in [('ck','E8','D8','2B'),('d0','B8','A8','2A'),('d1','C8','C9','2B'),('d2','B7','A7','2A'),('d3','B9','A9','2B')]:
  for leg,pin in [('P',pp),('N',pn)]:extra['cam_'+name+'.'+leg]=(pin,'Input',bank,'1.2 V')
 for name,values in extra.items():
  assert tuple(pins[name][k] for k in ('Pin Number','Direction','Bank','I/O Bank Voltage'))==values,name
 assert set(pins)=={x['Signal Name'] for x in base['pins']}|set(extra)
 assert len(pins)==len({p['Pin Number'] for p in pins.values()})==79
 assert not [p for p in rows if not p['Signal Name'] and p['Direction'] in ('Output','Bidirectional') and p['Function']=='User IO']
 orig=ET.parse(REF/'ti60f225_oob.peri.xml');new=ET.parse(BUILD/'ti60_camera.peri.xml')
 for tag in ('lvds','mipi_dphy'):
  for node in new.findall('.//{'+PN+'}'+tag):
   before=orig.find('.//{'+PN+'}'+tag+'[@name="'+node.get('name')+'"]')
   assert before is not None and ET.tostring(node)==ET.tostring(before),tag
 assert len(new.findall('.//{'+PN+'}mipi_dphy'))==5
 assert (ROOT/'vendor/csi_rx_controller.sv').read_bytes()==(REF/'rtl/csi_rx_controller.sv').read_bytes()
 active=json.loads((BUILD/'manifest.json').read_text())['csi_active']
 assert active['version']=='5.15' and active['pack_type']==1 and active['pixel_sideband']
 assert sha(ROOT/'vendor/camera_csi.sv')==active['sha256'],'Current CSI configuration changed'
 assert (ROOT/'vendor/rtl/ddr3_controller/ddr3_top.v').read_bytes()==(REF/'rtl/ddr3_controller/ddr3_top.v').read_bytes()
 assert (BUILD/'ddr3_parameter.vh').read_bytes()==(REF/'rtl/ddr3_controller/ddr3_parameter.vh').read_bytes()
 top=(ROOT/'rtl/ti60_camera_top.sv').read_text()
 for fragment in ["assign io_cam_scl_OUT=1'b0", "assign io_cam_sda_OUT=1'b0",'assign o_cam_rst_p=reset_ui || !sensor_reset_n',
  '.axi_clk(core_clk)','.axi_reset_n(!reset_ui)','.async_reset(!sys_rst_n || !pll_locked || !core_pll_locked || !user_pll_locked)',
  'assign cam_d0_RST=reset_byte']:
  assert fragment in top,'Electrical/reset protection missing: '+fragment
 return {'active_pins':79,'pins':list(pins.values()),'unused_gpio_drivers':0,'physical_rails_and_jumpers_measured':False}
def audit(require_bit=True):
 manifest=json.loads((BUILD/'manifest.json').read_text())
 for name,value in manifest['sources'].items():assert sha(WS/name)==value,'Stale source: '+name
 for name,value in manifest['cpu_generated'].items():assert sha(BUILD/name)==value,'Stale CPU netlist: '+name
 for name,value in manifest['boot_ram'].items():assert sha(BUILD/name)==value,'Stale boot RAM: '+name
 assert sha(BUILD/'firmware_manifest.json')==manifest['firmware_manifest']
 firmware=json.loads((BUILD/'firmware_manifest.json').read_text())
 for name,value in firmware['files'].items():assert sha(WS/name)==value,'Stale firmware: '+name
 for model in firmware['models']:
  assert sha(WS/'pycode/runs/distinct_student_v1'/model['style']/'model.pt')==model['checkpoint_sha256']
 timing_path=BUILD/'outflow/ti60_camera.timing.rpt'
 assert timing_path.stat().st_mtime_ns>(BUILD/'manifest.json').stat().st_mtime_ns,'Stale timing report'
 report=timing_path.read_text()
 required={'core_clk':10.,'hdmi_tx_slow_clk':13.468,'hdmi_tx_fast_clk':2.694,'sdram_clk':2.5,'rx_cal_clk':2.5,'tx_cal_clk':2.5,'tx_cal_clk_90edge':2.5,'i_cam_ck_CLKOUT':14.286}
 for clock,period in required.items():assert re.search(r'^\s*'+clock+r'\s+'+f'{period:.3f}'+r'\s',report,re.M),'Missing clock: '+clock
 summary=report.split('---------- 2. Clock Relationship Summary (begin) ----------')[1].split('---------- Clock Relationship Summary (end)')[0]
 a,b=summary.split('Hold (Min) Clock Relationship')
 def rows(t):return [(m[1],m[2],float(m[3]),float(m[4])) for m in re.finditer(r'^\s*(\S+)\s+(\S+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+\(R-R\)',t,re.M)]
 setup,hold=rows(a),rows(b)
 assert len(setup)>=22 and len(hold)>=22,'Incomplete timing relationship report'
 assert min(x[3] for x in setup+hold)>=0,'Negative setup/hold slack'
 place=(BUILD/'outflow/ti60_camera.place.out').read_text()
 assert not re.search(r'WARNING.*\[SDC|Unable to run|no vaild startpoints|Failed to run',place),'Ignored timing constraints'
 cdc=json.loads((BUILD/'cdc_constraints.json').read_text())
 assert len(cdc['gray_paths'])==116 and len(cdc['csi_gray_clock_bounds'])==22
 assert len(cdc['bundle_paths'])==14 and len(cdc['scalar_first_stages'])==17
 board=electrical()
 resources={}
 text=(BUILD/'outflow/ti60_camera.place.rpt').read_text()
 for label in ('Memory Blocks','DSP Blocks','XLRs'):
  m=re.search(r'^'+label+r': (\d+) / (\d+)',text,re.M);assert m,label
  resources[label]=[int(m[1]),int(m[2])];assert int(m[1])<=int(m[2])
 tests=['camera','format','csi_status','fps','control','pool','capture_ddr','stream']
 for name in tests:assert 'PASS' in (ROOT/'build/sim'/(name+'_run.log')).read_text()
 assert json.loads((BUILD/'firmware_test.json').read_text())['tests'][0]['result']=='PASS'
 assert 'PASS strip engine' in (ROOT/'sim/runtime/run.log').read_text()
 for receipt in ['sim/sapphire/verification.json','sim/csi_vendor/verification.json','sim/csi_full_480/verification.json']:
  test=json.loads((ROOT/receipt).read_text())
  assert test['result']=='PASS','Missing licensed integration test '+receipt
  for path,expected in test.get('sources_sha256',{}).items():assert sha(Path(path))==expected,'Stale integration test: '+path
 bit=BUILD/'outflow/ti60_camera.bit'
 if require_bit:assert bit.exists() and bit.stat().st_mtime_ns>timing_path.stat().st_mtime_ns,'Missing current bitstream'
 return {'scope':'CAD and behavioral validation only; no programming or real camera measurement','resources':resources,
  'setup_min_ns':min(x[3] for x in setup),'hold_min_ns':min(x[3] for x in hold),'setup':setup,'hold':hold,
  'source_manifest_sha256':sha(BUILD/'manifest.json'),'electrical':board,
  'configuration_sha256':{n:sha(BUILD/n) for n in ('ti60_camera.xml','ti60_camera.peri.xml','ti60_camera.sdc','cdc_constraints.json')},
  'bitstream_sha256':sha(bit) if require_bit else None,
  'not_measured':['physical MIPI bank rails/jumpers','camera Bayer/FPS/brightness','real DDR/CNN/HDMI concurrency and FPS','real Sapphire execution and interrupts']}
if __name__=='__main__':
 result=audit();(BUILD/'signoff.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print('PASS camera candidate CAD audit',result['resources'],result['setup_min_ns'],result['hold_min_ns'],result['bitstream_sha256'])
