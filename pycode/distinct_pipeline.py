"""Current-turn sequential distillation; wait for immutable completed teachers."""
from pathlib import Path
import json,subprocess,sys,time
from prepare_distinct_styles import ROOT,STYLES
from export_hardware import export

def main():
    teacher=ROOT/'runs/distinct_teacher_v2';output=ROOT/'runs/distinct_student_v1'
    output.mkdir(parents=True,exist_ok=True)
    deadline=time.monotonic()+3*3600
    for name in STYLES:
        while not (teacher/name/'experiment.json').exists():
            if time.monotonic()>deadline:raise TimeoutError('Teacher did not complete: '+name)
            time.sleep(5)
        command=[sys.executable,str(ROOT/'train_optimized.py'),'--stage','student','--catalog','distinct',
          '--teacher',str(teacher),'--baseline',str(ROOT/'runs/four_styles_v1'),
          '--styles',str(ROOT/'styles/distinct_v1'),'--output',str(output),'--style',name,
          '--warm-start',str(ROOT/'runs/fpga_student_phase'),'--qat-from-start',
          '--channels','6','--depth','5','--coordinate-phase','4',
          '--epochs','12','--size','192','--batch-size','12','--palette-weight','120',
          '--lr','0.0004','--distill-weight','24']
        print('DISTILL',name,flush=True)
        with (output/f'{name}_console.log').open('w',encoding='utf-8') as log:
            subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
        info=export(output/name/'model.pt',output/'export'/name)
        print('EXPORTED',name,'best epoch',info['epoch'],flush=True)
    (output/'complete.json').write_text(json.dumps({'styles':list(STYLES),'teacher':str(teacher),'scope':'all four trained QAT students exported; no hardware programming'},indent=2),encoding='utf-8')
    print('ALL FOUR DISTINCT STUDENTS COMPLETE',flush=True)

if __name__=='__main__':main()
