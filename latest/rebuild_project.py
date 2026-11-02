"""Rebuild copied Efinity project through exact CDC/STA. Never programs hardware.

Stops before bit generation: a fresh CAD result is not a new functional release.
"""
from pathlib import Path
import argparse,importlib,os,sys
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT/'elinx/projects/camera_art_ten_paint';B=PROJECT/'build/720p'
def main():
 p=argparse.ArgumentParser();p.add_argument('--efinity',type=Path,default=Path(os.environ.get('EFINITY_HOME','E:/software/efinity')));p.add_argument('--java-home',type=Path);p.add_argument('--run',action='store_true',help='Actually run licensed CAD; default prints plan');a=p.parse_args()
 if not a.run:print('Plan: relocate -> map -> interface -> constraints -> route -> D-PHY proof -> constraints -> route -> final proof -> board audit. No pgm/JTAG/Flash. Add --run to execute.');return
 import relocate;relocate.main();sys.path.insert(0,str(PROJECT/'upstream_scripts'))
 import desktop_process,tool_run,native_constraints
 ef=a.efinity.resolve();assert (ef/'scripts/efx_run.py').is_file(),ef
 def environment():
  os.environ['EFINITY_HOME']=str(ef)
  for key,sub in {'EFXPT_HOME':'pt','EFXPGM_HOME':'pgm','EFXDBG_HOME':'debugger','EFXIPM_HOME':'ipm'}.items():os.environ[key]=str(ef/sub)
  os.environ['PYTHONHOME']=str(ef/'python311');os.environ.pop('PYTHONPATH',None);temp=PROJECT/'build/tmp';temp.mkdir(parents=True,exist_ok=True)
  for key in ['TMP','TEMP','TMPDIR']:os.environ[key]=str(temp)
  java=a.java_home or Path(os.environ.get('JAVA_HOME','E:/softare_FPGA/vivado2023/Vivado/2023.2/tps/win64/jre17.0.7_7'))
  prefixes=[str(ef/'bin'),str(ef/'python311/bin')]
  if java.is_dir():os.environ['JAVA_HOME']=str(java);prefixes.insert(0,str(java/'bin'))
  os.environ['PATH']=os.pathsep.join(prefixes+[os.environ['PATH']])
  if 'LOCALAPPDATA' in os.environ:os.environ['EFINITY_USER_DIR_INI']=str(Path(os.environ['LOCALAPPDATA'])/'efinity/user_dir.ini')
 def run(command,cwd,output):return desktop_process.run([str(x).replace('E:/software/efinity',ef.as_posix()) for x in command],cwd,output)
 tool_run.environment=environment;tool_run.run=run;environment();py=str(ef/'python311/bin/python.exe')
 def stage(name):
  command=[py,str(ef/'scripts/efx_run.py'),'ti60_camera','--prj','--flow',name,'--output_dir','outflow'];assert run(command,B,B/('rebuild_'+name+'.log'))==0,name
 stage('map');assert run([py,str(ef/'scripts/efx_run_pt_unified.py'),'ti60_camera','Titanium','Ti60F225','--output_dir','outflow','--timing_model','I3','--project_xml','ti60_camera.xml'],B,B/'rebuild_interface.log')==0
 native_constraints.assemble(B);stage('pnr');proof=importlib.import_module('native_prove_dphy_cdc');sys.argv=['proof'];proof.main();native_constraints.assemble(B);stage('pnr');sys.argv=['proof','--final'];proof.main()
 import board_spec;board_spec.audit(B,camera=True)
 print('CAD and board audit finished. Review NEW timing/resource/numeric results before generating a new bit; original release/bit unchanged.')
if __name__=='__main__':main()
