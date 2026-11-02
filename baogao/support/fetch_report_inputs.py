"""Fetch the two unchanged public-domain source files used in this report."""
from pathlib import Path
import hashlib,json,urllib.request
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
 for item in json.loads((ROOT/'assets/source/sources.json').read_text(encoding='utf-8')):
  p=ROOT/'assets/source'/(item['name']+'.jpg')
  if not p.exists():
   with urllib.request.urlopen(urllib.request.Request(item['url'],headers={'User-Agent':'FPGAResearchReport/1.0'}),timeout=60) as r:p.write_bytes(r.read())
  assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256'],p
  print('Verified',p)
