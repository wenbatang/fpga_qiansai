"""Pinned, public HaGRID subset. Preserve subject IDs and exact ZIP ranges."""
from pathlib import Path
import concurrent.futures,hashlib,json,struct,time
from remote_hagrid import Remote
ROOT=Path(__file__).resolve().parent
def main():
 import sys
 sys.path.insert(0,str(ROOT/'build/deps'))
 import pyarrow.parquet as pq
 cat=json.loads((ROOT/'data/hagrid_catalogue.json').read_text(encoding='utf-8'))
 annotations=pq.read_table(ROOT/'data/hagrid_annotations.parquet').to_pandas()
 entries=sorted(cat['items'],key=lambda x:x['offset']);selected=[]
 for label,limit in [('rock',300),('palm',120)]:
  candidates=[]
  for i,z in enumerate(entries[:-1]):
   if '/train_val_'+label+'/' not in z['name'] or not z['name'].endswith('.jpg'):continue
   uid=Path(z['name']).stem
   if uid not in annotations.index:continue
   a=annotations.loc[uid];person=str(a['user_id'])
   # Deterministic subject-level split, shared across all HaGRID classes.
   h=int(hashlib.sha256(person.encode()).hexdigest()[:8],16)%10
   split='train' if h<7 else 'val' if h==7 else 'test'
   candidates.append(dict(z,range_size=entries[i+1]['offset']-z['offset'],person=person,split=split,source_label=label,bboxes=[list(x) for x in a['bboxes']],labels=list(a['labels'])))
  candidates.sort(key=lambda x:hashlib.sha256(x['name'].encode()).digest());selected.extend(candidates[:limit])
 def fetch(x):
  p=ROOT/'data/hagrid'/x['source_label']/Path(x['name']).name;p.parent.mkdir(parents=True,exist_ok=True)
  if not p.exists():
   r=Remote(cat['url'],1009688861);r.seek(x['offset']);data=r.read(x['range_size']);h=struct.unpack('<IHHHHHIIIHH',data[:30]);start=30+h[-2]+h[-1]
   assert h[0]==0x04034b50 and x['method']==0
   data=data[start:start+x['size']];assert len(data)==x['size']
   from PIL import Image
   import io
   Image.open(io.BytesIO(data)).verify();p.write_bytes(data)
  return dict(x,path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
 result=[];start=time.monotonic()
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
  for x in pool.map(fetch,selected):
   result.append(x)
   if len(result)%30==0:print('HaGRID',len(result),'/',len(selected),'seconds',round(time.monotonic()-start),flush=True)
 (ROOT/'data/hagrid_manifest.json').write_text(json.dumps(dict(items=result,commit=cat['commit'],url=cat['url'],annotation_sha256=hashlib.sha256((ROOT/'data/hagrid_annotations.parquet').read_bytes()).hexdigest()),indent=2),encoding='utf-8')
 print('HaGRID READY',len(result),flush=True)
if __name__=='__main__':main()
