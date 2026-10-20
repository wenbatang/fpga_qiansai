"""Build an immutable local snapshot with Efinity; never programs hardware.

Usage: python scripts/build_efinity.py --build [--tool C:/Efinity/2026.1]
All compiler output stays under this project's build/efinity directory.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(receipt):
    project=Path(receipt['project']).parent
    log=Path(receipt['log'])
    receipt['full_build_passed']=receipt['implementation_passed']=False
    try:
        assert receipt['exit_code']==0, 'compiler process failed'
        content=log.read_text(encoding='utf-8',errors='replace')
        phases={p:bool(re.search(rf'{p}\s*:\s*PASS',content)) for p in ('map','interface','pnr','pgm')}
        receipt['phases']=phases
        assert all(phases.values()), 'incomplete compiler phases'
        out=project/'outflow'
        report=(out/'style_video.timing.rpt').read_text()
        setup,hold=report.split('Setup (Max) Clock Relationship',1)[1].split('Hold (Min) Clock Relationship',1)
        hold=hold.split('Clock Relationship Summary (end)',1)[0]
        def worst(section):
            values=[float(m[1]) for line in section.splitlines()
                if (m:=re.search(r'\S+\s+\S+\s+[\d.-]+\s+([\d.-]+)\s+\([RF]-[RF]\)',line))]
            assert values,'missing timing paths'
            return min(values)
        receipt['wns_ns'],receipt['whs_ns']=worst(setup),worst(hold)
        assert receipt['wns_ns']>=0 and receipt['whs_ns']>=0, 'timing failed'
        receipt['interface_issues']=[dict(e.attrib) for e in ET.parse(out/'design_issue.xml').getroot()]
        assert not any(i.get('severity')=='error' for i in receipt['interface_issues']),'interface error'
        source_record=json.loads((ROOT/'build/source_receipt.json').read_text(encoding='utf-8'))
        reference=Path(source_record['reference'])
        def pins(path):
            rows=[line for line in path.read_text().splitlines() if line and not line.startswith('#')]
            return {r['Signal Name']:r for r in csv.DictReader(rows) if r['Signal Name']}
        actual=pins(out/'style_video.pinout.csv')
        expected=pins(reference/'outflow/ti60f225_oob.pinout.csv')
        for name,row in expected.items():
            if name.startswith('jtag_inst1_'):continue
            assert actual.get(name)==row, 'physical pin profile changed: '+name
        receipt['verified_pin_count']=len(expected)
        receipt['pinout_matches_verified_V4_J5']=True
        pt_report=(out/'style_video.pt_timing.rpt').read_text()
        for clock,period in [('core_clk',10),('i_mipi_rx_pclk',20),('CLK_5M',200),
                             ('hdmi_tx_slow_clk',13.468),('hdmi_tx_fast_clk',2.694),('sdram_clk',2.5)]:
            assert re.search(r'\|\s*'+clock+r'\s*\|\s*'+f'{period:.3f}'+r'\s*\|',pt_report),clock+' frequency mismatch'
        receipt['clock_profile_verified']=True
        implementation_log=(out/'style_video.log').read_text(encoding='utf-8',errors='replace')
        assert not re.search(r'invalid command name|Error\(s\) found while executing SDC',implementation_log), 'SDC execution error'
        assert 'random placement' not in implementation_log,'unassigned physical port'
        assert not re.search(r"No cells matched '[^']*(?:camera_capture|hdmi_display)[^']*'",implementation_log), 'Unmatched modular camera/display CDC constraints'
        receipt['modular_cdc_constraints_resolved']=True
        receipt['sdc_warnings']=len(re.findall(r'WARNING.*\[SDC ',implementation_log))
        receipt['timing_guide']='https://www.efinixinc.com/support/docs.php?p=e'
        receipt['sources_unchanged']=all((ROOT/path).is_file() and digest(ROOT/path)==sha for path,sha in receipt['sources'].items())
        assert receipt['sources_unchanged'],'sources changed during build; rebuild final version'
        bit=out/'style_video.bit'
        assert bit.is_file() and bit.stat().st_size>1000, 'bitstream missing'
        receipt.pop('reason',None)
        receipt.update(bitstream=str(bit),sha256=digest(bit),bytes=bit.stat().st_size,status='pass',
                       full_build_passed=True,implementation_passed=True)
    except (AssertionError,ValueError,FileNotFoundError) as exc:
        receipt.update(status='fail',reason=str(exc))
    return receipt

def build(tool):
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    base = ROOT / 'build/efinity' / stamp
    project = base / 'efinity'
    project.mkdir(parents=True)
    shutil.copytree(ROOT / 'rtl', base / 'rtl')
    shutil.copytree(ROOT / 'efinity', project, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('work_*', 'outflow', '*.log', '*.lck', '*.lock', '.lock', '__pycache__'))
    # An open IDE can save its cached file list after prepare adds new RTL.
    # Complete the isolated snapshot from the RTL actually copied above,
    # without closing the IDE or editing any inherited vendor file.
    snapshot_xml=project/'style_video.xml'
    xml_text=snapshot_xml.read_text(encoding='utf-8')
    namespace={'e':'http://www.efinixinc.com/enf_proj'}
    design=ET.fromstring(xml_text).find('e:design_info',namespace)
    listed={entry.get('name') for entry in design.findall('e:design_file',namespace)}
    required=['../rtl/'+p.name for p in sorted((base/'rtl').glob('*')) if p.suffix in ('.sv','.v')]
    added=[name for name in required if name not in listed]
    if added:
        anchor='        <efx:top_vhdl_arch name=""/>'
        if xml_text.count(anchor)!=1:raise ValueError('Cannot find native project source-list anchor')
        lines=''.join('        <efx:design_file name="'+name+'" version="default" library="default"/>\n' for name in added)
        xml_text=xml_text.replace(anchor,lines+anchor,1)
        snapshot_xml.write_text(xml_text,encoding='utf-8')
    entries=ET.fromstring(xml_text).findall('e:design_info/e:design_file',namespace)
    if len({entry.get('name') for entry in entries})!=len(entries):raise ValueError('Duplicate synthesis source')
    if not set(required).issubset({entry.get('name') for entry in entries}):raise ValueError('RTL omitted from synthesis')
    for entry in entries:
        if not (project/entry.get('name')).is_file():raise FileNotFoundError(entry.get('name'))
    sources = {str(p.relative_to(ROOT)): digest(p) for p in (ROOT / 'rtl').glob('*') if p.is_file()}
    sources.update({str(p.relative_to(ROOT)): digest(p) for p in (ROOT / 'efinity').glob('*')
                    if p.is_file() and p.suffix.lower() in ('.xml','.sdc','.mem','.memh')})
    runtime = base / 'runtime'
    runtime.mkdir()
    # Hook only our child Python processes. The installed Efinity files stay intact.
    (runtime / 'sitecustomize.py').write_text('''import os,subprocess
from pathlib import Path
_dll=[]
if os.name == 'nt':
    for rel in ('bin','python311/bin','pt/bin','pgm/bin'):
        p=Path(os.environ['EFINITY_HOME'])/rel
        if p.is_dir(): _dll.append(os.add_dll_directory(str(p)))
_original=subprocess.Popen
class ExplicitPopen(_original):
    def __init__(self,*args,**kwargs):
        if kwargs.get('env') is None: kwargs['env']=os.environ.copy()
        super().__init__(*args,**kwargs)
subprocess.Popen=ExplicitPopen
''', encoding='utf-8')
    env = os.environ.copy()
    env.update({'EFINITY_HOME':tool.as_posix(),'PYTHONHOME':str(tool/'python311'),
        'EFXPT_HOME':str(tool/'pt'),'EFXPGM_HOME':str(tool/'pgm'),
        'EFXDBG_HOME':str(tool/'debugger'),'EFXIPM_HOME':str(tool/'ipm'),
        'EFXSVF_HOME':str(tool/'debugger/svf_player'),
        'EFINITY_USER_DIR_INI':str(Path(env['LOCALAPPDATA'])/'efinity/user_dir.ini'),
        'QT_QPA_PLATFORM_PLUGIN_PATH':str(tool/'python311/platforms'),
        'PYTHONPATH':str(runtime),'PYTHONUNBUFFERED':'1'})
    env['PATH']=os.pathsep.join(str(tool/p) for p in ('python311/bin','bin','pgm/bin','debugger/bin','scripts'))+os.pathsep+env['PATH']
    command=[str(tool/'python311/bin/python.exe'),str(ROOT/'scripts/efinity_entry.py')]
    log=base/'compile.log'
    receipt={'checked_at':datetime.now(timezone(timedelta(hours=8))).isoformat(),
        'project':str(project/'style_video.xml'),'tool':str(tool),'sources':sources,
        'snapshot_sources_added':added,'verified_design_file_count':len(entries),
        'programmed':False,'status':'building','log':str(log)}
    target=ROOT/'build/efinity_receipt.json'
    target.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print('Compiling Efinity snapshot: '+str(project),flush=True)
    with log.open('w',encoding='utf-8') as stream:
        result=subprocess.run(command,cwd=project,env=env,stdout=stream,stderr=subprocess.STDOUT)
    receipt['exit_code']=result.returncode
    verify(receipt)
    target.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in receipt.items() if k!='sources'},indent=2),flush=True)
    return 0 if receipt['status']=='pass' else 1

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--build',action='store_true')
    group.add_argument('--verify-only',action='store_true')
    parser.add_argument('--tool',type=Path,default=Path('C:/Efinity/2026.1'))
    opts=parser.parse_args()
    if opts.build: raise SystemExit(build(opts.tool))
    target=ROOT/'build/efinity_receipt.json'
    receipt=verify(json.loads(target.read_text(encoding='utf-8')))
    target.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in receipt.items() if k!='sources'},indent=2))
    raise SystemExit(0 if receipt['status']=='pass' else 1)
