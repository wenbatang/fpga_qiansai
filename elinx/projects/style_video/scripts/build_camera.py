"""Efinity candidate build, no hardware programming. pgm means file generation."""
from pathlib import Path
import argparse,sys
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'build/camera_vga'
sys.path.append(str(ROOT/'scripts'))
from tool_run import environment,run
parser=argparse.ArgumentParser();parser.add_argument('--flow',choices=['map','interface','route','config'],default='map');args=parser.parse_args()
environment()
if args.flow=='interface':
 command=['E:/software/efinity/python311/bin/python.exe','E:/software/efinity/scripts/efx_run_pt_unified.py','ti60_camera','Titanium','Ti60F225','--output_dir','outflow','--timing_model','I3','--project_xml','ti60_camera.xml']
else:
 if args.flow=='route':
  from camera_constraints import assemble
  assemble(BUILD)
 if args.flow=='config':
  from camera_signoff import audit
  audit(require_bit=False)
 stage={'map':'map','route':'pnr','config':'pgm'}[args.flow]
 command=['E:/software/efinity/python311/bin/python.exe','E:/software/efinity/scripts/efx_run.py','ti60_camera','--prj','--flow',stage,'--output_dir','outflow']
raise SystemExit(run(command,BUILD,BUILD/(args.flow+'_console.log')))
