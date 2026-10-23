"""Verify single-bit D-PHY synchronizers using licensed native STA reports."""
from pathlib import Path
import argparse,hashlib,json,re,sys
ROOT=Path(__file__).resolve().parents[2];BUILD=ROOT/'build/camera_720_fast'
sys.path.insert(0,str(ROOT/'scripts'))
from tool_run import environment,run
from summarize_csi_cdc import rows
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--final',action='store_true');args=p.parse_args()
 prefix='final_' if args.final else ''
 environment();commands=[];chains=[]
 for lane in range(4):
  for signal in ('RxHS_settle','RxStopState'):
   first=f'inst_camera_dphy/u_efx_dphy_rx/genblk2[{lane}].rx_dword_align_inst/genblk1.{signal}_1P~FF'
   file=f'{prefix}dphy_lane{lane}_{signal}.rpt';chains.append((first,file))
   commands.append(f'report_timing -from {{{first}}} -npaths 200 -nworst 1 -file {{{file}}}')
 for name,launch,capture in [('byte_to_core','i_cam_ck_CLKOUT','core_clk'),('core_to_byte','core_clk','i_cam_ck_CLKOUT')]:
  commands.append(f'report_timing -from_clock {launch} -to_clock {capture} -npaths 2000 -nworst 1 -file {{{prefix}dphy_{name}.rpt}}')
 tcl=BUILD/'inspect_dphy.tcl';tcl.write_text('\n'.join(commands)+'\n')
 cmd=['E:/software/efinity/python311/bin/python.exe','E:/software/efinity/scripts/efx_run.py','ti60_camera','--prj','--flow','sta_tclsh','--output_dir','outflow','--tcl_script',str(tcl)]
 code=run(cmd,BUILD,BUILD/'dphy_sta_console.log');assert code==0
 log=(BUILD/'dphy_sta_console.log').read_text(errors='replace')
 assert not any(x in log for x in ('Failed to run command','Unable to generate slack report','Fail to open file'))
 proof={'map_sha256':sha(BUILD/'outflow/ti60_camera.map.v'),'dphy_sha256':sha(ROOT/'vendor/camera_dphy.sv'),
  'first_stages':[],'reports':{},'scope':'Native STA register endpoint topology; no analog metastability measurement'}
 for first,file in chains:
  path=BUILD/'outflow'/file;data=rows(path);assert len(data)==1,(file,data)
  r=data[0]
  assert r['source']==first+'|CLK' and r['destination']==first.replace('_1P~FF','_2P~FF')+'|D',r
  assert r['launch']==r['capture']=='i_cam_ck_CLKOUT (RISE)',r
  assert r['slack_ns']>0 and re.search(r'Logic Levels\s*:\s*0',path.read_text()),r
  proof['first_stages'].append({'first_stage':first,'only_second_stage_endpoint':True,'interstage_slack_ns':r['slack_ns']})
  proof['reports'][file]=sha(path)
 for name in ('byte_to_core','core_to_byte'):
  path=BUILD/'outflow'/f'{prefix}dphy_{name}.rpt';data=rows(path)
  assert 0<len(data)<2000,'Missing or truncated crossing report'
  for r in data:
   assert ('addr_sync/' in r['destination'] or (not args.final and any(r['destination']==f+'|D' for f,_ in chains))),r
   if args.final:assert r['slack_ns']>=0,r
  proof['reports'][path.name]=sha(path)
 if args.final:proof['vdb_sha256']=sha(BUILD/'outflow/ti60_camera.vdb')
 (BUILD/('dphy_final_proof.json' if args.final else 'dphy_cdc_proof.json')).write_text(json.dumps(proof,indent=2))
 print('PASS D-PHY CDC: eight unique first-to-second chains, minimum setup',min(x['interstage_slack_ns'] for x in proof['first_stages']))
if __name__=='__main__':main()
