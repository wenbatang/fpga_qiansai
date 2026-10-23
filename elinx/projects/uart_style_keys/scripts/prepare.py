"""Create isolated V4 UART/CNN/DDR/HDMI implementation; never program a board."""
from pathlib import Path
import argparse,copy,hashlib,json,re,shutil,sys
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];WS=ROOT.parents[2]
X=WS/'xilinx/projects/uart_style_keys'
REF=WS/'elinx/elinxdemo/Ti60F225_DemoBoard_v4/10_Ti60f225_sc431hai2hdmi_demo/Ti60f225_sc431hai2hdmi_v7/Ti60f225_sc431hai2hdmi_v7'
UART=REF.parents[2]/'17_Ti60F225_uart_demo/17_Ti60F225_uart_demo'
NS='http://www.efinixinc.com/enf_proj';PN='http://www.efinixinc.com/peri_design_db'
sys.path.insert(0,str(WS/'pycode'))
from export_hardware import load_export,pack_taps
import numpy as np
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--profile',choices=('720p','vga'),default='vga');a=parser.parse_args()
    width,height=(1280,720) if a.profile=='720p' else (640,480)
    build=ROOT/'build'/a.profile;build.mkdir(parents=True,exist_ok=True)
    source=ROOT/'rtl';source.mkdir(exist_ok=True);vendor=ROOT/'vendor';vendor.mkdir(exist_ok=True)
    reused={}
    for name in ('uart_8n1.sv','packet_reply.sv','style_keys.sv','style_key_control.sv','style_frame_engine.sv','style_read_arbiter.sv','frame_reader.sv','video_720p.sv','hdmi_encoder.sv','reset_sync.sv','crc32_byte.svh'):
        p=X/'rtl'/name;dst=source/name
        original=p.read_bytes()
        attribute_version=original.replace(b'ASYNC_REG="TRUE"',b'async_reg="true", syn_srlstyle="registers"')
        adapted=attribute_version
        if name=='style_keys.sv':
            adapted=adapted.replace(b'KEY2..KEY5: active low; external 4.7k pull-ups to Bank14 3.3V.',b'V4 KEY0..KEY3: active low, external pull-ups; TL/BR 3.3V.')
            adapted=adapted.replace(b'KEY2 > KEY3 > KEY4 > KEY5.',b'KEY0 > KEY1 > KEY2 > KEY3.')
        if dst.exists() and dst.read_bytes() not in (original,attribute_version,adapted):raise ValueError('Reused RTL differs: '+name)
        if not dst.exists() or dst.read_bytes()!=adapted:dst.write_bytes(adapted)
        reused[p.relative_to(WS).as_posix()]=digest(p)
    # Intentional local fork: Ti60 cannot afford 16KB of FFs for async reads.
    original=(X/'rtl/packet_rx_cobs.sv').read_text()
    packet=original.replace('output wire [7:0] read_data','output reg [7:0] read_data').replace('ram_style="distributed"','ram_style="block"')
    packet=packet.replace('assign read_data=read_address<MAX_BYTES ? memory[read_address] : 0;', 'always @(posedge clk) read_data<=read_address<MAX_BYTES ? memory[read_address] : 0;')
    (source/'packet_rx_cobs.sv').write_text(packet,encoding='utf-8')
    original=(X/'rtl/frame_writer.sv').read_text()
    writer=original.replace('reg [3:0] state;','reg [3:0] state;\n    reg read_phase;')
    writer=writer.replace('state<=IDLE; packet_address<=0;', 'read_phase<=0; state<=IDLE; packet_address<=0;')
    # An address changes at the end of a cycle. A one-cycle wait before every
    # read allows the registered RAM output to match that new address.
    writer=writer.replace('case (state)','if(state==HEADER || state==BEGIN_CRC || state==LOAD) read_phase<=~read_phase;\n            else read_phase<=0;\n            case (state)')
    for state in ('HEADER','BEGIN_CRC','LOAD'):writer=writer.replace(state+': begin',state+': if(read_phase) begin')
    (source/'frame_writer.sv').write_text(writer,encoding='utf-8')
    reused['intentional_packet_fork_original']=digest(X/'rtl/packet_rx_cobs.sv');reused['intentional_writer_fork_original']=digest(X/'rtl/frame_writer.sv')
    design=ET.parse(REF/'ti60f225_oob.xml')
    vendor_files=[]
    for node in design.findall('.//{'+NS+'}design_file'):
        name=node.get('name')
        if name.startswith('rtl/ddr3_controller/') or name in ['rtl/true_dual_port_ram.v','rtl/dual_clock_fifo.v','rtl/user_dual_port_ram.v','rtl/simple_dual_port_ram.v']:
            p=REF/name;dst=vendor/name;dst.parent.mkdir(parents=True,exist_ok=True)
            original=p.read_bytes();adapted=original
            if name.endswith('efx_fifo_wrapper.v'):
                adapted=original.replace(b'(* async_reg = "true" *)',b'(* async_reg = "true", syn_srlstyle = "registers" *)')
            if dst.exists() and dst.read_bytes() not in (original,adapted):raise ValueError('Vendor source changed: '+name)
            if not dst.exists() or dst.read_bytes()!=adapted:dst.write_bytes(adapted)
            vendor_files.append(dst);reused[p.relative_to(WS).as_posix()]=digest(p)
    loaded=[load_export(WS/'pycode/runs/distinct_student_v1/export'/name) for name in ('vangogh','ukiyoe','inkwash','oilpainting')]
    for i in range(5):
        layers=[]
        for meta,network in loaded:
            layer=dict(network[i])
            if i==4 and layer['weights'].shape[0]==1:
                layer['weights']=np.repeat(layer['weights'],3,axis=0);layer['bias']=np.repeat(layer['bias'],3)
            layers.append(layer)
        bits=layers[0]['weights'].shape[0]*layers[0]['weights'].shape[1]*2
        (build/f'w{i}.mem').write_text(''.join(f'{v:0{bits}x}\n' for layer in layers for v in pack_taps(layer['weights'])))
        (build/f'b{i}.mem').write_text(''.join(f'{int(v)&0xffffffff:08x}\n' for layer in layers for v in layer['bias']))
        (build/f's{i}.mem').write_text(''.join(f'{layer["shift"]:02x}\n' for layer in layers))
    params='.DEPTH(5),.COORD_PHASE(4),'+','.join(f'.{k}{i}("{(build/f"{k.lower()}{i}.mem").as_posix()}")' for i in range(5) for k in 'WBS')
    (build/'style_weights.vh').write_text('`define STYLE_WEIGHT_PARAMETERS '+params+'\n')
    # Preserve complete control, DDR ownership, inference, and safe-vblank flow.
    xtop=(X/'rtl/uart_style_top.sv').read_text();body=xtop[xtop.index('    wire [7:0] rx_data'):xtop.index('    xpm_fifo_async #(')]
    video=xtop[xtop.index('    wire hsync,vsync,de;'):xtop.index('    tmds_output display')]
    # CTA VIC 62: keep 74.25MHz; H total 3300, V total 750 => 30Hz.
    # Only the V4 instance overrides the portable module's 60Hz default.
    video=video.replace('video_720p #(', 'video_720p #(.H_FRONT(1760),')
    phy_ports=(REF/'rtl/ddr3_controller/ddr3_top.v').read_text()
    ports=phy_ports[phy_ports.index('output          [2:0]'):phy_ports.index('input                           app_sr_req')].strip()
    ports=ports.replace('CKE_WIDTH','1').replace('ROW_WIDTH','14').replace('BANK_WIDTH','3').replace('CS_WIDTH*RANK_RATIO','1').replace('DQS_WIDTH','2').replace('DQ_WIDTH','16').replace('DM_WIDTH','2').replace('ODT_WIDTH','1')
    ports=re.sub(r'//[^\n]*','',ports)
    head=f'''`include "style_weights.vh"
module ti60_style_top #(parameter integer PROC_WIDTH={width},PROC_HEIGHT={height},UART_BAUD=2000000,UART_PAYLOAD_BYTES=16384)
(input wire CLK_25M,CLK_27M,core_clk,hdmi_tx_slow_clk,
 input wire sdram_clk,rx_cal_clk,tx_cal_clk,tx_cal_clk_90edge,pll_locked,user_pll_locked,core_pll_locked,
 input wire [3:0] style_keys_n,input wire uart_rx,output wire uart_tx,
 output wire DDR3_PLL_RSTN,USER_PLL_RSTN,CORE_PLL_RSTN,
 output wire [9:0] tmds_tx_clk_TX_DATA,tmds_tx_data0_TX_DATA,tmds_tx_data1_TX_DATA,tmds_tx_data2_TX_DATA,
 output wire tmds_tx_clk_TX_RST,tmds_tx_data0_TX_RST,tmds_tx_data1_TX_RST,tmds_tx_data2_TX_RST,
 output wire tmds_tx_clk_TX_OE,tmds_tx_data0_TX_OE,tmds_tx_data1_TX_OE,tmds_tx_data2_TX_OE,
 {ports.rstrip(',')});
 wire ui_clk=core_clk,pixel_clk=hdmi_tx_slow_clk;
 wire sys_rst_n,reset_ui,reset_pixel,ddr_reset,calibrated;
 board_boot boot(.clk(CLK_25M),.keys_n(style_keys_n),.reset_n(sys_rst_n));
 assign DDR3_PLL_RSTN=sys_rst_n;assign USER_PLL_RSTN=sys_rst_n;assign CORE_PLL_RSTN=sys_rst_n;
 reset_sync ddr_rst(.clk(ui_clk),.async_reset(!sys_rst_n || !pll_locked || !core_pll_locked),.reset(ddr_reset));
 reset_sync rst_ui(.clk(ui_clk),.async_reset(ddr_reset || !calibrated),.reset(reset_ui));
 reset_sync rst_pixel(.clk(pixel_clk),.async_reset(!sys_rst_n || !user_pll_locked || !calibrated),.reset(reset_pixel));
'''
    fifo='''pixel_fifo_efx pixel_fifo(.rst(reset_ui || fifo_reset),.wr_clk(ui_clk),.rd_clk(pixel_clk),.din(fifo_data),
 .wr_en(fifo_write),.rd_en(fifo_read),.dout(fifo_pixel),.full(fifo_full),.empty(fifo_empty),
 .wr_rst_busy(fifo_wr_busy),.rd_rst_busy(fifo_rd_busy),.wr_data_count(fifo_word_count));
'''
    tmds='''tmds_efx display(.clk(pixel_clk),.reset(reset_pixel),.rgb(rgb),.de(de),.hsync(hsync),.vsync(vsync),
 .blue(tmds_tx_data0_TX_DATA),.green(tmds_tx_data1_TX_DATA),.red(tmds_tx_data2_TX_DATA),.clock_word(tmds_tx_clk_TX_DATA));
assign tmds_tx_clk_TX_RST=reset_pixel;assign tmds_tx_data0_TX_RST=reset_pixel;
assign tmds_tx_data1_TX_RST=reset_pixel;assign tmds_tx_data2_TX_RST=reset_pixel;
assign tmds_tx_clk_TX_OE=1'b1;assign tmds_tx_data0_TX_OE=1'b1;
assign tmds_tx_data1_TX_OE=1'b1;assign tmds_tx_data2_TX_OE=1'b1;
'''
    rt=(REF/'rtl/ti60f225_oob_top.v').read_text(encoding='utf-8',errors='replace');ddr=rt[rt.index('ddr3_top                 u_ddr3_top'):];ddr=ddr[:ddr.index(');')+2]
    ddr=ddr.replace('(core_clk','(ui_clk').replace('w_arstn','!ddr_reset')
    # AXI byte addresses and exact beat geometry match the Xilinx generic core.
    start=ddr.index('.s_axi_awid');ddr=re.sub(r'\.cal_done\s*\([^)]*\)\s*,?','',ddr[:start])+''' .s_axi_awid(4'd0),.s_axi_awaddr({2'b0,awaddr}),.s_axi_awlen(8'd0),.s_axi_awsize(3'd4),.s_axi_awburst(2'd1),
 .s_axi_awlock(1'b0),.s_axi_awcache(4'b0011),.s_axi_awprot(3'd0),.s_axi_awqos(4'd0),.s_axi_awvalid(awvalid),.s_axi_awready(awready),
 .s_axi_wdata(wdata),.s_axi_wstrb(16'hffff),.s_axi_wlast(1'b1),.s_axi_wvalid(wvalid),.s_axi_wready(wready),
 .s_axi_bid(),.s_axi_bresp(bresp),.s_axi_bvalid(bvalid),.s_axi_bready(bready),
 .s_axi_arid(4'd0),.s_axi_araddr({2'b0,araddr}),.s_axi_arlen(8'd15),.s_axi_arsize(3'd4),.s_axi_arburst(2'd1),
 .s_axi_arlock(1'b0),.s_axi_arcache(4'b0011),.s_axi_arprot(3'd0),.s_axi_arqos(4'd0),.s_axi_arvalid(arvalid),.s_axi_arready(arready),
 .s_axi_rid(),.s_axi_rdata(rdata),.s_axi_rresp(rresp),.s_axi_rlast(rlast),.s_axi_rvalid(rvalid),.s_axi_rready(rready),
 .cal_done(calibrated));\n'''
    (source/'ti60_style_top.sv').write_text(head+body+fifo+video+tmds+ddr+'endmodule\n',encoding='utf-8')
    peri=ET.parse(REF/'ti60f225_oob.peri.xml');pt=peri.getroot();pt.set('name','ti60_style')
    gpio=pt.find('{'+PN+'}gpio_info')
    for n in list(gpio):
        if n.tag.endswith('comp_gpio') and not n.get('name','').startswith(('ddr','verf','CLK_25M','CLK_27M')):gpio.remove(n)
        elif n.tag.endswith('bus') and not n.get('name','').startswith('ddr'):gpio.remove(n)
        elif n.tag.endswith('comp_gpio') and n.get('name') in ('ddr_addr[14]','ddr_addr[15]'):gpio.remove(n)
        elif n.tag.endswith('bus') and n.get('name')=='ddr_addr':n.set('msb','13')
    u=ET.parse(UART/'top.peri.xml')
    for old,new in [('rxd','uart_rx'),('txd','uart_tx')]:
        node=copy.deepcopy(u.find('.//{'+PN+'}comp_gpio[@name="'+old+'"]'));node.set('name',new)
        for child in node:
            child.set('name',new);child.set('clock_name','')
            if new=='uart_rx':child.set('is_register','false')
            else:child.set('register_option','none')
        gpio.append(node)
    base=copy.deepcopy(ET.parse(REF/'ti60f225_oob.peri.xml').find('.//{'+PN+'}comp_gpio[@name="i_arstn"]'))
    for i,pin in enumerate(['GPIOL_07','GPIOR_22','GPIOR_21','GPIOL_03']):
        node=copy.deepcopy(base);node.set('name',f'style_keys_n[{i}]');node.set('bus_name','style_keys_n');node.set('gpio_def',pin)
        for child in node:child.set('name',f'style_keys_n[{i}]')
        gpio.append(node)
    ET.SubElement(gpio,'{'+PN+'}bus',name='style_keys_n',mode='input',msb='3',lsb='0')
    for node in list(gpio.findall('{'+PN+'}global_unused_config')):
        gpio.remove(node);gpio.append(node)
    for node in list(gpio.findall('{'+PN+'}bus')):
        gpio.remove(node);gpio.append(node) # XSD: every comp_gpio precedes buses
    plls=pt.find('{'+PN+'}pll_info')
    for node in list(plls):
        if node.get('name') not in ('DDR3_PLL','USER_PLL','MIPI_TX_PLL'):plls.remove(node)
        elif node.get('name')=='DDR3_PLL':
            node.find('{'+PN+'}comp_output_clock[@name="clk_100m"]').set('conn_type','rclk')
        elif node.get('name')=='MIPI_TX_PLL':
            node.set('name','CORE_PLL');node.set('reset_name','CORE_PLL_RSTN');node.set('locked_name','core_pll_locked')
            for clock in list(node.findall('{'+PN+'}comp_output_clock')):
                if clock.get('name')!='core_clk':node.remove(clock)
        elif node.get('name')=='USER_PLL':
            node.set('multiplier','2') # 2.970GHz VCO, within installed device limits
            for clock in list(node.findall('{'+PN+'}comp_output_clock')):
                if clock.get('name')=='vid_clk_dvi2':node.remove(clock)
                elif clock.get('name')=='hdmi_tx_slow_clk':clock.set('out_divider','40')
                elif clock.get('name')=='hdmi_tx_fast_clk':clock.set('out_divider','8')
    for tag in ('mipi_dphy_info','jtag_info'):
        node=pt.find('{'+PN+'}'+tag)
        if node is not None:
            for child in list(node):node.remove(child) # API requires empty registry
    lvds=pt.find('{'+PN+'}lvds_info')
    for node in list(lvds):
        if not node.get('name','').startswith('tmds_tx'):lvds.remove(node)
    ET.register_namespace('efxpt',PN);peri.write(build/'ti60_style.peri.xml',encoding='utf-8',xml_declaration=True)
    from lxml import etree as LE
    schema=LE.XMLSchema(LE.parse('E:/software/efinity/pt/bin/schema/peri_design_db.xsd'))
    schema.assertValid(LE.parse(str(build/'ti60_style.peri.xml')))
    tree=design.getroot();tree.set('name','ti60_style');tree.set('location',build.as_posix())
    info=tree.find('{'+NS+'}design_info');info.find('{'+NS+'}top_module').set('name','ti60_style_top')
    for n in list(info.findall('{'+NS+'}design_file')):info.remove(n)
    files=[*sorted(source.glob('*.sv')),*sorted((WS/'common/rtl').glob('style_*.sv')),*vendor_files]
    for index,p in enumerate(files,1):info.insert(index,ET.Element('{'+NS+'}design_file',name=p.as_posix(),version='default',library='default'))
    for n in tree.find('{'+NS+'}interface_info'):n.set('name','ti60_style.peri.xml')
    constraints=tree.find('{'+NS+'}constraint_info')
    for n in list(constraints):constraints.remove(n)
    ET.SubElement(constraints,'{'+NS+'}sdc_file',name='ti60_style.sdc');ET.SubElement(constraints,'{'+NS+'}inter_file',name='')
    for n in tree.find('{'+NS+'}synthesis'):
        if n.get('name')=='max-bit-blast-mem-size':n.set('value','32768')
    for section in ('synthesis','place_and_route'):
        for node in tree.find('{'+NS+'}'+section):
            if node.get('name')=='max_threads':node.set('value','4')
    # Includes resolve from this isolated tool cwd; no undocumented map option.
    shutil.copyfile(source/'crc32_byte.svh',build/'crc32_byte.svh')
    shutil.copyfile(vendor/'rtl/ddr3_controller/ddr3_parameter.vh',build/'ddr3_parameter.vh')
    for n in tree.find('{'+NS+'}debugger'):
        if n.get('name')=='auto_instantiation':n.set('value','off')
    # No old CSI/JTAG paths. Interface tool generates current DDR/LVDS pin timing.
    (build/'ti60_style.sdc').write_text('create_clock -name CLK_25M -period 40 [get_ports CLK_25M]\ncreate_clock -name CLK_27M -period 37.037037 [get_ports CLK_27M]\n',encoding='utf-8')
    ET.register_namespace('efx',NS);design.write(build/'ti60_style.xml',encoding='utf-8',xml_declaration=True)
    manifest={'profile':a.profile,'size':[width,height],'scope':'V4 UART/DDR/CNN/HDMI attempt; not yet hardware verified',
        'display':{'mode':'720p30','active':[1280,720],'totals':[3300,750],'horizontal':[1280,1760,40,220],'vertical':[720,5,5,20],'pixel_hz':74250000,'serial_hz':371250000,'refresh_hz':30,'placement':'centered, no scaling'},
        'sources':{str(p.relative_to(WS)):digest(p) for p in files},'reused':reused,'models':[m for m,_ in loaded],
        'weights':{p.name:digest(p) for p in build.glob('*.mem')},'schema_source':digest(REF/'ti60f225_oob.peri.xml')}
    (build/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Prepared',build,'source files',len(files),'128bit AXI, four real models')
if __name__=='__main__':main()
