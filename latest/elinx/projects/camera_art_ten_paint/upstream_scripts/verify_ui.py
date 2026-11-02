from pathlib import Path
import subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1]
for name in ['snapshot','guard','riscv_m','ten_firmware','ten_sapphire','calibration_firmware','mapped_snapshot','guard_mapped']:
 if name in ['mapped_snapshot','guard_mapped']:
  while not (ROOT/'build/probe_ten_control/outflow/video_control_apb_fast.map.v').exists():time.sleep(2)
 print('START',name,flush=True)
 with (ROOT/'build'/('verify_'+name+'.log')).open('w',encoding='utf-8') as stream:
  r=subprocess.run([sys.executable,'-B','sim/check_'+name+'.py'],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
 assert r.returncode==0,(name,r.returncode)
 print('PASS',name,flush=True)
