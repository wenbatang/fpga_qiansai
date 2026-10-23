"""Bind the exact-arithmetic resource optimization to the corrected-pin baseline."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'build/baseline_resource_20261019'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def audit(folder,resources):
 snapshot=json.loads((BASE/'snapshot.json').read_text(encoding='utf-8'))
 for relative,value in snapshot['files'].items():
  assert sha(BASE/relative)==value,'Changed preserved resource baseline '+relative
 for filename,value in snapshot['other_projects'].items():
  assert sha(Path(filename))==value,'Unrelated project changed '+filename
 old=json.loads((BASE/'build'/folder.name/'manifest.json').read_text(encoding='utf-8'))
 new=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
 assert old['sources'].keys()==new['sources'].keys(),'Changed synthesis file set'
 changed=[name for name in old['sources'] if old['sources'][name]!=new['sources'][name]]
 assert [name.replace('\\','/') for name in changed]==['elinx/projects/uart_art_styles/rtl/art_conv3x3.sv'],changed
 for name in ['weights','models','tiling','size','display','reference','reused','schema_source']:
  assert old[name]==new[name],'Changed image/model/interface contract '+name
 assert (folder/'ti60_style.peri.xml').read_bytes()==(BASE/'build'/folder.name/'ti60_style.peri.xml').read_bytes(),'Electrical interface changed'
 signed=json.loads((BASE/'build'/folder.name/'signoff.json').read_text(encoding='utf-8'))
 assert resources['ram10']['used']<=221,'RAM savings missing'
 assert resources['dsp']['used']==144,'Unexpected DSP mapping'
 from verification import simulations
 receipts=simulations()
 for case in ['tiles','link','height720']:
  before=json.loads((BASE/'sim'/case/'verification.json').read_text(encoding='utf-8'))
  after=json.loads((ROOT/'sim'/case/'verification.json').read_text(encoding='utf-8'))
  def signature(text):
   # Simulator wall time, memory totals and exit timestamps are not DUT cycles.
   return {'pass':sorted(set(re.findall(r'^PASS [^\n]+',text,re.M))),
           'jobs':sorted(set(re.findall(r'^JOB \d+ pixels \d+',text,re.M))),
           'finish_time':sorted(set(re.findall(r'\$finish called at(?: time\s*:)?\s*(\d+)',text)))}
  assert signature(before['result'])==signature(after['result']),'Functional result/cycle count changed '+case
 return {'baseline_snapshot_sha256':sha(BASE/'snapshot.json'),
  'baseline_bit_sha256':signed['bitstream_sha256'],'before':signed['resources'],'after':resources,
  'changed_production_sources':changed,'unchanged_models_rom_geometry_clocks_interface':True,
  'simulation_results_and_cycles_unchanged':True,'other_project_fingerprints':len(snapshot['other_projects']),
  'method':['small bias ROMs in logic with original synchronous read and pipeline',
            'nine first-layer multipliers in logic with unchanged full signed arithmetic and latency'],
  'tradeoff':'More spare logic used to free scarce RAM10 and DSP; no reduction in channels, precision, frame size or styles'}
