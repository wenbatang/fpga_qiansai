"""Read-only bundle integrity and physical-configuration checks; no hardware IO."""
from pathlib import Path
import csv,hashlib,importlib.util,json,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT/'elinx/projects/camera_art_ten_paint'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical(path):
 p=Path(path)
 if p.name=='ti60_camera.xml':return p.read_text(encoding='utf-8').replace(PROJECT.as_posix(),'@PROJECT_ROOT@').replace(str(PROJECT),'@PROJECT_ROOT@').encode()
 if p.name=='split.json':return p.read_text(encoding='utf-8').replace(str(ROOT),'@BUNDLE_ROOT@').replace(ROOT.as_posix(),'@BUNDLE_ROOT@').replace(str(ROOT).replace('\\','\\\\'),'@BUNDLE_ROOT@').encode()
 return p.read_bytes()
def main():
 manifest=json.loads((ROOT/'bundle_manifest.json').read_text(encoding='utf-8'))
 for name,expected in manifest['files'].items():
  p=ROOT/name;assert p.is_file(),name;assert hashlib.sha256(canonical(p)).hexdigest()==expected,name
 assert sha(PROJECT/'release/ti60_camera.bit')=='75766d7cdd66154d2d8da1db7a800ed49f38864ae52316c97b2dadaab959a2de'
 assert sha(ROOT/'pycode/ten_style/runs/ten_painterly_v2/model.pt')=='7250b683772fdd9c3756f9f062ce639aadfcbfbc49eb64e6ac2e15588e489e86'
 ns={'e':'http://www.efinixinc.com/enf_proj'};xml=PROJECT/'build/720p/ti60_camera.xml';tree=ET.parse(xml);count=0
 for node in tree.findall('.//e:design_file',ns):
  p=Path(node.get('name'));assert p.is_file() and p.resolve().is_relative_to(ROOT.resolve()),node.get('name');count+=1
 # Compare every actual pin with the independently transcribed board mapping.
 p=PROJECT/'upstream_scripts/board_spec.py';spec=importlib.util.spec_from_file_location('release_board',p);board=importlib.util.module_from_spec(spec);spec.loader.exec_module(board)
 assert sha(board.PDF)==board.PDF_SHA
 csvpath=PROJECT/'release/evidence/outflow/ti60_camera.pinout.csv';rows=list(csv.DictReader(x for x in csvpath.read_text(encoding='utf-8').splitlines() if x and not x.startswith('#')));actual={r['Signal Name']:r for r in rows if r['Signal Name']};expected=board.expected_pins(True);assert set(actual)==set(expected)
 for n,values in expected.items():assert tuple(actual[n][k] for k in ['Pin Number','Direction','Bank','I/O Bank Voltage'])==values,n
 assert len(actual)==79
 pn={'p':'http://www.efinixinc.com/peri_design_db'};peri=ET.parse(PROJECT/'build/720p/ti60_camera.peri.xml');banks={n.get('name'):n.get('iostd').split()[0] for n in peri.findall('.//p:iobank',pn)}
 assert banks=={'1A':'1.8','1B':'1.8','2A':'1.2','2B':'1.2','3A':'1.8','3B':'1.5','4A':'1.5','4B':'1.5','TL':'3.3','TR':'3.3','BL':'3.3','BR':'3.3'}
 provenance=json.loads((ROOT/'source_provenance.json').read_text(encoding='utf-8'));production=0
 for item in provenance['copied_files']:
  rel=item['destination'];parts=Path(rel).parts
  if any(x in parts for x in ['rtl','vendor','firmware','parameters','ip']) and not rel.endswith('.json'):
   assert sha(ROOT/rel)==item['sha256'],'Production source changed: '+rel;production+=1
 print('PASS:',len(manifest['files']),'bundle files;',count,'self-contained design files;',production,'original production files;79 physical pins;12 banks. No CAD rerun or hardware access.')
if __name__=='__main__':main()
