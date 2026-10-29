"""CAD only; never download. Bit generation is gated by local functional/electrical/STA audits."""
from pathlib import Path
import argparse,sys,json,hashlib,re,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'build/720p';sys.path.insert(0,str(Path(__file__).parent))
from tool_run import environment,run
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def execute(stage):
    environment()
    py='E:/software/efinity/python311/bin/python.exe'
    if stage=='interface':cmd=[py,'E:/software/efinity/scripts/efx_run_pt_unified.py','ti60_camera','Titanium','Ti60F225','--output_dir','outflow','--timing_model','I3','--project_xml','ti60_camera.xml']
    elif stage=='prove' or stage=='prove-final':cmd=[py,str(ROOT/'scripts/native_prove_dphy_cdc.py'),*(['--final'] if stage=='prove-final' else [])]
    else:cmd=[py,'E:/software/efinity/scripts/efx_run.py','ti60_camera','--prj','--flow',stage,'--output_dir','outflow']
    print('START',stage,flush=True);code=run(cmd,B,B/(stage+'_console.log'));assert code==0,stage;print('PASS',stage,flush=True)
def capture():
    ns={'e':'http://www.efinixinc.com/enf_proj'};t=ET.parse(B/'ti60_camera.xml');paths=[Path(x.get('name')) for x in t.findall('.//e:design_file',ns)]
    assert paths and all(p.resolve().is_relative_to(ROOT.resolve()) for p in paths),'New project must not compile old sources'
    critical=set(paths)
    for directory in [ROOT/'scripts',ROOT/'firmware',ROOT/'parameters/c8',ROOT/'vendor',B/'ip',B/'rtl']:
        for path in directory.rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix not in ['.pyc','.log']:
                # Validation-only tools can improve after map without changing
                # compiled logic. Final review fingerprints these separately.
                if directory==ROOT/'scripts' and (path.name.startswith('probe') or path.name in ['signoff.py','final_review.py','quality_compare.py','simutil.py']):continue
                critical.add(path)
    for path in B.glob('*.h'):critical.add(path)
    for name in ['ti60_camera.xml','ti60_camera.peri.xml','weights47.mem','firmware.bin','firmware_manifest.json']:
        critical.add(B/name)
    for name in ['model_selection.json','accumulator_bound.json','reuse_manifest.json']:
        critical.add(ROOT/'build'/name)
    firmware=json.loads((B/'firmware_manifest.json').read_text(encoding='utf-8'))
    assert firmware['styles']==4 and firmware['config_writes_per_style']==346 and len(firmware['lanes'])==4
    for name,digest in firmware['lanes'].items():
        assert Path(name).name==name
        for path in [B/name,B/'ip/control_soc'/name]:
            assert sha(path)==digest,'Boot RAM differs from frozen firmware: '+str(path)
            critical.add(path)
    assert all(p.resolve().is_relative_to(ROOT.resolve()) for p in critical),'Build inputs must stay local'
    value=dict(format_version=2,sources={str(p.resolve()):sha(p) for p in paths},
               inputs_sha256={str(p.resolve()):sha(p) for p in sorted(critical)},
               project=sha(B/'ti60_camera.xml'),interface=sha(B/'ti60_camera.peri.xml'),
               weight_rom=sha(B/'weights47.mem'),firmware=sha(B/'firmware.bin'),board_programmed=False)
    (B/'build_inputs.json').write_text(json.dumps(value,indent=2),encoding='utf-8')
def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['map','interface','route','prove','prove-final','config','audit']);a=p.parse_args()
    if a.action=='map':capture();execute('map')
    elif a.action=='route':
        import native_constraints;native_constraints.assemble(B);execute('pnr')
    elif a.action=='config':
        from signoff import audit
        audit(False);execute('pgm');result=audit(True);(B/'signoff.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    elif a.action=='audit':
        from signoff import audit
        print(json.dumps(audit(True),ensure_ascii=False,indent=2))
    else:execute(a.action)
if __name__=='__main__':main()
