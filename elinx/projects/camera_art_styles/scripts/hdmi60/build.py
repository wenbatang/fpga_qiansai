"""Independent camera720p60 build; full native D-PHY proof, no hardware I/O."""
from pathlib import Path
import argparse,hashlib,json,shutil,sys,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'build/camera_ppi';BUILD=ROOT/'build/camera_ppi60';WS=ROOT.parents[2]
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(Path(__file__).parent))
from contract import parent_audit,top_text
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')

def prepare():
 parent_audit();assert not BUILD.exists(),'Preserve existing candidate'
 BUILD.mkdir();(BUILD/'rtl').mkdir();top=BUILD/'rtl/ti60_camera_ppi_top.sv';top.write_text(top_text(),encoding='utf-8')
 m=read(BASE/'manifest.json')
 # Copy only actual inputs. CPU HDL and four initialization byte lanes remain
 # byte-identical; no IP upgrade, firmware edit or tool-generated cache copy.
 for name in ['ddr3_parameter.vh','firmware_manifest.json','firmware.bin','firmware.elf','camera_mode.h','style_catalog.h',*m['boot_ram']]:
  shutil.copyfile(BASE/name,BUILD/name)
 for name in [*m['cpu_generated'],'ip/control_soc/control_soc.v','ip/control_soc/Testbench/modelsim/control_soc.v']:
  dest=BUILD/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(BASE/name,dest)
 for name in m['boot_ram']:shutil.copyfile(BASE/name,BUILD/'ip/control_soc'/name)
 shutil.copyfile(BASE/'ti60_camera.peri.xml',BUILD/'ti60_camera.peri.xml')
 ns='http://www.efinixinc.com/enf_proj';tree=ET.parse(BASE/'ti60_camera.xml');info=tree.find('{'+ns+'}design_info')
 replacements={str(ROOT/'rtl/ti60_camera_ppi_top.sv'):top,
  str(ROOT/'rtl/video_system.sv'):ROOT/'rtl/hdmi60/video_system60.sv',
  str(ROOT/'rtl/video_raster.sv'):ROOT/'rtl/hdmi60/video_raster60.sv',
  str(ROOT/'rtl/fps_overlay.sv'):ROOT/'rtl/hdmi60/fps_overlay60.sv',
  str(BASE/'ip/control_soc/control_soc.v'):BUILD/'ip/control_soc/control_soc.v'}
 for node in info.findall('{'+ns+'}design_file'):
  key=str(Path(node.get('name')))
  if key in replacements:node.set('name',replacements[key].as_posix())
 vendor=read(ROOT/'vendor/hdmi_v7/provenance.json')
 added=[ROOT/'rtl/hdmi60/tmds_hdmi60.sv',*[ROOT/'vendor/hdmi_v7'/n for n in vendor['design_files']]]
 position=max(i for i,n in enumerate(info) if n.tag=='{'+ns+'}design_file')+1
 for p in added:
  info.insert(position,ET.Element('{'+ns+'}design_file',name=p.as_posix(),version='default',library='default'));position+=1
 ET.register_namespace('efx',ns);tree.write(BUILD/'ti60_camera.xml',encoding='utf-8')
 m['sources']={str(Path(n.get('name')).relative_to(WS)):sha(Path(n.get('name'))) for n in info.findall('{'+ns+'}design_file')}
 m['display']='1280x720p60, 74.25MHz, 1650x750, centered VGA + C/I/H60 overlay'
 m['parent_camera30']={name:sha(BASE/name) for name in ['manifest.json','signoff.json','outflow/ti60_camera.bit']}
 m['compatibility_tools']={str(p.relative_to(ROOT)):sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))}
 m['project_xml_sha256']=sha(BUILD/'ti60_camera.xml');m['status']='independent 720p60 candidate; requires new simulations, CAD and native D-PHY proof'
 write(BUILD/'manifest.json',m)
 (BUILD/'ti60_camera.sdc').write_text('create_clock -name CLK_25M -period 40 [get_ports CLK_25M]\n')
 print('Prepared independent camera_ppi60; unchanged CPU firmware/weights and physical interface',flush=True)

def command_run(command,log):
 from tool_run import run
 code=run(command,BUILD,BUILD/log)
 if code:raise SystemExit(code)

def flow(stage):
 from tool_run import environment
 from camera_ppi_constraints import assemble
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
  audit_contract()
  # Before excluding D-PHY first stages, route once fully timed and prove
  # first-to-second endpoint topology. Repeat native proof on final routing.
  for stage in ['map','interface','pnr']:flow(stage)
  proof();flow('pnr');proof(True);flow('pgm')
  from signoff import audit
  r=audit(True);write(BUILD/'signoff.json',r);print('PASS CAMERA720P60',r['resources'],r['setup_min_ns'],r['hold_min_ns'],r['bitstream_sha256'],flush=True)
 elif a.action=='prove':proof()
 elif a.action=='prove-final':proof(True)
 elif a.action=='audit':
  from signoff import audit
  r=audit(True);print('PASS CAMERA720P60 CURRENT BINDING',r['bitstream_sha256'])
 else:flow({'map':'map','interface':'interface','route':'pnr','config':'pgm'}[a.action])
