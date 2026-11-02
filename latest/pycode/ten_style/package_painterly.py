"""Export an isolated parameter package, without touching any FPGA project."""
from pathlib import Path
import argparse,json,hashlib
import numpy as np
from hardware_qat import load
from integer import model_layers
from export import write_exports
ROOT=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--checkpoint',type=Path,required=True);p.add_argument('--package',type=Path,required=True);a=p.parse_args()
 assert not a.package.exists(),'An earlier export is preserved'
 model,data=load(a.checkpoint);assert data.get('painting_teachers') and data['hardware_qat']
 write_exports([model_layers(model,s) for s in range(10)],a.package,a.checkpoint,data)
 path=a.package/'build/model_selection.json';selection=json.loads(path.read_text(encoding='utf-8'))
 selection.update(teacher_is_c8=False,painting_retraining=True,reference_hashes=data['reference_hashes'],
  teacher_strategy='Actual paint-reference Gram + four high-capacity painting teachers; frozen C8 outputs only weak anchors for the other six slots',
  weak_c8_anchor_slots=[1,5,6,7,8,9],refinement_steps=data['refinement_steps'],training_visits=data['training_visits'],
  package_only=True,fpga_project_modified=False)
 path.write_text(json.dumps(selection,ensure_ascii=False,indent=2),encoding='utf-8')
 blob=bytearray();files=[a.checkpoint,Path(__file__),ROOT/'export.py',ROOT/'hardware_qat.py',ROOT/'integer.py',ROOT/'network.py']
 for s in range(10):
  folder=next((a.package/'parameters/c6').glob(f'{s:02d}_*'));raw=(folder/'parameters.bin').read_bytes();assert len(raw)==712
  blob.extend(raw+bytes(736-len(raw)));files.extend(p for p in folder.glob('*') if p.is_file())
 assert len(blob)==7360
 actual=b''.join(int(line,16).to_bytes(4,'little') for line in (a.package/'build/720p/weights.mem').read_text().split())
 assert actual==blob
 files.extend([path,a.package/'build/720p/weights.mem',a.package/'build/accumulator_bound.json'])
 result=dict(result='PASS',checkpoint_sha256=sha(a.checkpoint),styles=10,rom_bytes=7360,
  config_writes_per_style=216,weights_per_style=396,package_only=True,fpga_project_modified=False,
  sources_sha256={str(p.resolve()):sha(p) for p in files},reference_hashes=data['reference_hashes'])
 (a.package/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print('PASS independent painterly parameter package',a.package,flush=True)
if __name__=='__main__':main()
