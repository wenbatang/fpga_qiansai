"""Read a pinned public ZIP catalogue with HTTP ranges; no full1GB download."""
from pathlib import Path
import io,json,time,urllib.request,zipfile
ROOT=Path(__file__).resolve().parent
class Remote(io.RawIOBase):
 def __init__(self,url,size):self.url=url;self.size=size;self.position=0;self.cache={}
 def seekable(self):return True
 def tell(self):return self.position
 def seek(self,offset,whence=0):
  self.position=offset if whence==0 else self.position+offset if whence==1 else self.size+offset
  return self.position
 def read(self,n=-1):
  if n<0:n=self.size-self.position
  n=min(n,self.size-self.position)
  if n<=0:return b''
  key=(self.position,n)
  if key not in self.cache:
   request=urllib.request.Request(self.url,headers={'Range':f'bytes={self.position}-{self.position+n-1}'})
   for attempt in range(5):
    try:
     with urllib.request.urlopen(request,timeout=40) as response:
      assert response.status==206,'Public host did not return a range'
      data=response.read(n+1);assert len(data)==n,(len(data),n);self.cache[key]=data
     break
    except (OSError,AssertionError):
     if attempt==4:raise
     time.sleep(attempt+1)
  self.position+=n;return self.cache[key]
def main():
 meta=json.loads((ROOT/'data/hagrid_hf.json').read_text(encoding='utf-8'))
 url='https://huggingface.co/datasets/cj-mills/hagrid-sample-30k-384p/resolve/'+meta['sha']+'/hagrid-sample-30k-384p.zip'
 with zipfile.ZipFile(Remote(url,1009688861)) as archive:
  items=[dict(name=z.filename,size=z.file_size,compressed=z.compress_size,offset=z.header_offset,method=z.compress_type) for z in archive.infolist()]
 (ROOT/'data/hagrid_catalogue.json').write_text(json.dumps(dict(commit=meta['sha'],url=url,items=items),indent=2),encoding='utf-8')
 print('ZIP catalogue',len(items),items[:5],flush=True)
if __name__=='__main__':main()
