"""Package acquisition refactoring; retain historical bitstreams and hardware marker."""
from datetime import datetime,timezone,timedelta
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT=Path(__file__).resolve().parents[1]
B=ROOT/'build'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    target=B/'camera_capture_receipt.json'
    if target.exists():assert not read(target).get('hardware_tested'),'Preserve hardware feedback'
    baseline=read(B/'performance_monitor_receipt.json');old=Path(baseline['project']).parent
    assert sha(Path(baseline['bitstream']))==baseline['sha256']
    for path in (old.parent/'rtl').glob('*'):
        if path.name!='style_ti60_top.v':assert sha(path)==sha(ROOT/'rtl'/path.name),'Changed leaf RTL: '+path.name
    assert sha(old/'style_video.peri.xml')==sha(ROOT/'efinity/style_video.peri.xml'),'Physical peripherals changed'
    # SDC changes only relocate existing FIFO/Gray constraints beneath the wrapper.
    sdc=(old/'style_video.sdc').read_text(encoding='utf-8')
    for name in ['camera_cdc','abort_cdc','stat_camera','stat_drops','stat_errors']:
        sdc=sdc.replace('{'+name+'/', '{camera_capture/'+name+'/')
    assert sdc==(ROOT/'efinity/style_video.sdc').read_text(encoding='utf-8'),'SDC changed outside capture instance paths'
    cfg=read(B/'source_receipt.json')
    assert cfg['camera_capture_module']=='style_camera_capture'
    assert cfg['performance_monitor_enabled'] and cfg['wb_calibration_enabled']
    assert cfg['camera_profile']=='short_exposure' and cfg['bayer_pattern']==3 and cfg['tone_profile']=='gamma18'
    for entry in cfg['files']:
        assert sha(ROOT/entry['path'])==entry['sha256']==sha(Path(entry['source'])),'Vendor input changed'
    ef=read(B/'efinity_receipt.json');validation=read(B/'validation_receipt.json')
    assert ef['status']=='pass' and ef['full_build_passed'] and ef['sources_unchanged']
    assert all(sha(ROOT/p)==h for p,h in ef['sources'].items()),'Current inputs differ from implementation snapshot'
    expected_records=baseline['test_count']+10
    assert validation['passed'] and validation['test_count']==expected_records
    assert all(sha(ROOT/p)==h for p,h in validation['sources'].items()),'Validation source set stale'
    archive=B/'camera_capture_image';archive.mkdir(exist_ok=True)
    for name in ['source_receipt.json','validation_receipt.json','efinity_receipt.json']:
        shutil.copy2(B/name,archive/name)
    for name in ['capture','capture_profiles']:
        r=read(B/name/'receipt.json');assert r['passed']
        assert all(sha(ROOT/p)==h for p,h in r['source_sha256'].items())
        shutil.copy2(B/name/'receipt.json',archive/(name+'_receipt.json'))
    for folder in ['rtl','scripts','sim/capture','sim/wb_calibration']:
        for path in (ROOT/folder).rglob('*'):
            if path.is_file() and path.suffix in ('.sv','.v','.vh','.py') and '__pycache__' not in path.parts:
                dest=archive/'sources'/path.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
    bit=B/'style_video_camera_capture.bit';shutil.copy2(Path(ef['bitstream']),bit)
    def resources(project):
        text=(project/'outflow/style_video.map.rpt').read_text(encoding='utf-8')
        return {key:int(re.search(r'\b'+key+r'\s*:\s*(\d+)',text)[1]) for key in ('EFX_LUT4','EFX_DSP48','EFX_FF','EFX_RAM10')}
    current_resources=resources(Path(ef['project']).parent);previous_resources=resources(old)
    record=dict(packaged_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),
        status='built_timing_passed_pending_hardware',bitstream=str(bit),sha256=sha(bit),bytes=bit.stat().st_size,
        project=ef['project'],wns_ns=ef['wns_ns'],whs_ns=ef['whs_ns'],test_count=validation['test_count'],
        new_simulation_tests=5,new_generation_checks=5,reused_source_matching_records=baseline['test_count'],
        verified_pin_count=ef['verified_pin_count'],design_file_count=ef['verified_design_file_count'],
        module='style_camera_capture',input='camera_clk: high-active VS/HS, DE, four RAW10 pixels/40bit',
        output='core_clk: RGB888 ready/valid, SOF/EOL/EOF/frame_id; abort/ID; Gray counters; FIFO level and sticky cancellation fault',
        optional_diagnostic='camera_clk RAW mean pulse + 40bit A/B/C/D, before all corrections',
        baseline_bitstream=baseline['bitstream'],baseline_sha256=baseline['sha256'],
        leaf_rtl_unchanged=True,sdc_only_instance_paths_changed=True,clocks_and_pins_unchanged=True,
        vendor_inputs_unchanged=True,camera_registers_unchanged=True,frame_rate_increase=False,
        hardware_tested=False,programmed_by_assistant=False,competition_complete=False,
        resources_total=current_resources,baseline_resources_total=previous_resources,
        resource_delta={k:current_resources[k]-v for k,v in previous_resources.items()},
        validation_receipt='build/camera_capture_image/validation_receipt.json')
    target.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    shutil.copy2(target,archive/'package_receipt.json')
    print(json.dumps(record,indent=2))


if __name__=='__main__':main()
