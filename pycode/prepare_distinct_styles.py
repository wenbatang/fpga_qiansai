"""Prepare a separate, provenance checked four-style generation; never edit v1 refs."""
from pathlib import Path
import hashlib,io,json,shutil
import requests
from PIL import Image
from prepare_styles import ROOT

STYLES={
    'vangogh':{'label':'梵高·星月夜','monochrome':False},
    'ukiyoe':{'label':'浮世绘·赤富士','monochrome':False},
    'inkwash':{'label':'水墨国画','monochrome':True},
    'oilpainting':{'label':'彩色油画','monochrome':False},
}
OUTPUT=ROOT/'styles/distinct_v1'

def prepare():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    session=requests.Session();session.headers['User-Agent']='FPGAStyleStudy/1.0 (local research)'
    specs={
      'vangogh':{'title':'The Starry Night','artist':'Vincent van Gogh','source_page':'https://www.moma.org/collection/works/79802',
        'repository_page':'https://commons.wikimedia.org/wiki/File:Van_Gogh_-_Starry_Night_-_Google_Art_Project.jpg',
        'image_url':'https://thumb.wikimedia.org/wikipedia/commons/thumb/e/ea/Van_Gogh_-_Starry_Night_-_Google_Art_Project.jpg/1280px-Van_Gogh_-_Starry_Night_-_Google_Art_Project.jpg',
        'license':'Wikimedia Commons PD-Art (public-domain painting reproduction)','crop':[0,.02,1,.82]},
      'ukiyoe':{'object_id':36490,'crop':[.03,.04,.97,.96]},
      'oilpainting':{'title':'Two Sisters (On the Terrace)','artist':'Pierre-Auguste Renoir',
        'source_page':'https://www.artic.edu/artworks/14655',
        'repository_page':'https://commons.wikimedia.org/wiki/File:Pierre-Auguste_Renoir_-_Two_Sisters_(On_the_Terrace)_-_Google_Art_Project.jpg',
        'image_url':'https://thumb.wikimedia.org/wikipedia/commons/thumb/7/77/Pierre-Auguste_Renoir_-_Two_Sisters_%28On_the_Terrace%29_-_Google_Art_Project.jpg/960px-Pierre-Auguste_Renoir_-_Two_Sisters_%28On_the_Terrace%29_-_Google_Art_Project.jpg',
        'license':'Wikimedia Commons PD-Art (public-domain painting reproduction)','crop':[.03,.03,.97,.97]},
    }
    manifest={}
    for name,spec in STYLES.items():
        dest=OUTPUT/f'{name}.jpg';meta=OUTPUT/f'{name}.json'
        if dest.exists() and meta.exists():
            record=json.loads(meta.read_text(encoding='utf-8'))
            assert hashlib.sha256(dest.read_bytes()).hexdigest()==record['training_sha256']
            manifest[name]=record;continue
        if name=='inkwash':
            record=json.loads((ROOT/'styles/inkwash.json').read_text(encoding='utf-8'))
            shutil.copy2(ROOT/'styles/inkwash.jpg',dest)
            record.update(spec);record['generation']='distinct_v1';record['name']=name
        else:
            record={**spec,**specs[name],'name':name,'generation':'distinct_v1'}
            if 'object_id' in record:
                url=f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{record['object_id']}"
                reply=session.get(url,timeout=60);reply.raise_for_status();obj=reply.json()
                assert obj['isPublicDomain'] and obj['primaryImage']
                record.update(title=obj['title'],artist=obj['artistDisplayName'],source_page=obj['objectURL'],
                              image_url=obj['primaryImage'],license='Met Open Access / CC0',api_url=url)
            if 'artic_id' in record:
                url=f"https://api.artic.edu/api/v1/artworks/{record['artic_id']}"
                reply=session.get(url,timeout=60);reply.raise_for_status();payload=reply.json();obj=payload['data']
                assert obj['is_public_domain'] and obj['image_id']
                record.update(title=obj['title'],artist=obj['artist_display'],source_page=f"https://www.artic.edu/artworks/{record['artic_id']}",
                    image_url=f"{payload['config']['iiif_url']}/{obj['image_id']}/full/1400,/0/default.jpg",
                    license='Art Institute of Chicago public domain / CC0',api_url=url)
            reply=session.get(record['image_url'],timeout=120);reply.raise_for_status();raw=reply.content
            (OUTPUT/f'{name}_source.jpg').write_bytes(raw)
            im=Image.open(io.BytesIO(raw)).convert('RGB');w,h=im.size
            l,t,r,b=record['crop'];im=im.crop((round(w*l),round(h*t),round(w*r),round(h*b)))
            im.thumbnail((1400,1400),Image.Resampling.LANCZOS);im.save(dest,quality=95)
            record['source_sha256']=hashlib.sha256(raw).hexdigest()
            record['training_sha256']=hashlib.sha256(dest.read_bytes()).hexdigest()
        meta.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');manifest[name]=record
        print('PREPARED',name,record['title'],flush=True)
    (OUTPUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return manifest

if __name__=='__main__':prepare()
