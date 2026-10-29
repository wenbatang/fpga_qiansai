"""Build independent C6/RF33 RV32 firmware and four Sapphire boot byte lanes.

Only the learned catalog and the two 1217->365 constants in a private main.c
clone change. Sensor table, readback/exposure safety, fail paths and PLIC code
remain byte-identical to the accepted source. No old build or hardware access.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import struct
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
WS = ROOT.parents[2]
BASE = ROOT / 'build/camera_720_fast'
EXPORT = WS / 'pycode/runs/fps_student_v1/refined/rf33/export'
TOOL = Path('E:/softare_FPGA/xpack-riscv-none-elf-gcc-15.2.0-1-win32-x64/xpack-riscv-none-elf-gcc-15.2.0-1/bin')
STYLES = ('vangogh', 'papercut', 'comic', 'inkwash')
BOOT_PREFIX = 'EfxSapphireSoc.v_toplevel_system_ramA_logic_ram_symbol'
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(WS / 'pycode'))
from tool_run import run
from art6_border import load_export


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def catalog(export_root=EXPORT):
    addresses, values, models = None, [], []
    for style in STYLES:
        metadata, layers = load_export(export_root / style)
        assert [int(layer['dilation']) for layer in layers] == [1, 1, 2, 4, 8]
        if metadata['monochrome']:
            assert layers[-1]['weights'].shape[0] == 1
            layers[-1]['weights'] = np.repeat(layers[-1]['weights'], 3, axis=0)
            layers[-1]['bias'] = np.repeat(layers[-1]['bias'], 3)
        aa, vv = [], []
        for index, layer in enumerate(layers):
            weights = layer['weights']
            cout, cin = weights.shape[:2]
            lanes = 3 if index == 4 else 6
            assert cout == lanes and cin == (3 if index == 0 else 6)
            chunks = (cin * lanes * 8 + 31) // 32
            for tap in range(9):
                packed = sum((int(weights[o, c, tap // 3, tap % 3]) & 255) << (8 * (o * cin + c))
                             for o in range(lanes) for c in range(cin))
                for chunk in range(chunks):
                    aa.append((index << 11) | (tap << 5) | chunk)
                    vv.append((packed >> (chunk * 32)) & 0xffffffff)
            for channel, bias in enumerate(layer['bias']):
                aa.append(0x4000 | (index << 11) | channel)
                vv.append(int(bias) & 0xffffffff)
            aa.append(0x8000 | (index << 11))
            vv.append(int(layer['shift']))
        assert len(aa) == 365
        if addresses is not None:
            assert addresses == aa
        addresses = aa
        values.append(vv)
        models.append(metadata)
    return models, addresses, values


def build_firmware(output):
    output = Path(output).resolve()
    assert output.is_relative_to((ROOT / 'build').resolve()), 'Output must remain inside this project build/'
    assert output.name.startswith(('camera_fps_', 'fps_c6_')), 'Independent fps build required; old releases protected'
    output.mkdir(parents=True, exist_ok=True)
    assert not (output / 'firmware.bin').exists(), 'Keep existing firmware; use a fresh independent build'
    code = output / 'firmware'
    code.mkdir(exist_ok=True)
    original = ROOT / 'firmware/main.c'
    source = original.read_text(encoding='utf-8')
    assert source.count('1217') == 2
    modified = source.replace('1217', '365')
    assert modified.replace('365', '1217') == source
    (code / 'main.c').write_text(modified, encoding='utf-8')
    for name in ('start.S', 'link.ld'):
        shutil.copyfile(ROOT / 'firmware' / name, code / name)
    shutil.copyfile(BASE / 'camera_mode.h', output / 'camera_mode.h')
    baseline = json.loads((BASE / 'firmware_manifest.json').read_text(encoding='utf-8'))
    assert baseline['mode_commands'] == 163
    models, addresses, values = catalog()
    header = '#include <stdint.h>\nstatic const uint16_t style_addresses[365]={' + ','.join(map(str, addresses)) + '};\n'
    header += 'static const uint32_t style_values[4][365]={' + ','.join('{' + ','.join(map(str, row)) + '}' for row in values) + '};\n'
    (output / 'style_catalog.h').write_text(header, encoding='utf-8')
    (output / 'config.mem').write_text(''.join(f'{address:04x}{value:08x}\n' for row in values
                                            for address, value in zip(addresses, row)), encoding='ascii')
    command = [str(TOOL / 'riscv-none-elf-gcc.exe'), '-march=rv32i_zicsr', '-mabi=ilp32', '-Os', '-ffreestanding',
               '-fno-builtin', '-fno-pic', '-msmall-data-limit=0', '-nostdlib', '-Wl,--no-relax', '-Wl,-Map=firmware.map',
               '-T', str(code / 'link.ld'), '-I', str(output), str(code / 'start.S'), str(code / 'main.c'), '-lgcc', '-o', 'firmware.elf']
    assert run(command, output, output / 'firmware_compile.log') == 0, 'RV32 compile failed'
    for fmt, name in (('ihex', 'firmware.hex'), ('binary', 'firmware.bin')):
        assert run([str(TOOL / 'riscv-none-elf-objcopy.exe'), '-O', fmt, 'firmware.elf', name],
                   output, output / (name + '.log')) == 0, 'objcopy failed'
    binary = (output / 'firmware.bin').read_bytes()
    assert len(binary) <= 32768
    address_bytes = struct.pack('<' + 'H' * len(addresses), *addresses)
    value_bytes = b''.join(struct.pack('<' + 'I' * len(row), *row) for row in values)
    assert binary.count(address_bytes) == 1 and binary.count(value_bytes) == 1, 'Actual compiled catalog missing or duplicated'
    image = binary + bytes(32768 - len(binary))
    boot = {}
    for lane in range(4):
        name = BOOT_PREFIX + str(lane) + '.bin'
        data = ''.join(f'{byte:08b}\n' for byte in image[lane::4])
        (output / name).write_text(data, encoding='ascii')
        dest = output / 'ip/control_soc' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(output / name, dest)
        boot[name] = sha(output / name)
    reconstructed = bytearray(32768)
    for lane in range(4):
        reconstructed[lane::4] = bytes(int(row, 2) for row in (output / (BOOT_PREFIX + str(lane) + '.bin')).read_text().splitlines())
    assert reconstructed == image
    files = [Path(__file__), *sorted(code.glob('*')), output / 'camera_mode.h', output / 'style_catalog.h',
             output / 'config.mem', output / 'firmware.elf', output / 'firmware.hex', output / 'firmware.bin',
             *(output / name for name in boot)]
    for style in STYLES:
        files.extend(p for p in (EXPORT / style).glob('*') if p.is_file())
    manifest = {'result': 'PASS_COMPILE_CATALOG_AND_BOOT_IMAGE', 'isa': 'RV32I_Zicsr, ILP32',
                'ram_base': '0xf9000000', 'ram_bytes': 32768, 'apb_base': '0xf8100000', 'irq': 16,
                'sensor_7bit_address': 48, 'sensor_id': 'cd6b', 'mode_commands': 163,
                'mode_source': baseline['mode_source'], 'models': models, 'weights_per_style': 1296,
                'writes_per_style': 365, 'firmware_bytes': len(binary), 'boot_ram': boot,
                'original_main_sha256': sha(original), 'main_delta': 'Exactly two literal counts 1217->365; all other bytes unchanged.',
                'camera_mode_header_unchanged': sha(BASE / 'camera_mode.h') == sha(output / 'camera_mode.h'),
                'catalog_found_in_actual_binary': True, 'boot_ram_matches_firmware': True,
                'runtime_sensor_faults_or_sapphire_rtl': 'Not tested by this compiler helper; run new firmware behavioral and Sapphire regressions.',
                'hardware_accessed': False, 'files': {str(path.relative_to(WS)): sha(path) for path in files}}
    (output / 'firmware_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print('PASS C6 RF33 RV32', len(binary), 'bytes,4x365 catalog exact in binary,4x8192 boot byte lanes; old firmware unchanged', flush=True)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    build_firmware(parser.parse_args().build)
