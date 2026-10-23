"""Check routed ports against the visually reviewed BaseC FMC schematic (p2,4-7)."""
from pathlib import Path
import csv
import argparse
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent


def expected_ports():
    ports = {}
    def add(name, pads, bank, direction, standard):
        for i, pad in enumerate(pads.split()):
            port = f"{name}[{i}]" if '[' not in name and len(pads.split()) > 1 else name
            ports[port] = (pad, str(bank), direction, standard)
    # Schematic p4: DDR net labels at U1F/U1G. p5: two x16 components.
    add('ddr3_dq', 'AF14 AF17 AE15 AE17 AD16 AF20 AD15 AF19 AB15 AC14 AA18 AA14 AB16 AB14 AA17 AD14 AD19 AC19 AD18 AA19 AC17 AA20 AC18 AB17 Y17 V16 V17 W14 V18 W15 V19 W16', 32, 'INOUT', 'SSTL15_T_DCI')
    add('ddr3_dm', 'AF15 AA15 AB19 V14', 32, 'OUT', 'SSTL15')
    add('ddr3_dqs_p', 'AE18 Y15 AD20 W18', 32, 'INOUT', 'DIFF_SSTL15_T_DCI')
    add('ddr3_dqs_n', 'AF18 Y16 AE20 W19', 32, 'INOUT', 'DIFF_SSTL15_T_DCI')
    add('ddr3_addr', 'AF8 AB10 V9 Y7 AC9 W8 Y11 V8 AA8 AC11 AD9 AA10 AF9 V7 Y8', 33, 'OUT', 'SSTL15')
    add('ddr3_ba', 'AA7 AB11 AF7', 33, 'OUT', 'SSTL15')
    for name, pad in {'ras_n':'AD8','cas_n':'W10','we_n':'W9','reset_n':'Y10',
                     'ck_p[0]':'AA9','ck_n[0]':'AB9','cke[0]':'AF10','cs_n[0]':'AB7','odt[0]':'AC8'}.items():
        standard = 'DIFF_SSTL15' if name.startswith('ck_') else ('LVCMOS15' if name=='reset_n' else 'SSTL15')
        add('ddr3_'+name, pad, 33, 'OUT', standard)
    # p4/p6: CH340E TXD -> FPGA B20 input; FPGA C22 output -> CH340E RXD.
    for name,pad in {'sys_clk':'G22','sys_rst_n':'D26','uart_rx':'B20','uart_tx':'C22','tmds_out_en':'E22'}.items():
        add(name,pad,14,'IN' if name in ('sys_clk','sys_rst_n','uart_rx') else 'OUT','LVCMOS33')
    add('tmds_clk_p','F17',15,'OUT','TMDS_33')
    add('tmds_clk_n','E17',15,'OUT','TMDS_33')
    add('tmds_data_p','J15 E15 G17',15,'OUT','TMDS_33')
    add('tmds_data_n','J16 E16 F18',15,'OUT','TMDS_33')
    return ports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-dir', type=Path, default=ROOT/'vivado')
    project = parser.parse_args().project_dir
    expected = expected_ports()
    root = ET.parse(ROOT/'ip/mig.prj').getroot()
    for tag,value in {'VccAuxIO':'1.8V','TimePeriod':'2500','InputClkFreq':'200','InternalVref':'0',
                      'mrCasLatency':'6','mr2CasWriteLatency':'5'}.items():
        assert root.findtext(f'.//{tag}')==value, (tag,root.findtext(f'.//{tag}'))
    mig = {p.get('name'):p.get('PADName') for p in root.findall('.//PinSelection/Pin')}
    assert mig == {n:v[0] for n,v in expected.items() if n.startswith('ddr3_')}, 'MIG pin map differs from schematic'
    with (project/'pin_audit.tsv').open(encoding='utf-8',newline='') as stream:
        actual = {r['port']:r for r in csv.DictReader(stream,delimiter='\t')}
    assert actual.keys()==expected.keys(), ('Unexpected/missing ports',actual.keys()^expected.keys())
    for name,(pad,bank,direction,standard) in expected.items():
        p=actual[name]
        assert (p['package_pin'],p['bank'],p['direction'],p['iostandard'])==(pad,bank,direction,standard), (name,p,expected[name])
        if name.startswith('ddr3_'):
            assert p['vccaux_io']=='NORMAL', (name,p)
    assert len({v[0] for v in expected.values()})==len(expected), 'Pin collision'
    with (project/'clocks.tsv').open(encoding='utf-8',newline='') as stream:
        clocks = {r['clock']:float(r['period_ns']) for r in csv.DictReader(stream,delimiter='\t')}
    for name, period in {'clk_out1_uart_ddr_clocks':5.0,'mem_refclk':2.5,'clk_pll_i':10.0,
                         'pixel_raw':1000/74.25,'serial_raw':1000/371.25}.items():
        assert name in clocks and abs(clocks[name]-period)<0.001, (name,clocks.get(name),period)
    print(f'PASS board audit: {len(expected)} routed ports match BaseC FMC schematic; Bank14/15=3.3V, Bank32/33=1.5V; VCCAUX_IO NORMAL/1.8V; external VREF, DDR3-800.')
    print('PASS clocks: 200 MHz reference, 400 MHz DDR, 100 MHz UI, 74.25/371.25 MHz HDMI')


if __name__=='__main__':
    main()
