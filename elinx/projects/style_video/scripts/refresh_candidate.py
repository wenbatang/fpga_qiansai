"""Compile firmware, generate NEW SoC, prepare new project; source mutations serial."""
from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
for name,extra in [('prepare_runtime_cnn.py',[]),('build_firmware.py',[]),('tool_run.py',['--csi']),('tool_run.py',[]),('prepare_camera.py',[])]:
 subprocess.run([sys.executable,str(ROOT/'scripts'/name),*extra],cwd=ROOT,check=True)
