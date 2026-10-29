"""Offline Efinity flow; fail-closed bit generation, no hardware commands."""
from pathlib import Path
import argparse,hashlib,json,sys,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'build/720p'
sys.path.insert(0,str(ROOT/'scripts'))
from tool_run import environment,run


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def capture():
    ns={'e':'http://www.efinixinc.com/enf_proj'}
    paths=[Path(n.get('name')).resolve() for n in ET.parse(B/'ti60_camera.xml').findall('.//e:design_file',ns)]
    assert paths and all(p.is_relative_to(ROOT.resolve()) for p in paths)
    assert not any(p.name.startswith('tiny_') for p in paths),'Half-resolution reference must not be compiled'
    critical=set(paths)
    for directory in [ROOT/'parameters/c6',ROOT/'firmware',ROOT/'vendor',B/'ip',B/'rtl']:
        critical.update(p for p in directory.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ['.pyc','.log'])
    critical.update(ROOT/'scripts'/n for n in ['build.py','firmware.py','prepare.py','board_spec.py','native_constraints.py','native_prove_dphy_cdc.py','tool_run.py','desktop_process.py'])
    critical.update(B.glob('*.h'))
    critical.update(B/n for n in ['ti60_camera.xml','ti60_camera.peri.xml','firmware.bin','firmware_manifest.json','weights.mem'])
    critical.update(ROOT/'build'/n for n in ['model_selection.json','accumulator_bound.json','reuse_manifest.json'])
    fw=json.loads((B/'firmware_manifest.json').read_text(encoding='utf-8'))
    assert fw['styles']==4 and fw['config_writes_per_style']==216 and fw['weights_rom_bytes']==2944
    for name,digest in fw['lanes'].items():
        for p in [B/name,B/'ip/control_soc'/name]:assert sha(p)==digest;critical.add(p)
    assert all(p.resolve().is_relative_to(ROOT.resolve()) for p in critical)
    (B/'build_inputs.json').write_text(json.dumps(dict(format_version=3,sources={str(p):sha(p) for p in paths},
        inputs_sha256={str(p.resolve()):sha(p) for p in sorted(critical)},board_programmed=False),indent=2),encoding='utf-8')


def execute(stage):
    environment();py='E:/software/efinity/python311/bin/python.exe'
    if stage=='interface':command=[py,'E:/software/efinity/scripts/efx_run_pt_unified.py','ti60_camera','Titanium','Ti60F225','--output_dir','outflow','--timing_model','I3','--project_xml','ti60_camera.xml']
    elif stage in ['prove','prove-final']:command=[py,str(ROOT/'scripts/native_prove_dphy_cdc.py'),*(['--final'] if stage=='prove-final' else [])]
    else:command=[py,'E:/software/efinity/scripts/efx_run.py','ti60_camera','--prj','--flow',stage,'--output_dir','outflow']
    print('START',stage,flush=True);code=run(command,B,B/(stage+'_console.log'));assert code==0,stage;print('PASS',stage,flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['map','interface','route','prove','prove-final','config','audit']);a=parser.parse_args()
    if a.action=='map':capture();execute('map')
    elif a.action=='route':
        from native_constraints import assemble
        assemble(B);execute('pnr')
    elif a.action=='config':
        selected=json.loads((ROOT/'build/model_selection.json').read_text(encoding='utf-8'))
        assert not selected.get('provisional',True) and selected.get('independent_styles'),'Only frozen final independent styles may generate a delivery bit'
        from signoff import audit
        audit(False);execute('pgm');result=audit(True)
        (B/'signoff.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    elif a.action=='audit':
        from signoff import audit
        print(json.dumps(audit(True),ensure_ascii=False,indent=2))
    else:execute(a.action)


if __name__=='__main__':main()
