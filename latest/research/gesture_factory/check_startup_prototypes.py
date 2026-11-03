"""Test a boot preset with the production C extractor and integer distance.

The four medoids per class must be genuine training examples. Class support,
negative acceptance and per-digit recall gate the hardware handoff.
"""
from pathlib import Path
import ctypes
import json
import numpy as np

ROOT = Path(__file__).resolve().parent
BOARD = ROOT.parents[1] / "elinx/projects/camera_art_ten_paint"
P32 = ctypes.POINTER(ctypes.c_uint32)
P8 = ctypes.POINTER(ctypes.c_uint8)

def mirror(x):
    hog = x[..., :64].reshape(-1,4,4,4)[:,:,::-1, :][:,:,:,[0,3,2,1]]
    gray = x[...,64:128].reshape(-1,8,8)[:,:,::-1]
    mask = x[...,128:].reshape(-1,8,8)[:,:,::-1]
    return np.concatenate([a.reshape(-1,64) for a in (hog,gray,mask)],axis=1)

def distances(x, bank):
    # Equivalent integer distance to cal_distance_view for normal and mirrored ROI.
    options = []
    for view in (x,mirror(x)):
        diff=np.abs(view.astype(np.int16)[:,None]-bank.astype(np.int16)[None])
        options.append((diff[:,:,:64].sum(2)+diff[:,:,64:128].sum(2)//2+2*diff[:,:,128:].sum(2))//224)
    return np.minimum(*options)

def features(ds):
    lib=ctypes.CDLL(str(BOARD/"sim/classifier_v2/calibrated.dll"))
    lib.input_words.argtypes=[P32]
    lib.cal_predict.argtypes=[P32]
    lib.trace_features.argtypes=[P8]
    lib.cal_capture_background.argtypes=[ctypes.c_uint]
    bg=np.zeros(2048,np.uint32)
    lib.input_words(bg.ctypes.data_as(P32))
    for i in range(3):
        assert lib.cal_capture_background(i)==0
    out=[]; keep=[]
    for index,(rgb,mask) in enumerate(zip(ds["rgb"],ds["mask"])):
        pic=np.where(mask[:,:,None]>0,rgb,0).astype(np.uint16)
        pixels=((pic[:,:,0]>>3)<<11)|((pic[:,:,1]>>2)<<5)|(pic[:,:,2]>>3)
        words=np.ascontiguousarray(pixels,dtype="<u2").view("<u4").ravel()
        lib.input_words(words.ctypes.data_as(P32))
        metrics=np.zeros(6,np.uint32)
        lib.cal_predict(metrics.ctypes.data_as(P32))
        if metrics[5]!=4:continue  # reached classification but no personal templates loaded
        f=np.zeros(192,np.uint8)
        lib.trace_features(f.ctypes.data_as(P8))
        out.append(f);keep.append(index)
    return np.stack(out),np.asarray(keep)

def main():
    ds=np.load(ROOT/"build/factory_masks_reviewed.npz")
    f,keep=features(ds)
    labels,split=ds["labels"][keep],ds["split"][keep]
    protos=[]; limits=[]; support=[]
    for digit in range(10):
        train=f[(labels==digit)&(split=="train")]
        support.append(len(train))
        dm=distances(train,train)
        chosen=[int(dm.sum(1).argmin())]
        while len(chosen)<min(4,len(train)):
            cost=np.minimum(dm[:,chosen].min(1)[:,None],dm).sum(0)
            cost[chosen]=np.iinfo(cost.dtype).max
            chosen.append(int(cost.argmin()))
        protos.append(train[chosen])
        limits.append(int(np.clip(2*dm[np.ix_(chosen,chosen)].max()+8,14,40)))
    ids=np.flatnonzero(split=="test")
    scores=np.stack([distances(f[ids],bank).min(1) for bank in protos],axis=1)
    order=np.argsort(scores,axis=1,kind="stable");best=order[:,0];rows=np.arange(len(ids))
    first=scores[rows,best]; gap=scores[rows,order[:,1]]-first
    chosen=np.where((first<=np.asarray(limits)[best])&(gap>=np.maximum(first//8,2)),best,10)
    # Include foreground extraction failure as rejection when scoring all labeled inputs.
    all_labels=ds["labels"][ds["split"]=="test"]
    all_pred=np.full(len(all_labels),10)
    all_pred[np.searchsorted(np.flatnonzero(ds["split"]=="test"),keep[ids])]=chosen
    cm=np.bincount(all_labels*11+all_pred,minlength=121).reshape(11,11)
    counts=cm.sum(1)
    recall=[float(cm[k,k]/counts[k]) if counts[k] else None for k in range(10)]
    reasons=[]
    if min(support)<100 or min(counts[:10])<30:reasons.append("insufficient real/person-held-out class support")
    if any(r is None or r<.8 for r in recall):reasons.append("recall below 80% or absent")
    if cm[10,:10].sum()/max(1,counts[10])>.02:reasons.append("negative false acceptance exceeds 2%")
    if cm.trace()/counts.sum()<.9:reasons.append("accuracy below 90%")
    metric=dict(result="NOT_READY" if reasons else "OFFLINE_PASS",reasons=reasons,train_support=support,
        counts=counts.tolist(),recall=recall,accuracy=float(cm.trace()/counts.sum()),confusion=cm.tolist(),
        negative_false_accept=int(cm[10,:10].sum()),negative_total=int(counts[10]),
        scope="People-disjoint public pictures; offline hand masks composited against empty background; production C feature extractor. No physical measurement.")
    out=ROOT/"build/startup_prototypes.json"
    out.write_text(json.dumps(metric,indent=2),encoding="utf8")
    print(json.dumps({k:v for k,v in metric.items() if k not in ["confusion","scope"]}))
if __name__=="__main__":
    main()
