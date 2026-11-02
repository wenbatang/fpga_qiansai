"""Curate a complete current release, preserving the signed source project."""
from pathlib import Path
import hashlib,json,shutil
WS=Path(__file__).resolve().parents[2];DEST=WS/'latest';BASE=WS/'elinx/projects/camera_art_ten_paint'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
records=[]
def copy(source,target=None):
 source=Path(source);target=target or DEST/source.relative_to(WS)
 target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
 records.append(dict(source=str(source.relative_to(WS)),destination=str(target.relative_to(DEST)),sha256=sha(source)))
def tree(source,target=None):
 for f in Path(source).rglob('*'):
  if f.is_file() and not any(x in ['__pycache__','.venv','work','work_syn','work_pnr'] for x in f.parts) and f.suffix not in ['.pyc','.wlf','.vvp']:copy(f,(Path(target)/f.relative_to(source)) if target else None)
def main():
 assert not (DEST/'source_provenance.json').exists(),'Do not overwrite an existing release'
 DEST.mkdir(exist_ok=True);signed=json.loads((BASE/'build/720p/signoff.json').read_text(encoding='utf-8'));assert signed['result']=='PASS' and sha(BASE/'build/720p/outflow/ti60_camera.bit')==signed['bitstream_sha256']
 for folder in ['rtl','firmware','vendor','pc','parameters','docs']:tree(BASE/folder)
 for n in ['README.md','architecture.html']:copy(BASE/n)
 B=BASE/'build/720p';P=DEST/BASE.relative_to(WS)
 for folder in ['ip','rtl']:
  if (B/folder).is_dir():tree(B/folder)
 for p in B.iterdir():
  if p.is_file() and (p.suffix in ['.xml','.sdc','.h','.vh','.bin','.mem','.elf','.hex','.map']):copy(p)
 # Original CAD and verification evidence is archived as evidence, not rerun
 # results for a new absolute path. Rebuild never reuses an old PASS tag.
 for p in B.iterdir():
  if p.is_file() and p.suffix in ['.json','.log']:copy(p,P/'release/evidence'/p.name)
 for p in (B/'outflow').iterdir():
  if p.is_file() and p.suffix in ['.rpt','.csv','.log']:copy(p,P/'release/evidence/outflow'/p.name)
 copy(B/'outflow/ti60_camera.bit',P/'release/ti60_camera.bit')
 for p in (BASE/'build').glob('*.json'):copy(p,P/'release/evidence'/p.name)
 # Preserve all handwritten build/verification sources. Their historical audit
 # chain remains identified as upstream; standalone package entry is relocate.py.
 tree(BASE/'scripts',P/'upstream_scripts')
 for p in (BASE/'sim').glob('*.py'):copy(p,P/'verification_sources'/p.name)
 if (BASE/'sim/templates').is_dir():tree(BASE/'sim/templates',P/'verification_sources/templates')
 for name in signed['simulations']:
  p=BASE/'sim'/name/'verification.json'
  if p.exists():copy(p,P/'release/evidence/simulations'/name/'verification.json')
 # Code and final models needed by the exact ten-style training procedure.
 for folder in ['ten_style','full720_style','painterly_style']:
  for p in (WS/'pycode'/folder).glob('*'):
   if p.is_file() and (p.suffix in ['.py','.md'] or p.name=='requirements.txt'):copy(p)
 copy(WS/'pycode/style_network.py')
 for run in ['ten_painterly_v2','ten_painterly_probe_v1','ten_c6_texture_v1','ten_c6_v2']:
  for n in ['model.pt','initial.pt','training.csv','split.json','launch.json','complete.json','status.json']:
   p=WS/'pycode/ten_style/runs'/run/n
   if p.exists():copy(p)
 tree(WS/'pycode/ten_style/runs/ten_painterly_v2/package')
 for n in ['model.pt','training.csv','complete.json']:
  p=WS/'pycode/painterly_style/runs/paint_final'/n
  if p.exists():copy(p)
 launch=json.loads((WS/'pycode/ten_style/runs/ten_painterly_v2/launch.json').read_text(encoding='utf-8'))
 for p in launch['reference_hashes']:copy(Path(p))
 for p in launch['c8_teacher_hashes']:copy(Path(p))
 # Fixed public-content split, excluding all user demonstration photographs.
 splitpath=WS/'pycode/ten_style/runs/ten_c6_v2/split.json';split=json.loads(splitpath.read_text(encoding='utf-8'));content=[]
 excluded=set(split['user_images_sha256'].values())
 for filename in split['training']+split['validation']:
  p=Path(filename);digest=sha(p);assert digest not in excluded
  copy(p,DEST/'pycode/convertpic/val2017'/p.name);content.append(dict(filename=p.name,split='train' if filename in split['training'] else 'validation',sha256=digest))
 # Current authoritative hardware PDFs, not old revisions or entire demos.
 hw=WS/'elinx/elinxdemo/Ti60F225_DemoBoard_v4'
 for n in ['TI60F225I3-V4_SCH-20261012（原理图）.pdf','摄像头SC431HAI_数据手册_V1.1.pdf']:copy(hw/n)
 # Relocation edits only paths and training cache lookup. RTL/firmware/peri/bit
 # are identical to the signed source. Save original metadata separately.
 for run in ['ten_painterly_v2','ten_painterly_probe_v1','ten_c6_texture_v1','ten_c6_v2']:
  p=DEST/'pycode/ten_style/runs'/run/'split.json'
  if not p.exists():continue
  d=json.loads(p.read_text(encoding='utf-8'));shutil.copy2(p,p.with_name('split.original.json'))
  for key in ['training','validation']:d[key]=[str(DEST/'pycode/convertpic/val2017'/Path(x).name) for x in d[key]]
  # Demonstration/private user paths are provenance only, not dependencies.
  d['demonstration']=[];p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
 p=DEST/'pycode/full720_style/train.py';s=p.read_text(encoding='utf-8').replace("Path('C:/Users/wenbatang/.cache/torch/hub/checkpoints/vgg19-dcbb9e9d.pth')","Path(torch.hub.get_dir())/'checkpoints/vgg19-dcbb9e9d.pth'");p.write_text(s,encoding='utf-8')
 # Prepare a relocatable template; peri and HDL are never rewritten.
 p=P/'build/720p/ti60_camera.xml';s=p.read_text(encoding='utf-8');template=s.replace(BASE.as_posix(),'@PROJECT_ROOT@').replace(str(BASE),'@PROJECT_ROOT@');(p.with_suffix('.xml.in')).write_text(template,encoding='utf-8');p.write_text(template.replace('@PROJECT_ROOT@',P.as_posix()),encoding='utf-8')
 p=P/'README.md';s=p.read_text(encoding='utf-8').replace('(build/720p/outflow/ti60_camera.bit)','(release/ti60_camera.bit)').replace('显示L0时握拳','显示L0时五指弯成O形').replace('0握拳，1～5伸指数，6拇指＋小指，7三指捏合，8拇指＋食指，9食指弯钩。','0为O形；1食指；2食指＋中指；3中指＋无名指＋小指；4除拇指；5全掌；6拇指＋小指；7拇指＋食指＋小指；8拇指＋食指；9食指弯钩。');p.write_text(s,encoding='utf-8')
 (DEST/'source_provenance.json').write_text(json.dumps(dict(source_project=str(BASE),source_bit_sha256=signed['bitstream_sha256'],model_sha256=sha(DEST/'pycode/ten_style/runs/ten_painterly_v2/model.pt'),copied_files=records,content_split=content,content_images=536,board_programmed=False,scope='Curated source/config/IP/firmware/model/content archive. No CAD rerun. Source provenance hashes are original bytes; path/cache/doc edits are recorded by bundle manifest.'),ensure_ascii=False,indent=2),encoding='utf-8')
 print('LATEST',len(records),'copied files;',sum(p.stat().st_size for p in DEST.rglob('*') if p.is_file()),'bytes',flush=True)
if __name__=='__main__':main()
