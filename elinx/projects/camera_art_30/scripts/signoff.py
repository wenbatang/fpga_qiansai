"""Fail closed: four-model simulation, source binding, board pins, native CDC and STA."""
from pathlib import Path
import json,hashlib,re,shutil,tempfile,copy
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'build/720p'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def check_selection():
    import numpy as np
    selected=json.loads((ROOT/'build/model_selection.json').read_text(encoding='utf-8'))
    wanted=[(0,0,'vangogh'),(1,3,'papercut'),(2,4,'comic'),(3,5,'inkwash')]
    assert [(r['slot'],r['source_slot'],r['name']) for r in selected['styles']]==wanted
    assert selected['rom_bytes']==4864 and selected['stride_bytes']==1216
    actual=sorted(p.name for p in (ROOT/'parameters/c8').iterdir() if p.is_dir())
    assert actual==[f'{slot:02d}_{name}' for slot,_,name in wanted]
    parameters=[];blob=bytearray();maximum=0
    for row in selected['styles']:
        folder=ROOT/'parameters/c8'/f"{row['slot']:02d}_{row['name']}"
        meta=json.loads((folder/'metadata.json').read_text(encoding='utf-8'))
        assert meta['slot']==row['source_slot'] and meta['name']==row['name'] and meta['architecture']=='c8'
        assert len(meta['layers'])==10 and meta['bytes']==1159
        for key in ['npz','bin']:assert sha(folder/f'parameters.{key}')==meta[f'{key}_sha256']==row[f'{key}_sha256']
        data=np.load(folder/'parameters.npz');raw=bytearray()
        for i in range(10):
            w=data[f'w{i}'].astype(np.int64);bias=data[f'b{i}'].astype(np.int64);shift=data[f'shift{i}']
            maximum=max(maximum,int((np.abs(w).sum((1,2,3))*255+np.abs(bias)).max()))
            assert np.all(shift>=0) and np.all(shift<=20)
            for key,bits,dtype in [('w',8,'i1'),('b',32,'<i4'),('shift',8,'u1')]:
                values=data[f'{key}{i}'];items=[int(v)&((1<<bits)-1) for v in values.flatten()]
                assert [int(v,16) for v in (folder/f'layer{i}_{key}.mem').read_text().split()]==items
                raw.extend(values.astype(dtype).tobytes())
        assert len(raw)==1159 and bytes(raw)==(folder/'parameters.bin').read_bytes()
        blob.extend(raw+bytes(1216-len(raw)));parameters.append(dict(meta,local_slot=row['slot'],source_slot=row['source_slot']))
    assert maximum<2**23
    words=[int(v,16) for v in (B/'weights47.mem').read_text().split()]
    assert len(words)==1216 and b''.join(v.to_bytes(4,'little') for v in words)==bytes(blob)
    from shared import audit as shared_audit
    return parameters,shared_audit()
def check_constraints():
    from native_constraints import assemble
    # Regenerate in an isolated directory: never overwrite constraints used by
    # a completed route merely to make an audit appear current.
    with tempfile.TemporaryDirectory(prefix='audit_sdc_',dir=ROOT/'build') as location:
        folder=Path(location);assert folder.resolve().is_relative_to((ROOT/'build').resolve())
        (folder/'outflow').mkdir()
        for name in ['ti60_camera.map.v','ti60_camera.pt.sdc']:shutil.copy2(B/'outflow'/name,folder/'outflow'/name)
        shutil.copy2(B/'dphy_cdc_proof.json',folder/'dphy_cdc_proof.json')
        assemble(folder)
        assert (folder/'ti60_camera.sdc').read_bytes()==(B/'ti60_camera.sdc').read_bytes(),'SDC differs from exact native allowlist regeneration'
        assert json.loads((folder/'cdc_constraints.json').read_text())==json.loads((B/'cdc_constraints.json').read_text())
    return dict(sdc_sha256=sha(B/'ti60_camera.sdc'),pt_sdc_sha256=sha(B/'outflow/ti60_camera.pt.sdc'),native_constraints_sha256=sha(ROOT/'scripts/native_constraints.py'))
def check_receipt(folder):
    path=ROOT/'sim'/folder/'verification.json';r=json.loads(path.read_text(encoding='utf-8'))
    assert r['result']=='PASS',folder
    sources=r.get('sources_sha256');logs=r.get('logs_sha256')
    assert isinstance(sources,dict) and sources and isinstance(logs,dict) and logs,'Empty simulation binding: '+folder
    for p,s in {**sources,**logs}.items():assert sha(p)==s,'Stale simulation: '+p
    assert any(Path(p).resolve().is_relative_to((ROOT/'rtl').resolve()) for p in sources),'No production RTL bound by '+folder
    candidates=[p for p in sources if Path(p).resolve().is_relative_to((ROOT/'build/experiments').resolve())]
    if candidates or r.get('production_aliases'):
        assert folder=='dma_mapped','Unexpected experimental source in production verification: '+folder
        check_production_aliases(r)
    return r

def check_production_aliases(r):
    """Verify an unchanged true-PASS archive plus exact whole-source aliases.

    Candidate execution is retained as candidate execution. These checks permit
    reuse only when the compiled files and promoted production files are equal;
    they do not relabel simulation geometry or create new functional coverage.
    """
    folder=ROOT/'sim/dma_mapped';archive=folder/'candidate_verification.json'
    original=json.loads(archive.read_text(encoding='utf-8'))
    assert original['result']=='PASS' and original['integer_max_abs_error']==0
    assert original['styles']==[0,1,2,3] and original['pixels_per_style']==256*40
    assert 'production_aliases' not in original,'Archive must be the unmodified candidate receipt'
    assert original.get('sources_sha256') and original.get('logs_sha256')
    for p,s in {**original['sources_sha256'],**original['logs_sha256']}.items():assert sha(p)==s,'Stale archived candidate evidence: '+p
    binding=ROOT/'build/probe_dma/inputs.json';net=ROOT/'build/probe_dma/outflow/tiny_dma_probe.map.v'
    assert original['sources_sha256'][str(binding)]==sha(binding)
    assert original['sources_sha256'][str(net)]==sha(net)
    mapped_inputs=json.loads(binding.read_text(encoding='utf-8'))
    for p,s in mapped_inputs.items():assert sha(p)==s,'Candidate map input no longer frozen: '+p
    expected=copy.deepcopy(original);aliases=[]
    for name,production in [('tiny_pointwise_fixed.sv',ROOT/'rtl/tiny_pointwise.sv'),('video_tile_engine_fixed.sv',ROOT/'rtl/p720/video_tile_engine_async.sv')]:
        candidate=ROOT/'build/experiments'/name
        assert candidate.read_bytes()==production.read_bytes(),'Candidate/production promotion differs'
        digest=sha(candidate)
        assert mapped_inputs[str(candidate)]==original['sources_sha256'][str(candidate)]==digest
        aliases.append(dict(compiled_source=str(candidate),production_source=str(production),sha256=digest,equivalence='Complete source files are byte-for-byte identical; no new simulation claimed'))
        expected['sources_sha256'][str(production)]=digest
    finalizer=ROOT/'sim/finalize_dma_provenance.py'
    expected['production_aliases']=aliases
    expected['sources_sha256'][str(archive)]=sha(archive)
    expected['sources_sha256'][str(finalizer)]=sha(finalizer)
    expected['scope']+='; compiled fixed candidate sources and promoted production files verified byte-identical'
    assert expected==r,'Alias finalization changed results, logs, coverage, inputs or unapproved fields'
    assert r['logs_sha256']==original['logs_sha256']
    return aliases
def audit(bit=True):
    m=json.loads((B/'build_inputs.json').read_text(encoding='utf-8'))
    assert m['format_version']==2 and m['inputs_sha256'],'Re-map with the complete frozen input manifest'
    for p,s in m['inputs_sha256'].items():assert Path(p).resolve().is_relative_to(ROOT.resolve()) and sha(p)==s,'Mapped input changed: '+p
    for p,s in m['sources'].items():assert sha(p)==s,'Source changed after mapping: '+p
    for file,key in [('ti60_camera.xml','project'),('ti60_camera.peri.xml','interface'),('weights47.mem','weight_rom'),('firmware.bin','firmware')]:assert sha(B/file)==m[key]
    sims={}
    for folder in ['pointwise','kernel','dma','full','control','sapphire','mapped','dma_mapped','top_safety','keys','fps_jobs','fps_reader','fps_write_pressure2','scheduling']:
        r=check_receipt(folder);sims[folder]=sha(ROOT/'sim'/folder/'verification.json')
    mapped=check_receipt('mapped');probe_inputs=json.loads((ROOT/'build/probe/inputs.json').read_text())
    for p,s in probe_inputs.items():assert sha(p)==s,'Stale mapped probe input: '+p
    assert str(ROOT/'build/probe/outflow/tiny_probe.map.v') in mapped['sources_sha256']
    from board_spec import audit as electrical
    board=electrical(B,camera=True,top=B/'rtl/ti60_camera_ppi_top.sv')
    firmware=json.loads((B/'firmware_manifest.json').read_text(encoding='utf-8'));lanes=[]
    assert firmware['result']=='PASS' and firmware['styles']==4 and firmware['config_writes_per_style']==346 and firmware['weights_rom_bytes']==4864 and len(firmware['lanes'])==4
    for p,s in firmware['files'].items():assert sha(p)==s,'Firmware source changed after compilation: '+p
    for name,digest in firmware['lanes'].items():
        assert sha(B/name)==digest and sha(B/'ip/control_soc'/name)==digest
        lanes.append([int(v,2) for v in (B/name).read_text(encoding='ascii').split()])
    image=bytes(value for row in zip(*lanes) for value in row);assert image[:firmware['firmware_bytes']]==(B/'firmware.bin').read_bytes()
    assert sha(B/'firmware.bin')==firmware['firmware_sha256'] and firmware['firmware_bytes']<30720
    old=ROOT.parent/'camera_art_styles/build/camera_720_fast/ti60_camera.peri.xml'
    assert (B/'ti60_camera.peri.xml').read_bytes()==old.read_bytes(),'No board or PLL change authorized'
    report=(B/'outflow/ti60_camera.timing.rpt').read_text(encoding='utf-8');assert 'Timing Model: I3' in report
    summary=report.split('---------- 2. Clock Relationship Summary (begin) ----------')[1].split('---------- Clock Relationship Summary (end)')[0]
    rows=[float(x[1]) for x in re.findall(r'^\s*\S+\s+\S+\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+\(R-R\)',summary,re.M)];assert len(rows)>=40 and min(rows)>=0,'Negative/missing timing relationships'
    cdc=json.loads((B/'cdc_constraints.json').read_text());proof=json.loads((B/'dphy_final_proof.json').read_text());assert proof['map_sha256']==sha(B/'outflow/ti60_camera.map.v') and proof['vdb_sha256']==sha(B/'outflow/ti60_camera.vdb')
    assert len(proof['first_stages'])==8 and all(x['only_second_stage_endpoint'] and x['interstage_slack_ns']>0 for x in proof['first_stages'])
    for file,s in proof['reports'].items():assert sha(B/'outflow'/file)==s
    sdc=(B/'ti60_camera.sdc').read_text();assert 'set_clock_groups' not in sdc and 'set_multicycle_path' not in sdc
    setuptext,holdtext=summary.split('Hold (Min) Clock Relationship')
    def slack(text):return [float(x[1]) for x in re.findall(r'^\s*\S+\s+\S+\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+\(R-R\)',text,re.M)]
    full=check_receipt('full');assert full['pixels']==1280*720 and full['styles']==[0,1,2,3]
    assert len(full['per_style'])==4 and [r['slot'] for r in full['per_style']]==[0,1,2,3]
    for case in full['per_style']:
        assert case['pixels']==1280*720 and case['integer_max_abs_error']==0 and case['ui_cycles']>0
        assert abs(case['model_fps']-full['ui_hz']/case['ui_cycles'])<1e-9 and case['model_fps']>30
    parameters,shared_proof=check_selection();constraint_proof=check_constraints()
    bounds=json.loads((ROOT/'build/accumulator_bound.json').read_text());assert bounds['max_abs_sum_bound']<2**23 and bounds['styles_compared']==4
    rpt=(B/'outflow/ti60_camera.map.rpt').read_text(encoding='utf-8');resources={name:int(re.search(name+r'\s*:\s*(\d+)',rpt)[1]) for name in ['EFX_RAM10','EFX_DSP48','EFX_FF','EFX_LUT4']}
    assert resources['EFX_RAM10']<=256 and resources['EFX_DSP48']<=160
    place=(B/'outflow/ti60_camera.place.rpt').read_text(encoding='utf-8');match=re.search(r'^XLRs:\s*(\d+)\s*/\s*(\d+)',place,re.M);assert match and int(match[1])<=int(match[2])==60800
    result=dict(result='PASS',process=[1280,720],feature_branch=[640,360],styles=4,display=[1280,720,60],target_inference_fps=30,board_fps_verified=False,board_programmed=False,setup_min_ns=min(slack(setuptext)),hold_min_ns=min(slack(holdtext)),resources=resources,full_frame_model=dict(ui_cycles=full['ui_cycles'],ui_hz=full['ui_hz'],cnn_period_ns=full['cnn_period_ns'],model_fps=full['model_fps'],scope=full['scope']),electrical=board,simulations=sims,parameters=parameters,accumulator_bound=bounds,inputs=m,cdc=cdc)
    artifacts=[B/'outflow'/name for name in ['ti60_camera.map.v','ti60_camera.vdb','ti60_camera.map.rpt','ti60_camera.place.rpt','ti60_camera.timing.rpt','ti60_camera.pt.sdc']]
    artifacts += [B/name for name in ['ti60_camera.sdc','cdc_constraints.json','dphy_cdc_proof.json','dphy_final_proof.json','build_inputs.json']]
    assert (B/'outflow/ti60_camera.map.v').stat().st_mtime_ns>=(B/'build_inputs.json').stat().st_mtime_ns,'Netlist predates current input capture'
    result.update(shared_proof=shared_proof,constraint_regeneration=constraint_proof,xlr_used=int(match[1]),full_frame_all_styles=full['per_style'],dma_mapped_production_aliases=check_receipt('dma_mapped').get('production_aliases',[]),cad_artifacts_sha256={str(p):sha(p) for p in artifacts},validation_scripts_sha256={str(ROOT/'scripts'/name):sha(ROOT/'scripts'/name) for name in ['signoff.py','final_review.py','simutil.py']})
    if bit:
        path=B/'outflow/ti60_camera.bit'
        assert path.stat().st_mtime_ns>=max(p.stat().st_mtime_ns for p in artifacts),'Bit predates mapped/routed/currently-proven design; regenerate config'
        result['bitstream_sha256']=sha(path)
    return result
