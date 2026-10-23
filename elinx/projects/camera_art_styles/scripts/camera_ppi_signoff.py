"""Fail-closed CAD release audit of the independent public-PPI camera build.

This generates no hardware traffic. A PASS is not a physical board acceptance.
"""
from pathlib import Path
import csv,hashlib,json,re,importlib.util,xml.etree.ElementTree as ET
REF=Path(__file__).resolve().parents[3]/'elinxdemo/Ti60F225_DemoBoard_v4/10_Ti60f225_sc431hai2hdmi_demo/Ti60f225_sc431hai2hdmi_v7/Ti60f225_sc431hai2hdmi_v7'

ROOT=Path(__file__).resolve().parents[1]
WS=ROOT.parents[2]
BUILD=ROOT/'build/camera_ppi'
OLD=ROOT.parent/'style_video/build/camera_ppi'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def receipt(name):
    data=json.loads((ROOT/name).read_text(encoding='utf-8'))
    assert data['result']=='PASS',name
    for path,expected in data.get('sources_sha256',{}).items():
        assert sha(Path(path))==expected,'Stale simulation: '+path
    for path,expected in data.get('sources',{}).items():
        assert sha(WS/path)==expected,'Stale simulation: '+path
    return data

def electrical():
    # Pair review imports the UART signoff in the same interpreter. Resolve
    # this project's contract by file, never a cached UART board_spec module.
    spec=importlib.util.spec_from_file_location('camera_correct_board_spec',ROOT/'scripts/board_spec.py')
    contract=importlib.util.module_from_spec(spec);spec.loader.exec_module(contract)
    old=contract.audit(BUILD,camera=True)
    # Old camera_vga is an unsigned CSI candidate. Permit only the two
    # corrected key-pad changes against its interface template.
    assert (OLD/'ti60_camera.peri.xml').read_bytes()==(BUILD/'ti60_camera.peri.xml').read_bytes(),'Camera electrical interface changed'
    assert (ROOT/'vendor/rtl/ddr3_controller/ddr3_top.v').read_bytes()==(REF/'rtl/ddr3_controller/ddr3_top.v').read_bytes()
    assert (BUILD/'ddr3_parameter.vh').read_bytes()==(REF/'rtl/ddr3_controller/ddr3_parameter.vh').read_bytes()
    top=(ROOT/'rtl/ti60_camera_ppi_top.sv').read_text(encoding='utf-8')
    for fragment in ["assign io_cam_scl_OUT=1'b0", "assign io_cam_sda_OUT=1'b0",
                     'assign o_cam_rst_p=reset_ui || !sensor_reset_n',
                     '.async_reset(!sys_rst_n || !pll_locked || !core_pll_locked || !user_pll_locked)',
                     'assign cam_d0_RST=reset_byte','camera_dphy inst_camera_dphy',
                     '.cam_error(bridge_error)']:
        assert fragment in top,fragment
    assert 'camera_csi ' not in top
    return old

def audit(require_bit=True):
    manifest=json.loads((BUILD/'manifest.json').read_text(encoding='utf-8'))
    assert sha(OLD/'manifest.json')==manifest['baseline_manifest_sha256'],'Unsigned CSI baseline metadata changed'
    old_manifest=json.loads((OLD/'manifest.json').read_text(encoding='utf-8'))
    assert sha(OLD/'ti60_camera.peri.xml')==manifest['interface'],'Baseline interface changed outside reviewed correction'
    for name,value in manifest['sources'].items():
        assert sha(WS/name)==value,'Stale source: '+name
    for name,value in manifest['scripts'].items():assert sha(ROOT/'scripts'/name)==value,'Stale build script '+name
    ns={'e':'http://www.efinixinc.com/enf_proj'}
    project=ET.parse(BUILD/'ti60_camera.xml')
    files={str(Path(x.get('name')).relative_to(WS)) for x in project.findall('.//e:design_file',ns)}
    assert files==set(manifest['sources']),'Source list mismatch'
    assert project.find('.//e:top_module',ns).get('name')=='ti60_camera_ppi_top'
    for name,value in manifest['cpu_generated'].items():
        assert sha(BUILD/name)==value,'Stale CPU netlist: '+name
    for name,value in manifest['boot_ram'].items():
        assert sha(BUILD/name)==value,'Stale CPU RAM: '+name
        assert sha(BUILD/'ip/control_soc'/name)==value,'IP RAM differs'
    firmware=json.loads((BUILD/'firmware_manifest.json').read_text(encoding='utf-8'))
    assert sha(BUILD/'firmware_manifest.json')==manifest['firmware_manifest']
    assert firmware['writes_per_style']==1217 and firmware['firmware_bytes']<=32768
    for name,value in firmware['files'].items():
        assert sha(WS/name)==value,'Stale firmware: '+name
    for model in firmware['models']:
        assert sha(WS/'pycode/runs/art6_v2/student'/model['style']/'model.pt')==model['checkpoint_sha256']
    # Reassemble the four byte lanes and compare every actual firmware byte.
    lanes=[]
    for index in range(4):
        path=BUILD/f'EfxSapphireSoc.v_toplevel_system_ramA_logic_ram_symbol{index}.bin'
        lanes.append([int(s,2) for s in path.read_text(encoding='utf-8').split()])
    image=bytes(v for row in zip(*lanes) for v in row)
    binary=(BUILD/'firmware.bin').read_bytes()
    assert image[:len(binary)]==binary,'Boot RAM does not contain firmware'
    assert manifest['dphy_active']['version']=='5.8'
    assert sha(ROOT/'vendor/camera_dphy.sv')==manifest['dphy_active']['sha256']
    mapped=(BUILD/'outflow/ti60_camera.map.v').read_text(encoding='utf-8')
    assert 'pixel_bits_cnt' not in mapped and 'inst_efx_csi2_rx/' not in mapped
    timing_path=BUILD/'outflow/ti60_camera.timing.rpt'
    assert timing_path.stat().st_mtime_ns>(BUILD/'manifest.json').stat().st_mtime_ns
    report=timing_path.read_text(encoding='utf-8')
    assert 'Timing Model: I3' in report
    required={'core_clk':10.,'hdmi_tx_slow_clk':13.468,'hdmi_tx_fast_clk':2.694,
              'sdram_clk':2.5,'rx_cal_clk':2.5,'tx_cal_clk':2.5,'tx_cal_clk_90edge':2.5,
              'i_cam_ck_CLKOUT':14.286}
    for clock,period in required.items():
        assert re.search(r'^\s*'+clock+r'\s+'+f'{period:.3f}'+r'\s',report,re.M),clock
    summary=report.split('---------- 2. Clock Relationship Summary (begin) ----------')[1].split('---------- Clock Relationship Summary (end)')[0]
    a,b=summary.split('Hold (Min) Clock Relationship')
    def rows(text):
        return [(m[1],m[2],float(m[3]),float(m[4])) for m in re.finditer(r'^\s*(\S+)\s+(\S+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+\(R-R\)',text,re.M)]
    setup,hold=rows(a),rows(b)
    assert len(setup)>=22 and len(hold)>=22,'Incomplete timing relationship report'
    assert min(x[3] for x in setup+hold)>=0,'Negative setup/hold slack'
    place=(BUILD/'outflow/ti60_camera.place.out').read_text(encoding='utf-8')
    assert not re.search(r'WARNING.*\[SDC|Unable to run|no vaild startpoints|Failed to run',place),'Ignored timing constraints'
    cdc=json.loads((BUILD/'cdc_constraints.json').read_text(encoding='utf-8'))
    assert len(cdc['gray_paths'])==136 and len(cdc['scalar_first_stages'])==17
    assert len(cdc['bundle_paths'])==14 and len(cdc['dphy_first_stages'])==8
    assert cdc['dphy_proof_sha256']==sha(BUILD/'dphy_cdc_proof.json')
    for filename in ('dphy_cdc_proof.json','dphy_final_proof.json'):
        proof=json.loads((BUILD/filename).read_text(encoding='utf-8'))
        assert proof['map_sha256']==sha(BUILD/'outflow/ti60_camera.map.v')
        assert proof['dphy_sha256']==sha(ROOT/'vendor/camera_dphy.sv')
        assert len(proof['first_stages'])==8
        for item in proof['first_stages']:
            assert item['only_second_stage_endpoint'] and item['interstage_slack_ns']>0
        for name,value in proof['reports'].items():
            assert sha(BUILD/'outflow'/name)==value,'Stale native STA report'
    assert proof['vdb_sha256']==sha(BUILD/'outflow/ti60_camera.vdb')
    sdc=(BUILD/'ti60_camera.sdc').read_text(encoding='utf-8')
    assert not any(x in sdc for x in ('set_clock_groups','set_multicycle_path'))
    assert sdc.count('set_max_delay')==150
    for item in cdc['dphy_first_stages']:
        assert f'set_false_path -to [get_pins {{{item}}}]' in sdc
    # Matching licensed behavioral IP and fault tests; no analog claim.
    simulations={}
    for name in ('sim/ppi_faults/verification.json','sim/dphy_bridge/verification.json',
                 'sim/dphy_full/verification.json','sim/sapphire/verification.json',
                 'sim/runtime/verification.json','sim/top_safety/verification.json','sim/camera_fault_shutdown/verification.json'):
        simulations[name]=receipt(name)
    assert len(simulations['sim/dphy_bridge/verification.json']['cases'])==6
    assert simulations['sim/dphy_full/verification.json']['cases'][0]['pass']
    cpu=BUILD/'ip/control_soc/Testbench/modelsim/control_soc.v'
    assert cpu.read_bytes()==(ROOT/'sim/sapphire/control_soc.v').read_bytes(),'CPU simulation instance differs'
    for name in manifest['boot_ram']:
        assert (BUILD/name).read_bytes()==(ROOT/'sim/sapphire'/name).read_bytes()
    for name in ('camera','format','csi_status','fps','pool','capture_ddr','stream'):
        assert 'PASS' in (ROOT/'build/sim'/(name+'_run.log')).read_text(encoding='utf-8'),name
    for name,value in manifest['unchanged_module_evidence'].items():
        assert sha(WS/name)==value
        assert sha(ROOT/'rtl'/Path(name).name)==value
    board=electrical()
    resources={}
    for label in ('Memory Blocks','DSP Blocks','XLRs'):
        m=re.search(r'^'+label+r': (\d+) / (\d+)',(BUILD/'outflow/ti60_camera.place.rpt').read_text(encoding='utf-8'),re.M)
        assert m,label
        resources[label]=[int(m[1]),int(m[2])]
        assert int(m[1])<=int(m[2])
    bit=BUILD/'outflow/ti60_camera.bit'
    if require_bit:
        assert bit.exists() and bit.stat().st_mtime_ns>timing_path.stat().st_mtime_ns,'Missing current bit'
    inputs=['manifest.json','ti60_camera.xml','ti60_camera.peri.xml','ti60_camera.sdc',
            'cdc_constraints.json','dphy_cdc_proof.json','dphy_final_proof.json',
            'outflow/ti60_camera.map.v','outflow/ti60_camera.vdb',
            'outflow/ti60_camera.timing.rpt','outflow/ti60_camera.pinout.csv']
    return {'result':'PASS','scope':'CAD and behavioral validation; not physical board acceptance',
            'architecture':'D-PHY5.8 public PPI, atomic FIFO, UI-domain CSI RAW10 parser',
            'resources':resources,'setup_min_ns':min(x[3] for x in setup),'hold_min_ns':min(x[3] for x in hold),
            'setup':setup,'hold':hold,'electrical':board,'configuration_sha256':{n:sha(BUILD/n) for n in inputs},
            'simulation_receipts_sha256':{n:sha(ROOT/n) for n in simulations},
            'bitstream_sha256':sha(bit) if require_bit else None,'board_programmed':False,
            'packet_scope':manifest['packet_scope'],
            'not_measured':['physical rails/jumpers','sensor one-packet-per-HS mode compatibility',
                            'Bayer/FPS/brightness','DDR/CNN/HDMI concurrency and actual FPS','real CPU interrupts']}

if __name__=='__main__':
    result=audit()
    (BUILD/'signoff.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PASS camera PPI CAD audit',result['resources'],result['setup_min_ns'],result['hold_min_ns'],result['bitstream_sha256'])
