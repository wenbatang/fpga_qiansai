"""Measure an isolated learned CNN at 100 MHz; no board pin or system claim."""
from pathlib import Path
import argparse,hashlib,json,re,sys
ROOT=Path(__file__).resolve().parents[1];WORKSPACE=ROOT.parents[2]
sys.path.insert(0,str(WORKSPACE/'pycode'))
from export_hardware import load_export,pack_taps
from desktop_process import run


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--export',required=True,type=Path)
    p.add_argument('--name',default='core_measurement')
    p.add_argument('--width',type=int,default=640);p.add_argument('--height',type=int,default=480)
    a=p.parse_args()
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,31}',a.name):raise ValueError('Use an English build name')
    folder=ROOT/'build'/a.name;folder.mkdir(parents=True,exist_ok=True)
    metadata,layers=load_export(a.export)
    if len(layers) not in (3,5):raise ValueError('Unsupported depth')
    import numpy as np
    for i,layer in enumerate(layers):
        if i==len(layers)-1 and layer['weights'].shape[0]==1:
            layer['weights']=np.repeat(layer['weights'],3,axis=0);layer['bias']=np.repeat(layer['bias'],3)
        hex_width=layer['weights'].shape[0]*layer['weights'].shape[1]*2
        (folder/f'w{i}.mem').write_text(''.join(f'{v:0{hex_width}x}\n' for v in pack_taps(layer['weights'])*4))
        (folder/f'b{i}.mem').write_text(''.join(f'{int(v)&0xffffffff:08x}\n' for v in list(layer['bias'])*4))
        (folder/f's{i}.mem').write_text((f'{layer["shift"]:02x}\n')*4)
    params=','.join(f'.{kind}{i}("{(folder/f"{kind.lower()}{i}.mem").as_posix()}")' for i in range(len(layers)) for kind in 'WBS')
    module='style_cnn_stream' if len(layers)==3 else 'style_cnn_stream5'
    if len(layers)==5:params=f'.COORD_PHASE({metadata.get("coordinate_phase",0)}),'+params
    (folder/'core_top.sv').write_text(f'''module core_top(input wire clk,reset,start,input wire[1:0]style,
input wire[23:0]in_rgb,input wire in_valid,output wire in_ready,
output wire[23:0]out_rgb,output wire out_valid,input wire out_ready,output wire done);
{module} #(.WIDTH({a.width}),.HEIGHT({a.height}),{params}) dut(.*);
endmodule
''')
    sources=[*sorted((WORKSPACE/'common/rtl').glob('style_*.sv')),folder/'core_top.sv']
    script='\n'.join(f'read_verilog -sv {{{source.as_posix()}}}' for source in sources)
    script+='''
synth_design -top core_top -part xc7k325tffg676-2 -mode out_of_context
create_clock -name clk -period 10 [get_ports clk]
report_utilization -file utilization.rpt
opt_design
place_design
phys_opt_design
route_design
report_timing_summary -file timing.rpt
report_utilization -file routed_utilization.rpt
report_drc -file drc.rpt
write_checkpoint -force routed.dcp
'''
    (folder/'measure.tcl').write_text(script)
    (folder/'scope.json').write_text(json.dumps({'scope':'isolated core; one learned style repeated; no system bitstream',
        'width':a.width,'height':a.height,'weights':metadata,
        'source_sha256':{str(s):hashlib.sha256(s.read_bytes()).hexdigest() for s in sources}},indent=2))
    raise SystemExit(run(['E:/softare_FPGA/vivado2023/Vivado/2023.2/bin/vivado.bat','-mode','batch','-source',
        str(folder/'measure.tcl')],folder,folder/'console.log'))


if __name__=='__main__':main()
