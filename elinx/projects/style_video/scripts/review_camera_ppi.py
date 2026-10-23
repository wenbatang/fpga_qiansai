"""Independent re-review of a frozen release, without rebuilding/programming it."""
from pathlib import Path
import csv,hashlib,importlib.util,json,re,shutil,tempfile,xml.etree.ElementTree as ET
from camera_ppi_signoff import audit
from camera_ppi_constraints import assemble
ROOT=Path(__file__).resolve().parents[1];WS=ROOT.parents[2]
BUILD=ROOT/'build/camera_ppi';OUT=ROOT/'build/electrical_review_20261019_correct_schematic'
PN='http://www.efinixinc.com/peri_design_db'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 OUT.mkdir(exist_ok=True)
 # Compare to the existing released hashes, rather than silently replacing
 # them with whatever files happen to exist at review time.
 signed=json.loads((BUILD/'signoff.json').read_text(encoding='utf-8'))
 assert signed['result']=='PASS'
 assert sha(BUILD/'outflow/ti60_camera.bit')==signed['bitstream_sha256'],'Released bit changed'
 for name,value in signed['configuration_sha256'].items():assert sha(BUILD/name)==value,'Released input/report changed: '+name
 for name,value in signed['simulation_receipts_sha256'].items():assert sha(ROOT/name)==value,'Released simulation receipt changed'
 current=audit()
 assert current['bitstream_sha256']==signed['bitstream_sha256']
 # Rerun independent schematic-transcribed 66-pin audit; do not merely read
 # the previous cached JSON. Then add the 13 camera/control physical pads.
 spec=importlib.util.spec_from_file_location('tile_board_review',ROOT.parent/'uart_style_tiles/scripts/board_audit.py')
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 base=module.audit('vga')
 expected={x['Signal Name']:(x['Pin Number'],x['Direction'],x['Bank'],x['I/O Bank Voltage']) for x in base['pins']}
 expected.update({'io_cam_scl':('D12','Bidirectional','TR','3.3 V'),
                  'io_cam_sda':('B14','Bidirectional','TR','3.3 V'),
                  'o_cam_rst_p':('C12','Output','TR','3.3 V')})
 for name,pp,pn,bank in [('ck','E8','D8','2B'),('d0','B8','A8','2A'),('d1','C8','C9','2B'),('d2','B7','A7','2A'),('d3','B9','A9','2B')]:
  for leg,pin in [('P',pp),('N',pn)]:expected[f'cam_{name}.{leg}']=(pin,'Input',bank,'1.2 V')
 rows=list(csv.DictReader(s for s in (BUILD/'outflow/ti60_camera.pinout.csv').read_text().splitlines() if s and not s.startswith('#')))
 pins={x['Signal Name']:x for x in rows if x['Signal Name']}
 assert set(pins)==set(expected) and len(pins)==len({x['Pin Number'] for x in pins.values()})==79
 for name,values in expected.items():
  assert tuple(pins[name][k] for k in ('Pin Number','Direction','Bank','I/O Bank Voltage'))==values,name
 assert not [x for x in rows if not x['Signal Name'] and x['Direction'] in ('Output','Bidirectional') and 'User IO' in x['Function']]
 tree=ET.parse(BUILD/'ti60_camera.peri.xml')
 bank_expected={'1A':'1.8','1B':'1.8','2A':'1.2','2B':'1.2','3A':'1.8','3B':'1.5','4A':'1.5','4B':'1.5','TL':'3.3','TR':'3.3','BL':'3.3','BR':'3.3'}
 banks=tree.findall('.//{'+PN+'}iobank')
 assert {x.get('name'):x.get('iostd').split()[0] for x in banks}==bank_expected
 assert all(x.get('is_dyn_voltage')=='false' for x in banks)
 assert tree.find('.//{'+PN+'}global_unused_config').get('state')=='input with weak pullup'
 for mipi in tree.findall('.//{'+PN+'}mipi_dphy'):
  assert mipi.get('ops_type')=='rx'
  info=mipi.find('{'+PN+'}rx_info')
  assert info.get('is_reversible')=='false'
  assert info.get('is_fifo')==('false' if mipi.get('name')=='cam_ck' else 'true')
 for lvds in tree.findall('.//{'+PN+'}lvds'):
  assert lvds.get('ops_type')=='tx'
  info=lvds.find('{'+PN+'}adv_ltx_info')
  assert info.get('is_serial')=='true' and info.get('serial_width')=='10' and info.get('is_half_rate')=='true'
 top=(ROOT/'rtl/ti60_camera_ppi_top.sv').read_text()
 ddr_signals=('ddr_ck_hi','ddr_ck_lo','ddr_reset_n','ddr_cke','ddr_cs_n','ddr_ras_n','ddr_cas_n','ddr_we_n','ddr_addr','ddr_ba',
  'ddr_dqs_oe','ddr_dqs_oe_n','ddr_dq_oe','ddr_dqs_in_hi','ddr_dqs_in_lo','ddr_dq_in_hi','ddr_dq_in_lo',
  'ddr_dqs_out_hi','ddr_dqs_out_lo','ddr_dq_out_hi','ddr_dq_out_lo','ddr_dm_hi','ddr_dm_lo','ddr_odt')
 for signal in ddr_signals:
  assert re.search(r'\.'+signal+r'\s*\('+signal+r'\s*\)',top),'Lost DDR data/OE binding: '+signal
  assert not re.search(r'assign\s+'+signal+r'\s*=',top),'DDR output override: '+signal
 # Generate the exact intended constraints in a disposable local directory.
 # The production SDC/map/proof are read-only throughout this operation.
 with tempfile.TemporaryDirectory(dir=OUT) as folder:
  folder=Path(folder);(folder/'outflow').mkdir()
  for name in ('outflow/ti60_camera.map.v','outflow/ti60_camera.pt.sdc','dphy_cdc_proof.json'):
   shutil.copyfile(BUILD/name,folder/name)
  assemble(folder)
  assert (folder/'ti60_camera.sdc').read_bytes()==(BUILD/'ti60_camera.sdc').read_bytes(),'Routed constraints differ from exact whitelist'
  assert json.loads((folder/'cdc_constraints.json').read_text())==json.loads((BUILD/'cdc_constraints.json').read_text())
 safety=json.loads((ROOT/'sim/top_safety/verification.json').read_text())
 assert safety['result']=='PASS'
 for name,value in safety['sources_sha256'].items():assert sha(Path(name))==value,'Stale top safety test'
 fault_path=ROOT/'sim/camera_fault_shutdown/verification.json'
 faults=json.loads(fault_path.read_text())
 assert faults['result']=='PASS' and len(faults['cases'])==8
 for case in faults['cases']:
  assert case['result']=='PASS' and not case['capture_enabled'] and case['module_reset_asserted'] and case['i2c_released']
 for name,value in faults['sources_sha256'].items():assert sha(Path(name))==value,'Stale camera shutdown test'
 # Exhaustive capture addresses at production geometry and all raw banks.
 for bank in range(3):
  addresses=[0x400000+bank*0x200000+i*16 for i in range(640*480//8)]
  assert len(set(addresses))==38400 and addresses[-1]+16<=0x400000+(bank+1)*0x200000
  assert all(a%16==0 and (a&4095)<=4080 for a in addresses)
 result={'result':'PASS_SOFTWARE_REVIEW','bitstream_sha256':signed['bitstream_sha256'],
  'active_pins':79,'bank_voltages':bank_expected,'unused_gpio_drivers':0,
  'ddr_oe_data_bindings_checked':len(ddr_signals),'constraints_match_exact_regeneration':True,
  'setup_min_ns':current['setup_min_ns'],'hold_min_ns':current['hold_min_ns'],
  'schematic_sha256':sha(WS/'elinx/elinxdemo/Ti60F225_DemoBoard_v4/TI60F225I3-V4_SCH-20261012（原理图）.pdf'),
  'top_safety_receipt_sha256':sha(ROOT/'sim/top_safety/verification.json'),
  'firmware_fault_shutdown_receipt_sha256':sha(fault_path),'firmware_fault_cases_passed':8,
  'user_confirmed_physical_configuration':{'camera_connector':'J4','J2':'2-3','J3':'2-3','source':'user reply 2026-10-16; not instrument measurement'},
  'actual_rails_current_temperature_measured':False,'end_to_end_board_verified':False,
  'power_on_flash_image_known':False,'power_on_flash_user_statement':'Unknown or never programmed; user reply 2026-10-16',
  'warnings':['Inherited HDMI lvds_rule_tx_distance at GPIOR_P_09; physical signal integrity unmeasured'],
  'camera_packet_mode':'Sensor manual p14 figs1-7/1-8 depict one packet per HS; actual configured stream not measured',
  'scope':'Frozen bit / schematic / port direction / source / STA / protection simulation; no board access'}
 (OUT/'review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
