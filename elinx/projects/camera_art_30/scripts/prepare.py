"""Copy the reviewed C8 reference into an independent four-style experiment.

Never overwrite an existing source or copy a reference CAD result as a new one.
"""
from pathlib import Path
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
WS = ROOT.parents[2]
REF = WS / 'style_model/elinx'
B = ROOT / 'build/720p'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def copy(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        shutil.copy2(source, destination)


def main():
    if (ROOT / 'build/reuse_manifest.json').exists():
        raise RuntimeError('Already initialized; do not overwrite the optimized project. Use build.py.')
    records = {}
    for directory in ['rtl', 'scripts', 'firmware', 'pc', 'vendor']:
        for source in (REF / directory).rglob('*'):
            if not source.is_file() or '__pycache__' in source.parts:
                continue
            if directory == 'scripts' and source.name == 'prepare.py':
                continue
            destination = ROOT / source.relative_to(REF)
            copy(source, destination)
            records[str(source)] = dict(destination=str(destination), sha256=sha(source))
    # Only editable test sources; every verification receipt is generated anew.
    for source in (REF / 'sim').rglob('*'):
        if source.is_file() and source.suffix in ['.py', '.sv'] and 'work' not in source.parts:
            copy(source, ROOT / source.relative_to(REF))
    old_build = REF / 'build/720p'
    for directory in ['ip', 'rtl']:
        for source in (old_build / directory).rglob('*'):
            if source.is_file() and '__pycache__' not in source.parts:
                copy(source, B / source.relative_to(old_build))
    for name in ['ti60_camera.peri.xml', 'ddr3_parameter.vh', 'camera_mode.h', 'weights_catalog.h']:
        copy(old_build / name, B / name)
    ns = 'http://www.efinixinc.com/enf_proj'
    tree = ET.parse(old_build / 'ti60_camera.xml')
    for node in tree.findall('.//{' + ns + '}design_file'):
        source = Path(node.get('name'))
        destination = ROOT / source.relative_to(REF)
        copy(source, destination)
        node.set('name', destination.as_posix())
    ET.register_namespace('efx', ns)
    tree.write(B / 'ti60_camera.xml', encoding='utf-8')
    # The CPU-generated HDL can contain project paths to its local boot files.
    for directory in [B / 'ip', B / 'rtl']:
        for file in directory.rglob('*'):
            if file.is_file() and file.suffix in ['.v', '.sv', '.vh', '.xml']:
                text = file.read_text(encoding='utf-8')
                revised = text.replace(REF.as_posix(), ROOT.as_posix()).replace(str(REF), str(ROOT))
                if revised != text:
                    file.write_text(revised, encoding='utf-8')
    # Correct reference locations without changing the source reference project.
    for file in (ROOT / 'scripts').glob('*.py'):
        if file.name == 'prepare.py':
            continue
        text = file.read_text(encoding='utf-8')
        text = text.replace('STYLE=ROOT.parent', "STYLE=ROOT.parents[2]/'style_model'")
        text = text.replace('WS=ROOT.parents[1]', 'WS=ROOT.parents[2]')
        text = text.replace("STYLE.parent/'elinx/projects/camera_art_styles'", "ROOT.parent/'camera_art_styles'")
        text = text.replace("ROOT.parent.parent/'elinx/projects/camera_art_styles", "ROOT.parent/'camera_art_styles")
        file.write_text(text, encoding='utf-8')
    (ROOT / 'build/reuse_manifest.json').write_text(json.dumps(dict(
        source_project=str(REF), source_bit_sha256=sha(old_build / 'outflow/ti60_camera.bit'),
        sources=records, reference_read_only=True, board_programmed=False), indent=2), encoding='utf-8')
    print('Independent sources prepared; reference CAD results were not copied.')


if __name__ == '__main__':
    main()
