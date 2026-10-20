"""Package a verified Efinity calibration candidate; never programs hardware."""
from pathlib import Path
import json,hashlib,shutil
from datetime import datetime,timezone,timedelta
ROOT=Path(__file__).resolve().parents[1]
B=ROOT/'build';out=B/'wb_calibration_image'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
target=B/'wb_calibration_receipt.json'
if target.exists():
    assert not read(target).get('hardware_tested'), 'Preserve accepted candidate; use a new version name'
ef=read(B/'efinity_receipt.json')
assert ef['status']=='pass' and ef['full_build_passed'] and ef['implementation_passed']
assert ef['sources_unchanged'] and ef['wns_ns']>=0 and ef['whs_ns']>=0
assert ef['pinout_matches_verified_V4_J5'] and ef['clock_profile_verified']
assert all(sha(ROOT/p)==h for p,h in ef['sources'].items())
validation=read(B/'validation_receipt.json')
assert validation['all_passed'] and validation['passed']
assert all(sha(ROOT/p)==h for p,h in validation['sources'].items())
assert {'wb_calibration_control','wb_calibration_pipeline'} <= {s['name'] for s in validation['suites']}
prep=read(B/'wb_calibration_prepare_receipt.json')
assert prep['passed'] and all(sha(ROOT/p)==h for p,h in prep['sources'].items())
cfg=read(B/'source_receipt.json')
assert cfg['wb_calibration_enabled'] and cfg['bayer_pattern']==3
assert cfg['camera_profile']=='short_exposure' and cfg['tone_profile']=='gamma18'
assert cfg['black_level_profile']=='measured' and cfg['white_balance_profile']=='measured'
assert cfg['display_contrast_initial_level']==0
assert all(sha(ROOT/f['path'])==f['sha256']==sha(Path(f['source'])) for f in cfg['files'])
baseline=read(B/'white_balance_receipt.json')
assert sha(Path(baseline['bitstream']))==baseline['sha256']
old=Path(baseline['project']).parent
for p in (old.parent/'rtl').glob('*'):
    if p.name not in ('style_camera_preprocess.sv','style_ti60_top.v'):
        assert sha(p)==sha(ROOT/'rtl'/p.name),p.name
for name in ['style_video.sdc','style_video.peri.xml']:
    assert sha(old/name)==sha(ROOT/'efinity'/name)
source_bit=Path(ef['bitstream']);assert sha(source_bit)==ef['sha256']
out.mkdir(exist_ok=True)
bit=B/'style_video_wb_calibration.bit';shutil.copy2(source_bit,bit)
assert sha(bit)==ef['sha256']
receipts=['efinity_receipt.json','validation_receipt.json','wb_calibration_prepare_receipt.json',
          'black_prepare_receipt.json','source_receipt.json']
for name in receipts:shutil.copy2(B/name,out/name)
for name in ['wb_calibration_control','wb_calibration_pipeline']:
    shutil.copytree(B/name,out/name,dirs_exist_ok=True)
for folder in ['rtl','scripts','sim/wb_calibration']:
    for p in (ROOT/folder).rglob('*'):
        if p.is_file() and p.suffix in ('.sv','.v','.vh','.py') and '__pycache__' not in p.parts:
            dest=out/'sources'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
record=dict(packaged_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),
    status='built_timing_passed_pending_hardware',bitstream=str(bit),sha256=sha(bit),bytes=bit.stat().st_size,
    project=ef['project'],tool=ef['tool'],wns_ns=ef['wns_ns'],whs_ns=ef['whs_ns'],
    design_file_count=ef['verified_design_file_count'],verified_pin_count=ef['verified_pin_count'],
    clock_profile_verified=True,pinout_matches_verified_V4_J5=True,
    validation_receipt='build/wb_calibration_image/validation_receipt.json',test_count=validation['test_count'],
    control_tests='build/wb_calibration_image/wb_calibration_control/receipt.json',
    pipeline_tests='build/wb_calibration_image/wb_calibration_pipeline/receipt.json',
    baseline_bitstream=baseline['bitstream'],baseline_sha256=baseline['sha256'],
    default_gains_q8=dict(R=493,G=256,B=504),raw_black_levels=dict(A=65,B=66,C=66,D=67),
    calibration_frames=4,debounce_ms=20,timeout_seconds=2,gain_range_q8=[64,1024],
    minimum_corrected_site_mean=32,raw_site_mean_exclusive_max=960,
    green_gain_q8=256,bayer_pattern=3,tone_profile='gamma18',
    update_boundary='input camera SOF; output pixel markers and ready/valid unchanged',
    key1='right contrast',key2='one-shot neutral paper calibration',key3='restore fixed defaults',
    ui_marker='WB CAL 01',default_display_contrast=1.0,
    camera_registers_changed=False,ddr_format_changed=False,ddr_pixel_values_change_with_calibration=True,
    hardware_tested=False,programmed_by_assistant=False,image_quality_accepted=False,
    active_hardware_marker_changed=False,competition_complete=False,
    limitations='Manual neutral-target calibration only. Does not detect target chromaticity, pixel clipping from means, or optical spectral cause. No automatic exposure or full CCM. Hardware counters and outdoor color still require user confirmation.')
target.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
shutil.copy2(target,out/'package_receipt.json')
print(json.dumps(record,ensure_ascii=False,indent=2))
