"""Fail-closed release gate for ten full720 styles and optional RAM calibration."""
from pathlib import Path
import hashlib,json,re,shutil,tempfile
import numpy as np
ROOT=Path(__file__).resolve().parents[1];WS=ROOT.parents[2];BASE=ROOT.parent/'camera_art_ten_ui';B=ROOT/'build/720p'
SOURCE_IDS=[0,2,3,4,34,7,9,15,31,40]
TESTS=['snapshot','interaction','guard','mapped_snapshot','guard_mapped','ten_firmware','ten_sapphire','calibration_runtime','riscv_m','top_safety','ui_system','calibration_firmware','classifier_v2','gesture_stress','sapphire_latency','ten_kernel_24x40','ten_dma','ten_split','ten_split_pressure','ten_full_split','ten_mapped']

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def verify(path):
    path=Path(path);v=json.loads(path.read_text(encoding='utf-8'));assert v['result']=='PASS',path
    for key in ['sources_sha256','logs_sha256','source_hashes','teacher_hashes','outputs_sha256','training_hashes','validation_hashes','reference_hashes']:
        for p,h in v.get(key,{}).items():
            source=Path(p)
            if not source.is_absolute():
                assert path.resolve().is_relative_to(WS/'pycode/ten_style'),('Unexpected relative evidence',path,p)
                source=WS/'pycode/ten_style'/source
            assert sha(source)==h,'Stale evidence '+str(path)+': '+p
    return v,sha(path)
def inherited():
    old=json.loads((BASE/'build/720p/signoff.json').read_text(encoding='utf-8'))
    assert old['result']=='PASS' and old['bitstream_sha256']=='598a2312e477166d33e7d2cc7aa52d919913eb5d90a756221aaceabe5fe63099'
    for p,h in {**old['inputs']['inputs_sha256'],**old['cad_files_sha256']}.items():assert sha(p)==h
    assert sha(BASE/'build/720p/outflow/ti60_camera.bit')==old['bitstream_sha256']
    for folder,h in old['simulations'].items():
        p=BASE/'sim'/folder/'verification.json';assert sha(p)==h;verify(p)
    verify(BASE/'sim/calibration_firmware/verification.json')
    modified={'rtl/gesture_snapshot.sv','rtl/p720/video_system_720.sv'}
    frozen=json.loads((B/'build_inputs.json').read_text(encoding='utf-8'))
    for filename in frozen['sources']:
        p=Path(filename);rel=p.relative_to(ROOT).as_posix()
        if rel in modified:continue
        previous=BASE/rel;assert previous.is_file(),rel
        actual=p.read_bytes()
        if actual!=previous.read_bytes():
            assert actual.decode('utf-8').replace(ROOT.as_posix(),BASE.as_posix()).replace(str(ROOT),str(BASE))==previous.read_text(encoding='utf-8'),rel
    for p in (ROOT/'firmware').glob('*'):
        if p.is_file() and p.name not in ['gesture_runtime.c','gesture_calibrated.c']:assert sha(p)==sha(BASE/p.relative_to(ROOT)),p.name
    for rel in ['build/720p/camera_mode.h']:
        assert (ROOT/rel).read_bytes()==(BASE/rel).read_bytes()
    return old

def learned_models():
    selected=json.loads((ROOT/'build/model_selection.json').read_text(encoding='utf-8'))
    assert len(selected['styles'])==10 and [v['source_id'] for v in selected['styles']]==SOURCE_IDS
    assert [v['slot'] for v in selected['styles']]==list(range(10))
    assert selected['rom_bytes']==7360 and selected['stride_bytes']==736 and selected['training_step']==27500
    assert selected['hardware_qat'] and selected['independent_styles'] and not selected['provisional'] and not selected['downsample']
    assert selected['clipped_weights']==0 and sha(selected['source'])==selected['source_sha256']
    for p,h in selected['teacher_hashes'].items():assert sha(p)==h
    blob=bytearray();maximum=0;rounded=0;bins=[]
    for slot,record in enumerate(selected['styles']):
        folder=next((ROOT/'parameters/c6').glob(f'{slot:02d}_*'));params=folder/'parameters.npz'
        assert sha(params)==record['npz_sha256'];d=np.load(params);raw=bytearray();writes=0
        assert record['weights']==396 and record['config_writes']==216 and record['bytes']==712 and record['stride_bytes']==736
        for layer in range(10):
            w=d[f'w{layer}'].astype(np.int64);bias=d[f'b{layer}'].astype(np.int64);shift=d[f'shift{layer}'].astype(np.int64)
            shape=(6,3,1,1) if layer==0 else (3,6,1,1) if layer==9 else (6,1,3,3) if layer%2 else (6,6,1,1)
            assert w.shape==shape and bias.shape==shift.shape==(shape[0],)
            info=record['layers'][layer];assert info['d']==(1<<(layer//2) if layer%2 and layer<9 else 1)
            assert info['groups']==(6 if layer%2 and layer<9 else 1) and info['signed']==(layer==9)
            assert w.min()>=-127 and w.max()<=127 and shift.min()>=0 and shift.max()<=20
            bound=np.abs(w).sum((1,2,3))*255+np.abs(bias)
            half=np.where(shift>0,1<<np.maximum(shift-1,0),0)
            maximum=max(maximum,int(bound.max()));rounded=max(rounded,int((bound+half).max()))
            wb=w.astype('i1').tobytes();bb=bias.astype('<i4').tobytes();ss=shift.astype('u1').tobytes()
            raw.extend(wb+bytes((-len(wb))%4)+bb+ss+bytes((-len(ss))%4))
            writes+=(len(wb)+3)//4+2*len(ss)
        assert len(raw)==712 and writes==216 and raw==(folder/'parameters.bin').read_bytes()
        assert sha(folder/'parameters.bin')==record['bin_sha256'];bins.append(sha(folder/'parameters.bin'))
        blob.extend(raw+bytes(736-len(raw)))
    assert len(set(bins))==10 and maximum<2**21 and rounded<2**22
    current=b''.join(int(v,16).to_bytes(4,'little') for v in (B/'weights.mem').read_text().split())
    assert current==blob and len(current)==7360
    external={}
    for name in ['verification.json','audit.json']:
        value,digest=verify(WS/'pycode/ten_style/results/painterly_v2_final'/name);external[name]=digest
        if name=='audit.json':
            assert value['model_sha256']==selected['source_sha256'] and value['full720_cases']==50 and value['small_cases']==40
            assert value['new_training_steps']==13500 and value['max_accumulator_bound']==maximum and value['clipped_weights']==0
        else:
            assert value['checkpoint_sha256']==selected['source_sha256'] and value['small_cases']==40 and value['full_resolution']
            assert len(value['cases'])==50 and sorted(v['slot'] for v in value['cases'])==sorted(list(range(10))*5)
            assert all(v['pixels']==921600 and v['integer_max_abs_error']==0 and v['qat_max_abs_error']==0 for v in value['cases'])
            assert value['reference_hashes']==selected['reference_hashes'] and not value['board_images']
    package,digest=verify(WS/'pycode/ten_style/runs/ten_painterly_v2/package/verification.json');external['package']=digest
    assert package['checkpoint_sha256']==selected['source_sha256'] and package['rom_bytes']==7360
    cal,digest=verify(ROOT/'sim/classifier_v2/verification.json');external['calibrated_reference']=digest
    assert cal['target_bss_bytes']==18404 and cal['feature_values_equal']>0 and cal['canonical_values_equal']>0
    runtime=(ROOT/'firmware/gesture_runtime.c').read_text(encoding='utf-8')
    assert '#include "gesture_calibrated.c"' in runtime and '#include "gesture_cnn' not in runtime
    assert 'rv32im' in (ROOT/'scripts/firmware.py').read_text(encoding='utf-8')
    assert 'm2p0' in (B/'firmware.elf').read_bytes().decode('latin1')
    return dict(source_ids=SOURCE_IDS,checkpoint_sha256=selected['source_sha256'],rom_bytes=7360,max_abs_sum_bound=maximum,max_rounded_bound=rounded,evidence_sha256=external,gesture_classifier='enhanced supervised prototypes: largest component, illumination compensation, mirror tolerance, four exemplars and three-capture voting',gesture_requires_enrollment=True)
def check_scopes():
    records={name:verify(ROOT/'sim'/name/'verification.json')[0] for name in TESTS}
    assert records['ten_sapphire']['styles']==10 and records['ten_sapphire']['parameter_writes']==2160
    normal=[v for v in records['ten_firmware']['tests'] if not v['wrong_id'] and not v['missing_m']]
    assert len(normal)==1 and normal[0]['loaded']==list(range(10)) and normal[0]['parameter_writes']==2160
    v=records['calibration_runtime'];assert len(v['atomic_guard_races'])==8
    assert sorted(p['digit'] for p in v['workflows'] if p['case']=='fresh_four_seconds')==list(range(10))
    assert any(p['case']=='repeat_different_digits_without_absence' for p in v['workflows'])
    assert any(p['case']=='return_view_rearms_same_digit' for p in v['workflows'])
    assert records['ui_system']['auto_switch'] and records['ui_system']['ui_toggle']
    assert records['calibration_firmware']['roi_complete']==58
    assert any(p['case']=='majority_rejects_single_frame_wrong_digit' for p in v['workflows'])
    assert any(p['case']=='no_majority_never_qualifies' for p in v['workflows'])
    latency=records['sapphire_latency'];assert 0<latency['classification_ui_cycles']<33300000 and latency['clock_hz']==100000000
    stress=records['gesture_stress']['totals'];assert stress['enhanced']['correct']>stress['baseline']['correct'] and stress['enhanced']['wrong']<=stress['baseline']['wrong']
    for name,pixels in [('ten_kernel_24x40',960),('ten_mapped',960)]:
        q=records[name];assert q['styles']==list(range(10)) and q['pixels_per_style']==pixels and q['integer_max_abs_error']==0
    for name in ['ten_dma','ten_split','ten_split_pressure']:
        q=records[name];assert q['styles']==list(range(10)) and all(r['integer_max_abs_error']==0 and r['pixels']==3072 for r in q['per_style'])
    q=records['ten_full_split'];assert q['styles']==[0] and q['pixels']==921600 and q['split']
    assert q['per_style'][0]['integer_max_abs_error']==0
    return q['min_model_fps']

def audit(bit=True):
    old=inherited();frozen=json.loads((B/'build_inputs.json').read_text(encoding='utf-8'))
    for p,h in frozen['inputs_sha256'].items():assert sha(p)==h,'Mapped input changed: '+p
    tests={name:verify(ROOT/'sim'/name/'verification.json')[1] for name in TESTS}
    full720_split_model_fps=check_scopes()
    models=learned_models()
    fw=json.loads((B/'firmware_manifest.json').read_text(encoding='utf-8'))
    assert fw['styles']==10 and fw['config_writes_per_style']==216 and fw['weights_rom_bytes']==7360
    lanes=[]
    for name,h in fw['lanes'].items():
        assert sha(B/name)==h and sha(B/'ip/control_soc'/name)==h;lanes.append([int(v,2) for v in (B/name).read_text().split()])
    assert bytes(v for row in zip(*lanes) for v in row)[:fw['firmware_bytes']]==(B/'firmware.bin').read_bytes()
    for p,h in fw['files'].items():assert sha(p)==h
    end=int(re.search(r'(0xf9[0-9a-f]+)\s+__bss_end',(B/'firmware.map').read_text())[1],16)
    assert end+2048<=0xf9008000
    from board_spec import audit as electrical
    board=electrical(B,camera=True,top=B/'rtl/ti60_camera_ppi_top.sv')
    assert (B/'ti60_camera.peri.xml').read_bytes()==(BASE/'build/720p/ti60_camera.peri.xml').read_bytes()
    cdc=json.loads((B/'cdc_constraints.json').read_text());proof=json.loads((B/'dphy_final_proof.json').read_text())
    assert [len(cdc[k]) for k in ['scalar_first_stages','gray_paths','bundle_paths','dphy_first_stages']]==[23,166,87,8]
    assert proof['map_sha256']==sha(B/'outflow/ti60_camera.map.v') and proof['vdb_sha256']==sha(B/'outflow/ti60_camera.vdb')
    assert len(proof['first_stages'])==8 and all(v['only_second_stage_endpoint'] and v['interstage_slack_ns']>0 for v in proof['first_stages'])
    for p,h in proof['reports'].items():assert sha(B/'outflow'/p)==h
    from native_constraints import assemble
    with tempfile.TemporaryDirectory(prefix='ten_sdc_',dir=ROOT/'build') as tmp:
        folder=Path(tmp);(folder/'outflow').mkdir()
        for n in ['ti60_camera.map.v','ti60_camera.pt.sdc']:shutil.copy2(B/'outflow'/n,folder/'outflow'/n)
        shutil.copy2(B/'dphy_cdc_proof.json',folder/'dphy_cdc_proof.json');assemble(folder)
        assert (folder/'ti60_camera.sdc').read_bytes()==(B/'ti60_camera.sdc').read_bytes()
    sdc=(B/'ti60_camera.sdc').read_text();assert 'set_clock_groups' not in sdc and 'set_multicycle_path' not in sdc
    timing=(B/'outflow/ti60_camera.timing.rpt').read_text();assert 'Timing Model: I3' in timing
    summary=timing.split('---------- 2. Clock Relationship Summary (begin) ----------')[1].split('---------- Clock Relationship Summary (end)')[0]
    a,b=summary.split('Hold (Min) Clock Relationship')
    def slacks(t):return [float(x[1]) for x in re.findall(r'^\s*\S+\s+\S+\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+\(R-R\)',t,re.M)]
    setup,hold=slacks(a),slacks(b);assert len(setup)>=20 and len(hold)>=20 and min(setup)>=0 and min(hold)>=0
    report=(B/'outflow/ti60_camera.map.rpt').read_text()
    resources={k:int(re.search(k+r'\s*:\s*(\d+)',report)[1]) for k in ['EFX_RAM10','EFX_DSP48','EFX_FF','EFX_LUT4']}
    place=(B/'outflow/ti60_camera.place.rpt').read_text();xlr=int(re.search(r'^XLRs:\s*(\d+)\s*/\s*60800',place,re.M)[1])
    assert xlr<=60800 and resources['EFX_RAM10']<=256 and resources['EFX_DSP48']<=160
    result=dict(result='PASS',process=[1280,720],display=[1280,720,60],styles=10,models=models,firmware=fw,firmware_bss_end=hex(end),stack_headroom_bytes=0xf9008000-end,resources=resources,xlr_used=xlr,setup_min_ns=min(setup),hold_min_ns=min(hold),electrical=board,cdc=cdc,simulations=tests,full720_split_model_fps=full720_split_model_fps,inputs=frozen,inherited_bitstream_sha256=old['bitstream_sha256'],inherited_signoff_sha256=sha(BASE/'build/720p/signoff.json'),inherited_numeric_scope='Arithmetic RTL/protocol retained; THIS build rechecks new ten models in RTL and EFX plus full720 slot0 SPLIT',auditor_sha256=sha(Path(__file__)),board_programmed=False,board_fps_verified=False,gesture_accuracy_verified=False,scope='Full720 ten-style neural hardware plus optional on-board supervised enrollment; all timing/electrical/model/firmware/numeric checks are offline. Real enrolled-user accuracy and continuous system FPS pending.')
    reports=[B/'outflow'/n for n in ['ti60_camera.map.v','ti60_camera.vdb','ti60_camera.timing.rpt','ti60_camera.place.rpt','ti60_camera.pt.sdc']]+[B/n for n in ['ti60_camera.sdc','cdc_constraints.json','dphy_cdc_proof.json','dphy_final_proof.json']]
    result['cad_files_sha256']={str(p):sha(p) for p in reports}
    if bit:
        target=B/'outflow/ti60_camera.bit';assert target.stat().st_mtime_ns>=max(p.stat().st_mtime_ns for p in reports);result['bitstream_sha256']=sha(target)
    return result
