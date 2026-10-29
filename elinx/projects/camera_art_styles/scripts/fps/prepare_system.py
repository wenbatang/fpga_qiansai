"""Prepare an independent RF33 C6 / triple-output camera candidate.

No signed source is changed. This script never produces or downloads a bit.
"""
from pathlib import Path
import hashlib,json,shutil,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2];WS=ROOT.parents[2]
BASE=ROOT/'build/camera_720_fast';BUILD=ROOT/'build/camera_fps_rf33_720'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def prepare():
 assert not BUILD.exists(),'Preserve existing candidate'
 folder=ROOT/'rtl/fps'
 # Leave the already measured two-bank DMA experiment untouched.
 text=(folder/'fps_tile_engine.sv').read_text().replace('module fps_tile_engine #(','module fps_tile_engine_3bank #(')
 text=text.replace('input wire output_bank,','input wire[1:0] output_bank,')
 text=text.replace('out_base<=output_bank ? BANK_STRIDE:0;',"out_base<=output_bank==2'd2 ? 30'h00a00000:(output_bank==2'd1 ? BANK_STRIDE:0);")
 assert 'out_base<=output_bank ?' not in text and 'input wire[1:0] output_bank' in text
 (folder/'fps_tile_engine_3bank.sv').write_text(text)
 text=(ROOT/'rtl/p720/video_control_apb_fast.sv').read_text().replace('module video_control_apb_fast','module video_control_apb_fps')
 text=text.replace('WEIGHT_WRITES=1217','WEIGHT_WRITES=365')
 text=text.replace('load_layer==0 ? 2:8','(load_layer==0 || load_layer==4) ? 4:8')
 text=text.replace('(load_layer==4 ? 8:35)','8').replace('(load_layer==4 ? 2:11)','(load_layer==4 ? 2:5)')
 (folder/'video_control_apb_fps.sv').write_text(text)
 text=(ROOT/'rtl/p720/video_system_720.sv').read_text().replace('module video_system_720','module video_system_fps')
 for old,new in [('video_control_apb_fast control','video_control_apb_fps control'),('video_job_control jobs','video_job_control_fps jobs'),
  ('video_tile_engine_async #','fps_tile_engine_3bank #'),('frame_reader #','frame_reader_fps #'),('pixel_fifo_720 pixel_fifo','pixel_fifo_fps pixel_fifo')]:
  assert old in text; text=text.replace(old,new)
 text=text.replace('wire commit_valid,commit_bank,commit_ack,front_bank,front_valid;',
  'wire commit_valid,commit_ack,front_valid,commit_raw,displayed;wire[1:0]commit_bank,front_bank,output_bank;')
 text=text.replace('jobs(.clk(clk),.reset(reset),.start(start),','jobs(.clk(clk),.reset(reset),.start(start),.raw_mode(raw_mode),.output_bank(output_bank),.commit_raw(commit_raw),.displayed(displayed),')
 text=text.replace('.output_bank(commit_bank)', '.output_bank(output_bank)')
 text=text.replace('.fifo_rd_busy(1\'b0)', '.fifo_rd_busy(fifo_rd_busy)')
 text=text.replace('if(completed)front_raw<=engine_raw;', 'if(commit_ack)front_raw<=commit_raw;')
 (folder/'video_system_fps.sv').write_text(text)
 BUILD.mkdir();(BUILD/'rtl').mkdir()
 top=BUILD/'rtl/ti60_camera_ppi_top.sv'
 top.write_text((BASE/'rtl/ti60_camera_ppi_top.sv').read_text().replace('video_system_720 #(','video_system_fps #('))
 m=json.loads((BASE/'manifest.json').read_text())
 for name in ['ddr3_parameter.vh',*m['cpu_generated'],'ip/control_soc/control_soc.v','ip/control_soc/Testbench/modelsim/control_soc.v']:
  dest=BUILD/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(BASE/name,dest)
 shutil.copyfile(BASE/'ti60_camera.peri.xml',BUILD/'ti60_camera.peri.xml')
 ns='http://www.efinixinc.com/enf_proj';tree=ET.parse(BASE/'ti60_camera.xml');info=tree.find('{'+ns+'}design_info')
 replacements={str(BASE/'rtl/ti60_camera_ppi_top.sv'):top,str(BASE/'ip/control_soc/control_soc.v'):BUILD/'ip/control_soc/control_soc.v'}
 for old,new in [('rtl/p720/video_system_720.sv','video_system_fps.sv'),('rtl/p720/video_tile_engine_async.sv','fps_tile_engine_3bank.sv'),
  ('rtl/p720/video_cnn_async.sv','fps_cnn_async.sv'),('rtl/p720/video_cnn_view_pipe.sv','fps_cnn_view.sv'),
  ('rtl/p720/video_cnn_tile5_pipe.sv','fps_cnn5.sv'),('rtl/p720/video_conv3x3_pipe.sv','fps_conv3x3.sv'),
  ('rtl/style_line_ram.sv','fps_line_ram.sv'),('rtl/p720/video_control_apb_fast.sv','video_control_apb_fps.sv'),
  ('rtl/video_job_control.sv','video_job_control_fps.sv'),('rtl/frame_reader.sv','frame_reader_fps.sv'),('rtl/p720/pixel_fifo_720.sv','pixel_fifo_fps.sv')]:
  replacements[str(ROOT/old)]=folder/new
 replaced=set()
 for n in info.findall('{'+ns+'}design_file'):
  key=str(Path(n.get('name')))
  if key in replacements:n.set('name',replacements[key].as_posix());replaced.add(key)
 assert replaced==set(replacements),(set(replacements)-replaced)
 ET.register_namespace('efx',ns);tree.write(BUILD/'ti60_camera.xml',encoding='utf-8')
 (BUILD/'ti60_camera.sdc').write_text('create_clock -name CLK_25M -period 40 [get_ports CLK_25M]\n')
 m['parent_720']={n:sha(BASE/n) for n in ['manifest.json','signoff.json','outflow/ti60_camera.bit']}
 m['sources']={str(Path(n.get('name')).relative_to(WS)):sha(Path(n.get('name'))) for n in info.findall('{'+ns+'}design_file')}
 m['project_xml_sha256']=sha(BUILD/'ti60_camera.xml');m['interface_sha256']=sha(BUILD/'ti60_camera.peri.xml')
 m['status']='UNSIGNED_RF33_C6_CANDIDATE_NO_DOWNLOAD'
 m['fps_candidate']={'channels':6,'dilations':[1,1,2,4,8],'core':640,'halo':16,'cfg_writes':365,'output_bases':[0,0x200000,0xa00000],
  'source_bases':[0x400000,0x600000,0x800000],'user_selected_rf33':True,'hardware_access':False}
 for key in ['p720_tools','firmware_manifest','boot_ram']:
  m.pop(key,None) # New firmware generator must populate these, never reuse old image.
 (BUILD/'manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2))
 print('PREPARED UNSIGNED RF33 C6 / three-output candidate',BUILD)

if __name__=='__main__':prepare()
