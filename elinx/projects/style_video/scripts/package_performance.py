"""Package the passive-monitor candidate with source/timing/simulation checks."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,hashlib,shutil,re
R=Path(__file__).resolve().parents[1];B=R/'build';out=B/'performance_monitor_image'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
baseline=read(B/'wb_calibration_receipt.json');old=Path(baseline['project']).parent
assert sha(Path(baseline['bitstream']))==baseline['sha256']
allowed={'style_platform_core.sv','style_display_sink.sv','style_ti60_top.v'}
for p in (old.parent/'rtl').glob('*'):
    if p.name not in allowed:assert sha(p)==sha(R/'rtl'/p.name),p.name
core=(R/'rtl/style_platform_core.sv').read_text(encoding='utf-8')
core=core.replace(',PERF_ENABLE=0','')
core=core.replace('    input wire [15:0] perf_camera_level,perf_display_level,\n    output wire [1023:0] perf_snapshot,output wire perf_snapshot_valid,\n','')
core=core.replace('.psel(psel && !perf_select)','.psel(psel)')
core=core.replace('.prdata(regs_prdata),.pready(regs_pready),.pslverr(regs_pslverr)', '.prdata(prdata),.pready(pready),.pslverr(pslverr)')
insertion='\n'+(R/'scripts/perf_core.vh').read_text(encoding='utf-8')+'\n'
assert core.count(insertion)==1;core=core.replace(insertion,'',1)
assert core==(old.parent/'rtl/style_platform_core.sv').read_text(encoding='utf-8'),'Datapath/FSM changed outside observer wiring'
sink=(R/'rtl/style_display_sink.sv').read_text(encoding='utf-8')
sink=sink.replace('    output reg [31:0] underflow_count,\n    // Read-only write-domain FIFO occupancy for passive diagnostics.\n    output wire [FIFO_ADDR_BITS:0] monitor_fifo_level','    output reg [31:0] underflow_count')
sink=sink.replace('    assign monitor_fifo_level=wr_level;\n','')
assert sink==(old.parent/'rtl/style_display_sink.sv').read_text(encoding='utf-8')
for name in ['style_video.sdc','style_video.peri.xml']:
    assert sha(old/name)==sha(R/'efinity'/name),name
cfg=read(B/'source_receipt.json')
assert cfg['performance_monitor_enabled'] and cfg['wb_calibration_enabled']
assert cfg['camera_profile']=='short_exposure' and cfg['bayer_pattern']==3 and cfg['tone_profile']=='gamma18'
assert all(sha(R/f['path'])==f['sha256']==sha(Path(f['source'])) for f in cfg['files'])
ef=read(B/'efinity_receipt.json');validation=read(B/'validation_receipt.json')
assert ef['status']=='pass' and ef['full_build_passed'] and ef['sources_unchanged']
assert ef['wns_ns']>=0 and ef['whs_ns']>=0 and ef['pinout_matches_verified_V4_J5'] and ef['clock_profile_verified']
assert all(sha(R/p)==h for p,h in ef['sources'].items())
assert validation['all_passed'] and all(sha(R/p)==h for p,h in validation['sources'].items())
assert {'perf_monitor','perf_core'}<={s['name'] for s in validation['suites']}
assert all(s['passed'] for s in validation['suites'])
perf=read(B/'performance/receipt.json');assert perf['passed'] and perf['metrics']['underflows']==0
assert sha(Path(ef['bitstream']))==ef['sha256']
target=B/'performance_monitor_receipt.json'
if target.exists():assert not read(target).get('hardware_tested'),'Preserve hardware feedback; package a new named version'
out.mkdir(exist_ok=True)
bit=B/'style_video_performance.bit';shutil.copy2(ef['bitstream'],bit);assert sha(bit)==ef['sha256']
for name in ['efinity_receipt.json','validation_receipt.json','source_receipt.json']:
    shutil.copy2(B/name,out/name)
for name in ['perf_monitor','perf_core','performance']:
    shutil.copy2(B/name/'receipt.json',out/(name+'_receipt.json'))
for folder in ['rtl','scripts','sim/perf_monitor']:
    for p in (R/folder).rglob('*'):
        if p.is_file() and p.suffix in ('.sv','.v','.vh','.py') and '__pycache__' not in p.parts:
            d=out/'sources'/p.relative_to(R);d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,d)
record=dict(packaged_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),
    status='built_timing_passed_pending_hardware',bitstream=str(bit),sha256=sha(bit),bytes=bit.stat().st_size,
    project=ef['project'],wns_ns=ef['wns_ns'],whs_ns=ef['whs_ns'],test_count=validation['test_count'],
    verified_pin_count=ef['verified_pin_count'],design_file_count=ef['verified_design_file_count'],
    baseline_bitstream=baseline['bitstream'],baseline_sha256=baseline['sha256'],
    UI='PERF 01 at y104..117, four pages / 120 HDMI frames per page',
    latency_unit='1us on 100MHz physical core; APB PERF_TICK_HZ defines units',
    latency_scope='core capture-slot allocation to successful capture, queue, job completion and new front-pair publication; excludes exposure, frontend CDC, physical scan and monitor',
    record_pairing='CAP/JOB/QUEUE/TOTAL LAST fields use one published frame_id',
    bus_observation='platform AXI port, handshake bytes with WSTRB; response wait differs from consumer backpressure',
    register_bank='0x100..0x17c offsets; CONTROL2 freeze+snapshot, CONTROL1 automatic, CONTROL4 clear+freeze',
    crossing='608bit held bundled-data mailbox with synchronized request/ack; no diagnostic BRAM FIFO',
    datapath_and_state_machines_unchanged=True,clocks_and_pins_unchanged=True,vendor_inputs_unchanged=True,
    white_balance_buttons_preserved=True,hardware_tested=False,programmed_by_assistant=False,
    hardware_bandwidth_verified=False,competition_complete=False,
    validation_receipt='build/performance_monitor_image/validation_receipt.json',
    full_geometry_receipt=perf.get('source_receipt_path','build/performance/receipt.json'))
def resources(project):
    text=(project/'outflow/style_video.map.rpt').read_text(encoding='utf-8')
    return {key:int(re.search(r'\b'+key+r'\s*:\s*(\d+)',text)[1])
            for key in ['EFX_LUT4','EFX_DSP48','EFX_FF','EFX_RAM10']}
record['resources_total']=resources(Path(ef['project']).parent)
record['baseline_resources_total']=resources(old)
record['additional_resources']={k:record['resources_total'][k]-v for k,v in record['baseline_resources_total'].items()}
target.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
shutil.copy2(target,out/'package_receipt.json')
print(json.dumps(record,ensure_ascii=False,indent=2))
