"""Quarantine false/uncertain automatic7 labels without overwriting experiments."""
from pathlib import Path
import hashlib,json
import numpy as np
ROOT=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 source=ROOT/'build/factory_masks.npz';manifest=ROOT/'build/factory_masks_manifest.json';data=np.load(source);arrays={k:data[k] for k in data.files};items=json.loads(manifest.read_text(encoding='utf-8'))['items'];review=[]
 for i,item in enumerate(items):
  if item['label']!=7:continue
  expected='2feabed4-bf1a-4a0a-866f-2066873f4e6b.jpg'
  clear=Path(item['path']).name==expected
  if clear:assert sha(item['path'])=='9f76dca76caf218040c13adeb03ee77508cac4b5a90f4564fdb967f719738822'
  else:arrays['labels'][i]=10
  review.append(dict(index=i,path=item['path'],sha256=sha(item['path']),old_label=7,new_label=int(arrays['labels'][i]),status='visually_consistent' if clear else 'folded_or_unclear_thumb_reject'))
 output=ROOT/'build/factory_masks_reviewed.npz';np.savez_compressed(output,**arrays)
 result=dict(result='DATA_REVIEWED_NOT_READY',source_sha256=sha(source),manifest_sha256=sha(manifest),output_sha256=sha(output),manual_eye_review=review,remaining_class7_count=int((arrays['labels']==7).sum()),limitation='Only one visually suitable7; zero held-out validation/test7. Further training/deployment must remain blocked for ten-class release.')
 (ROOT/'build/manual_label_review.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('Reviewed class7 remaining:',result['remaining_class7_count'])
if __name__=='__main__':main()
