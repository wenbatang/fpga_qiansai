"""Fresh check of training, fixed-point predictions and isolated ROM export."""
from pathlib import Path
import csv,hashlib,json,math
import torch
ROOT=Path(__file__).resolve().parent;WS=ROOT.parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def verify(p):
 v=json.loads(p.read_text(encoding='utf-8'));assert v.get('result','PASS')=='PASS',p
 for key in ['sources_sha256','source_hashes','outputs_sha256','reference_hashes','c8_teacher_hashes']:
  for f,h in v.get(key,{}).items():assert sha(f)==h,('Stale evidence',p,f)
 return v
def main():
 run=ROOT/'runs/ten_painterly_v2';model=run/'model.pt';d=torch.load(model,map_location='cpu',weights_only=True)
 launch=verify(run/'launch.json');verify(run/'complete.json')
 probe=ROOT/'runs/ten_painterly_probe_v1';verify(probe/'launch.json');verify(probe/'complete.json')
 assert d['config']==dict(channels=6,styles=10) and d['hardware_qat'] and d['painting_teachers']
 assert d['step']==27500 and d['refinement_steps']==12000
 visits=[];files=[model,Path(__file__),run/'launch.json',run/'complete.json',probe/'launch.json',probe/'complete.json']
 for folder,n in [(probe,1500),(run,12000)]:
  rows=list(csv.DictReader((folder/'training.csv').open()));assert len(rows)==n
  assert [int(r['step']) for r in rows]==list(range(1,n+1))
  assert all(math.isfinite(float(r['loss'])) for r in rows)
  visits.append([sum(int(r['slot'])==s for r in rows) for s in range(10)]);files.append(folder/'training.csv')
 assert visits[0]==[1500]+[0]*9 and visits[1]==[3693]+[923]*9
 evaluation=verify(ROOT/'results/painterly_v2_final/verification.json')
 assert len(evaluation['cases'])==50 and evaluation['small_cases']==40 and evaluation['checkpoint_sha256']==sha(model)
 assert all(c['pixels']==921600 and c['integer_max_abs_error']==c['qat_max_abs_error']==0 for c in evaluation['cases'])
 assert evaluation['clipped_weights']==0 and evaluation['max_accumulator_bound']<2**21
 assert len(evaluation['spatial_shapes'])==10 and all(s[-2:]==[720,1280] for s in evaluation['spatial_shapes'])
 package=verify(run/'package/verification.json');assert package['checkpoint_sha256']==sha(model)
 assert package['styles']==10 and package['rom_bytes']==7360 and package['config_writes_per_style']==216 and package['weights_per_style']==396
 split=json.loads((run/'split.json').read_text(encoding='utf-8'));excluded=set(split['user_images_sha256'].values())
 assert len(split['training'])==512 and len(split['validation'])==24 and len(excluded)==34
 assert all(sha(p) not in excluded for p in split['training'])
 assert set(split['training']).isdisjoint(split['validation']);files.append(run/'split.json')
 preserved={}
 for name,expected in [('camera_art_ten','6196d9d3183350ee12cabcd739bbee986064a0e779bea7e7dc078397d753e739'),('camera_art_ten_ui','598a2312e477166d33e7d2cc7aa52d919913eb5d90a756221aaceabe5fe63099')]:
  bit=WS/'elinx/projects'/name/'build/720p/outflow/ti60_camera.bit';assert sha(bit)==expected;preserved[str(bit)]=expected
 files.extend([ROOT/'results/painterly_v2_final/verification.json',run/'package/verification.json'])
 result=dict(result='PASS',new_training_steps=13500,new_vangogh_steps=5193,other_style_steps=923,model_sha256=sha(model),
  full720_cases=50,small_cases=40,max_accumulator_bound=evaluation['max_accumulator_bound'],clipped_weights=0,
  rom_bytes=7360,config_writes_per_style=216,source_hashes={str(p):sha(p) for p in files},preserved_bitstreams=preserved,
  board_programmed=False,new_bitstream_generated=False,scope='Fresh software training/numerical/package evidence only. Perceptual quality judged from actual comparisons; no new FPGA mapping/timing or real-camera quality/FPS claim.')
 out=ROOT/'results/painterly_v2_final/audit.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({k:v for k,v in result.items() if k not in ['source_hashes','preserved_bitstreams']},indent=2))
if __name__=='__main__':main()
