"""Current mapped-cell CDC/Gray/bundled-data constraints, no clock-wide cuts."""
from pathlib import Path
import json,re
def assemble(folder):
 text=(folder/'outflow/ti60_camera.map.v').read_text(encoding='utf-8')
 records=[]
 for name,ports,attrs in re.findall(r'EFX_FF\s+(\S+)\s+\(([^;]*?)\)\s*/\*([^;]*?)\*/\s*;',text,re.S):
  p={k:re.sub(r'\s+','',v).lstrip('\\') for k,v in re.findall(r'\.(\w+)\(([^()]*)\)',ports)}
  records.append((name.lstrip('\\'),p,attrs))
 assert len(records)>10000
 drivers={p.get('Q'):(n,p) for n,p,a in records}
 period={'CLK_25M':40.,'CLK_27M':37.037037,'core_clk':10.,'hdmi_tx_slow_clk':13.468,
  'sdram_clk':2.5,'rx_cal_clk':2.5,'tx_cal_clk':2.5,'tx_cal_clk_90edge':2.5,'i_cam_ck_CLKOUT':14.285714}
 # SDC is ordered: the CSI clock must exist BEFORE generated I/O delays.
 lines=['create_clock -name CLK_25M -period 40 [get_ports CLK_25M]',
  'create_clock -name CLK_27M -period 37.037037 [get_ports CLK_27M]',
  'create_clock -name i_cam_ck_CLKOUT -period 14.285714 [get_ports i_cam_ck_CLKOUT]']
 lines += [x for x in (folder/'outflow/ti60_camera.pt.sdc').read_text(encoding='utf-8').splitlines() if '<USER' not in x]
 scalars={'system/control/scl_sync[0]~FF','system/control/sda_sync[0]~FF',
  'system/reader/request_sync[0]~FF','system/reader/window_sync[0]~FF',
  'system/video/ack_sync[0]~FF','system/video/valid_sync[0]~FF','system/pixel_fifo/rd_busy_sync[0]~FF',
  'system/fps/request_sync[0]~FF','system/fps/ack_sync[0]~FF','system/overlay_sync[0]~FF','format_guard/fault_sync[0]~FF'}
 scalars.update(f'system/keys/sync_meta[{i}]~FF' for i in range(4))
 scalars.update(f'boot/meta[{i}]~FF' for i in range(4))
 report={'scalar_first_stages':[],'gray_paths':[],'csi_gray_clock_bounds':[],'bundle_paths':[],'async_reset_pins':[]}
 for n,p,a in records:
  if "SR_SYNC=1'b0" in a and p.get('SR') not in (None,"1'b0","1'b1"):
   lines.append(f'set_false_path -to [get_pins {{{n}|SR}}]');report['async_reset_pins'].append(n+'|SR')
  if n in scalars:
   assert 'async_reg="true"' in a,n
   lines.append(f'set_false_path -to [get_pins {{{n}|D}}]');report['scalar_first_stages'].append(n+'|D')
  # Both V7 CSI FIFO and DDR/display FIFO use registered Gray source pointers.
  if ('addr_sync/' in n) and 'addr_cntr_gry_r' in p.get('D',''):
   source=drivers.get(p['D']);assert source,'Missing Gray source '+n
   origin,op=source;assert op['CLK'] in period and p['CLK'] in period
   bound=min(period[op['CLK']],period[p['CLK']])-.2
   lines.append(f'set_max_delay {bound:.3f} -from [get_pins {{{origin}|CLK}}] -to [get_pins {{{n}|D}}]')
   report['gray_paths'].append({'from':origin+'|CLK','to':n+'|D','bound_ns':bound})
  # Protected CSI synchronizer cells are absent from the plaintext map dump.
  # Bound each VISIBLE registered Gray source to every reachable register in
  # the destination clock instead. This does not cut inter-stage timing and
  # covers the hidden first stage without assuming its private cell names.
  if n.startswith('inst_efx_csi2_rx/') and re.search(r'addr_cntr_gry_r\[\d+\]~FF$',n):
   target='i_cam_ck_CLKOUT' if p['CLK']=='core_clk' else 'core_clk'
   assert p['CLK'] in ('core_clk','i_cam_ck_CLKOUT'),p
   bound=min(period[p['CLK']],period[target])-.2
   lines.append(f'set_max_delay {bound:.3f} -from [get_pins {{{n}|CLK}}] -to [get_clocks {{{target}}}]')
   report['csi_gray_clock_bounds'].append({'from':n+'|CLK','destination_clock':target,'bound_ns':bound})
  if n.startswith(('system/capture_fps[','system/inference_fps[')):
   source=drivers.get(p['D']);assert source and source[0].startswith('system/fps/bundle[')
   # Request takes two pixel edges; data must settle within ONE pixel period.
   # Hold is not meaningful across asynchronous clocks for this held bundle.
   lines.append(f'set_max_delay 13.000 -from [get_pins {{{source[0]}|CLK}}] -to [get_pins {{{n}|D}}]')
   lines.append(f'set_false_path -hold -to [get_pins {{{n}|D}}]')
   report['bundle_paths'].append(n+'|D')
 assert len(report['gray_paths'])==116,'DDR/display Gray bounds missing'
 assert len(report['csi_gray_clock_bounds'])==22,'CSI registered Gray source bounds missing'
 # V7's protected reset synchronizers have async SR pins hidden from map.v.
 # The path names and SR role are verified in the preliminary STA report.
 # Cut reset assertion/recovery only, keeping D paths between stages timed.
 reset_pattern='inst_efx_csi2_rx/*efx_resetsync*/async_reg*|SR'
 lines.append(f'set_false_path -to [get_pins {{{reset_pattern}}}]')
 report['protected_csi_reset_pattern']=reset_pattern
 # CSI asynchronous FIFO reset combiner FFs also use asynchronous SR, as
 # identified by the licensed STA reset paths (rd_rst_int / wr_rst_int).
 reset_int_pattern='inst_efx_csi2_rx/*rst_int~FF|SR'
 lines.append(f'set_false_path -to [get_pins {{{reset_int_pattern}}}]')
 report['protected_csi_reset_combiner_pattern']=reset_int_pattern
 # Only stage ZERO of the named vendor sideband synchronizers is exempt.
 # FIFO Gray synchronizers are outside this hierarchy and remain bounded.
 scalar_pattern='inst_efx_csi2_rx/*syncreg*/async_reg[0]*|D'
 lines.append(f'set_false_path -to [get_pins {{{scalar_pattern}}}]')
 report['protected_csi_scalar_first_stage_pattern']=scalar_pattern
 assert len(report['bundle_paths'])==14,'FPS bounded data bundle missing'
 for i in range(4):assert f'system/keys/sync_meta[{i}]~FF|D' in report['scalar_first_stages']
 # Never approve a CSI Gray synchronizer implemented as an SRL delay chain.
 assert not re.search(r'EFX_SRL8\s+\S*addr_sync/',text),'Gray synchronizer packed into SRL'
 (folder/'ti60_camera.sdc').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 (folder/'cdc_constraints.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print('Constrained',len(report['gray_paths']),'Gray bits,',len(report['scalar_first_stages']),'scalar entries and',len(report['bundle_paths']),'FPS bundle bits')
