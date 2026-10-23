"""Continue this optimization run as teacher checkpoints finish; no scheduler."""
from pathlib import Path
import argparse
import json
import subprocess
import sys
import time
from prepare_styles import ROOT


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--teacher',type=Path,default=ROOT/'runs/optimized_teacher_v2')
    parser.add_argument('--student',type=Path,default=ROOT/'runs/fpga_student_v2')
    parser.add_argument('--styles',nargs='+',default=['vangogh','inkwash','inkprint'])
    parser.add_argument('--channels',type=int,default=8)
    parser.add_argument('--depth',type=int,choices=(3,5),default=3)
    parser.add_argument('--wait-first',default='ukiyoe')
    parser.add_argument('--prerequisite',type=Path)
    parser.add_argument('--warm-start',type=Path)
    parser.add_argument('--epochs',type=int,default=18)
    parser.add_argument('--refine-quantization',action='store_true')
    parser.add_argument('--coordinate-phase',type=int,choices=(0,4),default=0)
    parser.add_argument('--lr',type=float)
    args=parser.parse_args()
    for style in args.styles:
        deadline=time.monotonic()+6*3600
        while not (args.teacher/style/'experiment.json').exists() or (args.wait_first and not (args.student/args.wait_first/'experiment.json').exists()) or (args.prerequisite and not args.prerequisite.exists()) or (args.warm_start and not (args.warm_start/style/'experiment.json').exists()):
            if time.monotonic()>deadline:raise TimeoutError(f'Teacher/student prerequisites did not finish: {style}')
            time.sleep(2)
        if (args.student/style/'experiment.json').exists():continue
        print(f'Training hardware student: {style}',flush=True)
        command=[sys.executable,'-u',str(ROOT/'train_optimized.py'),'--stage','student','--style',style,
                        '--teacher',str(args.teacher),'--output',str(args.student),'--epochs',str(args.epochs),'--size','256',
                        '--batch-size','12','--workers','2','--channels',str(args.channels),'--depth',str(args.depth),'--coordinate-phase',str(args.coordinate_phase)]
        if args.warm_start:command+=['--warm-start',str(args.warm_start),'--qat-from-start']
        if args.refine_quantization:
            command+=['--straight-through-clip','--distill-weight','48','--style-multiplier','0.5','--feature-distill-weight','0.15','--lr','0.0002']
        if args.lr:command+=['--lr',str(args.lr)]
        subprocess.run(command,check=True,cwd=ROOT)
    subprocess.run([sys.executable,str(ROOT/'export_hardware.py'),'--run',str(args.student),
                    '--output',str(args.student/'export')],check=True,cwd=ROOT)
    print('STUDENT TRAINING AND INTEGER EXPORT COMPLETE',flush=True)


if __name__=='__main__':main()
