"""Bounded idle SoT recovery with unchanged electrical and strict frame checks."""
from pathlib import Path
import hashlib,importlib.util,json,re,sys
ROOT=Path(__file__).resolve().parents[2]
WS=ROOT.parents[2]
BASE=ROOT/'build/camera_packet_trace60'
BUILD=ROOT/'build/camera_sot_recover60'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))

def parent_audit():
 saved=sys.modules.get('contract');folder=ROOT/'scripts/packet_trace'
 spec=importlib.util.spec_from_file_location('packet_trace_parent_contract',folder/'contract.py')
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 sys.modules['contract']=module
 try:
  spec=importlib.util.spec_from_file_location('packet_trace_parent_signoff',folder/'signoff.py')
  previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
  current=previous.audit(True)
  assert json.loads(json.dumps(current))==read(BASE/'signoff.json'),'Signed CAM2 parent changed'
  return current
 finally:
  if saved is None:sys.modules.pop('contract',None)
  else:sys.modules['contract']=saved

def top_text():
 source=(BASE/'rtl/ti60_camera_ppi_top.sv').read_text(encoding='utf-8')
 source=source.replace('wire[383:0] packet_trace;','wire[383:0] packet_trace;\n wire[31:0] soft_sot_records;')
 source=source.replace('csi_ppi_bridge_trace bridge(', 'csi_ppi_bridge_recover bridge(')
 source=source.replace('.trace_fields(packet_trace));', '.trace_fields(packet_trace),.soft_sot_records(soft_sot_records));')
 old="wire[31:0] diag_flags={17'd0,bridge_transport_fault"
 assert source.count(old)==1
 source=source.replace(old,"wire[31:0] diag_flags={(soft_sot_records>32'hffff ? 16'hffff : soft_sot_records[15:0]),\n  (|soft_sot_records),bridge_transport_fault")
 return source

def audit_contract():
 old=parent_audit();m=read(BUILD/'manifest.json')
 for name,value in m['parent_packet_trace60'].items():assert sha(BASE/name)==value,name
 for name in ['ti60_camera.peri.xml','firmware_manifest.json','firmware.bin',*m['boot_ram']]:
  assert (BUILD/name).read_bytes()==(BASE/name).read_bytes(),name
 assert (BUILD/'rtl/ti60_camera_ppi_top.sv').read_text(encoding='utf-8')==top_text()
 for name,value in m['sot_recovery_tools'].items():assert sha(ROOT/name)==value,name
 assert m['process']==[640,480] and m['camera']==[1920,1080]
 assert m['display']==read(BASE/'manifest.json')['display']
 bridge=(ROOT/'rtl/sot_recovery/csi_ppi_bridge_recover.sv').read_text(encoding='utf-8')
 restored=bridge.replace('module csi_ppi_bridge_recover #(', 'module csi_ppi_bridge_trace #(',1)
 restored,ports=re.subn(r'// RECOVERY_PORT_BEGIN\n.*?// RECOVERY_PORT_END\n','',restored,count=1,flags=re.S)
 restored,classifiers=re.subn(r'// RECOVERY_CLASSIFIER_BEGIN\n.*?// RECOVERY_CLASSIFIER_END\n','',restored,count=1,flags=re.S)
 assert ports==classifiers==1
 restored=restored.replace(' output wire[383:0] trace_fields\n);',' output wire[383:0] trace_fields);')
 restored=restored.replace('control_error || hard_sot_error || lane_overflow || transport_fault',
  'control_error || in_error || lane_overflow || transport_fault')
 restored=restored.replace('else if(hard_sot_error)trace_reason=2;', 'else if(in_error)trace_reason=2;')
 assert restored==(ROOT/'rtl/packet_trace/csi_ppi_bridge_trace.sv').read_text(encoding='utf-8'),'Unexpected parser change'
 for text in ['state==WAIT_SOT','sync_seen==0','hard_sot_error',
              'word_data[29:24]!=header_ecc(word_data[23:0])',
              'word_data[15:0]!=crc_value || raw_bytes!=0',
              '!vs || line_count!=RAW_HEIGHT','frame_ticks==FRAME_TIMEOUT-1']:
  assert text in bridge,text
 simulations={}
 for name in ['sim/sot_recovery_unit/verification.json','sim/sot_idle_repro/verification.json',
              'sim/top_safety_sot_recovery/verification.json']:
  item=read(ROOT/name);assert item['result']=='PASS',name
  for path,value in item.get('sources_sha256',{}).items():assert sha(Path(path))==value,path
  for path,value in item.get('logs_sha256',{}).items():assert sha(Path(path))==value,path
  simulations[name]={'receipt_sha256':sha(ROOT/name),'scope':item['scope']}
 return {'result':'PASS','parent_packet_trace_bit_sha256':old['bitstream_sha256'],
         'telemetry':'CAM2,24 fields,223 bytes,115200; flags bit15 soft seen,31:16 saturating soft record count',
         'boundary':'SoT only at WAIT, no partial lane sync, empty lane queues, no valid/sync; active/partial/queued SoT remains hard',
         'frame_checks':'ECC/CRC/WC/exact height/frame-end/timeout/downstream exact pixels/final DDR B retained',
         'new_cross_clock_payloads':0,'sensor_firmware_models_peri_and_hdmi_unchanged':True,
         'simulations':simulations,'scope':'Bounded protocol recovery and digital CAD; not guaranteed physical fault repair or arbitrary multi-fault proof',
         'board_programmed':False}
