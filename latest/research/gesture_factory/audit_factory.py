"""Fail-closed quality audit. A measured experiment is not a ready bitstream."""
from pathlib import Path
import hashlib,json
import numpy as np
ROOT=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 data=np.load(ROOT/'build/canonical.npz');sources=json.loads((ROOT/'build/factory_masks_manifest.json').read_text(encoding='utf-8'));people={s:set(data['persons'][data['split']==s]) for s in ['train','val','test']}
 assert not (people['train']&people['val'] or people['train']&people['test'] or people['val']&people['test'])
 counts={s:[int(((data['split']==s)&(data['labels']==k)).sum()) for k in range(11)] for s in people}
 quality=[]
 for run in ['cnn_v1','cnn_v2']:
  p=ROOT/'runs'/run/'metrics.json'
  if not p.exists():continue
  m=json.loads(p.read_text(encoding='utf-8'))
  assert all(sha(k)==v for k,v in m['source_sha256'].items()),'Changed experiment source: '+run
  assert m['counts']==counts
  reasons=[]
  for k in range(10):
   if counts['train'][k]<100 or counts['val'][k]<20 or counts['test'][k]<30:reasons.append('digit%d_insufficient_support'%k)
  per=m['test']['per_class']
  if any(z is None or z<.8 for z in per[:10]):reasons.append('per_digit_recall_below_80_percent_or_missing')
  if m['test']['accuracy']<.9:reasons.append('all_class_test_accuracy_below_90_percent')
  confusion=np.array(m['test']['confusion']);negative_false=int(confusion[10,:10].sum());negative_total=int(confusion[10].sum())
  if negative_total and negative_false/negative_total>.02:reasons.append('unthresholded_negative_false_accept_above_2_percent')
  reasons.extend(['offline_masks_do_not_validate_board_foreground_extraction','no_integer_or_production_firmware_or_CAD_validation','HaGRID_class7_automatic_labels_need_manual_review'])
  quality.append(dict(run=run,result='NOT_READY' if reasons else 'PASS',reasons=reasons,test_accuracy=m['test']['accuracy'],per_digit_test_recall=per[:10],negative_false_accept=[negative_false,negative_total],parameters=m['parameters'],metrics_sha256=sha(p)))
 # Manual eye-check receipt uses original cropped photographs, not predicted
 # labels. Three of four automatic "7" candidates have folded/unclear thumbs.
 candidates=[dict(index=i,path=r['path'],person=r['person'],split=r['split']) for i,r in enumerate(sources['items']) if r['label']==7]
 review=[]
 for r in candidates:
  clear=Path(r['path']).name=='2feabed4-bf1a-4a0a-866f-2066873f4e6b.jpg'
  if clear:assert sha(r['path'])=='9f76dca76caf218040c13adeb03ee77508cac4b5a90f4564fdb967f719738822'
  review.append(dict(r,manual_status='visually_consistent' if clear else 'rejected_or_unclear_thumb',usable_for_release=clear))
 manual_path=ROOT/'build/manual_label_review.json';manual=json.loads(manual_path.read_text(encoding='utf-8'))
 assert manual['source_sha256']==sha(ROOT/'build/factory_masks.npz') and manual['manifest_sha256']==sha(ROOT/'build/factory_masks_manifest.json')
 assert manual['output_sha256']==sha(ROOT/'build/factory_masks_reviewed.npz') and manual['remaining_class7_count']==1
 revised=np.load(ROOT/'build/factory_masks_reviewed.npz');raw=np.load(ROOT/'build/factory_masks.npz')
 for field in raw.files:
  if field!='labels':assert np.array_equal(raw[field],revised[field]),field
 expected=raw['labels'].copy()
 for r in manual['manual_eye_review']:expected[r['index']]=r['new_label']
 assert np.array_equal(expected,revised['labels'])
 result=dict(result='NOT_READY',handshape_spec='user_20261102_v1',person_split_disjoint=True,counts=counts,experiments=quality,class7_eye_review=review,manual_label_review_sha256=sha(manual_path),scope='Offline model research only; no FPGA project/firmware/pin/bit changes',preserved_bit=str(ROOT.parents[1]/'elinx/projects/camera_art_ten_paint/build/720p/outflow/ti60_camera.bit'),preserved_bit_sha256=sha(ROOT.parents[1]/'elinx/projects/camera_art_ten_paint/build/720p/outflow/ti60_camera.bit'),audit_source_sha256=sha(__file__))
 assert result['preserved_bit_sha256']=='75766d7cdd66154d2d8da1db7a800ed49f38864ae52316c97b2dadaab959a2de'
 (ROOT/'build/quality_audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({k:result[k] for k in ['result','person_split_disjoint','experiments','preserved_bit_sha256']},indent=2))
if __name__=='__main__':main()
