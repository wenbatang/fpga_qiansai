"""Create a Ti60F225 I3 map-only resource project for the portable CNN."""
from pathlib import Path
import argparse,hashlib,json,shutil,sys,os
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1];WORKSPACE=ROOT.parents[2]
sys.path.insert(0,str(WORKSPACE/'pycode'))
from export_hardware import load_export,pack_taps
NS='http://www.efinixinc.com/enf_proj'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export',type=Path,default=WORKSPACE/'xilinx/projects/uart_style_hdmi/build/preliminary_core/export')
    parser.add_argument('--name',default='core_map')
    parser.add_argument('--all-styles',action='store_true',help='Export directory contains four distinct style folders')
    parser.add_argument('--catalog',choices=('legacy','distinct'),default='legacy')
    args=parser.parse_args()
    import re
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,23}',args.name):raise ValueError('Use a short English build name')
    folder=ROOT/'build'/args.name;folder.mkdir(parents=True,exist_ok=True)
    styles=('vangogh','ukiyoe','inkwash','oilpainting') if args.catalog=='distinct' else ('ukiyoe','vangogh','inkwash','inkprint')
    loaded=[load_export(args.export/name) for name in styles] if args.all_styles else [load_export(args.export)]*4
    metadata,layers=loaded[0]
    if len(layers) not in (3,5):raise ValueError('Unsupported depth')
    depth=len(layers)
    import numpy as np
    normalized=[]
    for meta,items in loaded:
        if len(items)!=depth or meta.get('coordinate_phase',0)!=metadata.get('coordinate_phase',0):
            raise ValueError('Style geometry differs')
        items=[dict(layer) for layer in items]
        if items[-1]['weights'].shape[0]==1:
            items[-1]['weights']=np.repeat(items[-1]['weights'],3,axis=0)
            items[-1]['bias']=np.repeat(items[-1]['bias'],3,axis=0)
        normalized.append(items)
    for i in range(depth):
        layer=normalized[0][i]
        if any(items[i]['weights'].shape!=layer['weights'].shape for items in normalized):raise ValueError('Weight shapes differ')
        hex_width=layer['weights'].shape[0]*layer['weights'].shape[1]*2
        (folder/f'w{i}.mem').write_text(''.join(f'{v:0{hex_width}x}\n' for items in normalized for v in pack_taps(items[i]['weights'])))
        (folder/f'b{i}.mem').write_text(''.join(f'{int(v)&0xffffffff:08x}\n' for items in normalized for v in items[i]['bias']))
        (folder/f's{i}.mem').write_text(''.join(f'{items[i]["shift"]:02x}\n' for items in normalized))
    params=','.join(f'.{kind}{i}("{(folder/f"{kind.lower()}{i}.mem").as_posix()}")' for i in range(depth) for kind in 'WBS')
    module='style_cnn_stream' if depth==3 else 'style_cnn_stream5'
    if depth==5:params=f'.COORD_PHASE({metadata.get("coordinate_phase",0)}),'+params
    (folder/'core_top.sv').write_text(f'''module core_top(input wire clk,reset,start,input wire[1:0]style,
input wire[23:0]in_rgb,input wire in_valid,output wire in_ready,
output wire[23:0]out_rgb,output wire out_valid,input wire out_ready,output wire done);
{module} #(.WIDTH(640),.HEIGHT(480),{params}) dut(.*);
endmodule''')
    project=ET.parse(WORKSPACE/'elinx/elinxdemo/Ti60F225_DemoBoard_v4/17_Ti60F225_uart_demo/17_Ti60F225_uart_demo/top.xml')
    tree=project.getroot();tree.set('name','core_top');tree.set('location',folder.as_posix())
    for key in ('last_run_state','last_run_flow','config_result_in_sync','design_ood','place_ood','route_ood'):
        tree.attrib.pop(key,None)
    tree.find(f'{{{NS}}}device_info/{{{NS}}}family').set('name','Titanium')
    tree.find(f'{{{NS}}}device_info/{{{NS}}}device').set('name','Ti60F225')
    tree.find(f'{{{NS}}}device_info/{{{NS}}}timing_model').set('name','I3')
    design=tree.find(f'{{{NS}}}design_info');design.set('def_veri_version','sv_09')
    design.find(f'{{{NS}}}top_module').set('name','core_top')
    for old in list(design.findall(f'{{{NS}}}design_file')):design.remove(old)
    files=[*sorted((WORKSPACE/'common/rtl').glob('style_*.sv')),folder/'core_top.sv']
    # The schema requires design_file entries before top_vhdl_arch.
    for index,source in enumerate(files,1):
        design.insert(index,ET.Element(f'{{{NS}}}design_file',name=source.as_posix(),version='default',library='default'))
    constraints=tree.find(f'{{{NS}}}constraint_info')
    for child in list(constraints):constraints.remove(child)
    (folder/'core.sdc').write_text('create_clock -name clk -period 10 [get_ports clk]\n')
    ET.SubElement(constraints,f'{{{NS}}}sdc_file',name='core.sdc')
    ET.SubElement(constraints,f'{{{NS}}}inter_file',name='')
    for option in tree.find(f'{{{NS}}}synthesis'):
        if option.get('name')=='max-bit-blast-mem-size':option.set('value','32768')
    ET.register_namespace('efx',NS);project.write(folder/'core_top.xml',encoding='utf-8',xml_declaration=True)
    (folder/'scope.json').write_text(json.dumps({'scope':'map-only portable core; no board pin bindings or bitstream',
        'style_scope':'four distinct learned models' if args.all_styles else 'one learned style repeated',
        'part':'Ti60F225','timing_model':'I3','efinity':'2026.1 installed baseline','weights':[meta for meta,_ in loaded],
        'compiled_weights_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.glob('*.mem')},
        'sources':{p.as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}},ensure_ascii=False,indent=2))
    sys.path.insert(0,str(WORKSPACE/'xilinx/projects/uart_style_hdmi/scripts'))
    from desktop_process import run
    # Process-local tool environment: do not run Anaconda activation scripts
    # or change the installed Efinity defaults/global Windows environment.
    os.environ['EFINITY_HOME']='E:/software/efinity'
    for key,tail in {'EFXPT_HOME':'pt','EFXPGM_HOME':'pgm','EFXDBG_HOME':'debugger','EFXIPM_HOME':'ipm'}.items():
        os.environ[key]=f'E:/software/efinity/{tail}'
    os.environ['EFINITY_USER_DIR_INI']=str(Path(os.environ['LOCALAPPDATA'])/'efinity/user_dir.ini')
    os.environ['PYTHONHOME']='E:/software/efinity/python311';os.environ.pop('PYTHONPATH',None)
    os.environ['PATH']='E:/software/efinity/bin;E:/software/efinity/python311/bin;'+os.environ['PATH']
    raise SystemExit(run(['E:/software/efinity/python311/bin/python.exe','E:/software/efinity/scripts/efx_run.py',
        'core_top','--prj','--flow','map','--output_dir','outflow'],folder,folder/'console.log'))


if __name__=='__main__':main()
