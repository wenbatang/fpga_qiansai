"""Atomic guarded commit on actual EFX snapshot+control maps, real key RTL."""
from pathlib import Path
import json,shutil,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from simutil import questa,sha
def main():
 folder=ROOT/'sim/guard_mapped';folder.mkdir(exist_ok=True)
 tb=ROOT/'sim/guard/tb.sv';shutil.copy2(tb,folder/'tb.sv');shutil.copy2(ROOT/'build/720p/weights.mem',folder/'weights.mem')
 maps=[];bound=[Path(__file__),ROOT/'sim/check_guard.py',tb,folder/'tb.sv',folder/'weights.mem',ROOT/'scripts/simutil.py',ROOT/'rtl/style_keys47.sv']
 for directory,name in [('probe_snapshot','gesture_snapshot'),('probe_ten_control','video_control_apb_fast')]:
  probe=ROOT/'build'/directory;inputs=json.loads((probe/'inputs.json').read_text(encoding='utf-8'))
  for p,h in inputs.items():assert sha(Path(p))==h,'Stale mapped guard input '+p
  source=probe/'outflow'/(name+'.map.v');maps.append(source);bound.extend([source,probe/'inputs.json',*map(Path,inputs),probe/'map_console.log'])
 files=[*sorted(Path('E:/software/efinity/sim_models/verilog').glob('*.v')),*maps,ROOT/'rtl/style_keys47.sv',folder/'tb.sv']
 questa(folder,files)
 (folder/'verification.json').write_text(json.dumps(dict(result='PASS',scope='Actual EFX snapshot and control primitive maps + actual debounced key RTL; same/adjacent-edge guarded commit and exact view-edge rejection, no real board/metastability proof',sources_sha256={str(p):sha(p) for p in dict.fromkeys([*bound,*files])},logs_sha256={str(p):sha(p) for p in folder.glob('*.log')}),indent=2),encoding='utf-8')
if __name__=='__main__':main()
