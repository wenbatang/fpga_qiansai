"""Fresh full720 delivery review; no board, UART or programming actions."""
from pathlib import Path
import hashlib,importlib.util,json,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'build/720p';WS=ROOT.parents[2]
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(WS/'pycode/full720_style'))


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def review():
    from signoff import audit,check_receipt
    signed=audit(True);assert signed==json.loads((B/'signoff.json').read_text(encoding='utf-8')),'Stored signoff differs from fresh audit'
    reuse=json.loads((ROOT/'build/reuse_manifest.json').read_text(encoding='utf-8'));base=ROOT.parent/'camera_art_30'
    assert Path(reuse['source_project']).resolve()==base.resolve()
    for path,item in reuse['sources'].items():
        assert Path(path).resolve().is_relative_to(base.resolve())
        assert sha(path)==item['sha256'],'Preserved C8 source changed: '+path
    oldbit=base/'build/720p/outflow/ti60_camera.bit';assert sha(oldbit)==reuse['source_bit_sha256']
    oldrf=ROOT.parent/'camera_art_styles/build/camera_fps_rf33_srl_720/outflow/ti60_camera.bit'
    assert sha(oldrf)=='2a288989e1fdf84264a3579f7bd823b5f903aac50f661db0636ffd072cda2398'
    reference=WS/'style_model/elinx/build/720p/outflow/ti60_camera.bit'
    base_reuse=json.loads((base/'build/reuse_manifest.json').read_text(encoding='utf-8'))
    assert sha(reference)==base_reuse['source_bit_sha256']
    for path,item in base_reuse['sources'].items():assert sha(path)==item['sha256'],'Original style_model changed: '+path
    from network import load
    from integer import model_layers
    selected=json.loads((ROOT/'build/model_selection.json').read_text(encoding='utf-8'))
    model,meta=load(Path(selected['source']));assert meta['step']==6000 and meta['qat'] and meta['full_resolution']
    for path,digest in {**meta['source_hashes'],**meta['teacher_hashes']}.items():assert sha(path)==digest,'Training source changed: '+path
    split=json.loads((WS/'pycode/full720_style/runs/c6_v1/split.json').read_text(encoding='utf-8'))
    assert split==json.loads((WS/'style_model/runs/tiny47_c8_final/split.json').read_text(encoding='utf-8'))
    # Recompute every quantized value from the actual trained checkpoint.
    for slot,name in enumerate(['vangogh','papercut','comic','inkwash']):
        exported=np.load(ROOT/'parameters/c6'/f'{slot:02d}_{name}'/'parameters.npz')
        for index,layer in enumerate(model_layers(model,slot)):
            for key in ['w','b','shift']:assert np.array_equal(layer[key],exported[f'{key}{index}']),(slot,index,key)
    spec=importlib.util.spec_from_file_location('full720_cam4',ROOT/'pc/camera_view.py');cam=importlib.util.module_from_spec(spec);spec.loader.exec_module(cam)
    parser=cam.self_test();assert parser['result']=='PASS' and not parser['hardware_accessed']
    receipts={}
    for name,digest in signed['simulations'].items():
        value=check_receipt(name);assert sha(ROOT/'sim'/name/'verification.json')==digest
        receipts[name]=dict(verification_sha256=digest,sources=len(value['sources_sha256']),logs=len(value['logs_sha256']),scope=value['scope'])
    assert (ROOT/'sim/mapped/vsim.log').read_text(encoding='utf-8',errors='replace').count('PASS FULLRES kernel style')==4
    for kind in ['mapped','mapped_dma']:
        value=check_receipt(kind)
        assert any(Path(p).suffix=='.sv' and Path(p).is_relative_to(ROOT/'rtl') for p in value['sources_sha256'])
    docs=[ROOT/'README.md',ROOT/'architecture.html',*[ROOT/'docs'/n for n in ['model.md','implementation.md','validation.md','performance.md']]]
    assert all(p.exists() for p in docs)
    files={str(p):sha(p) for p in [*docs,*sorted((ROOT/'scripts').glob('*.py')),*sorted((ROOT/'pc').glob('*.py'))]}
    return dict(result='PASS',full_resolution=True,process=[1280,720],feature_branch=[1280,720],downsample=False,styles=4,
        trained_steps=meta['step'],quantized_checkpoint_reexport_equal=True,old_c8_bit_preserved=True,old_rf33_bit_preserved=True,reference_style_model_preserved=True,
        bitstream_sha256=signed['bitstream_sha256'],signoff_sha256=sha(B/'signoff.json'),min_model_fps=signed['min_model_fps'],full_frame_all_styles=signed['full_frame_all_styles'],
        resources=signed['resources'],xlr_used=signed['xlr_used'],setup_min_ns=signed['setup_min_ns'],hold_min_ns=signed['hold_min_ns'],
        simulations=receipts,parser=parser,delivery_files_sha256=files,board_programmed=False,board_fps_verified=False,
        scope='Fresh offline full720 numerical/CAD/electrical verification; real camera+DDR+HDMI FPS and analog measurements pending')


def main():
    try:value=review()
    except Exception as error:
        value=dict(result='FAIL',reason=str(error),exception=type(error).__name__,board_programmed=False)
        (B/'final_review.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');raise
    (B/'final_review.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(value,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
