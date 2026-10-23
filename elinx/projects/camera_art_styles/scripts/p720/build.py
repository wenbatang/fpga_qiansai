"""Independent true720 camera pipeline build; never access hardware."""
from pathlib import Path
import argparse, hashlib, json, shutil, sys, xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/camera_bias_fix60'
BUILD=ROOT/'build/camera_720_fast'
WS=ROOT.parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(Path(__file__).parent))
from contract import parent_audit,top_text

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')

def prepare():
 parent_audit()
 assert not BUILD.exists(),'Preserve existing candidate'
 BUILD.mkdir();(BUILD/'rtl').mkdir()
 top=BUILD/'rtl/ti60_camera_ppi_top.sv';top.write_text(top_text(),encoding='utf-8')
 folder=ROOT/'rtl/p720'
 m=read(BASE/'manifest.json')
 for name in ['ddr3_parameter.vh','firmware_manifest.json','firmware.bin','firmware.elf','camera_mode.h','style_catalog.h',*m['boot_ram']]:shutil.copyfile(BASE/name,BUILD/name)
 for name in [*m['cpu_generated'],'ip/control_soc/control_soc.v','ip/control_soc/Testbench/modelsim/control_soc.v']:
  dest=BUILD/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(BASE/name,dest)
 for name in m['boot_ram']:shutil.copyfile(BASE/name,BUILD/'ip/control_soc'/name)
 peri=(BASE/'ti60_camera.peri.xml').read_text(encoding='utf-8')
 marker='<efxpt:comp_output_clock name="core_clk" number="0" out_divider="20" is_dyn_phase="false" phase_setting="0" is_inverted="false" conn_type="gclk" />'
 assert peri.count(marker)==1
 peri=peri.replace(marker,marker+'\n            <efxpt:comp_output_clock name="cnn_clk" number="1" out_divider="12" is_dyn_phase="false" phase_setting="0" is_inverted="false" conn_type="gclk" />')
 (BUILD/'ti60_camera.peri.xml').write_text(peri,encoding='utf-8')
 ns='http://www.efinixinc.com/enf_proj';tree=ET.parse(BASE/'ti60_camera.xml');info=tree.find('{'+ns+'}design_info')
 pairs=[('rtl/bias_fix/video_system_bias_fixed.sv','video_system_720.sv'),('rtl/bias_fix/video_tile_engine_view_fixed.sv','video_tile_engine_async.sv'),('rtl/bias_fix/video_cnn_view_fixed.sv','video_cnn_view_pipe.sv'),('rtl/bias_fix/video_cnn_tile5_fixed.sv','video_cnn_tile5_pipe.sv'),('rtl/bias_fix/video_conv3x3_fixed.sv','video_conv3x3_pipe.sv'),('rtl/video_control_apb.sv','video_control_apb_fast.sv'),('rtl/camera_bayer_reduce.sv','camera_bayer_720.sv'),('rtl/camera_pack.sv','camera_pack_720.sv'),('rtl/camera_frame_writer.sv','camera_frame_writer_720.sv'),('rtl/pixel_fifo_efx.sv','pixel_fifo_720.sv')]
 replacements={str(BASE/'rtl/ti60_camera_ppi_top.sv'):top,**{str(ROOT/a):folder/b for a,b in pairs},str(ROOT/'rtl/view/video_raster_view.sv'):ROOT/'rtl/hdmi60/video_raster60.sv',str(BASE/'ip/control_soc/control_soc.v'):BUILD/'ip/control_soc/control_soc.v'}
 for name in ['stream_fifo_24.sv','video_cnn_async.sv']:ET.SubElement(info,'{'+ns+'}design_file',name=(folder/name).as_posix(),version='default',library='default')
 for node in list(info):
  if node.tag=='{'+ns+'}design_file':info.remove(node);info.insert(list(info).index(info.find('{'+ns+'}top_vhdl_arch')),node)
 replaced=set()
 for node in info.findall('{'+ns+'}design_file'):
  key=str(Path(node.get('name')))
  if key in replacements:node.set('name',replacements[key].as_posix());replaced.add(key)
 assert replaced==set(replacements)
 ET.register_namespace('efx',ns);tree.write(BUILD/'ti60_camera.xml',encoding='utf-8')
 m['sources']={str(Path(n.get('name')).relative_to(WS)):sha(Path(n.get('name'))) for n in info.findall('{'+ns+'}design_file')}
 m['parent_bias60']={n:sha(BASE/n) for n in ['manifest.json','signoff.json','outflow/ti60_camera.bit']}
 m['p720_tools']={str(p.relative_to(ROOT)):sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))}
 m['project_xml_sha256']=sha(BUILD/'ti60_camera.xml')
 m['process']=[1280,720];m['display']=[1280,720,60];m['cnn_clock_hz']=166666666.666667;m['ui_clock_hz']=100000000
 m['status']='Full720 pipeline candidate. CNN166.667MHz independent; UI/DDR/HDMI/pins/voltages/model/firmware unchanged. Release requires new simulation + native final STA + electrical audit.'
 write(BUILD/'manifest.json',m)
 (BUILD/'ti60_camera.sdc').write_text('create_clock -name CLK_25M -period 40 [get_ports CLK_25M]\n')
 print('PREPARED camera_720_fast: true1280x720, CNN166.667MHz, preserved CPU/model/electrical baseline')

def command_run(command,log):
 from tool_run import run
 code=run(command,BUILD,BUILD/log)
 if code:raise SystemExit(code)

def flow(stage):
 from tool_run import environment
 from constraints import assemble
 environment()
 if stage=='pnr':assemble(BUILD)
 if stage=='pgm':
  from signoff import audit
  write(BUILD/'pre_bit_review.json',audit(False))
 python='E:/software/efinity/python311/bin/python.exe'
 if stage=='interface':cmd=[python,'E:/software/efinity/scripts/efx_run_pt_unified.py','ti60_camera','Titanium','Ti60F225','--output_dir','outflow','--timing_model','I3','--project_xml','ti60_camera.xml']
 else:cmd=[python,'E:/software/efinity/scripts/efx_run.py','ti60_camera','--prj','--flow',stage,'--output_dir','outflow']
 print('START',stage,flush=True);command_run(cmd,stage+'_console.log');print('PASS',stage,flush=True)

def proof(final=False):
 from tool_run import environment
 environment()
 command_run(['E:/software/efinity/python311/bin/python.exe',str(Path(__file__).parent/'prove_dphy_cdc.py'),*(['--final'] if final else [])],('dphy_final_launcher.log' if final else 'dphy_initial_launcher.log'))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','compile','map','interface','route','prove','prove-final','config','audit']);a=p.parse_args()
 if a.action=='prepare':prepare()
 elif a.action=='compile':
  from contract import audit_contract
  audit_contract(require_sim=False)
  for stage in ['map','interface','pnr']:flow(stage)
  proof();flow('pnr');proof(True);flow('pgm')
  from signoff import audit
  r=audit(True);write(BUILD/'signoff.json',r);print('PASS CAMERA FULL720 FAST',r['resources'],r['setup_min_ns'],r['hold_min_ns'],r['bitstream_sha256'],flush=True)
 elif a.action=='prove':proof()
 elif a.action=='prove-final':proof(True)
 elif a.action=='audit':
  from signoff import audit
  r=audit(True);assert json.loads(json.dumps(r))==read(BUILD/'signoff.json');print('PASS CAMERA FULL720 FAST CURRENT BINDING',r['bitstream_sha256'])
 else:flow({'map':'map','interface':'interface','route':'pnr','config':'pgm'}[a.action])
