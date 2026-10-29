"""Native scalar/Gray/bundle constraints for the independent PPI architecture."""
from pathlib import Path
import hashlib,json,re

def assemble(folder):
 map_path=folder/'outflow/ti60_camera.map.v'
 text=map_path.read_text(encoding='utf-8')
 assert 'pixel_bits_cnt' not in text,'Old CSI byte-to-pixel core must not be present'
 records=[]
 for name,ports,attrs in re.findall(r'EFX_FF\s+(\S+)\s+\(([^;]*?)\)\s*/\*([^;]*?)\*/\s*;',text,re.S):
  p={k:re.sub(r'\s+','',v).lstrip('\\') for k,v in re.findall(r'\.(\w+)\(([^()]*)\)',ports)}
  records.append((name.lstrip('\\'),p,attrs))
 assert len(records)>10000
 drivers={p.get('Q'):(n,p) for n,p,a in records}
 periods={'CLK_25M':40.,'CLK_27M':37.037037,'core_clk':10.,'cnn_clk':6.,'hdmi_tx_slow_clk':13.468,
  'sdram_clk':2.5,'rx_cal_clk':2.5,'tx_cal_clk':2.5,'tx_cal_clk_90edge':2.5,'i_cam_ck_CLKOUT':14.285714}
 lines=['create_clock -name CLK_25M -period 40 [get_ports CLK_25M]',
  'create_clock -name CLK_27M -period 37.037037 [get_ports CLK_27M]',
  'create_clock -name i_cam_ck_CLKOUT -period 14.285714 [get_ports i_cam_ck_CLKOUT]']
 lines += [x for x in (folder/'outflow/ti60_camera.pt.sdc').read_text(encoding='utf-8').splitlines() if '<USER' not in x]
 scalars={'system/control/scl_sync[0]~FF','system/control/sda_sync[0]~FF',
  'system/reader/request_sync[0]~FF','system/reader/window_sync[0]~FF','system/reader/rd_busy_sync[0]~FF','system/video/ack_sync[0]~FF',
  'system/video/valid_sync[0]~FF','system/pixel_fifo/rd_busy_sync[0]~FF','system/fps/request_sync[0]~FF',
  'system/fps/ack_sync[0]~FF','system/overlay_sync[0]~FF','bridge/overflow_sync[0]~FF'}
 scalars.update(f'system/keys/sync_meta[{i}]~FF' for i in range(4))
 scalars.update(f'boot/meta[{i}]~FF' for i in (0,3))
 scalars.update('system/engine/cnn/'+n+'[0]~FF' for n in ['cfg_ack_sync','done_sync','cfg_request_sync','start_request_sync'])
 scalars.update('system/engine/cnn/'+n+'/rd_busy_sync[0]~FF' for n in ['in_stream','out_stream'])
 report={'scalar_first_stages':[],'gray_paths':[],'bundle_paths':[],'async_reset_pins':[],
  'dphy_first_stages':[],'no_csi_word_count_cdc':True}
 for name,p,attrs in records:
  if "SR_SYNC=1'b0" in attrs and p.get('SR') not in (None,"1'b0","1'b1"):
   lines.append(f'set_false_path -to [get_pins {{{name}|SR}}]');report['async_reset_pins'].append(name+'|SR')
  if name in scalars:
   assert 'async_reg="true"' in attrs,name
   lines.append(f'set_false_path -to [get_pins {{{name}|D}}]');report['scalar_first_stages'].append(name+'|D')
  if 'addr_sync/' in name and 'addr_cntr_gry_r' in p.get('D',''):
   origin,source=drivers[p['D']]
   bound=min(periods[source['CLK']],periods[p['CLK']])-.2
   lines.append(f'set_max_delay {bound:.3f} -from [get_pins {{{origin}|CLK}}] -to [get_pins {{{name}|D}}]')
   report['gray_paths'].append({'from':origin+'|CLK','to':name+'|D','bound_ns':bound})
  if name.startswith(('system/engine/cnn/fast_cfg[','system/engine/cnn/fast_start[')):
   origin,source=drivers[p['D']]
   expected='system/engine/cnn/cfg_mail[' if '/fast_cfg[' in name else 'system/engine/cnn/start_mail['
   assert origin.startswith(expected),(name,origin)
   lines += [f'set_max_delay 4.800 -from [get_pins {{{origin}|CLK}}] -to [get_pins {{{name}|D}}]',f'set_false_path -hold -to [get_pins {{{name}|D}}]']
   report['bundle_paths'].append(name+'|D')
  if name.startswith(('system/capture_fps[','system/inference_fps[')):
   origin,source=drivers[p['D']];assert origin.startswith('system/fps/bundle[')
   lines += [f'set_max_delay 13.000 -from [get_pins {{{origin}|CLK}}] -to [get_pins {{{name}|D}}]',
             f'set_false_path -hold -to [get_pins {{{name}|D}}]']
   report['bundle_paths'].append(name+'|D')
 assert len(report['gray_paths'])==166,('Expected 116 DDR/display +20 PPI FIFO Gray bits',len(report['gray_paths']))
 assert len(report['scalar_first_stages'])==24,len(report['scalar_first_stages'])
 assert not (set(scalars)-{n for n,p,a in records}),'Missing scalar CDC boundary'
 # C8 strips advance by128 and pool by2. Constant/unused origin bits are
 # removed by mapping:48 cfg +11 start +14 FPS bundle endpoints remain.
 assert 64<=len(report['bundle_paths'])<=85
 assert not re.search(r'EFX_SRL8\s+\S*addr_sync/',text),'Gray synchronizer implemented as SRL'
 # A preliminary route remains fully timed at protected D-PHY boundaries.
 # Only a verified native-STA chain proof permits first-stage D exceptions.
 proof_path=folder/'dphy_cdc_proof.json'
 if proof_path.exists():
  proof=json.loads(proof_path.read_text())
  assert proof['map_sha256']==hashlib.sha256(map_path.read_bytes()).hexdigest(),'Stale D-PHY topology proof'
  for item in proof['first_stages']:
   assert item['only_second_stage_endpoint'] and item['interstage_slack_ns']>0
   dest=item['first_stage']+'|D'
   lines.append(f'set_false_path -to [get_pins {{{dest}}}]');report['dphy_first_stages'].append(dest)
  for dest in proof.get('async_reset_pins',[]):
   lines.append(f'set_false_path -to [get_pins {{{dest}}}]');report['async_reset_pins'].append(dest)
  report['dphy_proof_sha256']=hashlib.sha256(proof_path.read_bytes()).hexdigest()
 (folder/'ti60_camera.sdc').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 (folder/'cdc_constraints.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print('PPI constraints:',len(report['gray_paths']),'Gray bits;',len(report['dphy_first_stages']),'verified D-PHY first stages')
