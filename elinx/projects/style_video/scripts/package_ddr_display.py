"""Package the three-module system with left original / right CNN reservation."""
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
    target=B/'ddr_display_modules_receipt.json'
    if target.exists():assert not read(target).get('hardware_tested'),'Preserve hardware observations'
    baseline=read(B/'camera_capture_receipt.json');old=Path(baseline['project']).parent
    assert sha(Path(baseline['bitstream']))==baseline['sha256']
    for path in (old.parent/'rtl').glob('*'):
        if path.name!='style_ti60_top.v':assert sha(path)==sha(ROOT/'rtl'/path.name),'Changed old leaf: '+path.name
    assert sha(old/'style_video.peri.xml')==sha(ROOT/'efinity/style_video.peri.xml')
    sdc=(old/'style_video.sdc').read_text(encoding='utf-8')
    for name,new in [('display_sink/fifo','hdmi_display/sink/fifo'),
                     ('color_stats_cdc','hdmi_display/raw_diagnostics.color_stats_cdc'),
                     ('stat_underflow','hdmi_display/stat_underflow')]:
        sdc=sdc.replace('{'+name+'/', '{'+new+'/')
    extra=''
    for a,b in [('wgray','wgray_r1'),('rgray','rgray_w1')]:
        p='hdmi_display/white_balance_diagnostic.wb_status_cdc/'
        extra+='set_bus_skew -from [get_cells {'+p+a+'[*]~FF}] -to [get_cells {'+p+b+'[*]~FF}] 10.000\n'
    marker='set_bus_skew -from [get_cells {camera_capture/stat_camera/'
    assert sdc.count(marker)==1;sdc=sdc.replace(marker,extra+marker,1)
    assert sdc==(ROOT/'efinity/style_video.sdc').read_text(encoding='utf-8'),'Unexpected SDC change'
    cfg=read(B/'source_receipt.json')
    assert cfg['ddr_framebuffer_module']=='style_ddr_framebuffer' and cfg['hdmi_display_module']=='style_hdmi_display'
    assert cfg['cnn_right_pane_reserved'] and cfg['wb_calibration_enabled'] and cfg['performance_monitor_enabled']
    assert cfg['camera_profile']=='short_exposure' and cfg['bayer_pattern']==3 and cfg['tone_profile']=='gamma18'
    for entry in cfg['files']:assert sha(ROOT/entry['path'])==entry['sha256']==sha(Path(entry['source']))
    ef=read(B/'efinity_receipt.json');validation=read(B/'validation_receipt.json')
    assert ef['status']=='pass' and ef['full_build_passed'] and ef['sources_unchanged']
    assert all(sha(ROOT/p)==h for p,h in ef['sources'].items())
    assert validation['passed'] and validation['test_count']==baseline['test_count']+8
    assert all(sha(ROOT/p)==h for p,h in validation['sources'].items())
    archive=B/'ddr_display_modules_image';archive.mkdir(exist_ok=True)
    for name in ['source_receipt.json','validation_receipt.json','efinity_receipt.json']:
        shutil.copy2(B/name,archive/name)
    for name in ['ddr_module','hdmi_module','hdmi_full','capture_profiles']:
        record=read(B/name/'receipt.json');assert record['passed']
        assert all(sha(ROOT/p)==h for p,h in record['source_sha256'].items())
        shutil.copy2(B/name/'receipt.json',archive/(name+'_receipt.json'))
    for folder in ['rtl','scripts','sim/video_modules','sim/capture','sim/wb_calibration']:
        for path in (ROOT/folder).rglob('*'):
            if path.is_file() and path.suffix in ('.sv','.v','.vh','.py') and '__pycache__' not in path.parts:
                dest=archive/'sources'/path.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
    bit=B/'style_video_ddr_display_modules.bit';shutil.copy2(Path(ef['bitstream']),bit)
    def resources(project):
        text=(project/'outflow/style_video.map.rpt').read_text(encoding='utf-8')
        return {k:int(re.search(r'\b'+k+r'\s*:\s*(\d+)',text)[1]) for k in ('EFX_LUT4','EFX_DSP48','EFX_FF','EFX_RAM10')}
    current=resources(Path(ef['project']).parent);previous=resources(old)
    record=dict(packaged_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),
        status='built_timing_passed_pending_hardware',bitstream=str(bit),sha256=sha(bit),bytes=bit.stat().st_size,
        project=ef['project'],wns_ns=ef['wns_ns'],whs_ns=ef['whs_ns'],test_count=validation['test_count'],
        new_module_simulations=8,regenerated_profile_checks=5,reused_unchanged_records=95,
        verified_pin_count=ef['verified_pin_count'],design_file_count=ef['verified_design_file_count'],
        modules=['style_camera_capture','style_ddr_framebuffer','style_hdmi_display'],
        layout='720p60 timing; original 640x480 at x0..639/y120..599, right image x640..1279 black after every overlay/error',
        cnn_reserved=True,hidden_result_tokens_still_consumed=True,internal_copy_still_enabled=True,
        riscv_interface='framebuffer APB3 paddr/psel/penable/pwrite/pwdata/prdata/pready/pslverr + irq; Sapphire not instantiated',
        cnn_interface='framebuffer accel_input/output RGB streams + start/abort; no CNN instantiated',
        hardware_tested=False,programmed_by_assistant=False,competition_complete=False,
        old_leaf_rtl_unchanged=True,camera_profile_unchanged=True,vendor_inputs_unchanged=True,
        clocks_and_pins_unchanged=True,sdc_change='display instance paths plus WB status FIFO Gray bus skew constraints',
        baseline_bitstream=baseline['bitstream'],baseline_sha256=baseline['sha256'],
        resources_total=current,baseline_resources_total=previous,resource_delta={k:current[k]-v for k,v in previous.items()},
        validation_receipt='build/ddr_display_modules_image/validation_receipt.json',
        full_geometry_display_receipt='build/hdmi_full/receipt.json')
    target.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8');shutil.copy2(target,archive/'package_receipt.json')
    print(json.dumps(record,indent=2))


if __name__=='__main__':main()
