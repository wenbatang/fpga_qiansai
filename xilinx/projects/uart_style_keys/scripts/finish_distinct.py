"""Validate final immutable models, then build profiles sequentially; never program hardware."""
from pathlib import Path
import subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1];WS=ROOT.parents[2]
EXPORT=WS/'pycode/runs/distinct_student_v1/export'
def run(stage,command,cwd):
    print('START',stage,flush=True)
    with (ROOT/'build'/f'final_{stage}.log').open('w',encoding='utf-8') as log:
        subprocess.run([sys.executable,*map(str,command)],cwd=cwd,stdout=log,stderr=subprocess.STDOUT,check=True)
    print('PASS',stage,flush=True)
def main():
    deadline=time.monotonic()+3*3600
    while not (WS/'pycode/runs/distinct_student_v1/complete.json').exists():
        if time.monotonic()>deadline:raise TimeoutError('Training not complete')
        time.sleep(5)
    run('four_cnn',[ROOT/'sim/check_cnn.py','--export',EXPORT,'--depth','5','--name','distinct_final'],ROOT/'build')
    run('tiny_cnn',[ROOT/'sim/check_cnn.py','--export',EXPORT,'--depth','5','--name','distinct_tiny','--width','1','--height','1'],ROOT/'build')
    run('four_key_link',[ROOT/'sim/check_link.py','--export',EXPORT],ROOT/'build')
    run('integer_evaluation',[WS/'pycode/evaluate_distinct.py'],WS/'pycode')
    run('teacher_comparisons',[WS/'pycode/compare_styles.py','--catalog','distinct','--run',WS/'pycode/runs/distinct_teacher_v2','--styles',WS/'pycode/styles/distinct_v1','--output',WS/'pycode/results/distinct_teacher_v2'],WS/'pycode')
    run('student_comparisons',[WS/'pycode/compare_styles.py','--catalog','distinct','--run',WS/'pycode/runs/distinct_student_v1','--styles',WS/'pycode/styles/distinct_v1','--output',WS/'pycode/results/distinct_student_v1'],WS/'pycode')
    for name in ['distinct_vga','distinct_720']:
        while not (ROOT/'sim'/name/'frame_verification.json').exists():
            if time.monotonic()>deadline:raise TimeoutError('Full-frame simulation not complete: '+name)
            time.sleep(5)
    for profile in ['720p','vga']:
        run('build_'+profile,[ROOT/'create_project.py','--profile',profile,'--build'],ROOT/'build')
        run('signoff_'+profile,[ROOT/'scripts/signoff.py','--profile',profile],ROOT/'build')
    run('architecture',[ROOT/'scripts/update_architecture.py'],ROOT/'build')
    print('FINAL DISTINCT VALIDATION AND BOTH SIGNED BITSTREAMS COMPLETE',flush=True)
if __name__=='__main__':main()
