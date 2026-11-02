"""Resolve project and dataset paths after copying/cloning latest anywhere."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parent
PROJECT=ROOT/'elinx/projects/camera_art_ten_paint'
def main():
 xml=PROJECT/'build/720p/ti60_camera.xml';template=xml.with_suffix('.xml.in').read_text(encoding='utf-8');xml.write_text(template.replace('@PROJECT_ROOT@',PROJECT.as_posix()),encoding='utf-8')
 for p in (ROOT/'pycode').rglob('split.json'):
  d=json.loads(p.read_text(encoding='utf-8'))
  for key in ['training','validation']:d[key]=[str(ROOT/'pycode/convertpic/val2017'/Path(x.replace('\\','/')).name) for x in d[key]]
  p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
 print('Project:',xml);print('Paths ready; HDL, peri, firmware and delivery bit unchanged.')
if __name__=='__main__':main()
