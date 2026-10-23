"""Prepare an isolated style accelerator project from verified UART baseline."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import sys
import numpy as np

ROOT=Path(__file__).resolve().parent
WORKSPACE=ROOT.parents[2]
BASE=ROOT.parent/'uart_hdmi'
sys.path.insert(0,str(WORKSPACE/'pycode'))
from export_hardware import load_export,pack_taps
STYLES=('vangogh','ukiyoe','inkwash','oilpainting')
PROFILES={'720p':(1280,720),'vga':(640,480)}


def prepare(export,profile='720p'):
    width,height=PROFILES[profile]
    build=ROOT/'build' if profile=='720p' else ROOT/'build/vga'
    project_name='vivado' if profile=='720p' else 'vivado_vga'
    script_name='create_project.tcl' if profile=='720p' else 'create_project_vga.tcl'
    build.mkdir(parents=True,exist_ok=True)
    for directory in ('rtl','scripts','build/weights','ip','constraints','pc'):
        (ROOT/directory).mkdir(parents=True,exist_ok=True)
    # Freeze reused editable sources inside this new project; never overwrite
    # a locally edited copy without noticing the different hash.
    files=['rtl/'+name for name in ('uart_8n1.sv','packet_rx.sv','packet_reply.sv','frame_reader.sv',
        'reset_sync.sv','video_clocks.sv','tmds_output.sv','hdmi_encoder.sv','hdmi_serializer10to1.sv','crc32_byte.svh')]
    files+=['scripts/desktop_process.py','pc/requirements.txt','ip/mig.prj']
    provenance={}
    for name in files:
        source=BASE/name; destination=ROOT/name
        if destination.exists() and destination.read_bytes()!=source.read_bytes():
            raise ValueError(f'Reused source changed; reconcile explicitly: {destination}')
        if not destination.exists():shutil.copyfile(source,destination)
        provenance[name]=hashlib.sha256(source.read_bytes()).hexdigest()
    # video_720p is an intentional fork: centered VGA ROI, unchanged HDMI timing.
    source=BASE/'rtl/video_720p.sv';destination=ROOT/'rtl/video_720p.sv'
    if not destination.exists():shutil.copyfile(source,destination)
    provenance['video_720p_original_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
    layers_by_style=[];models={};depth=None;coordinate_phase=None
    for name in STYLES:
        metadata,layers=load_export(export/name)
        if metadata['style']!=name:raise ValueError(f'Wrong style checkpoint in folder {name}')
        if depth is None:depth=len(layers)
        phase=metadata.get('coordinate_phase',0)
        if coordinate_phase is None:coordinate_phase=phase
        if phase!=coordinate_phase or phase not in (0,4) or phase and depth!=5:
            raise ValueError('All style coordinate features must match the supported geometry')
        if len(layers)!=depth or depth not in (3,5):raise ValueError('All styles must use the same supported depth')
        channels=8 if depth==3 else 6
        for index,layer in enumerate(layers):
            expected=(channels if index<depth-1 else 1 if metadata['monochrome'] else 3,(5 if phase else 3) if index==0 else channels)
            if layer['weights'].shape!=(expected[0],expected[1],3,3):
                raise ValueError(f'Unsupported model geometry: {name}/{index}')
            if not 0<=layer['shift']<=20 or metadata['layers'][index]['worst_case_abs_accumulator']>=2**31:
                raise ValueError('Unsafe quantization')
        if metadata['monochrome']:
            layers[-1]['weights']=np.repeat(layers[-1]['weights'],3,axis=0)
            layers[-1]['bias']=np.repeat(layers[-1]['bias'],3,axis=0)
        layers_by_style.append(layers);models[name]=metadata
    folder=ROOT/'build/weights'
    for i in range(depth):
        weight=[v for l in layers_by_style for v in pack_taps(l[i]['weights'])]
        bias=np.concatenate([l[i]['bias'] for l in layers_by_style])
        hex_width=layers_by_style[0][i]['weights'].shape[0]*layers_by_style[0][i]['weights'].shape[1]*2
        (folder/f'w{i}.mem').write_text(''.join(f'{v:0{hex_width}x}\n' for v in weight),encoding='ascii')
        (folder/f'b{i}.mem').write_text(''.join(f'{int(v)&0xffffffff:08x}\n' for v in bias),encoding='ascii')
        (folder/f's{i}.mem').write_text(''.join(f'{l[i]["shift"]:02x}\n' for l in layers_by_style),encoding='ascii')
    parameters=f'.DEPTH({depth}), .COORD_PHASE({coordinate_phase}), '+', '.join(f'.{kind}{i}("{(folder/f"{kind.lower()}{i}.mem").as_posix()}")' for i in range(depth) for kind in 'WBS')
    (ROOT/'rtl/style_weights.vh').write_text('`define STYLE_WEIGHT_PARAMETERS '+parameters+'\n')
    provenance['models']=models
    provenance['scope']={'profile':profile,'request_codec':'COBS','reply_codec':'SLIP','width':width,'height':height,
                         'pixel_format':'RGB565 little endian','depth':depth,'channels':channels,
                         'coordinate_phase':coordinate_phase,
                         'uart_baud':2000000,'max_payload_bytes':16384,'ui_clock_hz':100000000}
    provenance['source_sha256']={str(p.relative_to(WORKSPACE)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [*sorted((ROOT/'rtl').glob('*')),*sorted((WORKSPACE/'common/rtl').glob('style_*.sv')),
                  *sorted((ROOT/'scripts').glob('*.py')),*sorted((ROOT/'constraints').glob('*.xdc')),ROOT/'ip/mig.prj',
                  ROOT/'create_project.py',*sorted((ROOT/'pc').glob('*.py'))] if p.is_file()}
    provenance['compiled_weights_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.glob('*.mem')}
    template=(BASE/'scripts/create_project_fast.tcl').read_text()
    template=template.replace('vivado_fast',project_name).replace('uart_hdmi.xpr','uart_style.xpr').replace('create_project uart_hdmi','create_project uart_style')
    template=template.replace('set_property top uart_hdmi_top','add_files [glob [file join $root .. .. .. common rtl *.sv]]\nset_property top uart_style_top')
    template=template.replace('set_property include_dirs [list [file join $root rtl]]','set_property include_dirs [list [file join $root rtl]]')
    # Part/pins/IP versions and report/signoff gates stay at the reviewed baseline.
    template=template.replace('F:/fpga_qiansai/xilinx/projects/uart_hdmi/.venv/Scripts/python.exe','E:/software/anaconda/envs/yolo/python.exe')
    generic=f'UART_BAUD=2000000 UART_PAYLOAD_BYTES=16384 PROC_WIDTH={width} PROC_HEIGHT={height}'
    template=template.replace('if {[lsearch -exact $argv --build]>=0} {',
        'set_property generic {'+generic+'} [get_filesets sources_1]\nif {[lsearch -exact $argv --build]>=0} {')
    (ROOT/'scripts'/script_name).write_text(template)
    provenance['generated_tcl_sha256']=hashlib.sha256((ROOT/'scripts'/script_name).read_bytes()).hexdigest()
    (build/'source_manifest.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export',type=Path,default=WORKSPACE/'pycode/runs/distinct_student_v1/export')
    parser.add_argument('--profile',choices=PROFILES,default='720p')
    parser.add_argument('--build',action='store_true')
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    prepare(args.export,args.profile)
    if args.build:
        sys.path.insert(0,str(ROOT/'scripts'))
        from desktop_process import run
        build=ROOT/'build' if args.profile=='720p' else ROOT/'build/vga'
        script='create_project.tcl' if args.profile=='720p' else 'create_project_vga.tcl'
        command=['E:/softare_FPGA/vivado2023/Vivado/2023.2/bin/vivado.bat','-mode','batch','-source',
                 str(ROOT/'scripts'/script),'-tclargs','--build']
        if args.resume:command+=['--resume','--reset-synth']
        raise SystemExit(run(command,build,build/'vivado_console.log'))
    print('Prepared UART style project from actual learned weights')


if __name__=='__main__':main()
