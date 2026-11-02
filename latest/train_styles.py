"""Continue/reproduce the12000-step painting refinement in a fresh run directory."""
from pathlib import Path
import argparse,subprocess,sys
ROOT=Path(__file__).resolve().parent
def main():
 p=argparse.ArgumentParser();p.add_argument('--run',default='reproduce_painterly');p.add_argument('--steps',type=int,default=12000);a=p.parse_args()
 subprocess.run([sys.executable,str(ROOT/'relocate.py')],check=True)
 folder=ROOT/'pycode/ten_style';source=folder/'runs/ten_painterly_probe_v1/model.pt'
 assert not (folder/'runs'/a.run/'launch.json').exists(),'Use a fresh run name; signed models are preserved'
 subprocess.run([sys.executable,'retrain_painterly_v2.py','--source',str(source),'--run',a.run,'--steps',str(a.steps),'--batch','4','--size','144'],cwd=folder,check=True)
if __name__=='__main__':main()
