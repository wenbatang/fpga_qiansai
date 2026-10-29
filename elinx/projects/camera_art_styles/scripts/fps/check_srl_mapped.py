"""Independent C6 RF33 mapped-netlist arithmetic regression; no hardware access.

Four actual learned models, 365 runtime configuration words each. The same
nonuniform input and input/output stalls drive Efinity mapped native primitives
and editable RTL, compared with an independent NumPy reflect integer oracle.
No interface placement, timing signoff, whole-system FPS or bitstream is claimed.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
WS = ROOT.parents[2]
BUILD = ROOT / 'build/fps_c6_srl_mapped'
SIM = ROOT / 'sim/fps_srl/mapped'
NAME = 'fps_c6_srl_mapped'
RTL = [ROOT / 'rtl/fps' / name for name in ('fps_cnn5_srl.sv', 'fps_conv3x3_srl.sv', 'fps_line_ram.sv','fps_srl_weights.sv')]
Q = Path('E:/softare_FPGA/questasim/root/win64')
sys.path.insert(0, str(ROOT / 'scripts'))
from tool_run import run, environment


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def map_core():
    BUILD.mkdir(parents=True, exist_ok=True)
    top = BUILD / (NAME + '.sv')
    top.write_text('''module fps_c6_srl_mapped(
 input wire clk,reset,start,input wire[23:0]in_rgb,input wire in_valid,output wire in_ready,
 output wire[23:0]out_rgb,output wire out_valid,input wire out_ready,output wire done,
 input wire cfg_valid,input wire[15:0]cfg_address,input wire[31:0]cfg_data);
 fps_cnn5_srl #(.WIDTH(24),.HEIGHT(40),.FRAME_WIDTH(24),.D0(1),.D1(1),.D2(2),.D3(4),.D4(8)) core(
 .clk(clk),.reset(reset),.start(start),.style(3'd0),.origin_x(16'sd0),
 .in_rgb(in_rgb),.in_valid(in_valid),.in_ready(in_ready),.out_rgb(out_rgb),.out_valid(out_valid),
 .out_ready(out_ready),.done(done),.cfg_valid(cfg_valid),.cfg_address(cfg_address),.cfg_data(cfg_data));
endmodule
''', encoding='utf-8')
    ns = 'http://www.efinixinc.com/enf_proj'
    tree = ET.parse(ROOT / 'build/cnn_pipe_probe/cnn_pipe_probe.xml')
    project = tree.getroot()
    project.set('name', NAME)
    info = project.find('{' + ns + '}design_info')
    info.find('{' + ns + '}top_module').set('name', NAME)
    for node in list(info):
        if node.tag == '{' + ns + '}design_file':
            info.remove(node)
    for index, path in enumerate([top, *RTL]):
        info.insert(index + 1, ET.Element('{' + ns + '}design_file', name=path.as_posix(), version='default', library='default'))
    for node in tree.findall('.//{' + ns + '}sdc_file'):
        node.set('name', NAME + '.sdc')
    ET.register_namespace('efx', ns)
    tree.write(BUILD / (NAME + '.xml'), encoding='utf-8')
    (BUILD / (NAME + '.sdc')).write_text('create_clock -name clk -period 6 [get_ports clk]\n', encoding='utf-8')
    inputs = [Path(__file__), top, *RTL, BUILD / (NAME + '.xml'), BUILD / (NAME + '.sdc')]
    snapshots = {str(path): sha(path) for path in inputs}
    environment()
    assert run(['E:/software/efinity/python311/bin/python.exe', 'E:/software/efinity/scripts/efx_run.py',
                NAME, '--prj', '--flow', 'map', '--output_dir', 'outflow'], BUILD, BUILD / 'map_console.log') == 0
    mapped = BUILD / 'outflow' / (NAME + '.map.v')
    report = (BUILD / 'outflow' / (NAME + '.map.out')).read_text(encoding='utf-8')
    counts = {kind: int(re.search(r'^INFO\s*:\s*' + kind + r'\s*:\s*(\d+)', report, re.M)[1])
              for kind in ('EFX_RAM10', 'EFX_DSP48', 'EFX_FF', 'EFX_LUT4', 'EFX_SRL8', 'EFX_ADD')}
    assert counts['EFX_SRL8'] >= 1152, 'SRL weights were not actually inferred'
    assert all(sha(path) == value for path, value in snapshots.items())
    write_json(BUILD / 'mapping.json', {'result': 'PASS_MAP_ONLY', 'scope': __doc__, 'frame': [24, 40],
                                     'rf': 33, 'resources': counts, 'sources_sha256': snapshots,
                                     'mapped_netlist_sha256': sha(mapped), 'hardware_accessed': False})
    print('MAP COMPLETE', counts, flush=True)


def configuration(layers):
    import numpy as np
    if layers[-1]['weights'].shape[0] == 1:
        layers[-1]['weights'] = np.repeat(layers[-1]['weights'], 3, axis=0)
        layers[-1]['bias'] = np.repeat(layers[-1]['bias'], 3)
    words = []
    for index, layer in enumerate(layers):
        weights = layer['weights']
        cout, cin = weights.shape[:2]
        lanes = 3 if index == 4 else 6
        assert cout == lanes and cin == (3 if index == 0 else 6)
        chunks = (cin * lanes * 8 + 31) // 32
        for tap in range(9):
            packed = sum((int(weights[o, c, tap // 3, tap % 3]) & 255) << (8 * (o * cin + c))
                         for o in range(lanes) for c in range(cin))
            words.extend(((index << 11) | (tap << 5) | chunk, (packed >> (chunk * 32)) & 0xffffffff)
                         for chunk in range(chunks))
        words.extend((0x4000 | (index << 11) | channel, int(value) & 0xffffffff)
                     for channel, value in enumerate(layer['bias']))
        words.append((0x8000 | (index << 11), int(layer['shift'])))
    assert len(words) == 365
    return words


def simulate():
    import numpy as np
    sys.path.insert(0, str(WS / 'pycode'))
    from art6_border import load_export, integer_network
    SIM.mkdir(parents=True, exist_ok=True)
    mapping = json.loads((BUILD / 'mapping.json').read_text(encoding='utf-8'))
    assert all(sha(path) == value for path, value in mapping['sources_sha256'].items())
    mapped = BUILD / 'outflow' / (NAME + '.map.v')
    assert sha(mapped) == mapping['mapped_netlist_sha256']
    y, x = np.indices((40, 24))
    rgb = np.stack(((x * 37 + y * 19) & 255, (x * 11 + y * 29) & 255,
                    (x * 23 + y * 7) & 255), axis=-1).astype(np.uint8)
    def packed(image):
        return image[:, :, 0].astype(np.uint32) | (image[:, :, 1].astype(np.uint32) << 8) | (image[:, :, 2].astype(np.uint32) << 16)
    (SIM / 'input.mem').write_text(''.join(f'{int(v):06x}\n' for v in packed(rgb).flat), encoding='ascii')
    all_config, all_expected, models, export_files = [], [], {}, []
    for style in ('vangogh', 'papercut', 'comic', 'inkwash'):
        path = WS / 'pycode/runs/fps_student_v1/refined/rf33/export' / style
        meta, layers = load_export(path)
        assert [int(layer['dilation']) for layer in layers] == [1, 1, 2, 4, 8]
        all_config.extend(configuration(layers))
        expected = integer_network(rgb, layers, False)
        all_expected.extend(packed(expected).flat)
        models[style] = {'checkpoint_sha256': meta['checkpoint_sha256'], 'manifest_sha256': sha(path / 'manifest.json')}
        export_files.extend(p for p in path.glob('*') if p.is_file())
    (SIM / 'config.mem').write_text(''.join(f'{a:04x}{v:08x}\n' for a, v in all_config), encoding='ascii')
    (SIM / 'expected.mem').write_text(''.join(f'{int(v):06x}\n' for v in all_expected), encoding='ascii')
    tb = r'''`timescale 1ns/1ps
module tb;
reg clk=0;always #3 clk=~clk;
reg reset=1,start=0,cfg_valid=0,in_valid=0,out_ready=1;reg[15:0]cfg_address=0;reg[31:0]cfg_data=0;
reg[23:0]in_rgb=0;wire mr,rr,mv,rv,md,rd;wire[23:0]mo,ro;
fps_c6_srl_mapped dut(clk,reset,start,in_rgb,in_valid,mr,mo,mv,out_ready,md,cfg_valid,cfg_address,cfg_data);
fps_cnn5_srl #(.WIDTH(24),.HEIGHT(40),.FRAME_WIDTH(24),.D0(1),.D1(1),.D2(2),.D3(4),.D4(8)) reference(
 .clk(clk),.reset(reset),.start(start),.style(3'd0),.origin_x(16'sd0),.in_rgb(in_rgb),.in_valid(in_valid),.in_ready(rr),
 .out_rgb(ro),.out_valid(rv),.out_ready(out_ready),.done(rd),.cfg_valid(cfg_valid),.cfg_address(cfg_address),.cfg_data(cfg_data));
reg[47:0]cfg[0:1459];reg[23:0]image[0:959],expected[0:3839];
integer k,style,t=0,inputs=0,outputs=0,stalls=0,mismatches=0;reg running=0,blocked=0;reg[23:0]held;
always @(negedge clk)if(running)begin
 in_valid=inputs<960 && t%7!=0;in_rgb=image[inputs<960?inputs:0];out_ready=t%23<15;
end
always @(posedge clk)if(!reset&&running)begin
 t<=t+1;if(t>1000000)$fatal(1,"timeout");
 if({mr,mv,md}!=={rr,rv,rd})$fatal(1,"mapped/RTL handshake mismatch style%0d t%0d m%b r%b",style,t,{mr,mv,md},{rr,rv,rd});
 if(in_valid&&mr)inputs<=inputs+1;
 if(blocked&&(!mv||mo!==held))$fatal(1,"unstable mapped output");
 blocked<=mv&&!out_ready;held<=mo;if(mv&&!out_ready)stalls<=stalls+1;
 if(mv&&out_ready)begin
  if(outputs>=960)$fatal(1,"too many outputs");
  if(mo!==ro||mo!==expected[style*960+outputs])begin
   if(mismatches<4)$display("MISMATCH style%0d pixel%0d mapped%h rtl%h numpy%h",style,outputs,mo,ro,expected[style*960+outputs]);
   mismatches<=mismatches+1;
  end
  outputs<=outputs+1;
 end
end
initial begin
 $readmemh("config.mem",cfg);$readmemh("input.mem",image);$readmemh("expected.mem",expected);
 repeat(8)@(negedge clk);
 for(style=0;style<4;style=style+1)begin
  reset=1;in_valid=0;running=0;out_ready=1;blocked=0;
  for(k=0;k<365;k=k+1)begin
   cfg_valid=1;{cfg_address,cfg_data}=cfg[style*365+k];@(negedge clk);cfg_valid=0;@(negedge clk);
  end
  repeat(8)@(negedge clk);reset=0;inputs=0;outputs=0;t=0;stalls=0;mismatches=0;
  in_rgb=image[0];start=1;@(negedge clk);start=0;running=1;
  wait(md);@(negedge clk);running=0;in_valid=0;out_ready=1;
  $display("RESULT style%0d inputs%0d outputs%0d cycles%0d stalls%0d mismatches%0d",style,inputs,outputs,t,stalls,mismatches);
  if(inputs!=960||outputs!=960||stalls==0||mismatches!=0)$fatal(1,"coverage or mapped numerical mismatch");
 end
 $display("PASS C6 mapped equals RTL and independent NumPy: 4 learned RF33 models,3840 pixels,365 runtime config/model,input and output stalls");$finish;
end
endmodule
'''
    (SIM / 'tb.sv').write_text(tb, encoding='utf-8')
    primitives = sorted(Path('E:/software/efinity/sim_models/verilog').glob('*.v'))
    files = [SIM / 'tb.sv', mapped, *RTL, *primitives]
    sources = [Path(__file__), *files, *export_files, *(SIM / n for n in ('input.mem', 'config.mem', 'expected.mem'))]
    snapshots = {str(path): sha(path) for path in sources}
    for name, args in [('vlib', ['work']), ('vlog', ['-sv', '-timescale', '1ns/1ps', *map(str, files)]),
                       ('vsim', ['-c', 'tb', '-do', 'run -all; quit -f'])]:
        assert run([str(Q / (name + '.exe')), *args], SIM, SIM / (name + '.log')) == 0, name
    log = (SIM / 'vsim.log').read_text(errors='replace')
    assert 'PASS C6 mapped equals RTL' in log and '** Error:' not in log and '** Fatal:' not in log
    assert all(sha(path) == value for path, value in snapshots.items())
    write_json(SIM / 'verification.json', {'result': 'PASS', 'scope': __doc__, 'geometry': [24, 40],
                                         'models': models, 'pixels': 3840, 'runtime_writes_per_model': 365,
                                         'sources_sha256': snapshots, 'logs_sha256': {str(SIM / 'vsim.log'): sha(SIM / 'vsim.log')},
                                         'native_model_warning_lines': sum('** Warning:' in line for line in log.splitlines()),
                                         'mapped_timing_delays': False, 'whole_soc_or_physical_fps': False})
    print('PASS C6 MAPPED NUMERICAL REGRESSION', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('map', 'sim'))
    args = parser.parse_args()
    map_core() if args.action == 'map' else simulate()
