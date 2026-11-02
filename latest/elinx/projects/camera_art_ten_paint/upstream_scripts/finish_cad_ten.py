"""Sequential native CDC proof, route, final proof; keep verified OOC maps."""
from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
def main():
    for i,stage in enumerate(['prove','route','prove-final']):
        print('START',stage,flush=True)
        with (ROOT/'build'/f'ten_final_{i}.log').open('w',encoding='utf8') as stream:
            result=subprocess.run([sys.executable,'-B','scripts/build.py',stage],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
        assert result.returncode==0,(stage,result.returncode)
        print('PASS',stage,flush=True)
if __name__=='__main__':main()
