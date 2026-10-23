"""Bind display-only camera changes to both signed camera and tested UART."""
from pathlib import Path
import hashlib,importlib.util,json,sys,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2];WS=ROOT.parents[2]
BASE=ROOT/'build/camera_ppi';BUILD=ROOT/'build/camera_ppi60'
UART=ROOT.parent/'uart_art_styles'
sys.path.insert(0,str(ROOT/'scripts'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))

def parent_audit():
 spec=importlib.util.spec_from_file_location('camera30_parent',ROOT/'scripts/camera_ppi_signoff.py')
 mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 fresh=mod.audit();signed=read(BASE/'signoff.json')
 assert json.loads(json.dumps(fresh))==signed,'Old camera release changed'
 return signed

def top_text():
 text=(ROOT/'rtl/ti60_camera_ppi_top.sv').read_text(encoding='utf-8')
 old='.async_reset(!sys_rst_n || !pll_locked || !core_pll_locked || !user_pll_locked || !calibrated),.reset(reset_pixel)'
 assert text.count(old)==1 and text.count('video_system #(')==1 and text.count('tmds_efx display(')==1
 return text.replace(old,'.async_reset(!sys_rst_n || !pll_locked || !core_pll_locked || !user_pll_locked),.reset(reset_pixel)').replace('video_system #(','video_system60 #(').replace('tmds_efx display(','tmds_hdmi60 display(')

def audit_contract():
 old=parent_audit();m=read(BUILD/'manifest.json');before=read(BASE/'manifest.json')
 for name,value in m['parent_camera30'].items():assert sha(BASE/name)==value,name
 assert (BUILD/'ti60_camera.peri.xml').read_bytes()==(BASE/'ti60_camera.peri.xml').read_bytes()
 for name in ['firmware_manifest.json','firmware.bin',*m['boot_ram']]:
  assert (BUILD/name).read_bytes()==(BASE/name).read_bytes(),name
 assert m['process']==[640,480] and m['camera']==[1920,1080]
 assert m['display']=='1280x720p60, 74.25MHz, 1650x750, centered VGA + C/I/H60 overlay'
 assert m['models']==before['models'] and m['firmware_manifest']==before['firmware_manifest']
 assert (BUILD/'rtl/ti60_camera_ppi_top.sv').read_text(encoding='utf-8')==top_text()
 text=(ROOT/'rtl/video_system.sv').read_text(encoding='utf-8')
 expected=text.replace('module video_system #(','module video_system60 #(').replace('video_raster #(.H_FRONT(1760)','video_raster60 #(.H_FRONT(110)').replace('fps_overlay overlay(','fps_overlay60 overlay(')
 assert (ROOT/'rtl/hdmi60/video_system60.sv').read_text(encoding='utf-8')==expected,'Non-display system change'
 overlay=(ROOT/'rtl/fps_overlay.sv').read_text(encoding='utf-8')
 expected=overlay.replace('Cxx Ixx H30','Cxx Ixx H60').replace('module fps_overlay(','module fps_overlay60(').replace('8:code=12;9:code=3;10:code=0;','8:code=12;9:code=6;10:code=0;')
 assert (ROOT/'rtl/hdmi60/fps_overlay60.sv').read_text(encoding='utf-8')==expected,'Wrong H60 overlay derivation'
 assert (ROOT/'rtl/hdmi60/tmds_hdmi60.sv').read_bytes()==(UART/'rtl/hdmi60/tmds_hdmi60.sv').read_bytes()
 for part in ['assign blue=~b','assign green=~g','assign red=~r','assign clock_word=~c',".video_VIC(7'd4)"]:
  assert part in (ROOT/'rtl/hdmi60/tmds_hdmi60.sv').read_text(),part
 vendor=read(ROOT/'vendor/hdmi_v7/provenance.json')
 for name,value in vendor['files'].items():
  assert sha(ROOT/'vendor/hdmi_v7'/name)==value
  assert sha(Path(vendor['reference'])/'rtl/dvi_tx'/name)==value
 for name,value in m['compatibility_tools'].items():assert sha(ROOT/name)==value,name
 ns={'e':'http://www.efinixinc.com/enf_proj'};project=ET.parse(BUILD/'ti60_camera.xml')
 assert project.find('.//e:device',ns).get('name')=='Ti60F225'
 assert project.find('.//e:timing_model',ns).get('name')=='I3'
 assert sha(BUILD/'ti60_camera.xml')==m['project_xml_sha256']
 for node in project.findall('.//e:param[@name="max_threads"]',ns):assert node.get('value')=='4'
 simulations={}
 for name in ['sim/display60/verification.json','sim/top_safety60/verification.json']:
  data=read(ROOT/name);assert data['result']=='PASS'
  for path,value in data.get('sha256',data.get('sources_sha256',{})).items():assert sha(Path(path))==value,path
  for path,value in data.get('sources',{}).items():assert sha(ROOT/path)==value,path
  for path,value in data.get('logs',{}).items():assert sha(ROOT/path)==value,path
  simulations[name]={'receipt_sha256':sha(ROOT/name),'scope':data['scope']}
 # The exact same V7 IP and VIC4 wrapper were simulated in the working UART
 # build. Bind that original receipt and its original source paths explicitly.
 tx=read(UART/'sim/hdmi60/verification.json');assert tx['result']=='PASS' and tx['avi_vic']==4
 for path,value in tx['sha256'].items():assert sha(Path(path))==value,path
 return {'result':'PASS','parent_camera30_bit_sha256':old['bitstream_sha256'],
  'uart720p60_bit_sha256':sha(UART/'build/720p60_hdmi/outflow/ti60_style.bit'),
  'display_simulations':simulations,'unchanged_v7_tx_receipt_sha256':sha(UART/'sim/hdmi60/verification.json'),
  'tx_scope':'same byte-identical V7 IP/VIC4 wrapper; original UART public-output receipt explicitly reused, camera raster separately tested',
  'firmware_models_sensor_and_electrical_unchanged':True,'board_programmed':False}
