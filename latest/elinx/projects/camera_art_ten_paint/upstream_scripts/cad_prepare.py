"""One CAD process at a time, through final native proof; no bit generation."""
from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[1]


def main():
    commands=[['scripts/probe.py'],['scripts/probe.py','--dma'],*[['scripts/build.py',stage] for stage in ['map','interface','route','prove','route','prove-final']]]
    folder=ROOT/'build/cad_final';folder.mkdir(exist_ok=True)
    for i,args in enumerate(commands):
        print('START CAD',i+1,*args,flush=True)
        with (folder/f'{i+1:02d}.log').open('w',encoding='utf-8') as stream:
            result=subprocess.run([sys.executable,'-B',*args],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
        assert result.returncode==0,(args,folder/f'{i+1:02d}.log')
        print('PASS CAD',i+1,flush=True)
    print('PASS CAD through final native proof; no bit generated',flush=True)


if __name__=='__main__':main()
