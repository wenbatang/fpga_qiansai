"""Build an independent 720p60 HDMI/DDR-startup compatibility release; no board access."""
from pathlib import Path
import argparse, hashlib, json, re, shutil, sys, tempfile
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]; WS=ROOT.parents[2]
BASE=ROOT/'build/720p'; OUT=ROOT/'build/720p60_hdmi'
sys.path.insert(0,str(ROOT/'scripts'))
NS='http://www.efinixinc.com/enf_proj'
DISPLAY={'mode':'720p60','active':[1280,720],'totals':[1650,750],'horizontal':[1280,110,40,220],'vertical':[720,5,5,20],'pixel_hz':74250000,'serial_hz':371250000,'refresh_hz':60,'placement':'full 1280x720; no scaling'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')

def parent():
 m=read(BASE/'manifest.json'); s=read(BASE/'signoff.json')
 for name,value in m['sources'].items():assert sha(WS/name)==value,name
 for name,value in m['scripts'].items():assert sha(ROOT/'scripts'/name)==value,name
 for name,value in m['reference'].items():assert sha(WS/name)==value,name
 for name,value in m['weights'].items():assert sha(BASE/name)==value,name
 for name,value in s['configuration_sha256'].items():assert sha(BASE/name)==value,name
 for name,value in s['reports_sha256'].items():assert sha(BASE/'outflow'/name)==value,name
 for model in m['models']:
  assert sha(WS/'pycode/runs/art6_v2/student'/model['style']/'model.pt')==model['checkpoint_sha256']
 assert sha(BASE/'outflow/ti60_style.bit')==s['bitstream_sha256']
 return m,s

def top_text():
 text=(ROOT/'rtl/ti60_style_top.sv').read_text(encoding='utf-8')
 old='.async_reset(!sys_rst_n || !pll_locked || !core_pll_locked || !user_pll_locked || !calibrated),.reset(reset_pixel)'
 assert text.count(old)==1
 text=text.replace(old,'.async_reset(!sys_rst_n || !pll_locked || !core_pll_locked || !user_pll_locked),.reset(reset_pixel)')
 assert text.count('video_720p #(')==1 and text.count('tmds_efx display(')==1
 assert text.count('.H_FRONT(1760)')==1
 return text.replace('.H_FRONT(1760)','.H_FRONT(110)').replace('video_720p #(','video_720p_startup #(').replace('tmds_efx display(','tmds_hdmi60 display(')

def prepare():
 m,s=parent();assert not OUT.exists(),'Preserve existing candidate'
 OUT.mkdir();(OUT/'rtl').mkdir()
 top=OUT/'rtl/ti60_style_top.sv';top.write_text(top_text(),encoding='utf-8')
 for name in [*m['weights'],'style_weights.vh','style_profile.vh','crc32_byte.svh','ddr3_parameter.vh','ti60_style.peri.xml']:
  shutil.copyfile(BASE/name,OUT/name)
 tree=ET.parse(BASE/'ti60_style.xml');info=tree.find('{'+NS+'}design_info')
 for node in info.findall('{'+NS+'}design_file'):
  if Path(node.get('name')).name=='ti60_style_top.sv':node.set('name',top.as_posix())
 added=[ROOT/'rtl/hdmi30/video_720p_startup.sv',ROOT/'rtl/hdmi60/tmds_hdmi60.sv']
 vendor=read(ROOT/'vendor/hdmi_v7/provenance.json')
 added += [ROOT/'vendor/hdmi_v7'/name for name in vendor['design_files']]
 position=max(i for i,n in enumerate(info) if n.tag=='{'+NS+'}design_file')+1
 for path in added:
  info.insert(position,ET.Element('{'+NS+'}design_file',name=path.as_posix(),version='default',library='default'));position+=1
 ET.register_namespace('efx',NS);tree.write(OUT/'ti60_style.xml',encoding='utf-8')
 key=next(p for p in m['sources'] if Path(p).name=='ti60_style_top.sv');del m['sources'][key]
 for p in [top,*added,ROOT/'vendor/hdmi_v7/efx_fifo_define.vh']:m['sources'][str(p.relative_to(WS))]=sha(p)
 m['profile']='720p60_hdmi';m['display']=DISPLAY;m['scope']='standard 720p60, V7 HDMI AVI VIC4 and pre-DDR startup bars; original 1280x720 CNN/UART unchanged'
 m['parent']={name:sha(BASE/name) for name in ['manifest.json','signoff.json','outflow/ti60_style.bit']}
 m['diagnostic_tools']={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),ROOT/'sim/check_hdmi60.py',ROOT/'sim/check_hdmi60_reset.py']}
 m['project_xml_sha256']=sha(OUT/'ti60_style.xml');m['vendor_hdmi']=vendor
 write(OUT/'manifest.json',m)
 (OUT/'ti60_style.sdc').write_text('create_clock -name CLK_25M -period 40 [get_ports CLK_25M]\n')
 print('Prepared independent 720p60_hdmi; original release untouched',flush=True)

def binding():
 old,signed=parent();m=read(OUT/'manifest.json')
 assert m['display']==DISPLAY and m['size']==[1280,720]
 for key in ['weights','models','tiling','reference','reused','scripts','schema_source']:assert m[key]==old[key],key
 for name,value in m['parent'].items():assert sha(BASE/name)==value,name
 for name,value in m['sources'].items():assert sha(WS/name)==value,name
 for name,value in m['diagnostic_tools'].items():assert sha(ROOT/name)==value,name
 for name in [*m['weights'],'style_weights.vh','style_profile.vh','crc32_byte.svh','ddr3_parameter.vh','ti60_style.peri.xml']:
  assert (OUT/name).read_bytes()==(BASE/name).read_bytes(),name
 assert (OUT/'rtl/ti60_style_top.sv').read_text(encoding='utf-8')==top_text()
 assert sha(OUT/'ti60_style.xml')==m['project_xml_sha256']
 tree=ET.parse(OUT/'ti60_style.xml')
 assert tree.find('.//{'+NS+'}device').get('name')=='Ti60F225'
 assert tree.find('.//{'+NS+'}timing_model').get('name')=='I3'
 for node in tree.findall('.//{'+NS+'}param[@name="max_threads"]'):assert node.get('value')=='4'
 for name,value in m['vendor_hdmi']['files'].items():
  assert sha(ROOT/'vendor/hdmi_v7'/name)==value
  assert sha(Path(m['vendor_hdmi']['reference'])/'rtl/dvi_tx'/name)==value
 return m,signed

def audit(require_bit):
 from board_spec import audit as board_audit
 from constraints import assemble
 m,old=binding();board=board_audit(OUT)
 assert board['pins']==old['corrected_schematic']['pins']
 sim=read(ROOT/'sim/hdmi60/verification.json');assert sim['result']=='PASS'
 for name,value in sim['sha256'].items():assert sha(Path(name))==value,'Stale simulation '+name
 reset_sim=read(ROOT/'sim/hdmi60_reset/verification.json');assert reset_sim['result']=='PASS'
 for name,value in reset_sim['sha256'].items():assert sha(Path(name))==value,'Stale reset simulation '+name
 with tempfile.TemporaryDirectory(dir=OUT,prefix='constraint_review_') as temp:
  f=Path(temp);(f/'outflow').mkdir()
  for name in ['ti60_style.map.v','ti60_style.pt.sdc']:shutil.copyfile(OUT/'outflow'/name,f/'outflow'/name)
  assemble(f)
  for name in ['ti60_style.sdc','cdc_constraints.json']:assert (f/name).read_bytes()==(OUT/name).read_bytes(),name
 cdc=read(OUT/'cdc_constraints.json')
 assert len(cdc['single_bit_first_stages'])==12 and len(cdc['gray_pointer_paths'])>=116
 timing=OUT/'outflow/ti60_style.timing.rpt';text=timing.read_text(encoding='utf-8')
 assert timing.stat().st_mtime_ns>(OUT/'manifest.json').stat().st_mtime_ns and 'Timing Model: I3' in text
 for clock,period in old['required_clocks'].items():assert re.search(r'^\s*'+re.escape(clock)+r'\s+'+f'{period:.3f}'+r'\s',text,re.M),clock
 section=text.split('---------- 2. Clock Relationship Summary (begin) ----------')[1].split('---------- Clock Relationship Summary (end)')[0]
 a,b=section.split('Hold (Min) Clock Relationship')
 def rows(t):return [(v[1],v[2],float(v[3]),float(v[4])) for v in re.finditer(r'^\s*(\S+)\s+(\S+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+\(R-R\)',t,re.M)]
 setup,hold=rows(a),rows(b);assert len(setup)>=12 and len(hold)>=12 and min(v[3] for v in setup+hold)>=0,'Negative/incomplete timing'
 place=(OUT/'outflow/ti60_style.place.out').read_text(encoding='utf-8')
 assert not re.search(r'WARNING.*\[SDC|Unable to run|no vaild startpoints|Failed to run',place)
 place_rpt=(OUT/'outflow/ti60_style.place.rpt').read_text(encoding='utf-8');assert 'Missing Interface Pins' not in place_rpt
 resources={}
 for key,label in [('ram10','Memory Blocks'),('dsp','DSP Blocks'),('xlr','XLRs')]:
  v=re.search(r'^'+label+r': (\d+) / (\d+)',place_rpt,re.M);assert v
  resources[key]={'used':int(v[1]),'available':int(v[2])};assert int(v[1])<=int(v[2])
 assert resources['dsp']['used']==144
 bit=OUT/'outflow/ti60_style.bit'
 if require_bit:
  assert bit.stat().st_mtime_ns>=timing.stat().st_mtime_ns
  with bit.open() as f:header=bytes(int(next(f),16) for _ in range(300)).decode('ascii',errors='replace')
  assert 'Device: Ti60F225' in header and 'Die Name: Ti60_MP' in header
 return {'result':'PASS','scope':'720p60 HDMI startup/AVI compatibility release, actual CAD; no board access',
  'parent':m['parent'],'display':m['display'],'models':m['models'],'resources':resources,'electrical':board,
  'manifest_sha256':sha(OUT/'manifest.json'),'setup_min_ns':min(v[3] for v in setup),'hold_min_ns':min(v[3] for v in hold),
  'setup':setup,'hold':hold,'required_clocks':old['required_clocks'],'scalar_first_stages':12,
  'gray_paths':len(cdc['gray_pointer_paths']),'simulation':sim,'reset_simulation':reset_sim,'unchanged_cnn_uart_evidence':old['simulations'],
  'configuration_sha256':{name:sha(OUT/name) for name in ['ti60_style.xml','ti60_style.peri.xml','ti60_style.sdc','style_profile.vh','style_weights.vh','cdc_constraints.json']},
  'reports_sha256':{name:sha(OUT/'outflow'/name) for name in ['ti60_style.map.v','ti60_style.map.rpt','ti60_style.place.rpt','ti60_style.route.rpt','ti60_style.timing.rpt','ti60_style.pinout.csv','ti60_style.pt.rpt']},
  'bitstream':str(bit) if require_bit else None,'bitstream_sha256':sha(bit) if require_bit else None,
  'not_measured':['physical TMDS eye/clock/rail','actual monitor acceptance/EDID','DDR calibration on board','UART/CNN/display real concurrency']}

def build(stages):
 from desktop_process import run
 from tool_run import environment
 from constraints import assemble
 binding();environment()
 for stage in stages:
  if stage=='pnr':assemble(OUT)
  if stage=='pgm':write(OUT/'pre_bit_review.json',audit(False))
  if stage=='interface':cmd=['E:/software/efinity/python311/bin/python.exe','E:/software/efinity/scripts/efx_run_pt_unified.py','ti60_style','Titanium','Ti60F225','--output_dir','outflow','--timing_model','I3','--project_xml','ti60_style.xml']
  else:cmd=['E:/software/efinity/python311/bin/python.exe','E:/software/efinity/scripts/efx_run.py','ti60_style','--prj','--flow',stage,'--output_dir','outflow']
  print('START',stage,flush=True);code=run(cmd,OUT,OUT/(stage+'_console.log'))
  if code:raise SystemExit(code)
  print('PASS',stage,flush=True)
 if 'pgm' in stages:
  r=audit(True);write(OUT/'signoff.json',r);print('PASS 720p60 HDMI signed:',r['setup_min_ns'],r['hold_min_ns'],r['bitstream_sha256'],flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','compile','map','interface','route','config','audit']);a=p.parse_args()
 if a.action=='prepare':prepare()
 elif a.action=='audit':print(json.dumps(audit(True),ensure_ascii=False))
 else:build({'compile':['map','interface','pnr','pgm'],'map':['map'],'interface':['interface'],'route':['pnr'],'config':['pgm']}[a.action])
