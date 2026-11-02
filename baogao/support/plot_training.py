"""Plot real12000-step training log, never fabricated convergence curves."""
from pathlib import Path
import csv,numpy as np
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt
WS=Path(__file__).resolve().parents[2]
def main():
 p=WS/'pycode/ten_style/runs/ten_painterly_v2/training.csv'
 if not p.exists():p=WS/'latest/pycode/ten_style/runs/ten_painterly_v2/training.csv'
 rows=list(csv.DictReader(p.open()));assert len(rows)==12000
 steps=np.array([int(r['step']) for r in rows]);loss=np.array([float(r['loss']) for r in rows]);slot=np.array([int(r['slot']) for r in rows]);fig,axes=plt.subplots(1,2,figsize=(10,2.8),layout='constrained')
 for j in [0,1,4,9]:
  ids=slot==j;x=steps[ids];y=loss[ids];window=40;axes[0].plot(x[window-1:],np.convolve(y,np.ones(window)/window,mode='valid'),label='slot '+str(j),lw=1.1)
 axes[0].set(xlabel='Refinement step',ylabel='Weighted training loss');axes[0].legend(ncol=2,fontsize=8);axes[0].grid(alpha=.18);axes[1].bar(np.arange(10),np.bincount(slot,minlength=10),color='#247b91');axes[1].set(xlabel='Style slot',ylabel='Updates in 12000-step phase');axes[1].set_xticks(np.arange(10));axes[1].grid(axis='y',alpha=.18)
 for ax in axes:ax.spines[['top','right']].set_visible(False)
 out=WS/'baogao/assets/generated';fig.savefig(out/'training_log.pdf');fig.savefig(out/'training_log.png',dpi=220);print('Plotted12000 real rows')
if __name__=='__main__':main()
