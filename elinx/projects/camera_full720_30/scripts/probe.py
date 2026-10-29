"""Map actual full-size operators at small geometry for EFX primitive checking."""
from pathlib import Path
import argparse,hashlib,json,sys,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from tool_run import environment,run


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--dma',action='store_true');a=parser.parse_args()
    build=ROOT/'build'/('probe_dma' if a.dma else 'probe');build.mkdir(parents=True,exist_ok=True)
    top='full_dma_probe' if a.dma else 'full_probe';ns='http://www.efinixinc.com/enf_proj'
    tree=ET.parse(ROOT/'build/720p/ti60_camera.xml');tree.getroot().set('name',top)
    info=tree.find('{'+ns+'}design_info');info.find('{'+ns+'}top_module').set('name',top)
    for node in list(info):
        if node.tag=='{'+ns+'}design_file':info.remove(node)
    if a.dma:
        engine=ROOT/'rtl/p720/video_tile_engine_async.sv'
        text=engine.read_text(encoding='utf-8').replace('module video_tile_engine_async #(','module full_dma_probe #(').replace('WIDTH=1280,HEIGHT=720','WIDTH=128,HEIGHT=24').replace('TILE_CORE=320,HALO=16','TILE_CORE=48,HALO=16')
        wrapper=build/'full_dma_probe.sv';wrapper.write_text(text,encoding='utf-8')
        files=[wrapper,*[ROOT/'rtl/p720'/n for n in ['video_cnn_async.sv','stream_fifo_24.sv']],ROOT/'rtl/reset_sync.sv',ROOT/'vendor/rtl/ddr3_controller/common/efx_fifo_v2.3/efx_fifo_wrapper.v']
        origins=[engine]
    else:
        wrapper=build/'full_probe.sv'
        wrapper.write_text('''module full_probe(input wire clk,reset,start,input wire[23:0]in_rgb,input wire in_valid,output wire in_ready,output wire[23:0]out_rgb,output wire out_valid,input wire out_ready,output wire done,input wire cfg_valid,input wire[15:0]cfg_address,input wire[31:0]cfg_data);
full_kernel #(.WIDTH(24),.HEIGHT(40),.FRAME_WIDTH(24)) core(.clk(clk),.reset(reset),.start(start),.origin_x(16'sd0),.in_rgb(in_rgb),.in_valid(in_valid),.in_ready(in_ready),.out_rgb(out_rgb),.out_valid(out_valid),.out_ready(out_ready),.done(done),.cfg_valid(cfg_valid),.cfg_address(cfg_address),.cfg_data(cfg_data));endmodule
''',encoding='utf-8');files=[wrapper];origins=[]
    files.extend(ROOT/'rtl'/n for n in ['style_line_ram.sv','full_shared_params.sv','full_pointwise.sv','full_dw3x3.sv','full_kernel.sv','full_view.sv'])
    for file in files:info.insert(1,ET.Element('{'+ns+'}design_file',name=file.as_posix(),version='default',library='default'))
    tree.find('{'+ns+'}interface_info').clear();tree.find('{'+ns+'}constraint_info').clear()
    ET.register_namespace('efx',ns);tree.write(build/(top+'.xml'),encoding='utf-8')
    (build/'inputs.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [*origins,*files]},indent=2),encoding='utf-8')
    environment();assert run(['E:/software/efinity/python311/bin/python.exe','E:/software/efinity/scripts/efx_run.py',top,'--prj','--flow','map','--output_dir','outflow'],build,build/'map_console.log')==0


if __name__=='__main__':main()
