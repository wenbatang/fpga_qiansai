"""Fix the reproduced mapped bias write mismatch, retain electrical contract."""
from pathlib import Path
import hashlib,importlib.util,json,re,sys
ROOT=Path(__file__).resolve().parents[2];WS=ROOT.parents[2]
BASE=ROOT/'build/camera_view60';BUILD=ROOT/'build/camera_bias_fix60'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def parent_audit():
 saved=sys.modules.get('contract');folder=ROOT/'scripts/view'
 spec=importlib.util.spec_from_file_location('view_parent_contract',folder/'contract.py')
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);sys.modules['contract']=module
 try:
  spec=importlib.util.spec_from_file_location('view_parent_signoff',folder/'signoff.py')
  previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
  current=previous.audit(True)
  assert json.loads(json.dumps(current))==read(BASE/'signoff.json'),'Signed view parent changed'
  return current
 finally:
  if saved is None:sys.modules.pop('contract',None)
  else:sys.modules['contract']=saved
def top_text():
 text=(BASE/'rtl/ti60_camera_ppi_top.sv').read_text(encoding='utf-8')
 assert text.count('video_system_view #(')==1
 return text.replace('video_system_view #(', 'video_system_bias_fixed #(',1)
def audit_contract():
 old=parent_audit();m=read(BUILD/'manifest.json')
 for name,value in m['parent_view60'].items():assert sha(BASE/name)==value,name
 for name,value in m['bias_fix_tools'].items():assert sha(ROOT/name)==value,name
 for name in ['ti60_camera.peri.xml','firmware_manifest.json','firmware.bin',*m['boot_ram']]:
  assert (BUILD/name).read_bytes()==(BASE/name).read_bytes(),name
 assert (BUILD/'rtl/ti60_camera_ppi_top.sv').read_text(encoding='utf-8')==top_text()
 # All integration variants differ only by the new module names.
 for new,original in [('video_cnn_tile5_fixed.sv','rtl/video_cnn_tile5.sv'),
                      ('video_cnn_view_fixed.sv','rtl/view/video_cnn_view.sv'),
                      ('video_tile_engine_view_fixed.sv','rtl/view/video_tile_engine_view.sv'),
                      ('video_system_bias_fixed.sv','rtl/view/video_system_view.sv')]:
  text=(ROOT/'rtl/bias_fix'/new).read_text(encoding='utf-8')
  for a,b in [('video_system_bias_fixed','video_system_view'),('video_tile_engine_view_fixed','video_tile_engine_view'),
              ('video_cnn_view_fixed','video_cnn_view'),('video_cnn_tile5_fixed','video_cnn_tile5'),('video_conv3x3_fixed','video_conv3x3')]:
   text=text.replace(a,b)
  assert text==(ROOT/original).read_text(encoding='utf-8'),new
 # Reconstruct the old source by replacing ONLY the constant-index bias
 # writer block with its original dynamic whole-word/subword assignment.
 text=(ROOT/'rtl/bias_fix/video_conv3x3_fixed.sv').read_text(encoding='utf-8').replace('module video_conv3x3_fixed #(', 'module video_conv3x3 #(',1)
 text,n=re.subn(r' // Fixed channel decoders.*? end endgenerate\n','',text,count=1,flags=re.S);assert n==1
 marker='  if(cfg_address[15:14]==2 && cfg_data<=31)shifts[0]<=cfg_data[7:0];'
 text=text.replace(marker,'  if(cfg_address[15:14]==1 && cfg_address[10:0]<COUT)\n   biases[cfg_address[10:0]/LANES][(cfg_address[10:0]%LANES)*32+:32]<=cfg_data;\n'+marker,1)
 assert text==(ROOT/'rtl/video_conv3x3.sv').read_text(encoding='utf-8'),'Unexpected arithmetic change'
 sims={}
 for name in ['sim/cnn_mapped/reproduction.json','sim/cnn_bias_fixed/verification.json',
              'sim/bias_fix/runtime/verification.json','sim/bias_fix/top_safety/verification.json']:
  path=ROOT/name;item=read(path)
  assert item['result']==('REPRODUCED_MISMATCH' if 'reproduction' in name else 'PASS'),name
  for p,value in item.get('sources_sha256',{}).items():assert sha(Path(p))==value,p
  for p,value in item.get('logs_sha256',{}).items():assert sha(Path(p))==value,p
  sims[name]={'receipt_sha256':sha(path),'scope':item['scope']}
 return {'result':'PASS','parent_bit_sha256':old['bitstream_sha256'],
  'change':'Only dynamic bias subword writes replaced by one constant decoder per output channel; arithmetic/pipelines/protocol/model unchanged',
  'reproduction':'old mapped first-layer bias differs despite correct samples/weights; papercut output4d7e0b -> expanded RGB8,125,74 matches user CAM3 means',
  'validation':'real Efinix primitive netlist compared against actual RTL plus integer-reference CNN/DMA',
  'camera_display_protocol_firmware_models_peri_unchanged':True,'new_cross_clock_payloads':0,
  'simulations':sims,'scope':'Reproduced and corrected digital mapping failure; real new-bit camera quality still requires board confirmation',
  'board_programmed':False}
