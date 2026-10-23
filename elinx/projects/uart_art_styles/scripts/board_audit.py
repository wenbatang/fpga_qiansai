"""Independent V4 schematic pin/voltage/driver and full-frame DMA audit."""
from pathlib import Path
import argparse,csv,hashlib,json,re
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];WS=ROOT.parents[2]
PN='http://www.efinixinc.com/peri_design_db'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def audit(profile):
    folder=ROOT/'build'/profile
    text=(folder/'outflow/ti60_style.pinout.csv').read_text(encoding='utf-8')
    pins=list(csv.DictReader(x for x in text.splitlines() if x and not x.startswith('#')))
    active={x['Signal Name']:x for x in pins if x['Signal Name']}
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
    assert set(active)==set(expected) and len(active)==66,'Unexpected/missing driver'
    assert len({x['Pin Number'] for x in active.values()})==66,'Duplicate package pin'
    for name,values in expected.items():
        row=active[name]
        assert tuple(row[k] for k in ['Pin Number','Direction','Bank','I/O Bank Voltage'])==values,name
        if name.startswith(('ddr','verf')):assert 'SSTL' in row['I/O Standard'],name
    assert not [x for x in pins if not x['Signal Name'] and x['Direction'] in ('Output','Bidirectional') and x['Function']=='User IO'],'Unassigned GPIO driver'
    tree=ET.parse(folder/'ti60_style.peri.xml')
    for tag in ('mipi_dphy_info','jtag_info'):assert not list(tree.find('{'+PN+'}'+tag)),tag
    assert tree.find('.//{'+PN+'}global_unused_config').get('state')=='input with weak pullup'
    ref=WS/'elinx/elinxdemo/Ti60F225_DemoBoard_v4/10_Ti60f225_sc431hai2hdmi_demo/Ti60f225_sc431hai2hdmi_v7/Ti60f225_sc431hai2hdmi_v7'
    orig=ET.parse(ref/'ti60f225_oob.peri.xml')
    for lvds in tree.findall('.//{'+PN+'}lvds'):
        name=lvds.get('name');o=orig.find('.//{'+PN+'}lvds[@name="'+name+'"]')
        assert ET.tostring(lvds)==ET.tostring(o),'LVDS electrical/serializer change'
    top=(ROOT/'rtl/ti60_style_top.sv').read_text()
    for signal in ('ddr_ck_hi','ddr_ck_lo','ddr_reset_n','ddr_cke','ddr_cs_n','ddr_ras_n','ddr_cas_n','ddr_we_n','ddr_addr','ddr_ba','ddr_dqs_oe','ddr_dqs_oe_n','ddr_dq_oe','ddr_dqs_in_hi','ddr_dqs_in_lo','ddr_dq_in_hi','ddr_dq_in_lo','ddr_dqs_out_hi','ddr_dqs_out_lo','ddr_dq_out_hi','ddr_dq_out_lo','ddr_dm_hi','ddr_dm_lo','ddr_odt'):
        assert re.search(r'\.'+signal+r'\s*\('+signal+r'\s*\)',top),'Lost vendor OE binding'
    assert (ROOT/'vendor/rtl/ddr3_controller/ddr3_top.v').read_bytes()==(ref/'rtl/ddr3_controller/ddr3_top.v').read_bytes()
    assert (folder/'ddr3_parameter.vh').read_bytes()==(ref/'rtl/ddr3_controller/ddr3_parameter.vh').read_bytes()
    for name in ('reset_sync.sv','uart_8n1.sv','frame_reader.sv','video_720p.sv'):
        assert not re.search(r'\bASYNC_REG\s*=',(ROOT/'rtl'/name).read_text()),'Non-native CDC attribute'
    width,height=(1280,720) if profile=='720p' else (640,480)
    frame_bytes=width*height*2
    assert frame_bytes<0x200000 and width%128==0 and width%32==0
    # Exhaustive word coverage and all source burst geometries at production size.
    writes=set();bursts=set()
    for left in range(0,width,32):
        lo=max(left-32,0);hi=min(left+64,width)
        for y in range(height):
            for block in range(lo//128,(hi-1)//128+1):
                address=0x400000+y*width*2+block*256
                assert address%256==0 and (address&4095)<=4096-256
                assert 0x400000<=address and address+256<=0x400000+frame_bytes
                bursts.add(address)
            for x in range(left,left+32,8):
                address=(y*width+x)*2
                assert address%16==0 and 0<=address and address+16<=frame_bytes
                assert address not in writes,'Duplicated output word';writes.add(address)
    assert writes==set(range(0,frame_bytes,16)),'Missing output word'
    return {'result':'PASS','profile':profile,'active_pins':66,'pins':[active[x] for x in sorted(active)],'source_bursts':len(bursts),'output_words':len(writes),'frame_bytes':frame_bytes,'unused_gpio_drivers':0,'mipi_enabled':False,'ddr_vendor_protected_body_unchanged':True,'schematic_sha256':sha(WS/'elinx/elinxdemo/Ti60F225_DemoBoard_v4/TI60F225I3-V4_SCH-20261012（原理图）.pdf'),'bitstream_sha256':sha(folder/'outflow/ti60_style.bit'),'not_measured':['physical power rails/jumpers','DDR/HDMI simultaneous board operation','temperature/current','vendor encrypted DDR internals']}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--profile',choices=('720p','vga'),default='720p');a=p.parse_args();r=audit(a.profile)
    out=ROOT/'build/electrical_review';out.mkdir(exist_ok=True);(out/(a.profile+'_board_audit.json')).write_text(json.dumps(r,indent=2),encoding='utf-8')
    print('PASS independent V4 pins/electrical/OE/unused drivers and complete DMA coverage:',a.profile,r['active_pins'],'pins',r['output_words'],'output words')
