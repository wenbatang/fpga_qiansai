"""Read-only demo10 V7/V9 comparison; never prepare or build a vendor demo."""
from pathlib import Path
import hashlib,json,re,xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
WS=ROOT.parents[2]
DEMO=WS/'elinx/elinxdemo/Ti60F225_DemoBoard_v4/10_Ti60f225_sc431hai2hdmi_demo'
OUT=ROOT/'build/programming_review_20261017'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inventory(p):
 return {x.relative_to(p).as_posix():sha(x) for x in p.rglob('*') if x.is_file()
         and x.suffix.lower() in ('.v','.sv','.vh','.svh','.xml','.sdc','.json','.txt','.md')
         and not any(y in ('outflow','work_syn','work_pnr','ipm') for y in x.relative_to(p).parts)}
def mode(p):
 text=re.sub(r'/\*.*?\*/|//[^\n]*','',p.read_text(errors='replace'),flags=re.S)
 return [(int(i,16),int(a,16),int(v,16)) for i,a,v in re.findall(
  r"ROM\[8'h([0-9a-f]+)\]\s*=\s*\{16'h([0-9a-f]+),\s*8'h([0-9a-f]+)",text,re.I)]

def main():
 refs={v:DEMO/f'Ti60f225_sc431hai2hdmi_v{v}'/f'Ti60f225_sc431hai2hdmi_v{v}' for v in (7,9)}
 snapshots={f'v{v}':inventory(p) for v,p in refs.items()}
 before=OUT/'demo_v7_v9_before.json'
 assert snapshots==json.loads(before.read_text()),'Vendor reference source/config changed during review'
 a,b=snapshots['v7'],snapshots['v9']
 changed=sorted(n for n in a.keys()&b.keys() if a[n]!=b[n])
 assert a['ti60f225_oob.peri.xml']==b['ti60f225_oob.peri.xml']
 assert a['ti60f225_oob.sdc']==b['ti60f225_oob.sdc']
 assert all(a[n]==b[n] for n in a if n.startswith('rtl/ddr3_controller/'))
 assert a['rtl/csi_rx_controller.sv']==b['rtl/csi_rx_controller.sv']
 m7,m9=[mode(refs[v]/'rtl/cam_i2c_ctrl/i2c/i2c_master_reg_rom.v') for v in (7,9)]
 assert len(m7)==164 and len(m9)==146
 assert all(not(0x3200<=address<=0x3221) for _,address,_ in m9)
 firmware=json.loads((ROOT/'build/camera_ppi/firmware_manifest.json').read_text())
 assert firmware['mode_source']==sha(refs[7]/'rtl/cam_i2c_ctrl/i2c/i2c_master_reg_rom.v')
 mode_path=next(WS/n for n in firmware['files'] if Path(n).name=='camera_mode.h')
 assert sha(mode_path)==firmware['files'][str(mode_path.relative_to(WS))]
 actual_mode=mode_path.read_text()
 parsed=[(int(a,16),int(v,16)) for a,v in re.findall(r'\{0x([0-9a-f]+),0x([0-9a-f]+)\}',actual_mode)]
 assert parsed==[(a,v) for _,a,v in m7 if (a,v)!=(0x0100,1)]
 projects={
  'uart':ROOT.parent/'uart_style_tiles/build/720p/ti60_style.xml',
  'camera':ROOT/'build/camera_ppi/ti60_camera.xml'}
 dependencies={}
 for label,project in projects.items():
  sources=[x.get('name') for x in ET.parse(project).getroot().iter() if x.tag.endswith('design_file')]
  assert all('sc431hai2hdmi_v6' not in n.lower() for n in sources)
  assert all(Path(n).name not in ('raw_to_rgb.v','rgb_gain_v1.v','sensor_clipper.v') for n in sources)
  dependencies[label]={'source_count':len(sources),'v6_dependency':False,'vendor_debayer_dependency':False}
 alignment=json.loads((ROOT/'sim/bayer_alignment/verification.json').read_text())
 assert alignment['result']=='PASS' and alignment['source_sha256']==sha(ROOT/'rtl/camera_bayer_reduce.sv')
 pair=json.loads((OUT/'pair_720p.json').read_text())
 for label in projects:
  assert sha(Path(pair[label]['bit']))==pair[label]['bit_sha256']
 result={'result':'PASS_READ_ONLY_REVIEW','reference_versions':[7,9],
  'reference_source_configuration_files_unchanged':sum(map(len,snapshots.values())),
  'changed_common_files':changed,'added_v9_files':sorted(b.keys()-a.keys()),
  'peri_sdc_ddr_and_original_csi_identical':True,
  'sensor_active_commands':{'v7':len(m7),'v9':len(m9)},
  'current_camera_mode':'V7 163 standby commands; stream-on delayed until CPU validation/model load',
  'v9_not_drop_in':'No explicit 0x3200..0x3221 writes; FPGA clips 480 groups x 1080 lines. Current decoder enforces 1920 RAW10 / WC2400.',
  'dependencies':dependencies,'bayer_regression':alignment,
  'existing_signed_bits_unchanged':{k:pair[k]['bit_sha256'] for k in projects},
  'production_modified':False,'vendor_modified':False,'physical_validation':False}
 (OUT/'demo_v7_v9_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
