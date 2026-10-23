"""Authoritative board contract transcribed from corrected 20261012 V4 PDF.

PDF pages: power 3, USB/J8 4, keys 6/8, DDR 7, flash 9, HDMI 10/13,
camera 11 and oscillators 14. No hardware access or assumptions from filenames.
"""
from pathlib import Path
import csv,hashlib,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];WS=ROOT.parents[2]
PDF=WS/'elinx/elinxdemo/Ti60F225_DemoBoard_v4/TI60F225I3-V4_SCH-20261012（原理图）.pdf'
PDF_SHA='8cf636e4253848cf2bb8a612031bd0fd7e4183a8c59ae7be71b1008aaf669b41'
PN='http://www.efinixinc.com/peri_design_db'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def expected_pins(camera=False):
    expected={}
    def add(signal,pin,direction,bank,voltage):expected[signal]=(pin,direction,bank,voltage)
    # Independently transcribed from V4 schematic PDF pages 3/7/8/9/10.
    for i,(pin,bank) in enumerate([('C4','TL'),('P14','BR'),('N14','BR'),('A3','TL')]):add(f'style_keys_n[{i}]',pin,'Input',bank,'3.3 V')
    add('uart_rx','R4','Input','BL','3.3 V');add('uart_tx','R14','Output','BR','3.3 V')
    add('CLK_25M.P','J2','Input','1A','1.8 V');add('CLK_27M.P','H2','Input','1B','1.8 V')
    for signal,pp,pn in [('clk','H13','H12'),('data0','G15','F15'),('data1','H14','G14'),('data2','G13','F13')]:
        add('tmds_tx_'+signal+'.P',pp,'Output','3A','1.8 V');add('tmds_tx_'+signal+'.N',pn,'Output','3A','1.8 V')
    addresses=[('K15','N','3B'),('L13','N','3B'),('K12','P','3B'),('K6','N','4B'),('L11','P','3B'),('K8','P','4A'),('K10','P','3B'),('J13','N','3B'),('K11','N','3B'),('J14','N','3B'),('H10','P','3B'),('J10','N','3B'),('L12','P','3B'),('J12','N','3B')]
    for i,(pin,leg,bank) in enumerate(addresses):add(f'ddr_addr[{i}].{leg}',pin,'Output',bank,'1.5 V')
    for signal,pin,bank in [('ddr_ba[0].N','L7','4B'),('ddr_ba[1].N','L9','4A'),('ddr_ba[2].P','K14','3B'),('ddr_reset_n.N','H11','3B'),('ddr_cke[0].N','L8','4A'),('ddr_cs_n[0].N','M8','4B'),('ddr_we_n.P','L15','3B'),('ddr_ras_n.P','M14','3B'),('ddr_cas_n.N','M15','3B'),('ddr_odt[0].P','M7','4B'),('ddr_dm[0].P','M9','4A'),('ddr_dm[1].P','R8','4B'),('ddr_ck.P','J15','3B'),('ddr_ck.N','H15','3B')]:add(signal,pin,'Output',bank,'1.5 V')
    dq=[('R9','P'),('M10','N'),('R10','P'),('P9','N'),('P12','N'),('N10','P'),('P10','N'),('P11','P'),('P8','N'),('M6','N'),('R6','P'),('N8','P'),('P6','N'),('N6','P'),('R5','P'),('P5','N')]
    for i,(pin,leg) in enumerate(dq):add(f'ddr_dq[{i}].{leg}',pin,'Bidirectional','4A' if i<8 else '4B','1.5 V')
    for signal,pin,bank in [('ddr_dqs[0].P','R12','4A'),('ddr_dqs[0].N','R11','4A'),('ddr_dqs[1].P','R7','4B'),('ddr_dqs[1].N','P7','4B')]:add(signal,pin,'Bidirectional',bank,'1.5 V')
    add('verf0.P','K7','Input','4A','1.5 V');add('verf1.P','L6','Input','4B','1.5 V')
    if camera:
        add('io_cam_scl','D12','Bidirectional','TR','3.3 V')
        add('io_cam_sda','B14','Bidirectional','TR','3.3 V')
        add('o_cam_rst_p','C12','Output','TR','3.3 V')
        # J4 annotations identify module MD0 at D21, MD1 at D22, MD2 at D20.
        # Net suffix D20 is not camera logical lane zero.
        for name,pp,pn,bank in [('ck','E8','D8','2B'),('d0','B8','A8','2A'),('d1','C8','C9','2B'),('d2','B7','A7','2A'),('d3','B9','A9','2B')]:
            for leg,pin in [('P',pp),('N',pn)]:add(f'cam_{name}.{leg}',pin,'Input',bank,'1.2 V')
    return expected
def audit(folder,camera=False,top=None):
    assert sha(PDF)==PDF_SHA,'Authority PDF changed; re-review required'
    base='ti60_camera' if camera else 'ti60_style'
    records=list(csv.DictReader(x for x in (folder/'outflow'/(base+'.pinout.csv')).read_text(encoding='utf-8').splitlines() if x and not x.startswith('#')))
    active={p['Signal Name']:p for p in records if p['Signal Name']};expected=expected_pins(camera)
    assert set(active)==set(expected),'Unexpected/missing active physical ports'
    assert len(active)==len({p['Pin Number'] for p in active.values()}),'Duplicate physical pin'
    for name,values in expected.items():
        p=active[name];assert tuple(p[k] for k in ['Pin Number','Direction','Bank','I/O Bank Voltage'])==values,'Corrected schematic mismatch: '+name
        if name.startswith(('ddr','verf')):assert 'SSTL' in p['I/O Standard'],name
        if name.startswith(('style_keys_n','uart_','io_cam_','o_cam_rst_p')):assert '3.3' in p['I/O Standard'],name
    assert not [p for p in records if not p['Signal Name'] and p['Direction'] in ('Output','Bidirectional') and p['Function']=='User IO'],'Unused GPIO driver'
    tree=ET.parse(folder/(base+'.peri.xml'))
    banks={'1A':'1.8','1B':'1.8','2A':'1.2','2B':'1.2','3A':'1.8','3B':'1.5','4A':'1.5','4B':'1.5','TL':'3.3','TR':'3.3','BL':'3.3','BR':'3.3'}
    assert {p.get('name'):p.get('iostd').split()[0] for p in tree.findall('.//{'+PN+'}iobank')}==banks,'Board supply/bank mismatch'
    assert all(p.get('is_dyn_voltage')=='false' for p in tree.findall('.//{'+PN+'}iobank'))
    for i,pin in enumerate(['GPIOL_07','GPIOR_22','GPIOR_21','GPIOL_03']):
        p=tree.find('.//{'+PN+'}comp_gpio[@name="style_keys_n['+str(i)+']"]');assert p is not None and p.get('gpio_def')==pin,'Key GPIO mismatch'
        assert p.get('mode')=='input' and p.find('{'+PN+'}input_config') is not None and p.find('{'+PN+'}output_config') is None,'Key must be input'
    assert tree.find('.//{'+PN+'}global_unused_config').get('state')=='input with weak pullup'
    lanes=tree.findall('.//{'+PN+'}mipi_dphy');assert len(lanes)==(5 if camera else 0)
    for p in lanes:assert p.get('ops_type')=='rx','MIPI must not drive sensor lane'
    lvds=tree.findall('.//{'+PN+'}lvds');assert len(lvds)==4
    for p in lvds:
        a=p.find('{'+PN+'}adv_ltx_info');assert p.get('ops_type')=='tx' and a.get('serial_width')=='10' and a.get('is_half_rate')=='true'
    # PCB swaps P/N at the HDMI connector: compensate in RTL, not by renaming pads.
    rtl=(ROOT/'rtl/tmds_efx.sv').read_text()
    for text in ['assign blue=~b','assign green=~g','assign red=~r',"assign clock_word=~10'b1111100000"]:assert text in rtl,'HDMI board polarity compensation missing'
    if camera:
        t=(ROOT/'rtl/ti60_camera_ppi_top.sv').read_text() if top is None else top.read_text()
        for text in ["assign io_cam_scl_OUT=1'b0","assign io_cam_sda_OUT=1'b0",'assign o_cam_rst_p=reset_ui || !sensor_reset_n']:assert text in t,'Camera open drain/reset binding'
    return {'result':'PASS','schematic':str(PDF),'schematic_sha256':PDF_SHA,'active_pins':len(active),'pins':list(active.values()),'banks':banks,'key_pads':['C4','P14','N14','A3'],'key_gpio':['GPIOL_07','GPIOR_22','GPIOR_21','GPIOL_03'],
      'camera_enabled':camera,'hdmi_polarity_compensated':True,'j8_not_uart':True,'script_sha256':sha(Path(__file__)),'scope':'digital configuration vs corrected schematic; no physical rail/current/temperature or board acceptance'}
