"""Isolated local Efinity process environment; no programmer/serial access."""
from pathlib import Path
import os
from desktop_process import run
def environment():
 os.environ['EFINITY_HOME']='E:/software/efinity'
 for key,tail in {'EFXPT_HOME':'pt','EFXPGM_HOME':'pgm','EFXDBG_HOME':'debugger','EFXIPM_HOME':'ipm'}.items():os.environ[key]='E:/software/efinity/'+tail
 os.environ['EFINITY_USER_DIR_INI']=str(Path(os.environ['LOCALAPPDATA'])/'efinity/user_dir.ini')
 os.environ['PYTHONHOME']='E:/software/efinity/python311';os.environ.pop('PYTHONPATH',None)
 os.environ['PATH']='E:/software/efinity/bin;E:/software/efinity/python311/bin;'+os.environ['PATH']
