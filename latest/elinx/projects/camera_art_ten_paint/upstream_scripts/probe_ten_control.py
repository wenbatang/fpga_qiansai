"""Map final ten-style control ROM in isolation; offline, no board access."""
from pathlib import Path
import hashlib,json,shutil,sys,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from tool_run import environment,run
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    folder=ROOT/'build/probe_ten_control';folder.mkdir(exist_ok=True)
    rom=ROOT/'build/720p/weights.mem';assert len(rom.read_text().split())==1840,'Final ten-model ROM required'
    selected=ROOT/'build/model_selection.json';data=json.loads(selected.read_text(encoding='utf-8'))
    assert len(data['styles'])==10 and not data.get('provisional',True),'Final frozen models required'
    source=ROOT/'rtl/p720/video_control_apb_fast.sv';shutil.copy2(rom,folder/'weights.mem')
    ns='http://www.efinixinc.com/enf_proj';tree=ET.parse(ROOT/'build/720p/ti60_camera.xml');tree.getroot().set('name','video_control_apb_fast')
    info=tree.find('{'+ns+'}design_info');info.find('{'+ns+'}top_module').set('name','video_control_apb_fast')
    for n in list(info):
        if n.tag=='{'+ns+'}design_file':info.remove(n)
    info.insert(1,ET.Element('{'+ns+'}design_file',name=source.as_posix(),version='default',library='default'))
    tree.find('{'+ns+'}interface_info').clear();tree.find('{'+ns+'}constraint_info').clear();ET.register_namespace('efx',ns)
    project=folder/'video_control_apb_fast.xml';tree.write(project,encoding='utf-8')
    inputs={str(p):sha(p) for p in [source,rom,selected,folder/'weights.mem',project,Path(__file__)]}
    (folder/'inputs.json').write_text(json.dumps(inputs,indent=2),encoding='utf-8')
    environment();assert run(['E:/software/efinity/python311/bin/python.exe','E:/software/efinity/scripts/efx_run.py','video_control_apb_fast','--prj','--flow','map','--output_dir','outflow'],folder,folder/'map_console.log')==0
if __name__=='__main__':main()
