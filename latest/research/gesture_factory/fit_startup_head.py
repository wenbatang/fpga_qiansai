"""Fit a 192-32-11 integer head for the actual C feature interface and evaluate rejects."""
from pathlib import Path
import json
import hashlib
import argparse
import numpy as np
import torch
from torch import nn
from check_startup_prototypes import ROOT, features, mirror

def quant_layer(layer, ins, outs):
    coef=layer.weight.detach().numpy()*ins/outs
    shift=np.clip(np.floor(np.log2(127/np.maximum(1e-10,np.abs(coef).max(axis=1)))),0,16).astype(int)
    scale=2**shift
    w=np.floor(coef*scale[:,None]+.5).clip(-127,127).astype(np.int8)
    b=np.floor(layer.bias.detach().numpy()/outs*scale+.5).astype(np.int32)
    return w,b,shift

def infer(x,layers):
    for i,(w,b,s) in enumerate(layers):
        x=(x.astype(np.int64)@w.T+b+np.where(s>0,2**np.maximum(0,s-1),0))>>s
        if i==0:x=x.clip(0,255)
    return x

def classify(scores,threshold):
    ids=scores.argmax(axis=1); top=np.sort(scores,axis=1)
    return np.where(top[:,-1]-top[:,-2]>=threshold,ids,10)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--expanded',action='store_true',help='Train with extra compatible Chinese digits and clean ILY photos; hold out the original HaGRID 7')
    expanded=parser.parse_args().expanded
    suffix='_expanded' if expanded else ''
    torch.set_num_threads(2);torch.manual_seed(49327)
    src=ROOT/'build/factory_masks_reviewed.npz'
    dataset=np.load(src); feat,idx=features(dataset)
    labels=dataset['labels'][idx];splits=dataset['split'][idx]
    tr=splits=='train';val=splits=='val';test=splits=='test'
    train_x,train_y=feat[tr],labels[tr]
    sources={}; held7=feat[tr & (labels==7)]
    if expanded:
        train_x,train_y=train_x[train_y!=7],train_y[train_y!=7]
        legacy_path=ROOT/'build/masks.npz'
        clean_path=ROOT/'build/clean_love.npz'
        legacy=np.load(legacy_path); lf,li=features(legacy)
        use=(legacy['split'][li]=='train') & np.isin(legacy['labels'][li],[1,2,4,5,6,8,9])
        clean=np.load(clean_path); cf,ci=features(clean)
        fingerprints=[hashlib.sha256((ROOT/'build/clean_love'/str(clean['names'][i])).read_bytes()).hexdigest() for i in ci]
        _,unique=np.unique(fingerprints,return_index=True)
        cf=cf[np.sort(unique)]
        train_x=np.concatenate([train_x,lf[use],cf])
        train_y=np.concatenate([train_y,legacy['labels'][li][use],np.full(len(cf),7)])
        sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (legacy_path,clean_path)}
    x=torch.from_numpy(np.concatenate([train_x,mirror(train_x)])).float()/255
    y=torch.from_numpy(np.tile(train_y,2)).long()
    groups=[torch.where(y==k)[0] for k in range(11)]
    net=nn.Sequential(nn.Linear(192,32),nn.Hardtanh(0,4),nn.Linear(32,11))
    opt=torch.optim.AdamW(net.parameters(),lr=.003)
    best=-1
    for step in range(2000):
        batch=torch.cat([g[torch.randint(len(g),(12,))] for g in groups])
        loss=nn.functional.cross_entropy(net((x[batch]+torch.randn_like(x[batch])*.025).clamp(0,1)),y[batch])
        opt.zero_grad();loss.backward();opt.step()
        if (step+1)%100:continue
        quant=[quant_layer(net[0],1/255,4/255),quant_layer(net[2],4/255,1/32)]
        logits=infer(feat[val],quant)
        for threshold in range(0,257,8):
            pred=classify(logits,threshold);target=labels[val]
            false=np.mean(pred[target==10]!=10)
            if false>.02:continue
            acc=np.mean([np.mean(pred[target==k]==k) for k in range(10) if np.any(target==k)])
            if acc>best:
                best=float(acc); model=quant; margin=threshold; opt_step=step+1
    scores=infer(feat[test],model)
    pred=classify(scores,margin);truth=dataset['labels'][dataset['split']=='test']
    full=np.full(len(truth),10);full[np.searchsorted(np.where(dataset['split']=='test')[0],idx[test])]=pred
    conf=np.bincount(truth*11+full,minlength=121).reshape(11,11)
    recall=[float(conf[i,i]/conf[i].sum()) if conf[i].sum() else None for i in range(10)]
    ext=ROOT/'build/clean_love.npz'
    extra={}
    if expanded:
        v=classify(infer(held7,model),margin)
        extra=dict(attempts=len(v),correct=int((v==7).sum()),reject=int((v==10).sum()),wrong=int(((v!=10)&(v!=7)).sum()),note='Original HaGRID 7 excluded from this training. One sample, no generalization claim.')
    elif ext.exists():
        ds=np.load(ext);f,keep=features(ds);v=classify(infer(f,model),margin)
        extra=dict(attempts=len(ds['rgb']),features=len(keep),correct=int((v==7).sum()),reject=int((v==10).sum()),wrong=int(((v!=10)&(v!=7)).sum()),files=ds['names'].tolist(),note='Separate curated collection, participant IDs unavailable; repeated source frames possible.')
    payload={k+str(i):v for i,layer in enumerate(model) for k,v in zip(('w','b','s'),layer)}
    np.savez_compressed(ROOT/('build/startup_head'+suffix+'.npz'),**payload)
    reasons=[]
    support={part:[int(np.sum((dataset['labels']==k)&(dataset['split']==part))) for k in range(10)] for part in ('train','val','test')}
    support['train']=[int((train_y==k).sum()) for k in range(10)]
    if any(min(support[part]) < limit for part,limit in [('train',100),('val',20),('test',30)]):reasons.append('insufficient independent class support')
    if any(v is None or v < .8 for v in recall):reasons.append('per-class recall below 80% or missing')
    if conf.trace()/conf.sum()<.9:reasons.append('test accuracy below 90%')
    if conf[10,:10].sum()/max(1,conf[10].sum())>.02:reasons.append('non-target false accept above 2%')
    if not extra or extra['correct']/max(1,extra['attempts'])<.8:reasons.append('external digit 7 recall below 80% or missing')
    stat=dict(result='NOT_READY' if reasons else 'OFFLINE_PASS_ONLY',reasons=reasons,support=support,additional_training_sha256=sources,selected_on_validation_step=opt_step,margin_in_1_over_32=margin,
        validation_macro_recall_with_negative_gate=best,test_accuracy=float(conf.trace()/conf.sum()),
        negative_false_accept=[int(conf[10,:10].sum()),int(conf[10].sum())],per_digit_recall=recall,
        confusion=conf.tolist(),external_digit7=extra,train_source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),
        quantized_weight_count=192*32+32*11,scope='Integer software classifier over production C features extracted from masked RGB565 against a controlled background. No on-board result.')
    (ROOT/('build/startup_head_score'+suffix+'.json')).write_text(json.dumps(stat,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in stat.items() if k not in ['confusion','scope','external_digit7']}))
    print('independent digit 7', {k:v for k,v in extra.items() if k not in ['files','note']})
if __name__=='__main__':main()
