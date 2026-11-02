from pathlib import Path
import subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1]
commands=[['sim/check_interaction.py'],['sim/check_guard.py'],['sim/check_riscv_m.py'],['sim/check_top_safety.py'],['sim/check_ten_firmware.py'],['sim/check_ten_sapphire.py'],['sim/check_calibration_firmware.py'],['sim/check_ten_kernel.py'],['sim/check_ten_dma.py'],['sim/check_ten_dma.py','--split'],['sim/check_ten_dma.py','--split','--pressure'],['sim/check_ten_dma.py','--full','--split','--styles','0'],['sim/check_mapped_snapshot.py'],['sim/check_guard_mapped.py'],['sim/check_ten_mapped.py']]
for i,args in enumerate(commands):
 print('START',i,args,flush=True)
 with (ROOT/'build'/f'verify_paint_{i}.log').open('w',encoding='utf-8') as stream:
  r=subprocess.run([sys.executable,'-B',*args],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
 assert r.returncode==0,(i,args,r.returncode)
 print('PASS',i,args,flush=True)
