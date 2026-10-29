"""Select four actual C8 exports; retain original slot IDs in a manifest."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
STYLE = ROOT.parents[2] / 'style_model'
SLOTS = [0, 3, 4, 5]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    if (ROOT/'build/720p/build_inputs.json').exists() or (ROOT/'build/720p/outflow/ti60_camera.map.v').exists():
        raise RuntimeError('Mapped inputs are frozen; do not overwrite models/ROM during or after a build. Create a new project revision.')
    blob = bytearray()
    models = []
    for slot, original in enumerate(SLOTS):
        source = next((STYLE / 'parameters/c8').glob(f'{original:02d}_*'))
        name = source.name.split('_', 1)[1]
        dest = ROOT / 'parameters/c8' / f'{slot:02d}_{name}'
        dest.mkdir(parents=True, exist_ok=True)
        for file in source.iterdir():
            if file.is_file():
                shutil.copy2(file, dest / file.name)
        data = (dest / 'parameters.bin').read_bytes()
        assert len(data) == 1159
        blob.extend(data + bytes(1216 - len(data)))
        models.append(dict(slot=slot, source_slot=original, name=name,
                           source=str(source), npz_sha256=sha(source / 'parameters.npz'),
                           bin_sha256=sha(source / 'parameters.bin')))
    build = ROOT / 'build/720p'
    (build / 'weights47.mem').write_text(''.join(
        f'{int.from_bytes(blob[i:i+4], "little"):08x}\n'
        for i in range(0, len(blob), 4)), encoding='ascii')
    (ROOT / 'build/model_selection.json').write_text(json.dumps(dict(
        styles=models, rom_bytes=len(blob), stride_bytes=1216,
        original_models_modified=False, trained_this_turn=False), indent=2), encoding='utf-8')
    shutil.copy2(STYLE / 'integer.py', ROOT / 'scripts/integer.py')
    shutil.copy2(STYLE / 'network.py', ROOT / 'scripts/network.py')
    # Shared constant layers are identical in the selected four; conservative
    # accumulator bound was independently computed over the full superset47.
    bounds = json.loads((STYLE / 'elinx/build/accumulator_bound.json').read_text())
    bounds['styles_compared'] = 4
    bounds['bound_scope'] = 'Conservative bound over original47, selected4 are a subset'
    bounds['original_bound_sha256'] = sha(STYLE / 'elinx/build/accumulator_bound.json')
    (ROOT / 'build/accumulator_bound.json').write_text(json.dumps(bounds, indent=2), encoding='utf-8')
    print('Four learned exports frozen:', [r['name'] for r in models], 'ROM', len(blob), 'bytes')


if __name__ == '__main__':
    main()
