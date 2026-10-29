"""Keep failed FF build intact; fork an independent sequential-SRL RF33 build."""
from pathlib import Path
import hashlib,json,shutil,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2];WS=ROOT.parents[2]
OLD=ROOT/'build/camera_fps_rf33_720';NEW=ROOT/'build/camera_fps_rf33_srl_720'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
 assert not NEW.exists(),'Preserve candidate and failed reports'
 folder=ROOT/'rtl/fps'
 for name in ['fps_cnn5_srl.sv','fps_conv3x3_srl.sv','fps_srl_weights.sv']:assert (folder/name).exists(),name
 names=[('fps_cnn_view.sv','fps_cnn_view_srl.sv',[('fps_cnn_view','fps_cnn_view_srl'),('fps_cnn5 #','fps_cnn5_srl #')]),
  ('fps_cnn_async.sv','fps_cnn_async_srl.sv',[('fps_cnn_async','fps_cnn_async_srl'),('fps_cnn_view #','fps_cnn_view_srl #')]),
  ('fps_tile_engine_3bank.sv','fps_tile_engine_3bank_srl.sv',[('fps_tile_engine_3bank','fps_tile_engine_3bank_srl'),('fps_cnn_async #','fps_cnn_async_srl #')]),
  ('video_system_fps.sv','video_system_fps_srl.sv',[('module video_system_fps','module video_system_fps_srl'),('fps_tile_engine_3bank #','fps_tile_engine_3bank_srl #')])]
 for old,new,replacements in names:
  text=(folder/old).read_text()
  for a,b in replacements:assert a in text,a;text=text.replace(a,b)
  (folder/new).write_text(text)
 NEW.mkdir();m=json.loads((OLD/'manifest.json').read_text())
 files=['ddr3_parameter.vh','ti60_camera.peri.xml','camera_mode.h','style_catalog.h','config.mem',
  'firmware.bin','firmware.elf','firmware.hex','firmware_manifest.json',*m['cpu_generated'],*m['boot_ram'],
  'ip/control_soc/control_soc.v','ip/control_soc/Testbench/modelsim/control_soc.v']
 files+=[str(p.relative_to(OLD)) for p in (OLD/'firmware').glob('*')]
 files+=[str(p.relative_to(OLD)) for p in (OLD/'ip/control_soc').glob('*.bin')]
 files+=[str(p.relative_to(OLD)) for p in (OLD/'ip/control_soc/Testbench/modelsim').glob('*.bin')]
 for name in set(files):
  target=NEW/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(OLD/name,target)
 fw=json.loads((NEW/'firmware_manifest.json').read_text())
 old_rel=str(OLD.relative_to(WS));new_rel=str(NEW.relative_to(WS))
 fw['files']={k.replace(old_rel,new_rel):v for k,v in fw['files'].items()}
 (NEW/'firmware_manifest.json').write_text(json.dumps(fw,ensure_ascii=False,indent=2))
 top=NEW/'rtl/ti60_camera_ppi_top.sv';top.parent.mkdir()
 top.write_text((OLD/'rtl/ti60_camera_ppi_top.sv').read_text().replace('video_system_fps #(','video_system_fps_srl #('))
 ns='http://www.efinixinc.com/enf_proj';tree=ET.parse(OLD/'ti60_camera.xml');info=tree.find('{'+ns+'}design_info')
 replacements={str(folder/a):folder/b for a,b,_ in names}
 replacements.update({str(folder/'fps_cnn5.sv'):folder/'fps_cnn5_srl.sv',str(folder/'fps_conv3x3.sv'):folder/'fps_conv3x3_srl.sv'})
 for n in info.findall('{'+ns+'}design_file'):
  p=Path(n.get('name'));key=str(p)
  if key in replacements:p=replacements[key]
  elif p.is_relative_to(OLD):p=NEW/p.relative_to(OLD)
  n.set('name',p.as_posix())
 node=ET.Element('{'+ns+'}design_file',name=(folder/'fps_srl_weights.sv').as_posix(),version='default',library='default')
 info.insert(list(info).index(info.find('{'+ns+'}top_vhdl_arch')),node)
 ET.register_namespace('efx',ns);tree.write(NEW/'ti60_camera.xml',encoding='utf-8')
 (NEW/'ti60_camera.sdc').write_text('create_clock -name CLK_25M -period 40 [get_ports CLK_25M]\n')
 m['sources']={str(Path(n.get('name')).relative_to(WS)):sha(Path(n.get('name'))) for n in info.findall('{'+ns+'}design_file')}
 m['firmware_manifest']=sha(NEW/'firmware_manifest.json');m['project_xml_sha256']=sha(NEW/'ti60_camera.xml')
 m['status']='UNSIGNED_RF33_SRL_CANDIDATE_NO_DOWNLOAD';m['fps_candidate']['weights_storage']='Sequential SRL8; full ordered365 writes required'
 m['failed_ff_profile']={'path':str(OLD.relative_to(ROOT)),'reason':'Actual packed XLR69716 exceeds60800; 230RAM/130DSP alone did not prove fit',
  'place_report_sha256':sha(OLD/'outflow/ti60_camera.place.out')}
 (NEW/'manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2))
 assert (NEW/'firmware.bin').read_bytes()==(OLD/'firmware.bin').read_bytes()
 print('PREPARED UNSIGNED SRL RF33 profile; failed FF reports retained')

if __name__=='__main__':main()
