"""Independent full build. Config only after signoff; never programs a board."""
from pathlib import Path
import argparse,sys
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'build/camera_ppi'
sys.path.append(str(ROOT/'scripts'))
from tool_run import environment,run
p=argparse.ArgumentParser();p.add_argument('--flow',choices=['map','interface','route','config','sta'],default='map');a=p.parse_args()
environment()
python='E:/software/efinity/python311/bin/python.exe'
if a.flow=='interface':command=[python,'E:/software/efinity/scripts/efx_run_pt_unified.py','ti60_camera','Titanium','Ti60F225','--output_dir','outflow','--timing_model','I3','--project_xml','ti60_camera.xml']
else:
 if a.flow=='route':
  from camera_ppi_constraints import assemble
  assemble(BUILD)
 if a.flow=='config':
  from camera_ppi_signoff import audit
  audit(require_bit=False)
 command=[python,'E:/software/efinity/scripts/efx_run.py','ti60_camera','--prj','--flow',{'map':'map','route':'pnr','config':'pgm','sta':'sta_tclsh'}[a.flow],'--output_dir','outflow']
 if a.flow=='sta':command+=['--tcl_script',str(BUILD/'inspect_dphy.tcl')]
raise SystemExit(run(command,BUILD,BUILD/(a.flow+'_console.log')))
