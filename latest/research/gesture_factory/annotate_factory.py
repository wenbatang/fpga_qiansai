"""Offline pretrained annotation of public photos, never live camera capture.

MediaPipe is a teacher for masks/QA only. No claim of porting it to Ti60.
"""
from pathlib import Path
import hashlib,json,time
import cv2,numpy as np,mediapipe as mp
from extract_masks import masks
ROOT=Path(__file__).resolve().parent;WS=ROOT.parents[1]
MODEL=WS/'pycode/gesture_demo/assets/hand_landmarker.task'
def extended(points):
 p=np.asarray(points,np.float32)
 flags=[]
 for a,b,c,d in [(1,2,3,4),(5,6,7,8),(9,10,11,12),(13,14,15,16),(17,18,19,20)]:
  v=p[b]-p[a];w=p[d]-p[b];cos=float(v@w/(np.linalg.norm(v)*np.linalg.norm(w)+1e-6))
  if a==1:good=cos>.4 and np.linalg.norm(p[d]-p[17])>np.linalg.norm(p[c]-p[17])*1.05
  else:good=cos>.4 and np.linalg.norm(p[d]-p[0])>np.linalg.norm(p[b]-p[0])*1.08
  flags.append(bool(good))
 return flags
def main():
 sources=[ROOT/'data/asl_parquet_manifest.json',ROOT/'data/hagrid_manifest.json'];items=[]
 for source in sources:
  data=json.loads(source.read_text(encoding='utf-8'))
  for r in data['items']:items.append(dict(r,source='hagrid' if 'hagrid' in source.name else 'asl_hg'))
 opts=mp.tasks.vision.HandLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_path=str(MODEL)),num_hands=1,min_hand_detection_confidence=.25,min_hand_presence_confidence=.25,running_mode=mp.tasks.vision.RunningMode.IMAGE)
 rgb_arrays=[];mask_arrays=[];point_arrays=[];records=[];failed=[];t=time.monotonic()
 with mp.tasks.vision.HandLandmarker.create_from_options(opts) as detector:
  for i,r in enumerate(items):
   rgb=cv2.cvtColor(cv2.imread(r['path']),cv2.COLOR_BGR2RGB)
   if r['source']=='hagrid':
    matches=[j for j,label in enumerate(r['labels']) if label==r['source_label']]
    if len(matches)!=1:failed.append(dict(r,reason='multiple_or_missing_matching_hands'));continue
    x,y,w,h=r['bboxes'][matches[0]];H,W=rgb.shape[:2];side=max(w*W,h*H)*1.35;cx=(x+w/2)*W;cy=(y+h/2)*H
    left=max(0,int(cx-side/2));right=min(W,int(cx+side/2));top=max(0,int(cy-side/2));bottom=min(H,int(cy+side/2));rgb=rgb[top:bottom,left:right]
   H,W=rgb.shape[:2];side=max(H,W);padded=np.full((side,side,3),220,np.uint8);padded[(side-H)//2:(side+H)//2,(side-W)//2:(side+W)//2]=rgb
   rgb=cv2.resize(padded,(256,256),interpolation=cv2.INTER_LINEAR)
   result=detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=rgb));got=masks(rgb,result)
   if got is None:failed.append(dict(r,reason='teacher_no_hand'));continue
   mask,points=got;flags=extended(points);label=r.get('label',10)
   if r['source']=='hagrid':
    if r['source_label']=='palm':label=5 if flags==[True]*5 else 10
    # "rock" is NOT blindly relabeled as7: folded thumb is a negative.
    else:label=7 if flags==[True,True,False,False,True] else 10
   rgb_arrays.append(cv2.resize(rgb,(64,64),interpolation=cv2.INTER_AREA));mask_arrays.append(cv2.resize(mask,(64,64),interpolation=cv2.INTER_NEAREST));point_arrays.append(points/4)
   records.append(dict(r,label=label,extended=flags))
   if (i+1)%200==0:print('ANNOTATED',i+1,'kept',len(records),'seconds',round(time.monotonic()-t),flush=True)
 np.savez_compressed(ROOT/'build/factory_masks.npz',rgb=np.array(rgb_arrays,np.uint8),mask=np.array(mask_arrays,np.uint8),landmarks=np.array(point_arrays,np.float32),labels=np.array([r['label'] for r in records]),split=np.array([r['split'] for r in records]),persons=np.array([r['person'] for r in records]))
 (ROOT/'build/factory_masks_manifest.json').write_text(json.dumps(dict(items=records,failed=failed,source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources+[MODEL,Path(__file__)]},annotation_role='Offline teacher only; NOT board inference'),indent=2),encoding='utf-8')
 from collections import Counter
 print('READY',len(records),'failed',len(failed),Counter(r['label'] for r in records),flush=True)
if __name__=='__main__':main()
