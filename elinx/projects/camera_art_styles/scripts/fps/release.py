"""Generate an offline RF33 bit only after strict CAD/electrical/model audit.

This invokes Efinity's file-generation flow, never Programmer/JTAG/serial/Flash.
"""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[2];WS=ROOT.parents[2]
BUILD=ROOT/'build/camera_fps_rf33_srl_720';BASE=ROOT/'build/camera_720_fast'
from signoff import audit
sys.path.insert(0,str(ROOT/'scripts'))
from tool_run import environment,run
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
write=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')

def preserved():
 entries=read(BASE/'final_review.json')['preserved_releases']
 entries.append({'project':'camera_art_styles','profile':'camera_720_fast','bit_sha256':read(BASE/'signoff.json')['bitstream_sha256']})
 for e in entries:
  folder=WS/'elinx/projects'/e['project']/'build'/e['profile'];signed=read(folder/'signoff.json');m=read(folder/'manifest.json')
  name='ti60_camera' if e['profile'].startswith('camera') else 'ti60_style'
  assert sha(folder/'outflow'/(name+'.bit'))==signed['bitstream_sha256']==e['bit_sha256']
  for p,v in m['sources'].items():assert sha(WS/p)==v,p
  for p,v in signed['configuration_sha256'].items():assert sha(folder/p)==v,p
  for p,v in signed.get('reports_sha256',{}).items():assert sha(folder/'outflow'/p)==v,p
  for key in ('weights','boot_ram'):
   for p,v in m.get(key,{}).items():assert sha(folder/p)==v,p
  e['result']='PASS'
 return entries

def main():
 assert not (BUILD/'outflow/ti60_camera.bit').exists(),'Preserve an existing released bit'
 before=audit(False);history=preserved();write(BUILD/'pre_bit_review.json',before)
 environment()
 cmd=['E:/software/efinity/python311/bin/python.exe','E:/software/efinity/scripts/efx_run.py','ti60_camera','--prj','--flow','pgm','--output_dir','outflow']
 assert run(cmd,BUILD,BUILD/'offline_bit_generation.log')==0,'Offline bit generation failed'
 result=audit(True);write(BUILD/'signoff.json',result)
 write(BUILD/'final_review.json',{'result':'PASS','scope':'Current RF33 source/model/firmware/electrical/native STA binding plus preserved historical releases; no board access or measured FPS',
  'bit_sha256':result['bitstream_sha256'],'signoff_sha256':sha(BUILD/'signoff.json'),'preserved_releases':history,
  'sdc_rebuilt_identically':result['cdc']['sdc_rebuilt_identically'],'hardware_accessed':False})
 print('PASS RF33 OFFLINE BIT',result['resources'],result['setup_min_ns'],result['hold_min_ns'],result['bitstream_sha256'])

if __name__=='__main__':main()
