"""Run fresh portable RTL regressions and record a source-bound receipt.

Uses Icarus for the portable logic, not Efinix encrypted CSI/DDR/HDMI IP.
The separate build_efinity.py flow verifies the actual Efinity implementation.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse
import hashlib
import json
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parent.parent
DEFAULT_IVERILOG=shutil.which('iverilog') or r'D:\vscode\iverilog\iverilog\bin\iverilog.exe'
DEFAULT_VVP=shutil.which('vvp') or r'D:\vscode\iverilog\iverilog\bin\vvp.exe'
SUITES=[
    ('ddr_module','sim/video_modules/run_ddr.py','build/ddr_module/receipt.json'),
    ('hdmi_module','sim/video_modules/run_hdmi.py','build/hdmi_module/receipt.json'),
    ('hdmi_full','sim/video_modules/run_full.py','build/hdmi_full/receipt.json'),
    ('capture','sim/capture/run.py','build/capture/receipt.json'),
    ('capture_profiles','sim/capture/check_profiles.py','build/capture_profiles/receipt.json'),
    ('camera','sim/camera/run_camera.py','build/camera/receipt.json'),
    ('gamma','sim/gamma/run_gamma.py','build/gamma/receipt.json'),
    ('black_level','sim/black_level/run_black.py','build/black_level/receipt.json'),
    ('white_balance','sim/white_balance/run_white.py','build/white_balance/receipt.json'),
    ('wb_calibration_control','sim/wb_calibration/run_control.py','build/wb_calibration_control/receipt.json'),
    ('wb_calibration_pipeline','sim/wb_calibration/run_pipeline.py','build/wb_calibration_pipeline/receipt.json'),
    ('perf_monitor','sim/perf_monitor/run.py','build/perf_monitor/receipt.json'),
    ('perf_core','sim/perf_monitor/run_core.py','build/perf_core/receipt.json'),
    ('contrast_probe','sim/contrast_probe/run_probe.py','build/contrast_probe/receipt.json'),
    ('contrast_startup','sim/contrast_probe/run_startup.py','build/contrast_startup/receipt.json'),
    ('cfa_stats','sim/color_probe/run_stats.py','build/cfa_stats/receipt.json'),
    ('color_probe_overlay','sim/color_probe/run_overlay.py','build/color_probe_overlay/receipt.json'),
    ('camera_initializer','sim/camera/run_initializer.py','build/camera_initializer/receipt.json'),
    ('memory','sim/memory/run.py','build/memory/receipt.json'),
    ('display','sim/display/run.py','build/display/receipt.json'),
    ('platform','sim/platform/run_units.py','build/platform_units/receipt.json'),
    ('integration','sim/integration/run.py','build/integration/receipt.json'),
    ('performance','sim/performance/run.py','build/performance/receipt.json'),
]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iverilog',default=DEFAULT_IVERILOG)
    parser.add_argument('--vvp',default=DEFAULT_VVP)
    parser.add_argument('--collect',action='store_true',help='Verify existing passing receipts against current source SHA256; do not rerun unchanged tests')
    args=parser.parse_args()
    build=ROOT/'build';build.mkdir(exist_ok=True)
    target=build/'validation_receipt.json'
    receipt={'checked_at':datetime.now(timezone(timedelta(hours=8))).isoformat(),
        'all_passed':False,'passed':False,'programmed':False,'suites':[],
        'method':'source_hash_receipt_collection' if args.collect else 'fresh_run',
        'sources':{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in (ROOT/'rtl').glob('*') if p.suffix in ('.sv','.v')}}
    def save():target.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    save()
    try:
        for name,runner,record in SUITES:
            assert (ROOT/runner).is_file(), 'test suite not ready: '+runner
            print(('Collecting ' if args.collect else 'Running ')+name+'...',flush=True)
            log=build/(name+'_suite.log')
            if not args.collect:
                command=[sys.executable,str(ROOT/runner),'--iverilog',args.iverilog,'--vvp',args.vvp]
                if name=='camera':
                    # The full-resolution eight-frame cases need more wall
                    # time in Icarus after adding per-site RAW10 correction.
                    command+=['--run-timeout','900','--jobs','2']
                result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=2000)
                log.write_text(result.stdout+result.stderr,encoding='utf-8')
                assert result.returncode==0, f'{name} failed: {log}'
            details=json.loads((ROOT/record).read_text(encoding='utf-8'))
            assert details.get('passed') or details.get('all_passed'), f'{name} missing passing receipt'
            hashes=details.get('source_sha256') or details.get('rtl_sha256') or details.get('sources') or {}
            assert hashes, name+' missing tested source hashes'
            for path,sha in hashes.items():
                source=ROOT/path if '/' in path or '\\' in path else ROOT/'rtl'/path
                assert source.is_file() and hashlib.sha256(source.read_bytes()).hexdigest()==sha, name+' source changed: '+path
            tests=details.get('tests',[])
            assert tests and all(t.get('passed') and t.get('run_exit',t.get('exit_code'))==0 for t in tests),name+' failed or missing test exits'
            if args.collect:
                log.write_text('Verified existing test receipt against current source hashes: '+record+'\n'+
                    '\n'.join(str(t['name'])+': PASS, run exit 0' for t in tests)+'\n',encoding='utf-8')
            receipt['suites'].append({'name':name,'exit_code':0,'passed':True,
                'receipt':record,'tests':len(details.get('tests',[])),'log':str(log)})
            save();print(name+': PASS',flush=True)
        receipt['all_passed']=receipt['passed']=True
        receipt['test_count']=sum(s['tests'] for s in receipt['suites'])
        save();return 0
    except (AssertionError,ValueError,FileNotFoundError,subprocess.TimeoutExpired) as exc:
        receipt['reason']=str(exc);save();print(str(exc),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
