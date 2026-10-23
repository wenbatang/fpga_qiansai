"""Require current model/source binding, all working clocks, timing and V4 pins."""
from pathlib import Path
import argparse,csv,hashlib,json,re,datetime
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];WS=ROOT.parents[2]
from catalog import SELECTED,POLICY
PN='http://www.efinixinc.com/peri_design_db'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def audit(folder, require_bit=True):
    from verification import simulations,comparison
    verification=simulations();style_comparison=comparison()
    from board_spec import audit as correct_board_audit
    corrected_board=correct_board_audit(folder)
    manifest_path=folder/'manifest.json';manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest['tiling']!={'core_width':32,'halo':32,'input_width':96,'channels':12,'lanes':3,'strips':manifest['size'][0]//32,'boundary':POLICY,'coordinate':'none'}:raise ValueError('Wrong tiling contract')
    display=manifest['display']
    if display['mode']!='720p30' or display['totals']!=[3300,750] or display['horizontal']!=[1280,1760,40,220] or display['vertical']!=[720,5,5,20]:raise ValueError('Wrong display timing')
    if display['pixel_hz']!=74250000 or display['serial_hz']!=371250000 or display['pixel_hz']/(3300*750)!=display['refresh_hz'] or display['refresh_hz']!=30:raise ValueError('Wrong display clocks/rate')
    top=(ROOT/'rtl/ti60_style_top.sv').read_text(encoding='utf-8')
    if 'video_720p #(.H_FRONT(1760),.DISPLAY_WIDTH(PROC_WIDTH),.DISPLAY_HEIGHT(PROC_HEIGHT))' not in top:raise ValueError('Missing 30Hz instance override')
    if 'style_tile_engine #(' not in top:raise ValueError('Wrong engine')
    if '.async_reset(!sys_rst_n || !pll_locked || !core_pll_locked || !user_pll_locked),.reset(ddr_reset)' not in top:raise ValueError('Incomplete global PLL fault reset')
    if '.async_reset(!sys_rst_n || !pll_locked || !core_pll_locked || !user_pll_locked || !calibrated),.reset(reset_pixel)' not in top:raise ValueError('Incomplete pixel PLL fault reset')
    width,height=manifest['size']
    if (folder/'style_profile.vh').read_text()!=f'`define STYLE_PROC_WIDTH {width}\n`define STYLE_PROC_HEIGHT {height}\n':raise ValueError('Wrong profile header')
    for path,expected in manifest['sources'].items():
        if digest(WS/path)!=expected:raise ValueError('Source changed: '+path)
    for name,expected in manifest['weights'].items():
        if digest(folder/name)!=expected:raise ValueError('Weight changed: '+name)
    for name,value in manifest['scripts'].items():
        if digest(ROOT/'scripts'/name)!=value:raise ValueError('Changed build script '+name)
    for name,value in manifest['reference'].items():
        if digest(WS/name)!=value:raise ValueError('Changed mirror reference '+name)
    expected_styles=list(SELECTED)
    if [x['style'] for x in manifest['models']]!=expected_styles:raise ValueError('Style slots')
    for name,model in zip(expected_styles,manifest['models']):
        path=WS/'pycode/runs/art6_v2/student'/name/'model.pt'
        if digest(path)!=model['checkpoint_sha256']:raise ValueError('Model checkpoint changed')
    report_path=folder/'outflow/ti60_style.timing.rpt'
    if report_path.stat().st_mtime_ns<manifest_path.stat().st_mtime_ns:raise ValueError('Stale timing')
    report=report_path.read_text(encoding='utf-8')
    required_clocks={'core_clk':10.,'hdmi_tx_slow_clk':13.468,'hdmi_tx_fast_clk':2.694,'sdram_clk':2.5,'rx_cal_clk':2.5,'tx_cal_clk':2.5,'tx_cal_clk_90edge':2.5}
    for clock,period in required_clocks.items():
        if not re.search(r'^\s*'+re.escape(clock)+r'\s+'+f'{period:.3f}'+r'\s',report,re.M):raise ValueError('Missing clock constraint '+clock)
    summary=report.split('---------- 2. Clock Relationship Summary (begin) ----------')[1].split('---------- Clock Relationship Summary (end)')[0]
    setup_text,hold_text=summary.split('Hold (Min) Clock Relationship')
    rows=lambda text:[(m[1],m[2],float(m[3]),float(m[4])) for m in re.finditer(r'^\s*(\S+)\s+(\S+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+\(R-R\)',text,re.M)]
    setup,hold=rows(setup_text),rows(hold_text)
    if len(setup)<12 or len(hold)<12:raise ValueError('Incomplete clock relationship table')
    if any(x[3]<0 for x in setup+hold):raise ValueError('Negative setup/hold slack')
    place=(folder/'outflow/ti60_style.place.out').read_text(encoding='utf-8')
    if re.search(r'WARNING.*\[SDC|Unable to run|no vaild startpoints|Failed to run',place):raise ValueError('Invalid/ignored constraint')
    constraints=json.loads((folder/'cdc_constraints.json').read_text(encoding='utf-8'))
    if len(constraints['gray_pointer_paths'])<20:raise ValueError('Missing Gray timing bounds')
    mapped=(folder/'outflow/ti60_style.map.v').read_text(encoding='utf-8')
    if re.search(r'\bASYNC_REG\s*=',mapped):raise ValueError('Untranslated Xilinx CDC attribute')
    sync_cells=[]
    for match in re.finditer(r'EFX_FF\s+(\S+)\s+\(([^;]*?)\)\s*/\*([^;]*?)\*/\s*;\s*//([^\n]*)',mapped,re.S):
        name,ports,attrs,source=match.groups()
        if 'reset_sync.sv(' in source or ('uart_8n1.sv(' in source and 'sync_rx[' in name):
            # syn_srlstyle is consumed during inference; actual EFX_FF proves
            # the choice. async_reg remains on the mapped cell for placement.
            if 'async_reg="true"' not in attrs:raise ValueError('Missing native synchronizer attribute '+name)
            sync_cells.append(name)
    if len(sync_cells)!=12:raise ValueError('Missing 3 UART / 9 reset synchronizer FFs')
    if re.search(r'EFX_SRL8\s+\S*_addr_sync/',mapped):raise ValueError('Synchronizer packed to SRL')
    if 'Missing Interface Pins' in (folder/'outflow/ti60_style.place.rpt').read_text():raise ValueError('Missing board interface pins')
    text=(folder/'outflow/ti60_style.pinout.csv').read_text(encoding='utf-8')
    pins=list(csv.DictReader(line for line in text.splitlines() if line and not line.startswith('#')))
    active=[p for p in pins if p['Signal Name']]
    by_signal={p['Signal Name']:p for p in active}
    expected={'style_keys_n[0]':('C4','Input','TL','3.3 V'),
              'style_keys_n[1]':('P14','Input','BR','3.3 V'),
              'style_keys_n[2]':('N14','Input','BR','3.3 V'),
              'style_keys_n[3]':('A3','Input','TL','3.3 V'),
              'uart_rx':('R4','Input','BL','3.3 V'),'uart_tx':('R14','Output','BR','3.3 V'),
              'CLK_25M.P':('J2','Input','1A','1.8 V'),'CLK_27M.P':('H2','Input','1B','1.8 V'),
              'tmds_tx_clk.P':('H13','Output','3A','1.8 V'),'tmds_tx_clk.N':('H12','Output','3A','1.8 V'),
              'tmds_tx_data0.P':('G15','Output','3A','1.8 V'),'tmds_tx_data0.N':('F15','Output','3A','1.8 V'),
              'tmds_tx_data1.P':('H14','Output','3A','1.8 V'),'tmds_tx_data1.N':('G14','Output','3A','1.8 V'),
              'tmds_tx_data2.P':('G13','Output','3A','1.8 V'),'tmds_tx_data2.N':('F13','Output','3A','1.8 V')}
    for name,values in expected.items():
        p=by_signal[name]
        if tuple(p[x] for x in ('Pin Number','Direction','Bank','I/O Bank Voltage'))!=values:raise ValueError('Pin mismatch '+name)
    for p in active:
        name=p['Signal Name']
        if name.startswith(('ddr','verf')):
            if p['Bank'] not in ('3B','4A','4B') or p['I/O Bank Voltage']!='1.5 V' or 'SSTL' not in p['I/O Standard']:raise ValueError('DDR voltage/direction '+name)
            direction='Input' if name.startswith('verf') else 'Bidirectional' if name.startswith(('ddr_dq[','ddr_dqs[')) else 'Output'
            if p['Direction']!=direction:raise ValueError('DDR direction '+name)
        elif name not in expected:raise ValueError('Unexpected active pin '+name)
    # Original DDR/clock/TMDS gpio bindings are byte-for-byte retained except
    # intentionally unused address14/15; keys/UART independently checked above.
    ref=WS/'elinx/elinxdemo/Ti60F225_DemoBoard_v4/10_Ti60f225_sc431hai2hdmi_demo/Ti60f225_sc431hai2hdmi_v7/Ti60f225_sc431hai2hdmi_v7/ti60f225_oob.peri.xml'
    orig=ET.parse(ref);new=ET.parse(folder/'ti60_style.peri.xml')
    refs={x.get('name'):x for x in orig.findall('.//{'+PN+'}comp_gpio')}
    for node in new.findall('.//{'+PN+'}comp_gpio'):
        if node.get('name').startswith(('ddr','verf','CLK_25M','CLK_27M')):
            if ET.tostring(node)!=ET.tostring(refs[node.get('name')]):raise ValueError('Reference electrical config changed '+node.get('name'))
    bit=folder/'outflow/ti60_style.bit'
    if require_bit and (not bit.exists() or bit.stat().st_mtime_ns<report_path.stat().st_mtime_ns):raise ValueError('Missing current bitstream')
    width,height=manifest['size']
    config_names=['ti60_style.xml','ti60_style.peri.xml','ti60_style.sdc','style_weights.vh','style_profile.vh','crc32_byte.svh','ddr3_parameter.vh','cdc_constraints.json']
    resource_text=(folder/'outflow/ti60_style.place.rpt').read_text(encoding='utf-8')
    resources={}
    for key,label in [('ram10','Memory Blocks'),('dsp','DSP Blocks'),('xlr','XLRs')]:
        match=re.search(r'^'+label+r': (\d+) / (\d+)',resource_text,re.M)
        if not match:raise ValueError('Missing resource '+key)
        resources[key]={'used':int(match[1]),'available':int(match[2])}
        if resources[key]['used']>resources[key]['available']:raise ValueError('Over capacity '+key)
    from resource_contract import audit as resource_audit
    resource_optimization=resource_audit(folder,resources)
    board_summary=None
    if require_bit:
        from board_audit import audit as audit_board
        board=audit_board(folder.name)
        board_summary={k:v for k,v in board.items() if k!='pins'}
    receipt={'date_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':f'Ti60 V4 {width}x{height} UART + four selected art6 folded-CNN + DDR3 + 720p30 static-photo validation; no board download',
       'corrected_schematic':corrected_board,'display':display,'resources':resources,'resource_optimization':resource_optimization,'tiling':manifest['tiling'],'simulations':verification,'style_count_comparison':style_comparison,
       'native_uart_reset_sync_ffs':sync_cells,'padding':POLICY,'selected_original_ids':[0,3,4,5],'independent_board_audit':board_summary,
       'models':manifest['models'],'source_manifest_sha256':digest(manifest_path),'setup_min_ns':min(x[3] for x in setup),'hold_min_ns':min(x[3] for x in hold),
       'core_setup_ns':next(x[3] for x in setup if x[:2]==('core_clk','core_clk')),
       'active_package_pins':len(active),'pins':active,'setup':setup,'hold':hold,'required_clocks':required_clocks,
       'gray_paths':len(constraints['gray_pointer_paths']),'scalar_first_stages':len(constraints['single_bit_first_stages']),
       'async_reset_pins':len(constraints['async_reset_endpoints']),
       'configuration_sha256':{name:digest(folder/name) for name in config_names},
       'reports_sha256':{name:digest(folder/'outflow'/name) for name in ['ti60_style.map.v','ti60_style.map.rpt','ti60_style.place.rpt','ti60_style.route.rpt','ti60_style.timing.rpt','ti60_style.pinout.csv','ti60_style.pt.rpt']},
       'scripts_sha256':{p.name:digest(p) for p in (ROOT/'scripts').glob('*.py')},
       'bitstream':str(bit) if require_bit else None,'bitstream_sha256':digest(bit) if require_bit else None,
       'not_measured':['real UART/host camera','DDR calibration on board','HDMI/key/reset behavior','Ti60 continuous inference FPS','MIPI/RISC-V integration']}
    return receipt
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--profile',choices=('720p','vga'),default='720p');a=parser.parse_args()
    folder=ROOT/'build'/a.profile;result=audit(folder)
    (folder/'signoff.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PASS Ti60 full clock/Gray/timing/electrical/source audit:',result['active_package_pins'],'pins, setup',result['setup_min_ns'],'hold',result['hold_min_ns'],'core',result['core_setup_ns'])
    print('BIT SHA256',result['bitstream_sha256'])
