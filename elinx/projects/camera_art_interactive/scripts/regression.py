"""Sequential final-parameter RTL checks. No CAD or hardware commands."""
from pathlib import Path
import json,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1]


def main():
    selected=json.loads((ROOT/'build/model_selection.json').read_text(encoding='utf-8'))
    assert not selected.get('provisional',True),'Use frozen final hardware-QAT parameters'
    commands=[['sim/check_kernel.py','--width',str(w),'--height',str(h)] for w,h in [(48,40),(1,1),(3,5),(19,22)]]
    commands += [['sim/check_dma.py'],['sim/check_dma.py','--pressure'],['sim/check_dma.py','--split'],['sim/check_dma.py','--split','--pressure'],['sim/check_dma.py','--full','--styles','0','1','2','3'],['sim/check_dma.py','--full','--split','--styles','0']]
    commands += [[p] for p in ['sim/check_control.py','sim/check_sapphire.py','sim/check_keys.py','sim/check_top_safety.py','sim/check_display_state.py','sim/check_fps_jobs.py','sim/check_fps_write_pressure2.py','sim/fps_reader/check_reader.py','sim/scheduling/check_scheduler.py']]
    folder=ROOT/'build/regression';folder.mkdir(exist_ok=True);start=time.monotonic()
    for i,args in enumerate(commands):
        print('START',i+1,len(commands),*args,flush=True)
        with (folder/f'{i+1:02d}.log').open('w',encoding='utf-8') as stream:
            result=subprocess.run([sys.executable,'-B',*args],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
        assert result.returncode==0,(args,folder/f'{i+1:02d}.log')
        print('PASS',i+1,'seconds',round(time.monotonic()-start),flush=True)
    print('PASS all final RTL regression commands',flush=True)


if __name__=='__main__':main()
