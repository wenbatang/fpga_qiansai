"""Run local Efinity; never access programmer/JTAG/serial."""
from pathlib import Path
import argparse,os,sys
ROOT=Path(__file__).resolve().parents[1];WS=ROOT.parents[2]
sys.path.append(str(WS/'xilinx/projects/uart_style_hdmi/scripts'))
from desktop_process import run
parser=argparse.ArgumentParser();parser.add_argument('--profile',choices=('720p','vga'),default='720p');parser.add_argument('--flow',choices=('map','interface','compile','route','config'),default='compile');a=parser.parse_args()
folder=ROOT/'build'/a.profile
os.environ['EFINITY_HOME']='E:/software/efinity'
for key,tail in {'EFXPT_HOME':'pt','EFXPGM_HOME':'pgm','EFXDBG_HOME':'debugger','EFXIPM_HOME':'ipm'}.items():os.environ[key]=f'E:/software/efinity/{tail}'
os.environ['EFINITY_USER_DIR_INI']=str(Path(os.environ['LOCALAPPDATA'])/'efinity/user_dir.ini')
os.environ['PYTHONHOME']='E:/software/efinity/python311';os.environ.pop('PYTHONPATH',None)
os.environ['PATH']='E:/software/efinity/bin;E:/software/efinity/python311/bin;'+os.environ['PATH']
def constraints():
    # Efinity does not automatically add pt.sdc to the user constraint file.
    # Keep installed-interface timing and every PLL clock, omit template lines
    # with unresolved user placeholders. Do not sign off a boot-clock-only STA.
    from constraints import assemble
    assemble(folder)
if a.flow=='route':constraints()
if a.flow=='config':
    from signoff import audit
    audit(folder,require_bit=False)
for stage in (['map','interface','pnr','pgm'] if a.flow=='compile' else ['pnr','pgm'] if a.flow=='route' else ['pgm'] if a.flow=='config' else [a.flow]):
    if stage=='interface':
        command=['E:/software/efinity/python311/bin/python.exe','E:/software/efinity/scripts/efx_run_pt_unified.py','ti60_style','Titanium','Ti60F225','--output_dir','outflow','--timing_model','I3','--project_xml','ti60_style.xml']
    else:command=['E:/software/efinity/python311/bin/python.exe','E:/software/efinity/scripts/efx_run.py','ti60_style','--prj','--flow',stage,'--output_dir','outflow']
    print('START',stage,flush=True)
    code=run(command,folder,folder/(stage+'_console.log'))
    if code:raise SystemExit(code)
    print('PASS',stage,flush=True)
    if stage=='interface':constraints()
    if stage=='pnr':
        from signoff import audit
        audit(folder,require_bit=False)
