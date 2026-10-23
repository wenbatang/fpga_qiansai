"""Bound Gray pointer crossings and cut only verified synchronizer/async-reset pins."""
from pathlib import Path
import json,re

def assemble(folder):
    generated=(folder/'outflow/ti60_style.pt.sdc').read_text(encoding='utf-8')
    lines=[line for line in generated.splitlines() if '<USER' not in line]
    lines+=['create_clock -name CLK_25M -period 40 [get_ports CLK_25M]',
            'create_clock -name CLK_27M -period 37.037037 [get_ports CLK_27M]']
    mapped=(folder/'outflow/ti60_style.map.v').read_text(encoding='utf-8')
    records=[]
    for match in re.finditer(r'EFX_FF\s+(\S+)\s+\((.*?)\)\s*/\*(.*?)\*/\s*;',mapped,re.S):
        name,ports,attrs=match.groups()
        ports={key:re.sub(r'\s+','',value).lstrip('\\') for key,value in re.findall(r'\.(\w+)\(([^()]*)\)',ports)}
        records.append((name.lstrip('\\'),ports,attrs))
    if len(records)<1000:raise ValueError('Mapped FF parser did not find full design')
    drivers={ports.get('Q'):(name,ports) for name,ports,_ in records}
    scalars={'receiver/sync_rx[0]~FF','reader/request_sync[0]~FF','reader/window_sync[0]~FF',
             'video/ack_sync[0]~FF','video/valid_sync[0]~FF','pixel_fifo/rd_busy_sync[0]~FF'}
    scalars.update(f'keys/sync_meta[{i}]~FF' for i in range(4))
    scalars.update(f'boot/meta[{i}]~FF' for i in range(4))
    audit={'async_reset_endpoints':[],'single_bit_first_stages':[],'gray_pointer_paths':[]}
    period={'core_clk':10.,'hdmi_tx_slow_clk':13.468,'sdram_clk':2.5,'rx_cal_clk':2.5,'tx_cal_clk':2.5,'tx_cal_clk_90edge':2.5}
    for name,ports,attrs in records:
        if "SR_SYNC=1'b0" in attrs and ports.get('SR') not in (None,"1'b0","1'b1"):
            lines.append(f'set_false_path -to [get_pins {{{name}|SR}}]')
            audit['async_reset_endpoints'].append(name+'|SR')
        if name in scalars:
            lines.append(f'set_false_path -to [get_pins {{{name}|D}}]')
            audit['single_bit_first_stages'].append(name+'|D')
        if '_addr_sync/' in name and 'addr_cntr_gry_r' in ports.get('D',''):
            source=drivers.get(ports['D'])
            if source is None:raise ValueError('Missing registered Gray source '+name)
            origin,source_ports=source
            if source_ports['CLK'] not in period:raise ValueError(source_ports)
            bound=min(period[source_ports['CLK']],period[ports['CLK']])-.2
            # Efinity's STA startpoints are register CLK pins (Q is invalid).
            lines.append(f'set_max_delay {bound:.3f} -from [get_pins {{{origin}|CLK}}] -to [get_pins {{{name}|D}}]')
            audit['gray_pointer_paths'].append({'from':origin+'|CLK','to':name+'|D','bound_ns':bound})
    for i in range(4):
        if f'keys/sync_meta[{i}]~FF|D' not in audit['single_bit_first_stages']:raise ValueError('Missing key synchronizer')
    if len(audit['gray_pointer_paths'])<20:raise ValueError('FIFO Gray crossings not found')
    (folder/'ti60_style.sdc').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (folder/'cdc_constraints.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    print('Constraints: all PLL/PHY clocks,',len(audit['single_bit_first_stages']),'scalar first stages,',len(audit['gray_pointer_paths']),'bounded Gray paths,',len(audit['async_reset_endpoints']),'async reset pins')
