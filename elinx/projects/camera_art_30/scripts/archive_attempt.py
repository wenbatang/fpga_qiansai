"""Preserve a failed pre-bit attempt before changing its production sources."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT=Path(__file__).resolve().parents[1]
B=ROOT/'build/720p'


def main():
    destination=ROOT/'build/baseline_dynamic'
    assert not destination.exists(), 'An existing diagnostic archive must not be overwritten'
    destination.mkdir(parents=True)
    records={}
    for path in [*(ROOT/'rtl').rglob('*.sv'),*(B/'outflow').glob('*.map.v'),
                 *(B/'outflow').glob('*.rpt'),*(B/'outflow').glob('*.sdc'),
                 B/'build_inputs.json',B/'ti60_camera.xml',B/'ti60_camera.peri.xml',
                 B/'ti60_camera.sdc',B/'cdc_constraints.json',B/'dphy_cdc_proof.json']:
        target=destination/path.relative_to(ROOT)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target)
        records[str(target.relative_to(destination))]=hashlib.sha256(target.read_bytes()).hexdigest()
    for name in ['mapped','dma_mapped','debug_dma_raw','debug_dma_trace','debug_dma_model_review']:
        folder=ROOT/'sim'/name
        for path in folder.glob('*.log'):
            target=destination/'diagnostics'/name/path.name
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,target)
            records[str(target.relative_to(destination))]=hashlib.sha256(target.read_bytes()).hexdigest()
    (destination/'archive.json').write_text(json.dumps(dict(
        result='FAILED_NUMERICAL_MAPPING',bit_generated=False,board_programmed=False,
        files=records,scope='Old production dynamic two-dimensional partial writers; no delivery bit'),indent=2),encoding='utf-8')
    print('Archived failed production mapping:',len(records),'files')


if __name__=='__main__':main()
