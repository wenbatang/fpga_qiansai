"""Initialize an independent full-resolution CNN project; no old source changes."""
from pathlib import Path
import hashlib,json,shutil,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT.parent/'camera_art_30';B=ROOT/'build/720p'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def copy(src,dst):
    dst.parent.mkdir(parents=True,exist_ok=True)
    if not dst.exists():shutil.copy2(src,dst)


def main():
    assert not (ROOT/'build/reuse_manifest.json').exists(),'Already initialized'
    records={}
    for directory in ['rtl','firmware','vendor','pc']:
        for src in (BASE/directory).rglob('*'):
            if src.is_file() and '__pycache__' not in src.parts:
                dst=ROOT/src.relative_to(BASE);copy(src,dst);records[str(src)]=dict(sha256=sha(src),destination=str(dst))
    for name in ['board_spec.py','native_constraints.py','native_prove_dphy_cdc.py','desktop_process.py','tool_run.py','firmware.py']:
        copy(BASE/'scripts'/name,ROOT/'scripts'/name)
    for directory in ['ip','rtl']:
        for src in (BASE/'build/720p'/directory).rglob('*'):
            if src.is_file() and '__pycache__' not in src.parts:copy(src,B/src.relative_to(BASE/'build/720p'))
    for name in ['ti60_camera.peri.xml','camera_mode.h','ddr3_parameter.vh']:
        copy(BASE/'build/720p'/name,B/name)
    ns='http://www.efinixinc.com/enf_proj';tree=ET.parse(BASE/'build/720p/ti60_camera.xml');info=tree.find('{'+ns+'}design_info')
    removed={'tiny_spatial.sv','tiny_pointwise.sv','tiny_shared_params.sv','tiny_pool.sv','tiny_kernel.sv','tiny_view.sv'}
    for node in list(info):
        if node.tag!='{'+ns+'}design_file':continue
        src=Path(node.get('name'))
        if src.name in removed:info.remove(node);continue
        dst=ROOT/src.relative_to(BASE);copy(src,dst);node.set('name',dst.as_posix())
    for name in ['full_shared_params.sv','full_pointwise.sv','full_dw3x3.sv','full_kernel.sv','full_view.sv']:
        info.insert(1,ET.Element('{'+ns+'}design_file',name=(ROOT/'rtl'/name).as_posix(),version='default',library='default'))
    ET.register_namespace('efx',ns);tree.write(B/'ti60_camera.xml',encoding='utf-8')
    for file in (B/'ip').rglob('*'):
        if file.is_file() and file.suffix in ['.v','.sv','.vh','.xml']:
            text=file.read_text(encoding='utf-8');new=text.replace(BASE.as_posix(),ROOT.as_posix()).replace(str(BASE),str(ROOT))
            if new!=text:file.write_text(new,encoding='utf-8')
    changes={
        ROOT/'rtl/p720/video_cnn_async.sv':[(' tiny_view #(',' full_view #(')],
        ROOT/'rtl/p720/video_tile_engine_async.sv':[('TILE_CORE=128,HALO=32','TILE_CORE=320,HALO=16')],
        ROOT/'rtl/p720/video_control_apb_fast.sv':[
            ('WEIGHT_WRITES=346','WEIGHT_WRITES=216'),
            ('load_layer==0?216:load_layer==9?24:load_layer[0]?72:64','load_layer==0?20:load_layer==9?20:load_layer[0]?56:36'),
            ('load_layer==9?3:8','load_layer==9?3:6'),
            ('parameter_rom[0:1215]','parameter_rom[0:735]'),('weights47.mem','weights.mem'),("paddr<16'h2300","paddr<16'h1b80")],
        ROOT/'firmware/main.c':[('style*1216u','style*736u'),('p+=nc;','p+=(nc+3u)&~3u;'),('REG(0x58)!=346','REG(0x58)!=216')],
        ROOT/'scripts/firmware.py':[('config_writes_per_style=346','config_writes_per_style=216'),('weights_rom_bytes=4864','weights_rom_bytes=2944')],
        ROOT/'scripts/native_constraints.py':[
            ("assert len(report['bundle_paths'])==73","assert 64<=len(report['bundle_paths'])<=85")]
    }
    for file,replacements in changes.items():
        text=file.read_text(encoding='utf-8')
        for before,after in replacements:
            assert before in text,(file,before);text=text.replace(before,after)
        file.write_text(text,encoding='utf-8')
    (B/'weights_catalog.h').write_text('#include <stdint.h>\nstatic const uint16_t weight_count[10]={20,56,36,56,36,56,36,56,36,20};\nstatic const uint8_t channel_count[10]={6,6,6,6,6,6,6,6,6,3};\n',encoding='ascii')
    (ROOT/'build/reuse_manifest.json').write_text(json.dumps(dict(source_project=str(BASE),source_bit_sha256=sha(BASE/'build/720p/outflow/ti60_camera.bit'),sources=records,board_programmed=False),indent=2),encoding='utf-8')
    print('Independent full720 project copied. No CAD output/bit copied.')


if __name__=='__main__':main()
