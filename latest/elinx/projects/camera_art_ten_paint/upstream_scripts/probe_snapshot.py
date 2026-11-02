from pathlib import Path
import hashlib,json,sys,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from tool_run import environment,run


def main():
    folder=ROOT/'build/probe_snapshot';folder.mkdir(exist_ok=True);ns='http://www.efinixinc.com/enf_proj'
    tree=ET.parse(ROOT/'build/720p/ti60_camera.xml');tree.getroot().set('name','gesture_snapshot')
    info=tree.find('{'+ns+'}design_info');info.find('{'+ns+'}top_module').set('name','gesture_snapshot')
    for n in list(info):
        if n.tag=='{'+ns+'}design_file':info.remove(n)
    source=ROOT/'rtl/gesture_snapshot.sv';info.insert(1,ET.Element('{'+ns+'}design_file',name=source.as_posix(),version='default',library='default'))
    tree.find('{'+ns+'}interface_info').clear();tree.find('{'+ns+'}constraint_info').clear();ET.register_namespace('efx',ns);tree.write(folder/'gesture_snapshot.xml',encoding='utf-8')
    (folder/'inputs.json').write_text(json.dumps({str(source):hashlib.sha256(source.read_bytes()).hexdigest()},indent=2),encoding='utf-8')
    environment();assert run(['E:/software/efinity/python311/bin/python.exe','E:/software/efinity/scripts/efx_run.py','gesture_snapshot','--prj','--flow','map','--output_dir','outflow'],folder,folder/'map_console.log')==0


if __name__=='__main__':main()
