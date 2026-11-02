"""Download the author's public five-subject research dataset, with resume."""
from pathlib import Path
import hashlib,json,time,urllib.request
ROOT=Path(__file__).resolve().parent
URL='https://www.cvssp.org/FingerSpellingKinect2011/fingerspelling5.tar.bz2'
PAGE='https://empslocal.ex.ac.uk/people/staff/np331/index.php?section=FingerSpellingDataset'
def main():
 folder=ROOT/'data';folder.mkdir(exist_ok=True);path=folder/'fingerspelling5.tar.bz2';part=path.with_suffix('.partial')
 expected=2246539027;start=time.monotonic()
 if not path.exists():
  for attempt in range(6):
   position=part.stat().st_size if part.exists() else 0
   try:
    request=urllib.request.Request(URL,headers={'Range':f'bytes={position}-'} if position else {})
    with urllib.request.urlopen(request,timeout=45) as response:
     assert not position or response.status==206,'Cannot resume without supported ranges'
     previous=time.monotonic()
     with part.open('ab' if position else 'wb') as stream:
      while True:
       chunk=response.read(1024*1024)
       if not chunk:break
       stream.write(chunk);position+=len(chunk)
       if time.monotonic()-previous>5:print('ASL DOWNLOAD',position,'/',expected,'seconds',round(time.monotonic()-start),flush=True);previous=time.monotonic()
    assert position==expected,(position,expected);part.replace(path);break
   except Exception as e:
    print('DOWNLOAD RETRY',attempt,type(e).__name__,str(e)[:120],flush=True)
    if attempt==5:raise
  assert path.exists()
 h=hashlib.sha256()
 with path.open('rb') as stream:
  for chunk in iter(lambda:stream.read(8*1024*1024),b''):h.update(chunk)
 (folder/'asl_source.json').write_text(json.dumps(dict(source_page=PAGE,url=URL,bytes=path.stat().st_size,sha256=h.hexdigest(),role='Subject-grouped RGB/depth research data; images stay local; retain source notices'),indent=2),encoding='utf-8')
 print('ASL DOWNLOAD COMPLETE',path.stat().st_size,flush=True)
if __name__=='__main__':main()
