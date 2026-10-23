"""Read-only audit of all current Ti60 releases against the corrected board PDF."""
from pathlib import Path
import csv,hashlib,importlib.util,json,re,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];PROJECTS=ROOT.parent
OUT=ROOT/'build/schematic_review_20261019'
PN='http://www.efinixinc.com/peri_design_db'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(path):
 spec=importlib.util.spec_from_file_location('board_'+path.parents[1].name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def main():
 result={'result':'PASS_CONFIGURATION_REVIEW','scope':'all six rebuilt releases, corrected schematic, source/ROM/config/report/bit binding; no hardware access or measurement','releases':[]}
 for project,profiles in [('uart_art_styles',['720p','vga']),('uart_style_tiles',['720p','vga']),('uart_style_keys',['vga']),('style_video',['camera_ppi'])]:
  r=PROJECTS/project;contract=load(r/'scripts/board_spec.py');camera=project=='style_video';stem='ti60_camera' if camera else 'ti60_style'
  baseline=r/'build/baseline_wrong_schematic_20261019'
  for profile in profiles:
   f=r/'build'/profile;s=json.loads((f/'signoff.json').read_text(encoding='utf-8'));board=contract.audit(f,camera)
   assert sha(f/'outflow'/(stem+'.bit'))==s['bitstream_sha256'],'Changed released bit'
   signed_board=s['electrical'] if camera else s['corrected_schematic']
   assert signed_board['schematic_sha256']==contract.PDF_SHA and signed_board['script_sha256']==sha(r/'scripts/board_spec.py')
   assert signed_board['pins']==board['pins'],'Cached pin report differs'
   for name,value in s['configuration_sha256'].items():assert sha(f/name)==value,'Changed configuration '+name
   for name,value in s.get('reports_sha256',{}).items():assert sha(f/'outflow'/name)==value,'Changed CAD report '+name
   manifest=json.loads((f/'manifest.json').read_text(encoding='utf-8'));old=json.loads((baseline/'build'/profile/'manifest.json').read_text(encoding='utf-8'))
   assert manifest['sources']==old['sources'],'Production RTL/IP changed unexpectedly'
   assert manifest.get('weights')==old.get('weights'),'ROM changed'
   assert manifest.get('firmware_manifest')==old.get('firmware_manifest'),'CPU firmware changed'
   assert manifest.get('models')==old.get('models'),'Selected model changed'
   for name,value in manifest['sources'].items():assert sha(ROOT.parents[2]/name)==value,'Source fingerprint mismatch'
   before=ET.parse(baseline/'build'/profile/(stem+'.peri.xml'));after=ET.parse(f/(stem+'.peri.xml'))
   for i,pin in [(1,'GPIOR_22'),(2,'GPIOR_21')]:before.find('.//{'+PN+'}comp_gpio[@name="style_keys_n['+str(i)+']"]').set('gpio_def',pin)
   assert ET.tostring(before.getroot())==ET.tostring(after.getroot()),'Interface changed beyond the two reviewed input pads'
   timing=(f/'outflow'/(stem+'.timing.rpt')).read_text(encoding='utf-8');assert 'Timing Model: I3' in timing
   summary=timing.split('---------- 2. Clock Relationship Summary (begin) ----------')[1].split('---------- Clock Relationship Summary (end)')[0]
   a,b=summary.split('Hold (Min) Clock Relationship')
   def slacks(t):return [float(m[1]) for m in re.finditer(r'^\s*\S+\s+\S+\s+-?\d+\.\d+\s+(-?\d+\.\d+)\s+\(R-R\)',t,re.M)]
   setup,hold=slacks(a),slacks(b);assert len(setup)>=12 and len(hold)>=12 and min(setup+hold)>=0
   assert s['setup_min_ns']==min(setup) and s['hold_min_ns']==min(hold)
   old_signed=json.loads((baseline/'build'/profile/'signoff.json').read_text(encoding='utf-8'))
   result['releases'].append({'project':project,'profile':profile,'active_pins':board['active_pins'],'key_pads':board['key_pads'],'schematic_sha256':contract.PDF_SHA,
    'setup_min_ns':min(setup),'hold_min_ns':min(hold),'resources':s['resources'],'bit_sha256':s['bitstream_sha256'],'previous_wrong_key_bit_sha256':old_signed['bitstream_sha256'],
    'rtl_ip_rom_firmware_unchanged':True,'only_two_input_bindings_changed':True,'bank_voltages':board['banks'],'signoff_sha256':sha(f/'signoff.json'),'board_programmed':False})
 result['schematic_sha256']=contract.PDF_SHA
 safety={}
 for name in ['top_safety','camera_fault_shutdown']:
  p=ROOT/'sim'/name/'verification.json';data=json.loads(p.read_text());assert data['result']=='PASS'
  for source,value in data['sources_sha256'].items():assert sha(Path(source))==value,'Changed safety source'
  safety[name]={'receipt_sha256':sha(p),'scope':data['scope'],'cases':len(data.get('cases',[]))}
 result['fresh_safety_rechecks']=safety
 # Reserved supplies are part of the silicon pin model, not user RTL assignments.
 f=PROJECTS/'uart_art_styles/build/720p/outflow/ti60_style.pinout.csv'
 pins=list(csv.DictReader(x for x in f.read_text().splitlines() if x and not x.startswith('#')))
 result['reserved_power_pin_rows']=[p for p in pins if p['Pin Number'] in ['A1','N15','P4','B4','B13']]
 OUT.mkdir(exist_ok=True);(OUT/'all_projects.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print('PASS six current releases: corrected key pins, all voltage/direction/bank and timing relationships, unchanged production logic and models')
 print(json.dumps([{k:r[k] for k in ['project','profile','active_pins','setup_min_ns','hold_min_ns','bit_sha256']} for r in result['releases']],indent=2))
if __name__=='__main__':main()
