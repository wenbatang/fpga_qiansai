from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
for i,stage in enumerate(['map','interface','route','prove','route','prove-final']):
 print('START recovery',stage,flush=True)
 with (ROOT/'build'/f'recovery_seed1_{i}.log').open('w',encoding='utf-8') as stream:
  r=subprocess.run([sys.executable,'-B','scripts/build.py',stage],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
 assert r.returncode==0,(stage,r.returncode)
 print('PASS recovery',stage,flush=True)
