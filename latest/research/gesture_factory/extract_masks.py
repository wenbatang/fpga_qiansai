"""Offline pretrained-landmark-assisted masks; never reads a live camera.

This teacher is a preprocessing aid only, NOT asserted to run on the FPGA.
Group boundaries are inherited exactly from the preserved real-photo split.
"""
from pathlib import Path
import hashlib,json,sys,time
import cv2,numpy as np
import mediapipe as mp
ROOT=Path(__file__).resolve().parent;WS=ROOT.parents[1]
SOURCE=WS/'pycode/gesture_digits/build/data_manifest.json'
MODEL=WS/'pycode/gesture_demo/assets/hand_landmarker.task'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def masks(rgb,result):
 if not result.hand_landmarks:return None
 p=np.array([[a.x*rgb.shape[1],a.y*rgb.shape[0]] for a in result.hand_landmarks[0]],np.float32)
 if not np.isfinite(p).all():return None
 palm=np.linalg.norm(p[5]-p[17]);r=max(2.,palm*.12)
 # A coarse anatomical foreground seed with a wider uncertain boundary.
 seed=np.zeros(rgb.shape[:2],np.uint8);hull=cv2.convexHull(p[[0,1,2,5,9,13,17]].astype(np.int32));cv2.fillConvexPoly(seed,hull,1)
 for indices in [[0,1,2,3,4],[0,5,6,7,8],[0,9,10,11,12],[0,13,14,15,16],[0,17,18,19,20]]:
  for a,b in zip(indices,indices[1:]):cv2.line(seed,tuple(p[a].astype(int)),tuple(p[b].astype(int)),1,max(2,int(2*r)))
  cv2.circle(seed,tuple(p[indices[-1]].astype(int)),max(1,int(r)),1,-1)
 kernel=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(max(3,int(r*3)|1),)*2)
 probable=cv2.dilate(seed,kernel);sure=cv2.erode(seed,np.ones((3,3),np.uint8))
 labels=np.where(probable,cv2.GC_PR_FGD,cv2.GC_BGD).astype(np.uint8);labels[sure>0]=cv2.GC_FGD
 # Image-border is background unless an annotated wrist/finger reaches it.
 try:
  cv2.grabCut(cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR),labels,None,np.zeros((1,65),np.float64),np.zeros((1,65),np.float64),3,cv2.GC_INIT_WITH_MASK)
  clean=((labels==cv2.GC_FGD)|(labels==cv2.GC_PR_FGD)).astype(np.uint8)
 except cv2.error:clean=seed
 return clean,p
def main():
 out=ROOT/'build';out.mkdir(exist_ok=True);manifest=json.loads(SOURCE.read_text(encoding='utf-8'))
 assert not (out/'masks.npz').exists(),'Prior experiment preserved'
 opts=mp.tasks.vision.HandLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_path=str(MODEL)),num_hands=1,min_hand_detection_confidence=.2,min_hand_presence_confidence=.2,min_tracking_confidence=.2,running_mode=mp.tasks.vision.RunningMode.IMAGE)
 images=[];mask_arrays=[];points=[];metadata=[];start=time.monotonic();failed=[]
 with mp.tasks.vision.HandLandmarker.create_from_options(opts) as landmarker:
  for i,item in enumerate(manifest['items']):
   path=Path(item['local_path']);rgb=cv2.cvtColor(cv2.imread(str(path)),cv2.COLOR_BGR2RGB)
   # Upscaling cannot add information, but the pretrained detector expects a
   # larger image. Padding avoids treating a cropped wrist as a border error.
   enlarged=cv2.resize(rgb,(256,256),interpolation=cv2.INTER_CUBIC)
   result=landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=enlarged))
   got=masks(enlarged,result)
   if got is None:failed.append(dict(group=item['group'],label=item['label'],split=item['split'],path=str(path)));continue
   mask,p=got;mask=cv2.resize(mask,(64,64),interpolation=cv2.INTER_NEAREST)
   images.append(rgb);mask_arrays.append(mask);points.append(p/4)
   metadata.append(dict(path=str(path),sha256=sha(path),group=item['group'],label=item['label'],split=item['split']))
   if (i+1)%100==0:print('MASK',i+1,len(metadata),'seconds',round(time.monotonic()-start,1),flush=True)
 np.savez_compressed(out/'masks.npz',rgb=np.array(images,np.uint8),mask=np.array(mask_arrays,np.uint8),landmarks=np.array(points,np.float32),labels=np.array([x['label'] for x in metadata]),split=np.array([x['split'] for x in metadata]),groups=np.array([x['group'] for x in metadata]))
 result=dict(result='DATA_READY',items=metadata,failed=failed,source_sha256={str(p):sha(p) for p in [Path(__file__),SOURCE,MODEL]},model_role='Offline annotation only, not board inference',seconds=time.monotonic()-start)
 (out/'masks_manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('MASKS',len(metadata),'failed',len(failed),flush=True)
if __name__=='__main__':main()
