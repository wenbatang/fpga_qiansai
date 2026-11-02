from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
commands=[['scripts/probe.py'],['scripts/probe_snapshot.py'],['scripts/probe_ten_control.py'],*[['scripts/build.py',s] for s in ['map','interface','route','prove','route','prove-final']]]
for i,args in enumerate(commands):
 print('START',i,args,flush=True)
 with (ROOT/'build'/f'ui_cad_{i}.log').open('w',encoding='utf-8') as stream:
  r=subprocess.run([sys.executable,'-B',*args],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
 assert r.returncode==0,(args,r.returncode)
 print('PASS',i,args,flush=True)
