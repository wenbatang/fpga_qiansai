from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from simutil import questa,receipt,sha


def main():
    folder=ROOT/'sim/mapped_snapshot';folder.mkdir(exist_ok=True);build=ROOT/'build/probe_snapshot'
    inputs=json.loads((build/'inputs.json').read_text(encoding='utf-8'))
    for p,h in inputs.items():assert sha(p)==h
    original=ROOT/'sim/snapshot/tb.sv';(folder/'tb.sv').write_bytes(original.read_bytes())
    files=[*sorted(Path('E:/software/efinity/sim_models/verilog').glob('*.v')),build/'outflow/gesture_snapshot.map.v',folder/'tb.sv']
    questa(folder,files);receipt(folder,[*files,original,build/'inputs.json',*map(Path,inputs),Path(__file__)],'Actual EFX primitive map of color snapshot RTL, all2048 RGB565 words/APB/CPU ownership/bad frame/mode cancel/coincident SOF/diagnostics; no physical camera or hand accuracy')


if __name__=='__main__':main()
