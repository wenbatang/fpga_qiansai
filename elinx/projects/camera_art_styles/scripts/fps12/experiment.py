"""Independent unchanged-12ch resource/functional experiment. No board access."""
from pathlib import Path
import argparse,hashlib,json,re,sys,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2];RTL=ROOT/'rtl/fps12';BASE=ROOT/'build/fps12_probe_224';SIM=ROOT/'sim/fps12'
sys.path.insert(0,str(ROOT/'scripts'));from tool_run import run,environment
FILES=[RTL/n for n in ['fps12_cnn5.sv','fps12_conv3x3.sv','fps12_line_ram.sv','fps12_srl_weights.sv']]
Q=Path('E:/softare_FPGA/questasim/root/win64')
def receipt(out,scope,files):
 log=out/'vsim.log';assert 'PASS' in log.read_text(errors='replace') and '** Error:' not in log.read_text(errors='replace')
 (out/'verification.json').write_text(json.dumps({'result':'PASS','scope':scope,'sources_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},'logs_sha256':{str(log):hashlib.sha256(log.read_bytes()).hexdigest()}},indent=2))
def sim(out,top,files):
 out.mkdir(parents=True,exist_ok=True)
 for n,args in [('vlib',['work']),('vlog',['-sv','-timescale','1ns/1ps',*map(str,files)]),('vsim',['-c',top,'-do','run -all; quit -f'])]:
  assert run([str(Q/(n+'.exe')),*args],out,out/(n+'.log'))==0,n
 return out

def functional(core=160,width=128,suffix='runtime'):
 out=SIM/suffix;out.mkdir(parents=True,exist_ok=True)
 tb=(ROOT/'sim/p720/runtime48/tb.sv').read_text().replace('video_tile_engine_pipe','fps12_tile_engine').replace('.TILE_CORE(48)',f'.TILE_CORE({core})')
 if width!=128:
  import numpy as np
  from model_catalog import catalog,integer_network
  y,x=np.indices((24,width));r=(x*7+y*3)&31;g=(x*5+y*11)&63;b=(x*13+y*17)&31
  raw=((r<<11)|(g<<5)|b).astype(np.uint16)
  rgb=np.stack(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)),axis=-1).astype(np.uint8)
  (out/'raw.mem').write_text(''.join(f'{int(v):04x}\n' for v in raw.flat))
  expected=[]
  for meta,layers in catalog()[0]:
   result=integer_network(rgb,layers,False)
   pixels=((result[:,:,0].astype(np.uint16)>>3)<<11)|((result[:,:,1].astype(np.uint16)>>2)<<5)|(result[:,:,2]>>3)
   expected.extend(pixels.flat)
  (out/'expected.mem').write_text(''.join(f'{int(v):04x}\n' for v in expected))
  tb=tb.replace('.WIDTH(128),.HEIGHT(24)',f'.WIDTH({width}),.HEIGHT(24)').replace('12287',str(4*width*24-1)).replace('3071',str(width*24-1)).replace('3072',str(width*24)).replace('8000000','20000000')
  for name in ['raw.mem','expected.mem']:tb=tb.replace((ROOT/'sim/runtime'/name).as_posix(),(out/name).as_posix())
 (out/'tb.sv').write_text(tb)
 files=[out/'tb.sv',RTL/'fps12_tile_engine.sv',RTL/'fps12_cnn_view.sv',*FILES]
 fixtures=[ROOT/'sim/runtime/config.mem',*(out/n if width!=128 else ROOT/'sim/runtime'/n for n in ['raw.mem','expected.mem'])]
 sim(out,'tiles_tb',files);receipt(out,f'Four actual learned models,{width}x24 integer oracle,1217 runtimecfg,{core+64}-wide strip including all banks,rawcopy/fault/backpressure/finalB/mode lock; not whole SoC or physical FPS',files+fixtures)

def map_core(width=224,height=720,frame=1280,suffix=''):
 out=BASE/suffix if suffix else BASE;out.mkdir(parents=True,exist_ok=True);name='fps12_probe'
 text='module fps12_probe(input wire clk,reset,start,input wire signed[15:0]origin_x,input wire[23:0]in_rgb,input wire in_valid,output wire in_ready,output wire[23:0]out_rgb,output wire out_valid,input wire out_ready,output wire done,input wire cfg_valid,input wire[15:0]cfg_address,input wire[31:0]cfg_data);\n'
 text+=f' fps12_cnn5 #(.WIDTH({width}),.HEIGHT({height}),.FRAME_WIDTH({frame})) core(.clk(clk),.reset(reset),.start(start),.style(3\'d0),.origin_x(origin_x),.in_rgb(in_rgb),.in_valid(in_valid),.in_ready(in_ready),.out_rgb(out_rgb),.out_valid(out_valid),.out_ready(out_ready),.done(done),.cfg_valid(cfg_valid),.cfg_address(cfg_address),.cfg_data(cfg_data));\nendmodule\n'
 top=out/(name+'.sv');top.write_text(text)
 ns='http://www.efinixinc.com/enf_proj';tree=ET.parse(ROOT/'build/cnn_bias_fixed_probe/cnn_bias_fixed_probe.xml');root=tree.getroot();root.set('name',name)
 info=root.find('{'+ns+'}design_info');info.find('{'+ns+'}top_module').set('name',name)
 for n in list(info):
  if n.tag=='{'+ns+'}design_file':info.remove(n)
 for p in [top,*FILES]:
  node=ET.Element('{'+ns+'}design_file',name=p.as_posix(),version='default',library='default')
  info.insert(list(info).index(info.find('{'+ns+'}top_vhdl_arch')),node)
 ET.register_namespace('efx',ns);tree.write(out/(name+'.xml'),encoding='utf-8')
 environment();assert run(['E:/software/efinity/python311/bin/python.exe','E:/software/efinity/scripts/efx_run.py',name,'--prj','--flow','map','--output_dir','outflow'],out,out/'map_console.log')==0
 rpt=(out/'outflow'/f'{name}.map.rpt').read_text();mp=(out/'outflow'/f'{name}.map.v').read_text()
 resources={k:int(re.search(r'^'+k+r'\s*:\s*(\d+)',rpt,re.M)[1]) for k in ['EFX_ADD','EFX_LUT4','EFX_DSP48','EFX_FF','EFX_SRL8','EFX_RAM10']}
 v={'scope':'actual map of unchanged12ch standalone core,not whole SoC/pnr/bit','width':width,'height':height,'frame':frame,'resources':resources,'weight_srl_instances':len(re.findall(r'EFX_SRL8\s+\\?\S*weights',mp)),'sources_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [top,*FILES]}}
 (out/'resources.json').write_text(json.dumps(v,indent=2));print(json.dumps(v,indent=2))

def mapped(pattern=False):
 out=SIM/('mapped_pattern' if pattern else 'mapped');out.mkdir(parents=True,exist_ok=True)
 tb=(ROOT/'sim/p720/mapped/tb.sv').read_text().replace('cnn_pipe_probe dut(clk,reset,start,','fps12_probe dut(clk,reset,start,16\'sd0,').replace('video_cnn_tile5_pipe','fps12_cnn5').replace('style<4','style<1')
 tb=tb.replace('config.mem',(ROOT/'sim/runtime/config.mem').as_posix())
 if pattern:
  import numpy as np
  from model_catalog import catalog,integer_network
  y,x=np.indices((40,24));rgb=np.stack(((x*13+y*19)&255,(x*7+y*11)&255,(x*17+y*3)&255),axis=-1).astype(np.uint8)
  expect=integer_network(rgb,catalog()[0][0][1],False)
  for name,pixels in [('input.mem',rgb),('expected.mem',expect)]:
   words=pixels[:,:,0].astype(np.uint32)|(pixels[:,:,1].astype(np.uint32)<<8)|(pixels[:,:,2].astype(np.uint32)<<16)
   (out/name).write_text(''.join(f'{int(v):06x}\n' for v in words.flat))
  marker='reg running=0;'
  tb=tb.replace(marker,marker+'''reg[23:0]image[0:959],expected_pixels[0:959];
always @(negedge clk)begin
 if(running)begin in_rgb=inputs<960?image[inputs]:24'd0;out_ready=t%7!=0;end
 else out_ready=1;
end
''')
  marker=' $readmemh("'+(ROOT/'sim/runtime/config.mem').as_posix()+'",config_words);'
  assert marker in tb
  tb=tb.replace(marker,marker+'\n $readmemh("input.mem",image);$readmemh("expected.mem",expected_pixels);')
  tb=tb.replace('if(mo!==ro)begin','if(mo!==ro || mo!==expected_pixels[outputs])begin')
  tb=tb.replace('  start=1;','  in_rgb=image[0];start=1;')
 (out/'tb.sv').write_text(tb)
 files=[out/'tb.sv',BASE/'small/outflow/fps12_probe.map.v',*FILES,*Path('E:/software/efinity/sim_models/verilog').glob('*.v')]
 sim(out,'tb',files);receipt(out,'Actual mapped SRL weights vs RTL'+(' and independent Python integer reference,nonuniform input plus output stalls' if pattern else ',constant RGB16 input')+',learned vangogh complete24x40,1217runtimecfg; not full SoC',files+([out/'input.mem',out/'expected.mem'] if pattern else []))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['rtl','rtl208','map224','map208','mapsmall','mapped','mapped-pattern']);a=p.parse_args()
 if a.action=='rtl':functional()
 elif a.action=='rtl208':functional(144,384,'runtime208')
 elif a.action=='map224':map_core()
 elif a.action=='map208':map_core(208,720,1280,'w208')
 elif a.action=='mapsmall':map_core(24,40,24,'small')
 elif a.action=='mapped':mapped()
 elif a.action=='mapped-pattern':mapped(True)
