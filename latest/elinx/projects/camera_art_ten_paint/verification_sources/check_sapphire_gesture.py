from pathlib import Path
import shutil,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(Path(__file__).parent))
from simutil import questa,receipt,config_file
from check_classifier import pose
from check_runtime import rgb_packed


def main():
    folder=ROOT/'sim/sapphire_gesture';folder.mkdir(exist_ok=True);build=ROOT/'build/720p';base=ROOT.parent/'camera_art_interactive'
    for path in build.glob('Efx*.bin'):shutil.copy2(path,folder/path.name)
    shutil.copy2(build/'weights.mem',folder/'weights.mem');shutil.copy2(build/'ip/control_soc/Testbench/modelsim/control_soc.v',folder/'control_soc.v');config_file(folder/'config.mem',range(4))
    (folder/'mask.mem').write_text(''.join(f'{int(v):08x}\n' for v in rgb_packed(pose(3,True),0x7cc7)),encoding='ascii')
    template=base/'sim/sapphire/tb.sv';tb=template.read_text(encoding='utf-8')
    tb=tb.replace('.psel(sel),.penable(en)', '.psel(sel && !gsel),.penable(en)').replace('.prdata(rd),.pready(ready),.pslverror(error)', '.prdata(ctrl_rd),.pready(ctrl_ready),.pslverror(ctrl_error)')
    tb=tb.replace('if(starts==0)key<=1;','')
    start=tb.index('  if(starts>=2');end=tb.index('\n end\n initial begin',start);tb=tb[:start]+tb[end:]
    extra=r'''
wire gsel=(addr>='h80 && addr<='hbc) || (addr>='h2000 && addr<'h4000);
wire[31:0]ctrl_rd;wire ctrl_ready,ctrl_error;reg gready=0;reg[31:0]gseq=0;reg[31:0]mask[0:2047];reg[31:0]gdata;
assign rd=gsel?gdata:ctrl_rd;assign ready=gsel?1'b1:ctrl_ready;assign error=gsel?1'b0:ctrl_error;
always @*begin gdata=0;case(addr)
 'h80:gdata=8|gready;'h84:gdata=gseq;'h88:gdata=1;
 default:if(addr>='h2000 && addr<'h4000)gdata=mask[(addr-'h2000)>>2];
endcase end
initial $readmemh("mask.mem",mask);
reg[31:0]class_cost=0;
always @(posedge clk)if(sel && en && write && ready && gsel)begin
 if(addr=='h94)class_cost<=wd;
 if(addr=='h8c)begin if(wd==1)begin gready<=1;gseq<=gseq+1;end else gready<=0;end
 if(addr=='h90 && wd[7] && class_cost!=0)begin
  if(wd[2:0]!=3 || weight_writes!=216 || irqs<2)$fatal(1,"gesture/cfg/IRQ mismatch %h/%d/%d",wd,weight_writes,irqs);
  $display("PASS REAL SAPPHIRE RGB565 GREEN Chinese3 candidate=%h IRQs=%d classification_ui_cycles=%0d",wd,irqs,class_cost);$finish;
 end
end
'''
    # Declare names before instances so Questa does not create implicit nets.
    cut=extra.index('assign rd=');declarations=extra[:cut];logic=extra[cut:]
    tb=tb.replace(' control_soc cpu(',declarations+'\n control_soc cpu(')
    tb=tb.replace('endmodule',logic+'\nendmodule');(folder/'tb.sv').write_text(tb,encoding='utf-8')
    files=[folder/'control_soc.v',ROOT/'rtl/p720/video_control_apb_fast.sv',folder/'tb.sv']
    questa(folder,files,'tb_sapphire');receipt(folder,[*files,template,Path(__file__),ROOT/'sim/check_runtime.py',folder/'mask.mem',folder/'config.mem',folder/'weights.mem',*folder.glob('*.bin'),ROOT/'build/720p/firmware.bin',*list((ROOT/'firmware').glob('*'))],'Actual Sapphire3.4 RTL/new firmware/216 real weights/PLIC IRQ during RGB565 green Chinese3 segmentation/classification. ROI registers and image are explicit models; no four-second full SoC or real camera accuracy')


if __name__=='__main__':main()
