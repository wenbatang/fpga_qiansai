"""Independent four-style delivery audit. Fail closed; never program hardware."""
from pathlib import Path
import hashlib,importlib.util,json,sys
ROOT=Path(__file__).resolve().parents[1]
B=ROOT/'build/720p'
sys.path.insert(0,str(ROOT/'scripts'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def review():
    from signoff import audit,check_receipt,check_selection,check_constraints,check_production_aliases
    signed=audit(True)
    stored=json.loads((B/'signoff.json').read_text(encoding='utf-8'))
    assert signed==stored,'Stored signoff differs from a fresh full audit'
    reuse=json.loads((ROOT/'build/reuse_manifest.json').read_text(encoding='utf-8'))
    reference=ROOT.parents[2]/'style_model/elinx'
    assert Path(reuse['source_project']).resolve()==reference.resolve()
    assert reuse['reference_read_only'] and not reuse['board_programmed']
    for path,item in reuse['sources'].items():
        assert Path(path).resolve().is_relative_to(reference.resolve())
        assert sha(path)==item['sha256'],'Original reference source changed: '+path
    reference_bit=reference/'build/720p/outflow/ti60_camera.bit'
    assert sha(reference_bit)==reuse['source_bit_sha256'],'Original reference bit changed'
    selection=json.loads((ROOT/'build/model_selection.json').read_text(encoding='utf-8'))
    parameters,shared=check_selection()
    reference_files={}
    for row in selection['styles']:
        source=ROOT.parents[2]/'style_model/parameters/c8'/f"{row['source_slot']:02d}_{row['name']}"
        target=ROOT/'parameters/c8'/f"{row['slot']:02d}_{row['name']}"
        assert Path(row['source']).resolve()==source.resolve()
        for path in source.iterdir():
            if path.is_file():
                assert (target/path.name).read_bytes()==path.read_bytes(),'Copied parameter differs from source: '+str(path)
                reference_files[str(path)]=sha(path)
    # Every test must bind nonempty logs and actual current production source.
    receipts={}
    for name,digest in signed['simulations'].items():
        receipt=check_receipt(name);path=ROOT/'sim'/name/'verification.json'
        assert sha(path)==digest
        receipts[name]=dict(verification_sha256=digest,source_count=len(receipt['sources_sha256']),log_count=len(receipt['logs_sha256']),scope=receipt['scope'])
    kernel_log=(ROOT/'sim/mapped/vsim.log').read_text(encoding='utf-8',errors='replace')
    assert kernel_log.count('PASS MAPPED learned mode')==4
    dma=check_receipt('dma_mapped')
    assert any(Path(path).name.endswith('.map.v') and Path(path).resolve().is_relative_to((ROOT/'build').resolve()) for path in dma['sources_sha256']),'DMA mapped regression must bind the actual local netlist'
    assert str(ROOT/'rtl/p720/video_tile_engine_async.sv') in dma['sources_sha256'],'DMA mapped regression omitted production DMA'
    aliases=check_production_aliases(dma) if dma.get('production_aliases') else []
    assert aliases==signed['dma_mapped_production_aliases']
    spec=importlib.util.spec_from_file_location('camera_art_30_cam4',ROOT/'pc/camera_view.py')
    cam4=importlib.util.module_from_spec(spec);spec.loader.exec_module(cam4)
    parser=cam4.self_test();assert parser['result']=='PASS' and not parser['hardware_accessed']
    # Disabled reference generators must reject execution before performing I/O.
    disabled={}
    for name in ['integrate.py','organize_parameters.py','finish.py']:
        path=ROOT/'scripts'/name;text=path.read_text(encoding='utf-8')
        assert 'raise SystemExit(' in text and 'Disabled:' in text
        assert not any(token in text for token in ['write_text(','write_bytes(','shutil.','subprocess.'])
        disabled[name]=sha(path)
    constraints=check_constraints()
    assert constraints==signed['constraint_regeneration']
    validation_files={str(p):sha(p) for directory in [ROOT/'scripts',ROOT/'pc'] for p in sorted(directory.glob('*.py'))}
    for path in [ROOT/'README.md',ROOT/'architecture.html',ROOT/'docs/model_quality.md',ROOT/'docs/reference_review.md']:
        assert path.exists();validation_files[str(path)]=sha(path)
    return dict(result='PASS',project='build/720p/ti60_camera.xml',styles=4,source_slots=[0,3,4,5],process=[1280,720],feature_branch=[640,360],display=[1280,720,60],
                bitstream_sha256=signed['bitstream_sha256'],signoff_sha256=sha(B/'signoff.json'),
                original_source_files_unchanged=len(reuse['sources']),original_bit_unchanged=True,
                reference_bit=str(reference_bit),reference_parameters_sha256=reference_files,
                selected_parameter_folders=4,shared_parameters=shared,simulations=receipts,
                learned_kernel_mapped_pixels=4*24*40,dma_mapped_scope=dma['scope'],dma_mapped_production_aliases=aliases,cam4_parser=parser,
                setup_min_ns=signed['setup_min_ns'],hold_min_ns=signed['hold_min_ns'],resources=signed['resources'],xlr_used=signed['xlr_used'],
                full_frame_all_styles=signed['full_frame_all_styles'],constraint_regeneration=constraints,
                disabled_legacy_entrypoints=disabled,delivery_files_sha256=validation_files,
                board_programmed=False,board_fps_verified=False,
                scope='Fresh offline CAD/digital evidence and reference preservation; no board/analog/Flash verification')
def main():
    destination=B/'final_review.json'
    try:
        result=review()
    except Exception as error:
        result=dict(result='FAIL',reason=str(error),exception=type(error).__name__,board_programmed=False,board_fps_verified=False)
        destination.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False,indent=2));raise
    destination.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
