"""Run a local desktop tool with isolated Efinity environment; no hardware I/O."""
from pathlib import Path
import os, sys
ROOT=Path(__file__).resolve().parents[1]; WS=ROOT.parents[2]
sys.path.append(str(WS/'xilinx/projects/uart_style_hdmi/scripts'))
from desktop_process import run

def environment():
    os.environ['EFINITY_HOME']='E:/software/efinity'
    for key,tail in {'EFXPT_HOME':'pt','EFXPGM_HOME':'pgm','EFXDBG_HOME':'debugger','EFXIPM_HOME':'ipm'}.items():
        os.environ[key]='E:/software/efinity/'+tail
    os.environ['EFINITY_USER_DIR_INI']=str(Path(os.environ['LOCALAPPDATA'])/'efinity/user_dir.ini')
    os.environ['PYTHONHOME']='E:/software/efinity/python311'
    os.environ.pop('PYTHONPATH',None)
    # The installed Java 25 emits native-access warnings which IP Manager
    # treats as generation errors. Use the already installed Java 17 runtime.
    java='E:/softare_FPGA/vivado2023/Vivado/2023.2/tps/win64/jre17.0.7_7'
    os.environ['JAVA_HOME']=java
    os.environ['PATH']=java+'/bin;E:/software/efinity/bin;E:/software/efinity/python311/bin;'+os.environ['PATH']

if __name__=='__main__':
    environment()
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--csi',action='store_true');a=p.parse_args()
    directory=ROOT/('build/csi515_probe' if a.csi else 'build/camera_vga');directory.mkdir(parents=True,exist_ok=True)
    script='generate_csi_probe.py' if a.csi else 'generate_soc.py'
    raise SystemExit(run(['E:/software/efinity/python311/bin/python.exe',str(ROOT/'scripts'/script)],directory,directory/('csi_console.log' if a.csi else 'soc_console.log')))
