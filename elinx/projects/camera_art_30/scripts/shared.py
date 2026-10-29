"""Read-only check of shared constants; never rewrite already-mapped RTL/XML."""
from pathlib import Path
import numpy as np,json,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];STYLE=ROOT
def packed(values,bits):
    values=np.asarray(values).flatten();n=sum((int(v)&((1<<bits)-1))<<(i*bits) for i,v in enumerate(values));return f"{len(values)*bits}'h{n:x}"
def audit():
    paths=sorted((STYLE/'parameters/c8').glob('*/parameters.npz'));allparams=[np.load(p) for p in paths];base=allparams[0];assert len(paths)==4
    text='// Generated from frozen learned C8 exports; identical in all47 styles.\nmodule tiny_shared_params #(parameter LAYER=1,NW=72,COUT=8)(output wire[NW*8-1:0]weights,output wire[COUT*24-1:0]biases,output wire[COUT*5-1:0]shifts);\ngenerate\n'
    for li,layer in enumerate([1,3,5,7,9]):
        for d in allparams:
            for key in ['w','b','shift']:assert np.array_equal(d[f'{key}{layer}'],base[f'{key}{layer}'])
        text+=('if' if li==0 else 'else if')+f'(LAYER=={layer})begin\nassign weights={packed(base[f"w{layer}"],8)};\nassign biases={packed(base[f"b{layer}"],24)};\nassign shifts={packed(base[f"shift{layer}"],5)};\nend\n'
    text+='else begin assign weights=0;assign biases=0;assign shifts=0;end\nendgenerate\nendmodule\n';assert (ROOT/'rtl/tiny_shared_params.sv').read_text(encoding='ascii')==text,'Frozen shared RTL differs from selected four learned exports'
    manifest=json.loads((ROOT.parents[2]/'style_model/runs/tiny47_c8_final/int8/manifest.json').read_text(encoding='utf-8'));maximum=max(l['bound'] for r in manifest['records'] if r['slot'] in [0,3,4,5] for l in r['layers']);assert maximum<2**23
    declared=json.loads((ROOT/'build/accumulator_bound.json').read_text(encoding='utf-8'))
    assert declared['result']=='PASS' and declared['styles_compared']==4 and maximum<=declared['max_abs_sum_bound']<2**23
    return dict(result='PASS',styles_compared=4,source_slots=[0,3,4,5],shared_layers=[1,3,5,7,9],max_abs_sum_bound=maximum,declared_conservative_bound=declared['max_abs_sum_bound'],shared_rtl_sha256=__import__('hashlib').sha256((ROOT/'rtl/tiny_shared_params.sv').read_bytes()).hexdigest(),scope='Read-only constant equality/range audit; not hardware execution')
if __name__=='__main__':print(json.dumps(audit(),indent=2))
