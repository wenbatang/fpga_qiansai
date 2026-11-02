"""Create an independent gesture integration project from the signed baseline."""
from pathlib import Path
import hashlib,json,shutil,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT.parent/'camera_art_interactive';B=ROOT/'build/720p'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    assert not (ROOT/'build/reuse_manifest.json').exists(),'Existing candidate preserved'
    signed=json.loads((BASE/'build/720p/signoff.json').read_text(encoding='utf-8'));assert signed['result']=='PASS'
    assert sha(BASE/'build/720p/outflow/ti60_camera.bit')==signed['bitstream_sha256']
    records={}
    for directory in ['rtl','firmware','vendor','pc','scripts','parameters/c6','build/720p/ip','build/720p/rtl']:
        for source in (BASE/directory).rglob('*'):
            if not source.is_file() or '__pycache__' in source.parts:continue
            target=ROOT/source.relative_to(BASE)
            if target.exists():continue
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
            records[str(source)]=dict(sha256=sha(source),destination=str(target))
    for name in ['camera_mode.h','weights_catalog.h','ddr3_parameter.vh','ti60_camera.peri.xml','weights.mem']:
        shutil.copy2(BASE/'build/720p'/name,B/name)
    for name in ['model_selection.json','accumulator_bound.json']:
        shutil.copy2(BASE/'build'/name,ROOT/'build'/name)
    ns='http://www.efinixinc.com/enf_proj';tree=ET.parse(BASE/'build/720p/ti60_camera.xml')
    for node in tree.findall('.//{'+ns+'}design_file'):
        target=ROOT/Path(node.get('name')).relative_to(BASE);assert target.exists();node.set('name',target.as_posix())
    ET.register_namespace('efx',ns);tree.write(B/'ti60_camera.xml',encoding='utf-8')
    for directory in [B/'ip',B/'rtl']:
        for path in directory.rglob('*'):
            if path.is_file() and path.suffix in ['.v','.sv','.vh','.xml']:
                text=path.read_text(encoding='utf-8');new=text.replace(BASE.as_posix(),ROOT.as_posix()).replace(str(BASE),str(ROOT))
                if new!=text:path.write_text(new,encoding='utf-8')
    (ROOT/'build/reuse_manifest.json').write_text(json.dumps(dict(source_project=str(BASE),source_bit_sha256=signed['bitstream_sha256'],sources=records,board_programmed=False),indent=2),encoding='utf-8')
    print('Prepared independent gesture candidate; original signed project untouched')


if __name__=='__main__':main()
