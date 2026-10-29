"""Synthesize the independent C6 candidate core, never program hardware."""
from pathlib import Path
import argparse,hashlib,json,sys,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'));from tool_run import environment,run
p=argparse.ArgumentParser();p.add_argument('--width',type=int,default=672);p.add_argument('--height',type=int,default=720);args=p.parse_args()
name='fps_core_probe';out=ROOT/f'build/fps_probe_{args.width}_{args.height}';out.mkdir(exist_ok=True)
top=out/(name+'.sv')
top.write_text('''module fps_core_probe(input wire clk,reset,start,input wire signed[15:0]origin,
 input wire[23:0]in_rgb,input wire in_valid,output wire in_ready,
 output wire[23:0]out_rgb,output wire out_valid,input wire out_ready,output wire done,
 input wire cfg_valid,input wire[15:0]cfg_address,input wire[31:0]cfg_data);
 fps_cnn5 #(.WIDTH(@W@),.HEIGHT(@H@),.FRAME_WIDTH(1280)) core(
 .clk(clk),.reset(reset),.start(start),.style(3'd0),.origin_x(origin),
 .in_rgb(in_rgb),.in_valid(in_valid),.in_ready(in_ready),.out_rgb(out_rgb),.out_valid(out_valid),.out_ready(out_ready),.done(done),
 .cfg_valid(cfg_valid),.cfg_address(cfg_address),.cfg_data(cfg_data));endmodule
'''.replace('@W@',str(args.width)).replace('@H@',str(args.height)))
ns='http://www.efinixinc.com/enf_proj';tree=ET.parse(ROOT/'build/cnn_pipe_probe/cnn_pipe_probe.xml');prj=tree.getroot();prj.set('name',name)
info=tree.find('{'+ns+'}design_info');info.find('{'+ns+'}top_module').set('name',name)
for n in list(info):
 if n.tag=='{'+ns+'}design_file':info.remove(n)
files=[top,*[ROOT/'rtl/fps'/n for n in ['fps_cnn5.sv','fps_conv3x3.sv','fps_line_ram.sv']]]
for index,f in enumerate(files):info.insert(index+1,ET.Element('{'+ns+'}design_file',{'name':f.as_posix(),'version':'default','library':'default'}))
for n in tree.findall('.//{'+ns+'}sdc_file'):n.set('name',name+'.sdc')
ET.register_namespace('efx',ns);tree.write(out/(name+'.xml'),encoding='utf-8')
(out/(name+'.sdc')).write_text('create_clock -name clk -period 6 [get_ports clk]\n')
sha=lambda x:hashlib.sha256(x.read_bytes()).hexdigest()
(out/'manifest.json').write_text(json.dumps({'status':'EXPERIMENT_NOT_A_BITSTREAM','geometry':[args.width,args.height],'rf':33,'channels':6,'lanes':[6,6,6,6,3],'sources_sha256':{str(f):sha(f) for f in [Path(__file__),*files]}},indent=2))
environment()
assert run(['E:/software/efinity/python311/bin/python.exe','E:/software/efinity/scripts/efx_run.py',name,'--prj','--flow','map','--output_dir','outflow'],out,out/'map_console.log')==0
text=(out/'outflow'/(name+'.map.out')).read_text(encoding='utf-8')
import re
counts={kind:int(re.search(r'^INFO\s*:\s*'+kind+r'\s*:\s*(\d+)',text,re.M)[1]) for kind in ['EFX_RAM10','EFX_DSP48']}
(out/'map_resources.json').write_text(json.dumps({'result':'PASS','scope':'Actual core synthesis resource mapping only; not whole-system placement, timing, trained-model acceptance, FPS or downloadable bit','resources':counts,'map_sha256':sha(out/'outflow'/(name+'.map.v'))},indent=2))
print('MAPPED EXPERIMENTAL CORE',counts)
