"""Map production DMA + learned CNN at bounded geometry for primitive simulation."""
from pathlib import Path
import hashlib
import argparse
import json
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
B = ROOT / 'build/probe_dma'
sys.path.insert(0, str(ROOT / 'scripts'))
from tool_run import environment, run


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--engine',type=Path)
    parser.add_argument('--pointwise',type=Path)
    args=parser.parse_args()
    B.mkdir(parents=True, exist_ok=True)
    ns = 'http://www.efinixinc.com/enf_proj'
    tree = ET.parse(ROOT / 'build/720p/ti60_camera.xml')
    tree.getroot().set('name', 'tiny_dma_probe')
    info = tree.find('{' + ns + '}design_info')
    info.find('{' + ns + '}top_module').set('name', 'tiny_dma_probe')
    for node in list(info):
        if node.tag == '{' + ns + '}design_file':
            info.remove(node)
    source = args.engine.resolve() if args.engine else ROOT / 'rtl/p720/video_tile_engine_async.sv'
    text = source.read_text(encoding='utf-8')
    assert text.count('module video_tile_engine_async #(') == 1
    text = text.replace('module video_tile_engine_async #(', 'module tiny_dma_probe #(')
    text = text.replace('WIDTH=1280,HEIGHT=720', 'WIDTH=256,HEIGHT=40')
    text = text.replace('TILE_CORE=128,HALO=32', 'TILE_CORE=64,HALO=32')
    wrapper = B / 'tiny_dma_probe.sv'
    wrapper.write_text(text, encoding='utf-8')
    dependencies = [*[ROOT / 'rtl/p720' / n for n in ['video_cnn_async.sv', 'stream_fifo_24.sv']],
                    *[ROOT / 'rtl' / n for n in ['reset_sync.sv', 'style_line_ram.sv',
                    'tiny_shared_params.sv', 'tiny_spatial.sv', 'tiny_pointwise.sv',
                    'tiny_pool.sv', 'tiny_kernel.sv', 'tiny_view.sv']],
                    ROOT / 'vendor/rtl/ddr3_controller/common/efx_fifo_v2.3/efx_fifo_wrapper.v']
    files = [wrapper, *dependencies]
    if args.pointwise:
        files=[args.pointwise.resolve() if p==ROOT/'rtl/tiny_pointwise.sv' else p for p in files]
    for path in files:
        info.insert(1, ET.Element('{' + ns + '}design_file', name=path.as_posix(),
                                 version='default', library='default'))
    tree.find('{' + ns + '}interface_info').clear()
    tree.find('{' + ns + '}constraint_info').clear()
    ET.register_namespace('efx', ns)
    tree.write(B / 'tiny_dma_probe.xml', encoding='utf-8')
    (B / 'inputs.json').write_text(json.dumps({str(p): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [source, *files]}, indent=2), encoding='utf-8')
    environment()
    command = ['E:/software/efinity/python311/bin/python.exe',
               'E:/software/efinity/scripts/efx_run.py', 'tiny_dma_probe', '--prj',
               '--flow', 'map', '--output_dir', 'outflow']
    assert run(command, B, B / 'map_console.log') == 0


if __name__ == '__main__':
    main()
