"""Prepare an isolated style accelerator project from verified UART baseline."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parent
WORKSPACE=ROOT.parents[2]
BASE=ROOT.parent/'uart_hdmi'
sys.path.insert(0,str(WORKSPACE/'pycode'))
from export_hardware import pack_taps
from art6_border import load_export,POLICY
STYLES=('vangogh','monet','ukiyoe','papercut','comic','inkwash')
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
    files+=['pc/requirements.txt','ip/mig.prj']
    provenance={}
    for name in files:
        source=BASE/name; destination=ROOT/name
        if destination.exists() and destination.read_bytes()!=source.read_bytes():
            raise ValueError(f'Reused source changed; reconcile explicitly: {destination}')
        if not destination.exists():shutil.copyfile(source,destination)
        provenance[name]=hashlib.sha256(source.read_bytes()).hexdigest()
    # The local launcher intentionally records output in both packaged and
    # ordinary child processes. Keep its upstream fingerprint, not an overwrite.
    provenance['desktop_process_original_sha256']=hashlib.sha256((BASE/'scripts/desktop_process.py').read_bytes()).hexdigest()
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
        if len(layers)!=5 or phase!=0 or [l['dilation'] for l in layers]!=[1,2,4,8,16]:raise ValueError('Six-style build requires five layers, no XY, dilation 1/2/4/8/16')
        channels=12
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
                         'coordinate_phase':coordinate_phase,'dilations':[1,2,4,8,16],'styles':list(STYLES),'style_bits':3,
                         'uart_baud':2000000,'max_payload_bytes':16384,'ui_clock_hz':100000000,'padding':POLICY}
    provenance['source_sha256']={str(p.relative_to(WORKSPACE)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [*sorted((ROOT/'rtl').glob('*')),
                  *sorted((ROOT/'scripts').glob('*.py')),*sorted((ROOT/'constraints').glob('*.xdc')),ROOT/'ip/mig.prj',
                  ROOT/'create_project.py',*sorted((ROOT/'pc').glob('*.py')),
                  WORKSPACE/'pycode/art6_border.py',WORKSPACE/'pycode/render_border_art6.py'] if p.is_file()}
    provenance['compiled_weights_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.glob('*.mem')}
    template=(BASE/'scripts/create_project_fast.tcl').read_text()
    template=template.replace('vivado_fast',project_name).replace('uart_hdmi.xpr','uart_style.xpr').replace('create_project uart_hdmi','create_project uart_style')
    template='set_param general.maxThreads 4\n'+template
    template=template.replace('set_property top uart_hdmi_top','set_property top uart_style_top')
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
    parser.add_argument('--export',type=Path,default=WORKSPACE/'pycode/runs/art6_v2/export')
    parser.add_argument('--profile',choices=PROFILES,default='720p')
    parser.add_argument('--build',action='store_true')
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    if args.build:
        # Small learned boundary/operator checks precede CAD. The independent
        # full720 CNN can run alongside CAD; final signoff requires both.
        receipt=ROOT/'sim/border_learned/verification.json'
        deadline=time.monotonic()+2*3600
        while not receipt.exists():
            if time.monotonic()>deadline:raise TimeoutError('Learned boundary RTL proof not available')
            time.sleep(3)
        data=json.loads(receipt.read_text())
        if (data['width'],data['height'],data['pixels'])!=(71,69,39192) or 'PASS CNN' not in data['result']:
            raise ValueError('Invalid learned boundary CNN receipt')
        for path,value in data['sha256'].items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=value:raise ValueError('Stale full-size CNN '+path)
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
