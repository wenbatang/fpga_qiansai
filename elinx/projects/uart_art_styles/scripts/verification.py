"""Read-only binding of RTL simulations and four/six map comparison."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def simulations():
 receipts={}
 for name,marker in [('layer','PASS folded first layer'),('tiles','PASS folded tiles'),('link','PASS full style link'),('height720','PASS folded tiles')]:
  p=ROOT/'sim'/name/'verification.json';r=json.loads(p.read_text(encoding='utf-8'))
  assert marker in r['result'],name
  for filename,expected in r['sha256'].items():assert sha(Path(filename))==expected,'Changed simulation input/source '+filename
  receipts[name]={'receipt_sha256':sha(p),'result':r['result'],'frame':r.get('frame'),'kept_pixels':r.get('kept_pixels')}
 return receipts
def comparison():
 records={}
 for count in [4,6]:
  folder=ROOT/'build'/f'probe96_{count}';scope=json.loads((folder/'scope.json').read_text(encoding='utf-8'))
  for filename,expected in scope['sources'].items():assert sha(Path(filename))==expected,'Changed resource probe source'
  for name,expected in scope['weights'].items():assert sha(folder/name)==expected,'Changed resource probe ROM'
  report=folder/'outflow/core_top.map.rpt';s=report.read_text(encoding='utf-8')
  resources={k:int(re.search(r'^'+k+r'\s*:\s*(\d+)',s,re.M)[1]) for k in ['EFX_ADD','EFX_LUT4','EFX_DSP48','EFX_FF','EFX_SRL8','EFX_RAM10']}
  records[str(count)]={'resources':resources,'models':[m['style'] for m in scope['models']],'report_sha256':sha(report),'scope_sha256':sha(folder/'scope.json')}
 assert any(records['6']['resources'][k]>v for k,v in records['4']['resources'].items()),'Reconsider style selection if six has no cost'
 return {'scope':'Ti60 I3 CNN synthesis only; same 96x720 geometry and folding, real learned weights; not full design/place/board','decision':'four','selected_original_ids':[0,3,4,5],'probes':records}
if __name__=='__main__':print(json.dumps({'comparison':comparison(),'simulations':simulations()},ensure_ascii=False,indent=2))
