"""Read-only release check for the two Ti60 V4 demonstration projects.

No CAD generation, serial access, JTAG, Flash writes, or signoff replacement.
Output is a separate local review receipt.
"""
from pathlib import Path
import argparse,hashlib,importlib.util,json,sys,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
TILES=ROOT.parent/'uart_style_tiles'
OUT=ROOT/'build/programming_review_20261019'
NS={'p':'http://www.efinixinc.com/peri_design_db'}
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path)
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def frozen(folder):
 signed=json.loads((folder/'signoff.json').read_text(encoding='utf-8'))
 for name,value in signed['configuration_sha256'].items():assert sha(folder/name)==value,('Changed release configuration',name)
 for name,value in signed.get('reports_sha256',{}).items():assert sha(folder/'outflow'/name)==value,('Changed release report',name)
 for name,value in signed.get('simulation_receipts_sha256',{}).items():assert sha(ROOT/name)==value,('Changed integration receipt',name)
 return signed
def banks(folder,stem):
 tree=ET.parse(folder/(stem+'.peri.xml'))
 result={x.get('name'):x.get('iostd') for x in tree.findall('.//p:iobank',NS)}
 expected={'1A':'1.8','1B':'1.8','2A':'1.2','2B':'1.2','3A':'1.8','3B':'1.5','4A':'1.5','4B':'1.5','BL':'3.3','BR':'3.3','TL':'3.3','TR':'3.3'}
 assert {k:v.split()[0] for k,v in result.items()}==expected
 assert tree.find('.//p:global_unused_config',NS).get('state')=='input with weak pullup'
 assert all(x.get('is_dyn_voltage')=='false' for x in tree.findall('.//p:iobank',NS))
 return result
def files(folder,stem,signed):
 bit=folder/'outflow'/(stem+'.bit');hexfile=bit.with_suffix('.hex')
 assert sha(bit)==signed['bitstream_sha256'],'Released bit fingerprint changed'
 assert hexfile.exists() and abs(hexfile.stat().st_mtime-bit.stat().st_mtime)<30,'HEX not from the same generation'
 # Efinity text .bit/.hex use one hexadecimal octet per line. The SPI
 # generator changes its mode/startup prefix, so the whole files need not
 # match. Compare the application suffix and record both file fingerprints;
 # this check does not decode any protected configuration or prove Flash I/O.
 b=bytes.fromhex(bit.read_text());h=bytes.fromhex(hexfile.read_text())
 assert len(h)==len(b)+20 and h[532:]==b[512:],'HEX application suffix differs'
 for marker in ('Family: Titanium','Device: Ti60F225'):
  assert marker.encode() in b[:256] and marker.encode() in h[:256]
 assert b'Mode: passive' in b[:256] and b'Mode: active' in h[:256]
 assert b[:160]==h[:160],'HEX generation/project header differs'
 return {'project':str(folder/(stem+'.xml')),'bit':str(bit),'hex':str(hexfile),
         'bit_sha256':sha(bit),'hex_sha256':sha(hexfile),'bit_bytes_on_disk':bit.stat().st_size,
         'hex_application_suffix_matches':True,'hex_startup_prefix_not_independently_decoded':True,
         'recommended_initial_download':'JTAG using the signed .bit; no Flash write'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--uart-profile',choices=['720p','vga'],default='720p');args=p.parse_args()
 sys.path.insert(0,str(TILES/'scripts'))
 uart=load('uart_release_signoff',TILES/'scripts/signoff.py')
 u_folder=TILES/'build'/args.uart_profile;u_signed=frozen(u_folder)
 u=uart.audit(u_folder);assert u['bitstream_sha256']==u_signed['bitstream_sha256']
 sys.path.insert(0,str(ROOT/'scripts'))
 from camera_ppi_signoff import audit as camera_audit
 c_folder=ROOT/'build/camera_ppi';c_signed=frozen(c_folder);c=camera_audit()
 assert c['bitstream_sha256']==c_signed['bitstream_sha256']
 ub,cb=banks(u_folder,'ti60_style'),banks(c_folder,'ti60_camera');assert ub==cb
 result={'result':'PASS_FILE_AND_CAD_REVIEW','scope':'current signed Ti60 files; no rebuilding, programming or physical measurement',
  'uart':{**files(u_folder,'ti60_style',u_signed),'profile':args.uart_profile,'size':[1280,720] if args.uart_profile=='720p' else [640,480],
          'setup_min_ns':u['setup_min_ns'],'hold_min_ns':u['hold_min_ns'],'active_pins':u['active_package_pins'],
          'resources':u['resources'],'baud':2000000},
  'camera':{**files(c_folder,'ti60_camera',c_signed),'camera_raw':[1920,1080],'cnn':[640,480],
            'setup_min_ns':c['setup_min_ns'],'hold_min_ns':c['hold_min_ns'],'active_pins':c['electrical']['active_pins'],'resources':c['resources']},
  'banks_identical':ub,'display_both':'1280x720p30',
  'user_confirmed':'DemoBoard V4, matching SC431HAI module at J4, J2/J3 2-3',
  'physical_measurements':False,'existing_flash_content_known':False,'board_programmed':False}
 OUT.mkdir(exist_ok=True)
 (OUT/('pair_'+args.uart_profile+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2))
 print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
