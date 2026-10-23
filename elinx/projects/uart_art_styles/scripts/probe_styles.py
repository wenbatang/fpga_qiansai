"""Actual Ti60 mapping comparison of four and six unchanged twelve-channel models."""
from pathlib import Path
import sys,json,argparse,xml.etree.ElementTree as ET
from catalog import ROOT,WS,weights,SELECTED,ALL,sha,CORE,HALO
from tool_run import run,environment
N='http://www.efinixinc.com/enf_proj'
p=argparse.ArgumentParser();p.add_argument('--count',type=int,choices=[4,6],required=True);a=p.parse_args()
styles=SELECTED if a.count==4 else ALL
folder=ROOT/'build'/f'probe96_{a.count}';folder.mkdir(exist_ok=True);models=weights(folder,styles)
params=','.join(f'.{k}{i}("{(folder/f"{k.lower()}{i}.mem").as_posix()}")' for i in range(5) for k in 'WBS')
(folder/'core.sv').write_text(f'''module core_top(input wire clk,reset,start,input wire[2:0]style,input wire signed[15:0]origin_x,
input wire[23:0]in_rgb,input wire in_valid,output wire in_ready,
output wire[23:0]out_rgb,output wire out_valid,input wire out_ready,output wire done);
style_cnn_tile5 #(.WIDTH({CORE+2*HALO}),.HEIGHT(720),.FRAME_WIDTH(1280),.STYLE_COUNT({a.count}),{params}) dut(.*);
endmodule\n''')
ref=WS/'elinx/elinxdemo/Ti60F225_DemoBoard_v4/17_Ti60F225_uart_demo/17_Ti60F225_uart_demo/top.xml'
tree=ET.parse(ref);r=tree.getroot();r.set('name','core_top');r.set('location',str(folder))
for k in ['last_run_state','last_run_flow','config_result_in_sync','design_ood','place_ood','route_ood']:r.attrib.pop(k,None)
r.find(f'{{{N}}}device_info/{{{N}}}timing_model').set('name','I3')
d=r.find(f'{{{N}}}design_info');d.set('def_veri_version','sv_09');d.find(f'{{{N}}}top_module').set('name','core_top')
for node in list(d.findall(f'{{{N}}}design_file')):d.remove(node)
sources=[ROOT/'rtl/art_conv3x3.sv',ROOT/'rtl/style_line_ram.sv',ROOT/'rtl/style_cnn_tile5.sv',folder/'core.sv']
for i,s in enumerate(sources,1):d.insert(i,ET.Element(f'{{{N}}}design_file',name=s.as_posix(),version='default',library='default'))
c=r.find(f'{{{N}}}constraint_info')
for child in list(c):c.remove(child)
(folder/'core.sdc').write_text('create_clock -name clk -period 10 [get_ports clk]\n')
ET.SubElement(c,f'{{{N}}}sdc_file',name='core.sdc');ET.SubElement(c,f'{{{N}}}inter_file',name='')
for node in r.findall(f'{{{N}}}synthesis/{{{N}}}param'):
 if node.get('name')=='max-bit-blast-mem-size':node.set('value','32768')
 if node.get('name')=='max_threads':node.set('value','4')
ET.register_namespace('efx',N);tree.write(folder/'core_top.xml',encoding='utf-8',xml_declaration=True)
(folder/'scope.json').write_text(json.dumps({'scope':'core map only; no board interface/bit','styles':list(styles),'models':models,
 'sources':{str(s):sha(s) for s in sources},'weights':{p.name:sha(p) for p in folder.glob('*.mem')}},ensure_ascii=False,indent=2),encoding='utf-8')
environment()
raise SystemExit(run(['E:/software/efinity/python311/bin/python.exe','E:/software/efinity/scripts/efx_run.py','core_top','--prj','--flow','map','--output_dir','outflow'],folder,folder/'console.log'))
