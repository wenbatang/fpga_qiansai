"""CAD for the independent RF33 candidate. Never download or auto-release bit."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,sys
ROOT=Path(__file__).resolve().parents[2];BUILD=ROOT/'build/camera_fps_rf33_720'
sys.path.insert(0,str(ROOT/'scripts'))
from tool_run import environment,run

def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def bind():
 sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
 m=json.loads((BUILD/'manifest.json').read_text());fw=json.loads((BUILD/'firmware_manifest.json').read_text())
 assert fw['writes_per_style']==365 and fw['firmware_bytes']<=32768
 m['boot_ram']=fw['boot_ram'];m['firmware_manifest']=sha(BUILD/'firmware_manifest.json')
 for n in m['cpu_generated']:m['cpu_generated'][n]=sha(BUILD/n)
 for n in m['sources']:m['sources'][n]=sha(ROOT.parents[2]/n)
 m['fps_tools']={str(p.relative_to(ROOT)):sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))}
 (BUILD/'manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2))
 print('BOUND candidate firmware and sources; no release approval')

def main():
 global BUILD
 p=argparse.ArgumentParser();p.add_argument('action',choices=['bind','map','interface','route','prove','prove-final']);p.add_argument('--build',type=Path);a=p.parse_args()
 if a.build:
  BUILD=a.build.resolve()
  assert BUILD.parent==(ROOT/'build').resolve() and BUILD.name.startswith('camera_fps_')
 if a.action=='bind':bind();return
 environment()
 if a.action=='route':
  constraints=load('fps_constraints',Path(__file__).parent/'constraints.py');constraints.assemble(BUILD)
 if a.action.startswith('prove'):
  proof=load('fps_proof',ROOT/'scripts/p720/prove_dphy_cdc.py');proof.BUILD=BUILD
  sys.argv=[sys.argv[0],*(['--final'] if a.action=='prove-final' else [])];proof.main();return
 python='E:/software/efinity/python311/bin/python.exe'
 if a.action=='interface':
  cmd=[python,'E:/software/efinity/scripts/efx_run_pt_unified.py','ti60_camera','Titanium','Ti60F225','--output_dir','outflow','--timing_model','I3','--project_xml','ti60_camera.xml']
 else:cmd=[python,'E:/software/efinity/scripts/efx_run.py','ti60_camera','--prj','--flow',{'map':'map','route':'pnr'}[a.action],'--output_dir','outflow']
 assert run(cmd,BUILD,BUILD/(a.action+'_console.log'))==0,a.action
 print('PASS UNSIGNED FPS candidate',a.action)

if __name__=='__main__':main()
