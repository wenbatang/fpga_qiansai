"""Independent interactive clone; never edits the signed source project."""
from pathlib import Path
import hashlib,json,shutil,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT.parent/'camera_full720_30';B=ROOT/'build/720p'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
    assert not (ROOT/'build/reuse_manifest.json').exists(),'Already initialized'
    records={}
    for directory in ['rtl','firmware','vendor','pc','scripts','parameters/c6','build/720p/ip','build/720p/rtl']:
        for source in (BASE/directory).rglob('*'):
            if not source.is_file() or '__pycache__' in source.parts:continue
            target=ROOT/source.relative_to(BASE)
            if target.exists():continue
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
            records[str(source)]=dict(sha256=sha(source),destination=str(target))
    for name in ['camera_mode.h','weights_catalog.h','ddr3_parameter.vh','ti60_camera.peri.xml']:
        shutil.copy2(BASE/'build/720p'/name,B/name)
    ns='http://www.efinixinc.com/enf_proj';tree=ET.parse(BASE/'build/720p/ti60_camera.xml')
    for node in tree.findall('.//{'+ns+'}design_file'):
        source=Path(node.get('name'));target=ROOT/source.relative_to(BASE);assert target.exists();node.set('name',target.as_posix())
    ET.register_namespace('efx',ns);tree.write(B/'ti60_camera.xml',encoding='utf-8')
    for folder in [B/'ip',B/'rtl']:
        for path in folder.rglob('*'):
            if path.is_file() and path.suffix in ['.v','.sv','.vh','.xml']:
                text=path.read_text(encoding='utf-8');new=text.replace(BASE.as_posix(),ROOT.as_posix()).replace(str(BASE),str(ROOT))
                if new!=text:path.write_text(new,encoding='utf-8')
    value=dict(source_project=str(BASE),source_bit_sha256=sha(BASE/'build/720p/outflow/ti60_camera.bit'),sources=records,board_programmed=False)
    (ROOT/'build/reuse_manifest.json').write_text(json.dumps(value,indent=2),encoding='utf-8');print('Copied independent interactive project; no old build output/bit copied')


if __name__=='__main__':main()
