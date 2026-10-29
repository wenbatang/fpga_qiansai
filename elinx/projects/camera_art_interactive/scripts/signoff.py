"""Strict full720 release gate. No model/simulation/timing substitution."""
from pathlib import Path
import hashlib,json,re,shutil,tempfile
import numpy as np
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'build/720p';BASE=ROOT.parent/'camera_full720_30'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def check_receipt(name):
    path=ROOT/'sim'/name/'verification.json';value=json.loads(path.read_text(encoding='utf-8'))
    assert value['result']=='PASS',name
    assert value.get('sources_sha256') and value.get('logs_sha256'),('Empty binding',name)
    for p,digest in {**value['sources_sha256'],**value['logs_sha256']}.items():assert sha(p)==digest,'Stale test '+name+': '+p
    assert any(Path(p).resolve().is_relative_to((ROOT/'rtl').resolve()) for p in value['sources_sha256']),name
    return value


def check_models():
    selected=json.loads((ROOT/'build/model_selection.json').read_text(encoding='utf-8'))
    assert selected['trained_this_turn'] and not selected['downsample'] and selected['receptive_field']==31
    assert selected['independent_styles'] and not selected['shared_dw_head'] and not selected['provisional']
    assert selected['hardware_qat'] and selected['training_step']>=17000 and selected['clipped_weights']==0
    assert sha(selected['source'])==selected['source_sha256']
    assert [r['name'] for r in selected['styles']]==['vangogh','papercut','comic','inkwash']
    blob=bytearray();maximum=0;spatial={};heads=[]
    for slot,name in enumerate(['vangogh','papercut','comic','inkwash']):
        folder=ROOT/'parameters/c6'/f'{slot:02d}_{name}';m=json.loads((folder/'metadata.json').read_text(encoding='utf-8'));data=np.load(folder/'parameters.npz')
        assert m['slot']==slot and m['architecture']=='full_c6' and m['full_resolution'] and m['weights']==396 and m['config_writes']==216
        for key in ['npz','bin']:assert sha(folder/f'parameters.{key}')==m[f'{key}_sha256']
        raw=bytearray();weights=0
        for index,info in enumerate(m['layers']):
            w=data[f'w{index}'];bias=data[f'b{index}'];shift=data[f'shift{index}'];weights+=w.size
            expected_shape=(3,6,1,1) if index==9 else (6,3,1,1) if index==0 else (6,1,3,3) if index%2 else (6,6,1,1)
            assert w.shape==expected_shape and np.all(shift>=0) and np.all(shift<=20)
            if index in [1,3,5,7]:assert info['d']==2**((index-1)//2) and info['groups']==6
            bound=int((np.abs(w.astype(np.int64)).sum((1,2,3))*255+np.abs(bias.astype(np.int64))).max());maximum=max(maximum,bound)
            assert info['bound']==bound and bound<2**21
            for key,bits in [('w',8),('b',32),('shift',8)]:
                assert [int(v,16) for v in (folder/f'layer{index}_{key}.mem').read_text().split()]==[int(v)&((1<<bits)-1) for v in data[f'{key}{index}'].flatten()]
            wb=w.astype('i1').tobytes();sb=shift.astype('u1').tobytes();raw.extend(wb+bytes((-len(wb))%4)+bias.astype('<i4').tobytes()+sb+bytes((-len(sb))%4))
            if index in [1,3,5,7]:spatial.setdefault(index,[]).append(w.tobytes())
            if index==9:heads.append(w.tobytes())
        assert weights==396 and len(raw)==712 and bytes(raw)==(folder/'parameters.bin').read_bytes()
        blob.extend(raw+bytes(736-len(raw)))
    assert len(blob)==2944 and maximum<2**21
    bound_record=json.loads((ROOT/'build/accumulator_bound.json').read_text(encoding='utf-8'))
    assert bound_record['result']=='PASS' and bound_record['signed_accumulator_bits']==22 and bound_record['rounded_bits']==23 and bound_record['max_abs_sum_bound']==maximum
    assert all(len(set(values))==4 for values in spatial.values()) and len(set(heads))==4,'Spatial/head models must be independently learned'
    assert b''.join(int(v,16).to_bytes(4,'little') for v in (B/'weights.mem').read_text().split())==bytes(blob)
    compiled=json.loads((B/'build_inputs.json').read_text(encoding='utf-8'))['sources']
    assert any(Path(p).name=='full_parameter_bank.sv' for p in compiled)
    assert not any(Path(p).name=='full_shared_params.sv' for p in compiled),'Old shared learned constants compiled'
    quality=json.loads((ROOT/'build/quality/verification.json').read_text(encoding='utf-8'))
    assert quality['result']=='PASS' and quality['full_resolution'] and not quality['downsample'] and quality['weights_per_style']==396
    assert quality['independent_styles'] and quality['hardware_qat']
    assert len(quality['cases'])==8 and all(c['pixels']==921600 and c['integer_max_abs_error']==0 for c in quality['cases'])
    assert quality['small_integer_cases']==16 and quality['sources_sha256'] and quality['outputs_sha256']
    for p,digest in {**quality['sources_sha256'],**quality['outputs_sha256']}.items():assert sha(p)==digest,'Stale software quality evidence: '+p
    assert all(shape[-2:]==[720,1280] for trace in quality['spatial_shapes'] for shape in trace)
    assert all(c['hardware_qat_max_abs_error']==0 for c in quality['cases'])
    return dict(weights_per_style=396,receptive_field=31,model_rom_bytes=2944,config_writes=216,max_accumulator_bound=maximum,accumulator_bits=22,independent_styles=True,hardware_qat=True,quality_sha256=sha(ROOT/'build/quality/verification.json'))


def audit(bit=True):
    frozen=json.loads((B/'build_inputs.json').read_text(encoding='utf-8'));assert frozen['format_version']==3
    for p,digest in frozen['inputs_sha256'].items():assert sha(p)==digest,'Mapped input changed: '+p
    assert not any(Path(p).name.startswith('tiny_') for p in frozen['sources'])
    receipts={}
    for name in ['kernel_48x40','kernel_1x1','kernel_3x5','kernel_19x22','dma','dma_pressure','split','split_pressure','full','full_split','control','sapphire','keys','top_safety','display_state','fps_jobs','fps_write_pressure2','fps_reader','scheduling','mapped','mapped_dma']:
        check_receipt(name);receipts[name]=sha(ROOT/'sim'/name/'verification.json')
    full=check_receipt('full');assert full['styles']==[0,1,2,3] and full['pixels']==921600 and full['tile_core']==320 and full['halo']==16
    split=check_receipt('full_split');assert split['split'] and split['pixels']==921600 and split['styles']==[0]
    assert len(full['per_style'])==4
    for i,case in enumerate(full['per_style']):
        assert case['slot']==i and case['pixels']==921600 and case['integer_max_abs_error']==0
        assert abs(case['model_fps']-100000000/case['ui_cycles'])<1e-9 and case['model_fps']>30
    for kind,top in [('mapped','full_probe'),('mapped_dma','full_dma_probe')]:
        folder=ROOT/'build'/('probe' if kind=='mapped' else 'probe_dma');binding=json.loads((folder/'inputs.json').read_text(encoding='utf-8'))
        for p,digest in binding.items():assert sha(p)==digest
        r=check_receipt(kind);assert r['integer_max_abs_error']==0 and r['styles']==[0,1,2,3]
        assert str(folder/'outflow'/(top+'.map.v')) in r['sources_sha256']
        assert r['pixels_per_style']==(128*24 if kind=='mapped_dma' else 24*40)
        if kind=='mapped_dma':
            assert r['split'],'Native DMA must exercise the physical split selector and latched mode flag'
            engine=ROOT/'rtl/p720/video_tile_engine_async.sv'
            expected=engine.read_text(encoding='utf-8').replace('module video_tile_engine_async #(','module full_dma_probe #(').replace('WIDTH=1280,HEIGHT=720','WIDTH=128,HEIGHT=24').replace('TILE_CORE=320,HALO=16','TILE_CORE=48,HALO=16')
            assert (folder/'full_dma_probe.sv').read_text(encoding='utf-8')==expected,'DMA probe differs beyond module name and geometry'
            assert str(engine) in r['sources_sha256']
    models=check_models()
    fw=json.loads((B/'firmware_manifest.json').read_text(encoding='utf-8'));assert fw['config_writes_per_style']==216 and fw['weights_rom_bytes']==2944 and fw['firmware_bytes']<30720
    lanes=[]
    for name,digest in fw['lanes'].items():
        assert sha(B/name)==digest and sha(B/'ip/control_soc'/name)==digest
        lanes.append([int(v,2) for v in (B/name).read_text().split()])
    assert bytes(v for row in zip(*lanes) for v in row)[:fw['firmware_bytes']]==(B/'firmware.bin').read_bytes()
    for p,digest in fw['files'].items():assert sha(p)==digest
    from board_spec import audit as electrical
    board=electrical(B,camera=True,top=B/'rtl/ti60_camera_ppi_top.sv')
    assert (B/'ti60_camera.peri.xml').read_bytes()==(BASE/'build/720p/ti60_camera.peri.xml').read_bytes()
    cdc=json.loads((B/'cdc_constraints.json').read_text());proof=json.loads((B/'dphy_final_proof.json').read_text())
    assert len(cdc['scalar_first_stages'])==23 and len(cdc['gray_paths'])==166 and len(cdc['bundle_paths'])==75 and len(cdc['dphy_first_stages'])==8
    assert proof['map_sha256']==sha(B/'outflow/ti60_camera.map.v') and proof['vdb_sha256']==sha(B/'outflow/ti60_camera.vdb')
    assert len(proof['first_stages'])==8 and all(x['only_second_stage_endpoint'] and x['interstage_slack_ns']>0 for x in proof['first_stages'])
    for p,digest in proof['reports'].items():assert sha(B/'outflow'/p)==digest
    from native_constraints import assemble
    with tempfile.TemporaryDirectory(prefix='audit_sdc_',dir=ROOT/'build') as tmp:
        folder=Path(tmp);(folder/'outflow').mkdir()
        for name in ['ti60_camera.map.v','ti60_camera.pt.sdc']:shutil.copy2(B/'outflow'/name,folder/'outflow'/name)
        shutil.copy2(B/'dphy_cdc_proof.json',folder/'dphy_cdc_proof.json');assemble(folder)
        assert (folder/'ti60_camera.sdc').read_bytes()==(B/'ti60_camera.sdc').read_bytes()
        assert json.loads((folder/'cdc_constraints.json').read_text())==cdc
    sdc=(B/'ti60_camera.sdc').read_text();assert 'set_clock_groups' not in sdc and 'set_multicycle_path' not in sdc
    timing=(B/'outflow/ti60_camera.timing.rpt').read_text(encoding='utf-8');assert 'Timing Model: I3' in timing
    summary=timing.split('---------- 2. Clock Relationship Summary (begin) ----------')[1].split('---------- Clock Relationship Summary (end)')[0]
    a,b=summary.split('Hold (Min) Clock Relationship')
    def slacks(text):return [float(x[1]) for x in re.findall(r'^\s*\S+\s+\S+\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+\(R-R\)',text,re.M)]
    setup,hold=slacks(a),slacks(b);assert len(setup)>=20 and len(hold)>=20 and min(setup)>=0 and min(hold)>=0
    rpt=(B/'outflow/ti60_camera.map.rpt').read_text(encoding='utf-8');resources={key:int(re.search(key+r'\s*:\s*(\d+)',rpt)[1]) for key in ['EFX_RAM10','EFX_DSP48','EFX_FF','EFX_LUT4']}
    place=(B/'outflow/ti60_camera.place.rpt').read_text(encoding='utf-8');xlr=int(re.search(r'^XLRs:\s*(\d+)\s*/\s*60800',place,re.M)[1])
    assert resources['EFX_RAM10']<=256 and resources['EFX_DSP48']<=160 and xlr<=60800
    cad_files=[B/'outflow'/n for n in ['ti60_camera.map.v','ti60_camera.vdb','ti60_camera.timing.rpt','ti60_camera.place.rpt','ti60_camera.pt.sdc']]+[B/n for n in ['ti60_camera.sdc','cdc_constraints.json','dphy_cdc_proof.json','dphy_final_proof.json']]
    value=dict(result='PASS',process=[1280,720],feature_branch=[1280,720],downsample=False,display=[1280,720,60],styles=4,full_frame_all_styles=full['per_style'],min_model_fps=min(c['model_fps'] for c in full['per_style']),models=models,
        resources=resources,xlr_used=xlr,setup_min_ns=min(setup),hold_min_ns=min(hold),electrical=board,cdc=cdc,simulations=receipts,inputs=frozen,cad_files_sha256={str(p):sha(p) for p in cad_files},board_programmed=False,board_fps_verified=False,
        scope='Offline full-resolution learned RTL/EFX numerical/CAD/electrical evidence; no real camera+DDR+HDMI FPS acceptance')
    if bit:
        path=B/'outflow/ti60_camera.bit';assert path.stat().st_mtime_ns>=max(p.stat().st_mtime_ns for p in cad_files)
        value['bitstream_sha256']=sha(path)
    return value
