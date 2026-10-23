"""Independent enlarged preview. No sensor/PHY/voltage/model/firmware edits."""
from pathlib import Path
import hashlib,importlib.util,json,sys
ROOT=Path(__file__).resolve().parents[2];WS=ROOT.parents[2]
BASE=ROOT/'build/camera_sot_recover60';BUILD=ROOT/'build/camera_view60'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def parent_audit():
 saved=sys.modules.get('contract');folder=ROOT/'scripts/sot_recovery'
 spec=importlib.util.spec_from_file_location('sot_parent_contract',folder/'contract.py')
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);sys.modules['contract']=module
 try:
  spec=importlib.util.spec_from_file_location('sot_parent_signoff',folder/'signoff.py')
  previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
  current=previous.audit(True)
  assert json.loads(json.dumps(current))==read(BASE/'signoff.json'),'Signed parent changed'
  return current
 finally:
  if saved is None:sys.modules.pop('contract',None)
  else:sys.modules['contract']=saved
def top_text():
 text=(BASE/'rtl/ti60_camera_ppi_top.sv').read_text(encoding='utf-8')
 assert text.count('video_system_debug #(')==1
 text=text.replace('video_system_debug #(', 'video_system_view #(',1)
 text=text.replace('wire[383:0] packet_trace;', 'wire[383:0] packet_trace;\n wire[287:0] view_fields;')
 text=text.replace('.diag_status(diag_status));','.diag_status(diag_status),.view_fields(view_fields));',1)
 text=text.replace('camera_trace_uart diagnostics(', 'camera_view_uart diagnostics(',1)
 text=text.replace('diag_cycles,packet_trace}),.tx(uart_tx));','diag_cycles,packet_trace,view_fields}),.tx(uart_tx));',1)
 return text
def audit_contract():
 old=parent_audit();m=read(BUILD/'manifest.json')
 for name,value in m['parent_sot_recover60'].items():assert sha(BASE/name)==value,name
 for name,value in m['view_tools'].items():assert sha(ROOT/name)==value,name
 for name in ['ti60_camera.peri.xml','firmware_manifest.json','firmware.bin',*m['boot_ram']]:
  assert (BUILD/name).read_bytes()==(BASE/name).read_bytes(),name
 assert (BUILD/'rtl/ti60_camera_ppi_top.sv').read_text(encoding='utf-8')==top_text()
 assert m['camera']==[1920,1080] and m['process']==[640,480]
 assert m['display'].startswith('1280x720p60, 74.25MHz, 1650x750; 640x480 -> 960x720')
 sims={}
 for name in ['raster','keys_stats','runtime','uart','system','top_safety','reader']:
  path=ROOT/f'sim/view/{name}/verification.json';item=read(path)
  assert item['result']=='PASS',name
  for p,value in item.get('sources_sha256',{}).items():assert sha(Path(p))==value,p
  for p,value in item.get('logs_sha256',{}).items():assert sha(Path(p))==value,p
  sims[str(path.relative_to(ROOT))]={'receipt_sha256':sha(path),'scope':item['scope']}
 return {'result':'PASS','parent_bit_sha256':old['bitstream_sha256'],
  'source_format':'640x480 RGB565, source count and expanded 8-bit RGB sums; sampled before output-bank copy',
  'display':'960x720 nearest, centered in standard 720p60, synchronous line cache, exactly 307200 FIFO reads',
  'preview':'raw mode locked once per whole job; same source ownership/final DDR B/vblank commit',
  'fps':'Ixx counts completed neural jobs only; raw copies excluded',
  'diagnostics':'CAM3,33 fields,304 bytes,115200; first24 CAM2-compatible,append source/output stats/mode',
  'new_cross_clock_payloads':0,'firmware_sensor_phy_models_and_peri_unchanged':True,
  'simulations':sims,'board_programmed':False,
  'scope':'Diagnostic viewer; actual brightness, color/Bayer and style problem still need raw-vs-CNN board comparison'}
