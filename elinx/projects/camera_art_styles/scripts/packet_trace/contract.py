"""Detailed packet observer; keep all camera_debug60 acceptance decisions."""
from pathlib import Path
import hashlib,importlib.util,json,re,sys
ROOT=Path(__file__).resolve().parents[2]
WS=ROOT.parents[2]
BASE=ROOT/'build/camera_debug60'
BUILD=ROOT/'build/camera_packet_trace60'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))

def parent_audit():
 saved=sys.modules.get('contract')
 folder=ROOT/'scripts/diagnostics'
 spec=importlib.util.spec_from_file_location('camera_debug_parent_contract',folder/'contract.py')
 mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 sys.modules['contract']=mod
 try:
  spec=importlib.util.spec_from_file_location('camera_debug_parent_signoff',folder/'signoff.py')
  audit_mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit_mod)
  current=audit_mod.audit(True)
  assert json.loads(json.dumps(current))==read(BASE/'signoff.json'),'Signed diagnostic parent changed'
  return current
 finally:
  if saved is None:sys.modules.pop('contract',None)
  else:sys.modules['contract']=saved

def top_text():
 source=(BASE/'rtl/ti60_camera_ppi_top.sv').read_text(encoding='utf-8')
 source=source.replace('wire[31:0] diag_lines,diag_packets,diag_events,diag_header;',
  'wire[31:0] diag_lines,diag_packets,diag_events,diag_header;\n wire[383:0] packet_trace;')
 source=source.replace('csi_ppi_bridge_debug bridge(', 'csi_ppi_bridge_trace bridge(')
 source=source.replace('.debug_events(diag_events),.debug_header(diag_header));',
  '.debug_events(diag_events),.debug_header(diag_header),.trace_fields(packet_trace));')
 source=source.replace('camera_diag_uart diagnostics(', 'camera_trace_uart diagnostics(')
 source=source.replace('diag_captured,diag_inferred,diag_capture_errors,diag_raw_groups,diag_frames,diag_cycles}),.tx(uart_tx));',
  'diag_captured,diag_inferred,diag_capture_errors,diag_raw_groups,diag_frames,diag_cycles,packet_trace}),.tx(uart_tx));')
 return source

def audit_contract():
 parent=parent_audit();m=read(BUILD/'manifest.json')
 for name,value in m['parent_camera_debug60'].items():assert sha(BASE/name)==value,name
 for name in ['ti60_camera.peri.xml','firmware_manifest.json','firmware.bin',*m['boot_ram']]:
  assert (BUILD/name).read_bytes()==(BASE/name).read_bytes(),name
 assert (BUILD/'rtl/ti60_camera_ppi_top.sv').read_text(encoding='utf-8')==top_text()
 for name,value in m['packet_trace_tools'].items():assert sha(ROOT/name)==value,name
 assert m['process']==[640,480] and m['camera']==[1920,1080]
 assert m['display']==read(BASE/'manifest.json')['display']
 bridge=(ROOT/'rtl/packet_trace/csi_ppi_bridge_trace.sv').read_text(encoding='utf-8')
 normalized=bridge.replace('module csi_ppi_bridge_trace #(', 'module csi_ppi_bridge_debug #(',1)
 normalized,ports=re.subn(r'// TRACE_PORT_BEGIN\n.*?// TRACE_PORT_END',
  ' output reg[31:0] debug_events,debug_header);',normalized,count=1,flags=re.S)
 normalized,observers=re.subn(r'// TRACE_OBSERVER_BEGIN\n.*?// TRACE_OBSERVER_END\n',
  '',normalized,count=1,flags=re.S)
 assert ports==observers==1
 assert normalized==(ROOT/'rtl/diagnostics/csi_ppi_bridge_debug.sv').read_text(encoding='utf-8'), 'Original parser changed'
 # The complete legacy predicate must remain: no relaxation for LP status,
 # CRC/ECC/format/frame-end failures is authorized by these two board records.
 for text in ['if(control_error || in_error || lane_overflow || transport_fault)',
              'word_data[29:24]!=header_ecc(word_data[23:0])',
              'word_data[15:0]!=crc_value || raw_bytes!=0',
              '!vs || line_count!=RAW_HEIGHT', 'frame_ticks==FRAME_TIMEOUT-1']:
  assert text in bridge,text
 simulations={}
 for name in ['sim/packet_trace_bridge/verification.json','sim/packet_trace_uart/verification.json',
              'sim/packet_trace_parser/verification.json','sim/top_safety_packet_trace/verification.json',
              'sim/dphy_error_repro/small/verification.json','sim/dphy_error_repro/full/verification.json']:
  item=read(ROOT/name);assert item['result']=='PASS',name
  for path,value in item.get('sources_sha256',{}).items():assert sha(Path(path))==value,path
  for path,value in item.get('logs_sha256',{}).items():assert sha(Path(path))==value,path
  for key in ('sources','source_sha256','logs'):
   for path,value in item.get(key,{}).items():assert sha(ROOT/path)==value,path
  for path,value in item.get('log_sha256',{}).items():assert sha((ROOT/name).parent/path)==value,path
  simulations[name]={'receipt_sha256':sha(ROOT/name),'scope':item['scope']}
 return {'result':'PASS','parent_camera_debug60_bit_sha256':parent['bitstream_sha256'],
         'telemetry_uart_baud':115200,'telemetry_fields':24,'record_bytes':223,
         'acceptance_predicates_not_relaxed':True,'new_cross_clock_payloads':0,
         'sensor_firmware_models_peri_and_hdmi_unchanged':True,'simulations':simulations,
         'scope':'Error-source observer and fully connected licensed DPHY model tests; not physical root cause proof',
         'board_programmed':False}
