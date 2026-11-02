"""Pinned ASL-HG subset, regrouped by person instead of the source image split."""
from pathlib import Path
import argparse,collections,concurrent.futures,hashlib,json,re,time,urllib.request
ROOT=Path(__file__).resolve().parent
# Exact compatible handshapes only; source numeric3/6/7/8/9 are NOT relabeled.
POS={'O':0,'1':1,'2':2,'F':3,'4':4,'5':5,'Y':6,'L':8,'X':9}
NEG=['A','C','W','I','S','3','7']
def sha(data):return hashlib.sha256(data).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--per-person',type=int,default=24);a=p.parse_args()
 meta=json.loads((ROOT/'data/asl_hg_hf.json').read_text(encoding='utf-8'));groups=collections.defaultdict(list)
 for item in meta['siblings']:
  path=item['rfilename'];parts=path.split('/')
  if len(parts)!=3 or not path.endswith('.jpg'):continue
  label=parts[1]
  if label not in POS and label not in NEG:continue
  match=re.match(r'(P\d+)_',parts[2])
  assert match,path;groups[(label,match[1])].append(path)
 selected=[]
 for (source,person),files in sorted(groups.items()):
  # Spread across the captured sequence. All source train/test rows from a
  # subject stay in our SAME split, including neighboring video captures.
  files.sort();n=min(len(files),a.per_person if source in POS else max(6,a.per_person//3))
  indices=[(i*len(files))//n for i in range(n)]
  split='val' if person=='P8' else 'test' if person in ['P9','P10'] else 'train'
  for i in indices:selected.append(dict(remote_path=files[i],source_label=source,label=POS.get(source,10),person=person,group=person,split=split))
 def fetch(item):
  target=ROOT/'data/asl_hg'/item['remote_path'];target.parent.mkdir(parents=True,exist_ok=True)
  url='https://huggingface.co/datasets/juanjodurillo/asl-hg/resolve/'+meta['sha']+'/'+item['remote_path']
  if not target.exists():
   for attempt in range(4):
    try:
     data=urllib.request.urlopen(url,timeout=30).read();break
    except Exception:
     if attempt==3:raise
     time.sleep(attempt+1)
   from PIL import Image
   import io
   im=Image.open(io.BytesIO(data));im.verify();target.write_bytes(data)
  data=target.read_bytes();return dict(item,path=str(target),sha256=sha(data),bytes=len(data))
 records=[];start=time.monotonic()
 with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
  for item in pool.map(fetch,selected):
   records.append(item)
   if len(records)%100==0:print('ASL-HG',len(records),'/',len(selected),'seconds',round(time.monotonic()-start),flush=True)
 result=dict(source='https://huggingface.co/datasets/juanjodurillo/asl-hg',commit=meta['sha'],primary='https://doi.org/10.1016/j.dib.2026.112492',license='CC-BY-4.0',source_to_digit=POS,negative_source_labels=NEG,items=records,split_scope='P1-P7 train / P8 validation / P9-P10 test, ignoring source random image split',source_metadata_sha256=sha((ROOT/'data/asl_hg_hf.json').read_bytes()))
 (ROOT/'data/asl_hg_manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('ASL-HG READY',len(records),flush=True)
if __name__=='__main__':main()
