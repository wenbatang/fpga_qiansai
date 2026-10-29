"""Archive the provisional candidate before exporting final learned data."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'build/720p'


def main():
    selected=json.loads((ROOT/'build/model_selection.json').read_text(encoding='utf-8'))
    assert selected.get('provisional') and not (B/'outflow/ti60_camera.bit').exists()
    archive=ROOT/'build/attempt_runtime_trimmed';assert not archive.exists();archive.mkdir()
    for path in [ROOT/'rtl',ROOT/'parameters/c6']:
        shutil.copytree(path,archive/path.name)
    files=[ROOT/'build/model_selection.json',ROOT/'build/accumulator_bound.json',B/'build_inputs.json',B/'ti60_camera.sdc',B/'cdc_constraints.json',B/'dphy_cdc_proof.json',B/'dphy_final_proof.json']
    files += [p for p in (B/'outflow').glob('*') if p.suffix in ['.rpt','.out','.log','.vdb'] or p.name.endswith('.map.v')]
    records={}
    for p in files:
        if not p.exists():continue
        target=archive/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
        records[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
    (archive/'archive.json').write_text(json.dumps(dict(scope='Provisional candidate; no bit generated',files=records),indent=2),encoding='utf-8')
    # Only explicit candidate freeze/proof files, after their copies are checked.
    for name in ['build_inputs.json','dphy_cdc_proof.json','dphy_final_proof.json']:
        path=(B/name).resolve();assert path.parent==B.resolve() and path.is_relative_to(ROOT.resolve())
        if path.exists():assert hashlib.sha256(path.read_bytes()).hexdigest()==records[str(path)];path.unlink()
    print('Archived provisional runtime model/CAD evidence; final export unlocked')


if __name__=='__main__':main()
