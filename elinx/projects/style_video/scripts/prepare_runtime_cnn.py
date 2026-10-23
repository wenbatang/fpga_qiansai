"""Create a PRIVATE runtime-loadable fork of the signed integer CNN.

The public/Xilinx/previous Ti60 cores and learned model files stay unchanged.
The math/pipeline is unchanged; only ROM storage becomes CPU writable and the
DDR source base becomes a job-latched register.
"""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];WS=ROOT.parents[2]
def main():
 dst=ROOT/'rtl';dst.mkdir(exist_ok=True)
 original=(WS/'common/rtl/style_conv3x3.sv').read_text(encoding='utf-8')
 source=original.replace('module style_conv3x3 #(', 'module video_conv3x3 #(')
 source=source.replace('    output reg done\n','    output reg done,\n    input wire cfg_valid,input wire[1:0] cfg_kind,\n    input wire[3:0] cfg_tap,input wire[6:0] cfg_offset,input wire[31:0] cfg_data\n')
 start=source.index('    // Efinity:');end=source.index('    wire actual=',start)
 source=source[:start]+'''    // One active model is loaded by Sapphire while ALL layers are idle.
    // No reset clears these arrays; weights_valid in the control plane blocks
    // jobs until firmware writes the entire catalog and commits it.
    (* syn_ramstyle="registers" *) reg [CIN*COUT*8-1:0] weights [0:8];
    reg signed [31:0] biases [0:COUT-1];
    reg [7:0] shifts [0:0];
    always @(posedge clk) if(cfg_valid) begin
        if(cfg_kind==0 && cfg_tap<9 && cfg_offset<CIN*COUT)
            weights[cfg_tap][cfg_offset*8+:8]<=cfg_data[7:0];
        if(cfg_kind==1 && cfg_offset<COUT)biases[cfg_offset]<=cfg_data;
        if(cfg_kind==2 && cfg_data<=31)shifts[0]<=cfg_data[7:0];
    end
'''+source[end:]
 source=source.replace('style_hold*9+tap','tap').replace('biases[style_hold*COUT+output_channel]','biases[output_channel]').replace('shifts[style_hold]','shifts[0]')
 (dst/'video_conv3x3.sv').write_text(source,encoding='utf-8')
 original=(WS/'elinx/projects/uart_style_tiles/rtl/style_cnn_tile5.sv').read_text(encoding='utf-8')
 source=original.replace('style_tile_mask','video_tile_mask').replace('style_cnn_tile5','video_cnn_tile5').replace('style_conv3x3','video_conv3x3')
 source=source.replace('output wire done);','output wire done,\n input wire cfg_valid,input wire[15:0] cfg_address,input wire[31:0] cfg_data);')
 for layer in range(5):
  # Existing positional layer ports append the four private configuration pins.
  tail=['a,av,ar,);','b,bv,br,);','c,cv,cr,);','d,dv,dr,);','e,out_valid,out_ready,done);'][layer]
  source=source.replace(tail,tail[:-2]+f',cfg_valid && cfg_address[13:11]==3\'d{layer},cfg_address[15:14],cfg_address[10:7],cfg_address[6:0],cfg_data);')
 # Last layer already had a done output; others had an omitted done output.
 source=source.replace('out_ready,donecfg_valid','out_ready,done,cfg_valid')
 (dst/'video_cnn_tile5.sv').write_text(source,encoding='utf-8')
 original=(WS/'elinx/projects/uart_style_tiles/rtl/style_tile_engine.sv').read_text(encoding='utf-8')
 source=original.replace('style_tile_engine','video_tile_engine').replace('style_cnn_tile5','video_cnn_tile5')
 source=source.replace('input wire output_bank,','input wire output_bank,input wire[29:0] source_base,\n input wire cfg_valid,input wire[15:0] cfg_address,input wire[31:0] cfg_data,')
 source=source.replace('    reg[29:0] out_base,','    reg[29:0] source_hold;\n    reg[29:0] out_base,')
 source=source.replace('SOURCE_BASE+in_row_bytes','source_hold+in_row_bytes')
 source=source.replace('style_hold<=style;','style_hold<=style;source_hold<=source_base;')
 source=source.replace('out_base<=0;','out_base<=0;source_hold<=0;')
 source=source.replace('.done(cnn_done));','.done(cnn_done),.cfg_valid(cfg_valid),.cfg_address(cfg_address),.cfg_data(cfg_data));')
 (dst/'video_tile_engine.sv').write_text(source,encoding='utf-8')
 print('Private runtime CNN generated; public kernels/model exports unchanged')
if __name__=='__main__':main()
