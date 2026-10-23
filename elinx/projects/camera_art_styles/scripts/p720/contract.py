"""Independent full720 pipeline; preserve the board-tested VGA release."""
from pathlib import Path
import hashlib,importlib.util,json,re,sys
ROOT=Path(__file__).resolve().parents[2];WS=ROOT.parents[2]
BASE=ROOT/'build/camera_bias_fix60';BUILD=ROOT/'build/camera_720_fast'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def parent_audit():
 saved=sys.modules.get('contract');folder=ROOT/'scripts/bias_fix'
 spec=importlib.util.spec_from_file_location('bias_parent_contract',folder/'contract.py')
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);sys.modules['contract']=module
 try:
  spec=importlib.util.spec_from_file_location('bias_parent_signoff',folder/'signoff.py')
  previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
  current=previous.audit(True)
  assert json.loads(json.dumps(current))==read(BASE/'signoff.json'),'Signed VGA parent changed'
  return current
 finally:
  if saved is None:sys.modules.pop('contract',None)
  else:sys.modules['contract']=saved
def top_text():
 text=(BASE/'rtl/ti60_camera_ppi_top.sv').read_text(encoding='utf-8')
 text=text.replace('PROC_WIDTH=640,PROC_HEIGHT=480','PROC_WIDTH=1280,PROC_HEIGHT=720')
 text=text.replace('CLK_27M,core_clk,hdmi_tx_slow_clk','CLK_27M,core_clk,cnn_clk,hdmi_tx_slow_clk')
 text=text.replace('video_system_bias_fixed #(', 'video_system_720 #(').replace('system(.clk(ui_clk),','system(.clk(ui_clk),.fast_clk(cnn_clk),')
 return text
def electrical_delta():
 text=(BUILD/'ti60_camera.peri.xml').read_text(encoding='utf-8')
 extra='\n            <efxpt:comp_output_clock name="cnn_clk" number="1" out_divider="12" is_dyn_phase="false" phase_setting="0" is_inverted="false" conn_type="gclk" />'
 assert text.count(extra)==1,'Only audited additional CNN PLL output allowed'
 assert text.replace(extra,'')==(BASE/'ti60_camera.peri.xml').read_text(encoding='utf-8'),'Pin/bank or existing PLL change'
def audit_contract(require_sim=True):
 old=parent_audit();m=read(BUILD/'manifest.json')
 for name,value in m['parent_bias60'].items():assert sha(BASE/name)==value,name
 for name,value in m['p720_tools'].items():assert sha(ROOT/name)==value,name
 electrical_delta()
 for name in ['firmware_manifest.json','firmware.bin',*m['boot_ram']]:assert (BUILD/name).read_bytes()==(BASE/name).read_bytes(),name
 assert (BUILD/'rtl/ti60_camera_ppi_top.sv').read_text(encoding='utf-8')==top_text()
 sims={}
 if require_sim:
  for name in ['full','bayer_faults','bayer','bayer_full','runtime48','async_runtime','async_reset','capture','display','sapphire','top_safety','mapped']:
   path=ROOT/'sim/p720'/name/'verification.json';item=read(path);assert item['result']=='PASS',name
   for p,v in item.get('sources_sha256',{}).items():assert sha(Path(p))==v,p
   for p,v in item.get('logs_sha256',{}).items():assert sha(Path(p))==v,p
   sims[name]=sha(path)
 return {'result':'PASS','parent_bit_sha256':old['bitstream_sha256'],'process':[1280,720],
  'change':'Full-field bilinear Bayer 1080-to720; 17-bit capture words; CORE48+halo32; pipelined quantizer; atomic stream FIFOs and parameter/start/done mailboxes; CNN166.667MHz, UI100MHz; display FIFO512',
  'models_firmware_pins_voltages_ddr_hdmi_unchanged':True,'simulations':sims,'board_programmed':False}
