"""Map real C8 compute RTL for independent Efinity primitive-model regression."""
from pathlib import Path
import sys,xml.etree.ElementTree as ET,json,hashlib,argparse
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'build/probe';sys.path.insert(0,str(Path(__file__).parent));from tool_run import environment,run
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--pointwise',type=Path);args=parser.parse_args()
    B.mkdir(exist_ok=True);ns='http://www.efinixinc.com/enf_proj';tree=ET.parse(ROOT/'build/720p/ti60_camera.xml');tree.getroot().set('name','tiny_probe');info=tree.find('{'+ns+'}design_info');info.find('{'+ns+'}top_module').set('name','tiny_probe')
    for n in list(info):
        if n.tag=='{'+ns+'}design_file':info.remove(n)
    wrapper='''module tiny_probe(input wire clk,reset,start,input wire[23:0]in_rgb,input wire in_valid,output wire in_ready,output wire[23:0]out_rgb,output wire out_valid,input wire out_ready,output wire done,input wire cfg_valid,input wire[15:0]cfg_address,input wire[31:0]cfg_data);
tiny_kernel #(.WIDTH(24),.HEIGHT(40),.FRAME_WIDTH(24)) core(.clk(clk),.reset(reset),.start(start),.origin_x(16'sd0),.in_rgb(in_rgb),.in_valid(in_valid),.in_ready(in_ready),.out_rgb(out_rgb),.out_valid(out_valid),.out_ready(out_ready),.done(done),.cfg_valid(cfg_valid),.cfg_address(cfg_address),.cfg_data(cfg_data));endmodule\n''';(B/'tiny_probe.sv').write_text(wrapper,encoding='utf-8')
    files=[B/'tiny_probe.sv',*[ROOT/'rtl'/n for n in ['style_line_ram.sv','tiny_shared_params.sv','tiny_spatial.sv','tiny_pool.sv','tiny_kernel.sv']],args.pointwise.resolve() if args.pointwise else ROOT/'rtl/tiny_pointwise.sv']
    for path in files:info.insert(1,ET.Element('{'+ns+'}design_file',name=path.as_posix(),version='default',library='default'))
    (B/'inputs.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},indent=2),encoding='utf-8')
    tree.find('{'+ns+'}interface_info').clear();tree.find('{'+ns+'}constraint_info').clear();ET.register_namespace('efx',ns);tree.write(B/'tiny_probe.xml',encoding='utf-8')
    environment();code=run(['E:/software/efinity/python311/bin/python.exe','E:/software/efinity/scripts/efx_run.py','tiny_probe','--prj','--flow','map','--output_dir','outflow'],B,B/'map_console.log');assert code==0
if __name__=='__main__':main()
