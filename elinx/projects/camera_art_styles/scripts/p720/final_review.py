"""Fresh release binding, exact SDC reassembly without retaining duplicate maps."""
from pathlib import Path
import hashlib,json,os,re,sys,tempfile
ROOT=Path(__file__).resolve().parents[2];BUILD=ROOT/'build/camera_720_fast';WS=ROOT.parents[2]
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(Path(__file__).parent))
from signoff import audit
from constraints import assemble
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
fresh=audit(True);assert json.loads(json.dumps(fresh))==read(BUILD/'signoff.json')
with tempfile.TemporaryDirectory(prefix='sdc_review_',dir=BUILD) as tmp:
 check=Path(tmp);assert check.resolve().is_relative_to(BUILD.resolve())
 (check/'outflow').mkdir()
 for n in ['ti60_camera.map.v','ti60_camera.pt.sdc']:os.link(BUILD/'outflow'/n,check/'outflow'/n)
 os.link(BUILD/'dphy_cdc_proof.json',check/'dphy_cdc_proof.json');assemble(check)
 assert (check/'ti60_camera.sdc').read_bytes()==(BUILD/'ti60_camera.sdc').read_bytes()
 assert read(check/'cdc_constraints.json')==read(BUILD/'cdc_constraints.json')
mapped=(BUILD/'outflow/ti60_camera.map.v').read_text(encoding='utf-8');native=[]
for m in re.finditer(r'EFX_FF\s+(\S+)\s+\([^;]*?/\*([^;]*?)\*/\s*;\s*// ([^\n]+)',mapped,re.S):
 if 'rtl\\reset_sync.sv(5)' in m[3] or 'rtl/reset_sync.sv(5)' in m[3]:
  assert 'async_reg="true"' in m[2],m[1];native.append(m[1])
# EFX_MAP merges strip_domain's three identical reset FFs into the first
# three of in_stream.rd_reset. Prove the actual shared three-stage chain;
# do not count only the original source annotation or relax the chain length.
assert len(native)==15,('unmerged reset_sync native attribute count',native)
shared=[]
records={}
for name,ports,attrs in re.findall(r'EFX_FF\s+(\S+)\s+\(([^;]*?)\)\s*/\*([^;]*?)\*/\s*;',mapped,re.S):
 p={k:re.sub(r'\s+','',v).lstrip('\\') for k,v in re.findall(r'\.(\w+)\(([^()]*)\)',ports)}
 records[name.lstrip('\\')]=(p,attrs)
for index in range(3):
 name=f'system/engine/cnn/in_stream/rd_reset[{index}]~FF';p,a=records[name]
 assert 'async_reg="true"' in a and "SR_SYNC=1'b0" in a
 assert p['CLK']=='cnn_clk' and p['CE']=="1'b1"
 assert p['SR']=='system/engine/n524'
 assert p['D']==("1'b0" if index==0 else f'system/engine/cnn/in_stream/rd_reset[{index-1}]')
 assert ("D_POLARITY=1'b0" if index==0 else "D_POLARITY=1'b1") in a
 shared.append(name)
for index in range(2):
 p,a=records[f'system/engine/cnn/neural/neural/l0/state[{index}]~FF']
 assert p['SR']=='system/engine/cnn/in_stream/rd_reset[2]' and "SR_POLARITY=1'b0" in a
base=ROOT/'build/camera_bias_fix60';entries=read(base/'final_review.json')['preserved_releases']
entries.append({'project':'camera_art_styles','profile':'camera_bias_fix60','bit_sha256':read(base/'signoff.json')['bitstream_sha256']})
for e in entries:
 folder=WS/'elinx/projects'/e['project']/'build'/e['profile'];signed=read(folder/'signoff.json');m=read(folder/'manifest.json')
 name='ti60_camera' if e['profile'].startswith('camera') else 'ti60_style'
 assert sha(folder/'outflow'/(name+'.bit'))==signed['bitstream_sha256']==e['bit_sha256']
 for p,v in m['sources'].items():assert sha(WS/p)==v,p
 for p,v in signed['configuration_sha256'].items():assert sha(folder/p)==v,p
 for p,v in signed.get('reports_sha256',{}).items():assert sha(folder/'outflow'/p)==v,p
 for p,v in m.get('weights',{}).items():assert sha(folder/p)==v,p
 for p,v in m.get('boot_ram',{}).items():assert sha(folder/p)==v,p
 e['result']='PASS'
result={'result':'PASS','scope':'Fresh source/model/firmware/CAD/electrical binding, exact SDC reassembly, native reset attributes, fifteen preserved releases; no physical acceptance',
 'bit_sha256':fresh['bitstream_sha256'],'signoff_sha256':sha(BUILD/'signoff.json'),'native_reset_sync_ffs':native,'merged_strip_reset_chain':shared,'preserved_releases':entries,'sdc_rebuild_matches':True,'board_access':False}
(BUILD/'final_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS FINAL FULL720 REVIEW',fresh['bitstream_sha256'],len(entries),'prior releases')
