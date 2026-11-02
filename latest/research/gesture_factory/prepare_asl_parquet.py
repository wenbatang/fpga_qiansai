"""Extract pinned public images; original source split is NOT our person split."""
from pathlib import Path
import hashlib,io,json,re,sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'build/deps'))
import pyarrow.parquet as pq
from PIL import Image,ImageDraw,ImageOps
from download_asl_hg import POS,NEG
def main():
 path=ROOT/'data/asl_hg_test.parquet';table=pq.read_table(path);print(table.schema,flush=True)
 print('FIRST ROW META',{k:(str(v)[:120] if k!='image' else {kk:len(vv) if isinstance(vv,bytes) else vv for kk,vv in v.items()}) for k,v in table.slice(0,1).to_pylist()[0].items()},flush=True)
 records=[];images={}
 for row in table.to_pylist():
  photo=row['image'];filename=Path(photo['path']).name;match=re.match(r'(P\d+)_([^_]+)_',filename)
  assert match,filename
  person,source=match.groups()
  if source not in POS and source not in NEG:continue
  split='val' if person=='P8' else 'test' if person in ['P9','P10'] else 'train'
  target=ROOT/'data/asl_parquet'/source/filename;target.parent.mkdir(parents=True,exist_ok=True)
  data=photo['bytes'];assert data;target.write_bytes(data)
  records.append(dict(path=str(target),source_label=source,label=POS.get(source,10),person=person,split=split,sha256=hashlib.sha256(data).hexdigest()))
  if source not in images:images[source]=Image.open(io.BytesIO(data)).convert('RGB')
 manifest=dict(items=records,source='https://huggingface.co/datasets/juanjodurillo/asl-hg',commit=json.loads((ROOT/'data/asl_hg_hf.json').read_text(encoding='utf-8'))['sha'],parquet_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),source_to_digit=POS,negatives=NEG,split='Person-disjoint: P1-P7 train/P8 val/P9-P10 test')
 (ROOT/'data/asl_parquet_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
 canvas=Image.new('RGB',(800,((len(images)+4)//5)*200),'white');draw=ImageDraw.Draw(canvas)
 for i,(source,image) in enumerate(sorted(images.items())):
  x=i%5*160;y=i//5*200;canvas.paste(ImageOps.contain(image,(155,175)),(x,y+22));draw.text((x+2,y+2),source+' => '+str(POS.get(source,'negative')),fill='black')
 canvas.save(ROOT/'build/asl_mapping_check.png');print('READY',len(records),flush=True)
if __name__=='__main__':main()
