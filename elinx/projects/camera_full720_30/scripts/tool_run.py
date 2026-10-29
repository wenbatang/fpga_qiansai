"""Local licensed-tool launcher; all working/temp paths stay in this new project."""
from pathlib import Path
import os
from desktop_process import run
ROOT=Path(__file__).resolve().parents[1]
def environment():
    os.environ['EFINITY_HOME']='E:/software/efinity'
    for key,tail in {'EFXPT_HOME':'pt','EFXPGM_HOME':'pgm','EFXDBG_HOME':'debugger','EFXIPM_HOME':'ipm'}.items():os.environ[key]='E:/software/efinity/'+tail
    os.environ['EFINITY_USER_DIR_INI']=str(Path(os.environ['LOCALAPPDATA'])/'efinity/user_dir.ini')
    os.environ['PYTHONHOME']='E:/software/efinity/python311';os.environ.pop('PYTHONPATH',None)
    java='E:/softare_FPGA/vivado2023/Vivado/2023.2/tps/win64/jre17.0.7_7';os.environ['JAVA_HOME']=java
    os.environ['PATH']=java+'/bin;E:/software/efinity/bin;E:/software/efinity/python311/bin;'+os.environ['PATH']
    temp=ROOT/'build/tmp';temp.mkdir(exist_ok=True)
    for key in ('TMP','TEMP','TMPDIR'):os.environ[key]=str(temp)
