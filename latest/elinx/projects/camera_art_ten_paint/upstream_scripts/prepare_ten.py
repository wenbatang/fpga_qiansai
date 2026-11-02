"""Create an independent ten-style candidate; no old receipts or delivery bits."""
from pathlib import Path
import hashlib,json,shutil,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT.parent/'camera_art_gesture_fix'
B=ROOT/'build/720p'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert not (ROOT/'build/reuse_manifest.json').exists(),'Existing independent project preserved'
    old=json.loads((BASE/'build/720p/signoff.json').read_text(encoding='utf-8'))
    assert old['result']=='PASS' and old['bitstream_sha256']=='09adab80ee5ecddf723635273dc422db0a5d04452b1af1099f3c42fdf9ffc910'
    assert sha(BASE/'build/720p/outflow/ti60_camera.bit')==old['bitstream_sha256']
    records={}
    directories=['rtl','firmware','vendor','pc','scripts','build/720p/ip','build/720p/rtl']
    for directory in directories:
        for source in (BASE/directory).rglob('*'):
            if not source.is_file() or any(p in ['__pycache__','work','work_syn','work_pnr'] for p in source.parts):continue
            if source.suffix in ['.pyc','.log','.rpt','.bit','.wlf','.jou']:continue
            target=ROOT/source.relative_to(BASE)
            if target.exists():continue
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
            records[str(source)]=dict(sha256=sha(source),destination=str(target))
    for source in (BASE/'sim').glob('check_*.py'):
        target=ROOT/'sim'/source.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    for source in (BASE/'sim/templates').glob('*'):
        if source.is_file() and source.suffix in ['.sv','.v','.py','.tcl']:
            target=ROOT/'sim/templates'/source.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    for name in ['camera_mode.h','weights_catalog.h','ddr3_parameter.vh','ti60_camera.peri.xml','weights.mem','ti60_camera.xml']:
        shutil.copy2(BASE/'build/720p'/name,B/name)
    for directory in [ROOT/'rtl',B/'ip',B/'rtl',ROOT/'sim/templates']:
        for path in directory.rglob('*'):
            if path.is_file() and path.suffix in ['.v','.sv','.vh','.xml','.py']:
                text=path.read_text(encoding='utf-8');new=text.replace(BASE.as_posix(),ROOT.as_posix()).replace(str(BASE),str(ROOT))
                if new!=text:path.write_text(new,encoding='utf-8')
    ns='http://www.efinixinc.com/enf_proj';tree=ET.parse(B/'ti60_camera.xml')
    for node in tree.findall('.//{'+ns+'}design_file'):
        node.set('name',(ROOT/Path(node.get('name')).relative_to(BASE)).as_posix())
    ET.register_namespace('efx',ns);tree.write(B/'ti60_camera.xml',encoding='utf-8')
    (ROOT/'parameters/c6').mkdir(parents=True,exist_ok=True)
    (ROOT/'build/reuse_manifest.json').write_text(json.dumps(dict(source_project=str(BASE),source_bit_sha256=old['bitstream_sha256'],sources=records,models_pending=True,board_programmed=False),indent=2),encoding='utf-8')
    print('Prepared independent ten-style candidate; new ten-model export required before mapping')

if __name__=='__main__':main()
