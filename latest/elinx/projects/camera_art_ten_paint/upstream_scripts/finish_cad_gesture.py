"""Sequential native proof/reroute/proof and snapshot primitive probe."""
from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[1]


def main():
    commands=[['scripts/build.py','prove'],['scripts/build.py','route'],['scripts/build.py','prove-final'],['scripts/probe_snapshot.py']]
    for i,args in enumerate(commands):
        print('START',*args,flush=True)
        with (ROOT/'build'/f'gesture_final_{i}.log').open('w',encoding='utf-8') as stream:
            result=subprocess.run([sys.executable,'-B',*args],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
        assert result.returncode==0,args
        print('PASS',*args,flush=True)


if __name__=='__main__':main()
