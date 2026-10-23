"""Separate six-style experiment; existing four-style releases stay immutable."""
from pathlib import Path
import hashlib,io,json,re,shutil
import requests
from PIL import Image
ROOT=Path(__file__).resolve().parent
STYLES={
 'vangogh':{'label':'梵高旋涡厚涂','monochrome':False,'warm':'vangogh'},
 'monet':{'label':'莫奈印象派','monochrome':False,'warm':'oilpainting'},
 'ukiyoe':{'label':'日式浮世绘','monochrome':False,'warm':'ukiyoe'},
 'papercut':{'label':'彩色剪纸拼贴','monochrome':False,'warm':'oilpainting'},
 'comic':{'label':'复古漫画插画','monochrome':False,'warm':'ukiyoe'},
 'inkwash':{'label':'水墨国画','monochrome':True,'warm':'inkwash'},
}
REF=ROOT/'styles/art6_v1'
RUN=ROOT/'runs/art6_v2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def prepare():
 REF.mkdir(parents=True,exist_ok=True)
 session=requests.Session();session.headers['User-Agent']='FPGAStyleStudy/1.0 local training'
 records={}
 for name in STYLES:
  dst=REF/(name+'.jpg');meta=REF/(name+'.json')
  if meta.exists():
   record=json.loads(meta.read_text(encoding='utf-8'));assert sha(dst)==record['training_sha256']
   records[name]=record;continue
  if name in ('vangogh','inkwash'):
   src=ROOT/'styles/distinct_v1'/(name+'.jpg');shutil.copy2(src,dst)
   record=json.loads(src.with_suffix('.json').read_text(encoding='utf-8'))
  elif name in ('monet','papercut','comic'):
   # Dataset preprocessing of the user-reviewed concept sheet, not a claim
   # that the sheet itself was produced by the trained network.
   src=Path('C:/Users/wenbatang/.codex/generated_images/01a11596-a03a-7bc0-a344-70863fae7b9f/exec-7d37fbec-dd11-48c0-8e7c-a3ca2bbf20eb.png')
   local=REF/'concept_sheet_source.png'
   if not local.exists():shutil.copy2(src,local)
   box={'monet':(526,110,1011,520),'papercut':(526,566,1011,984),'comic':(1028,566,1522,984)}[name]
   with Image.open(local) as im:im.convert('RGB').crop(box).save(dst,quality=98)
   record={'title':STYLES[name]['label']+' AI概念参考','source':'user-reviewed generated concept sheet',
           'source_sha256':sha(local),'crop_xyxy':list(box),'license':'AI-generated reference; not a historical artwork',
           'source_page':None,'note':'Style reference only; never presented as trained inference output'}
  elif name=='ukiyoe':
   # Keep the proven public-domain reference when the public API is
   # unavailable; do not relabel a generated image as museum material.
   src=ROOT/'styles/distinct_v1/ukiyoe.jpg';shutil.copy2(src,dst)
   record=json.loads(src.with_suffix('.json').read_text(encoding='utf-8'))
  else:
   if name=='monet':
    api='https://api.artic.edu/api/v1/artworks/16568';payload=session.get(api,timeout=60);payload.raise_for_status();obj=payload.json()
    assert obj['data']['is_public_domain']
    url=obj['config']['iiif_url']+'/'+obj['data']['image_id']+'/full/1400,/0/default.jpg'
    record={'title':obj['data']['title'],'artist':obj['data']['artist_display'],'source_page':'https://www.artic.edu/artworks/16568','license':'Art Institute of Chicago CC0','api_url':api}
   else:
    api='https://collectionapi.metmuseum.org/public/collection/v1/objects/45434';payload=session.get(api,timeout=60);payload.raise_for_status();obj=payload.json()
    assert obj['isPublicDomain'];url=obj['primaryImage']
    record={'title':obj['title'],'artist':obj['artistDisplayName'],'source_page':obj['objectURL'],'license':'Met Open Access CC0','api_url':api}
   reply=session.get(url,timeout=120);reply.raise_for_status();(REF/(name+'_source.jpg')).write_bytes(reply.content)
   im=Image.open(io.BytesIO(reply.content)).convert('RGB');w,h=im.size
   im=im.crop((int(w*.025),int(h*.025),int(w*.975),int(h*.975)));im.thumbnail((1400,1400));im.save(dst,quality=96)
   record.update(image_url=url,source_sha256=hashlib.sha256(reply.content).hexdigest())
  record.update(name=name,label=STYLES[name]['label'],generation='art6_v1',monochrome=STYLES[name]['monochrome'],training_sha256=sha(dst))
  meta.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');records[name]=record
  print('PREPARED',name,flush=True)
 (REF/'manifest.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
 return records
if __name__=='__main__':prepare()
