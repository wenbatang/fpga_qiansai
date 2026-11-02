"""Actual keys/snapshot/control atomic gesture commit; no camera/CPU model."""
from pathlib import Path
import json,shutil,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from simutil import questa,sha
def main():
 folder=ROOT/'sim/guard';folder.mkdir(exist_ok=True);shutil.copy2(ROOT/'build/720p/weights.mem',folder/'weights.mem')
 tb=r'''module tb;
reg clk=0;always #5 clk=~clk;reg reset=1;reg[3:0]keys_n=15;reg front_valid=1;reg[1:0]front_mode=0;
reg[15:0]paddr=0;reg psel=0,penable=0,pwrite=0;reg[31:0]pwdata=0;
wire[31:0]prdata,gr,cr;wire selected,ge,ce,ready,ctrl_ready;wire[10:0]cpu_status;wire[255:0]diagnostics;
wire key_event,learn_event,capture_event,mode_event,guard_event,raw_mode,split_mode;
wire[5:0]key_style,guard_style,requested_style,loaded_style;wire[1:0]display_mode;
wire enable=front_valid && (front_mode==0 || front_mode==2) && display_mode==front_mode;
wire cancel=key_event || learn_event || mode_event;
style_keys47 #(.DEBOUNCE_CYCLES(3),.LEARN_HOLD_CYCLES(20)) keys(.clk(clk),.reset(reset),.keys_n(keys_n),.current_style(requested_style[3:0]),.learning_active(cpu_status[10]),.gesture_confirm(1'b0),.event_valid(key_event),.event_style(key_style),.raw_mode(raw_mode),.display_mode(display_mode),.split_mode(split_mode),.learn_event(learn_event),.capture_event(capture_event),.mode_event(mode_event));
gesture_snapshot snapshot(.clk(clk),.reset(reset),.enable(enable),.cancel(cancel),.learn_event(learn_event),.capture_event(capture_event),.frame_start(1'b0),.frame_end(1'b0),.frame_bad(1'b0),.pixel_valid(1'b0),.pixels(32'd0),.paddr(paddr),.psel(psel),.penable(penable),.pwrite(pwrite),.pwdata(pwdata),.prdata(gr),.selected(selected),.pslverror(ge),.cpu_status(cpu_status),.diagnostics(diagnostics),.guard_event(guard_event),.guard_style(guard_style));
video_control_apb_fast control(.clk(clk),.reset(reset),.paddr(paddr),.psel(psel&&!selected),.penable(penable),.pwrite(pwrite),.pwdata(pwdata),.prdata(cr),.pready(ctrl_ready),.pslverror(ce),.cfg_ready(1'b1),.busy(1'b0),.source_valid(1'b0),.source_frame(32'd0),.engine_cycles(32'd0),.inference_frames(32'd0),.capture_frames(32'd0),.dropped_frames(32'd0),.completed(1'b0),.failed(1'b0),.camera_fault(1'b0),.key_event(key_event),.key_style(key_style),.gesture_event(guard_event),.gesture_style(guard_style),.scl_in(1'b1),.sda_in(1'b1),.requested_style(requested_style),.loaded_style(loaded_style));
assign prdata=selected?gr:cr;assign ready=selected?1'b1:ctrl_ready;
integer guards=0,checks=0;reg[31:0]v,epoch,token;reg[5:0]old_style;
always @(posedge clk)if(!reset && guard_event)guards=guards+1;
task tick(input integer n);begin repeat(n)@(negedge clk);end endtask
task access(input[15:0]a,input[31:0]d,input w);begin
 psel=1;paddr=a;pwrite=w;pwdata=d;tick(1);penable=1;#1;
 if(!ready || (selected?ge:ce))$fatal(1,"APB interface error a%h",a);
 v=prdata;tick(1);psel=0;penable=0;pwrite=0;tick(1);
end endtask
task fresh_token;begin access('h88,0,0);epoch=v;access('hbc,epoch,1);end endtask
task result(input integer want,input integer style);begin access('hb8,0,0);if(v!=want || requested_style!=style)$fatal(1,"guard result%0d/%0d style%0d/%0d",v,want,requested_style,style);checks=checks+1;end endtask
task release_keys;begin keys_n=15;tick(14);end endtask
initial begin
 tick(4);reset=0;tick(14);
 fresh_token();access('hb8,9,1);result(1,9);
 access('hb8,10,1);result(4,9);
 access('hbc,epoch-1,1);access('hb8,3,1);result(2,9);
 front_valid=0;tick(3);fresh_token();access('hb8,3,1);result(3,9);front_valid=1;tick(3);
 fresh_token();access('h90,1024,1);access('hb8,3,1);result(3,9);access('h90,0,1);
 // A real long chord invalidates epoch before CPU consumes its sticky command.
 keys_n=9;tick(45);release_keys();fresh_token();access('hb8,3,1);result(3,9);
 access('hb4,3,1);fresh_token();access('hb8,9,1);result(1,9);
 // KEY1's registered event and guarded write are consumed at the same edge.
 fresh_token();keys_n=13;tick(5);psel=1;paddr='hb8;pwrite=1;pwdata=8;tick(1);
 if(!key_event)$fatal(1,"test did not align manual same edge");penable=1;tick(1);psel=0;penable=0;pwrite=0;tick(1);result(3,0);release_keys();
 // Accept at edgeT; a manual event atT+1 must win, with no delayed guard pulse.
 fresh_token();keys_n=13;tick(4);psel=1;paddr='hb8;pwrite=1;pwdata=8;tick(1);
 if(key_event)$fatal(1,"manual event arrived before intended guard edge");penable=1;#1;if(!guard_event)$fatal(1,"valid guarded ACCESS not combinational");tick(1);
 if(requested_style!=8 || !key_event)$fatal(1,"guard/manual adjacent edge setup");psel=0;penable=0;pwrite=0;tick(1);
 if(requested_style!=1 || guard_event)$fatal(1,"delayed guard overrode next-edge manual");result(1,1);release_keys();
 // KEY0 mode_event must exist BEFORE the actual view-update edge, not after it.
 fresh_token();keys_n=14;tick(4);psel=1;paddr='hb8;pwrite=1;pwdata=7;tick(1);
 if(!mode_event || display_mode!=0)$fatal(1,"mode_event is not view-edge aligned");penable=1;#1;if(guard_event)$fatal(1,"mode-edge gesture not rejected");tick(1);
 psel=0;penable=0;pwrite=0;if(display_mode!=1)$fatal(1,"real KEY0 did not change view");tick(1);result(3,1);release_keys();
 reset=1;tick(1);if(guard_event)$fatal(1,"guard active during reset");reset=0;tick(1);access('hb8,0,0);if(v!=0)$fatal(1,"guard result reset");access('hbc,0,0);if(v!=0)$fatal(1,"token reset");
 $display("PASS atomic guard %0d result checks, %0d commits, badID/stale/disabled/learning/sticky-toggle/same-edge-manual/next-edge-manual/exact KEY0 view-edge and reset",checks,guards);$finish;
end
initial begin #10000000;$fatal(1,"timeout");end
endmodule'''
 (folder/'tb.sv').write_text(tb,encoding='utf-8')
 files=[folder/'tb.sv',ROOT/'rtl/style_keys47.sv',ROOT/'rtl/gesture_snapshot.sv',ROOT/'rtl/p720/video_control_apb_fast.sv']
 questa(folder,files)
 bound=[*files,Path(__file__),ROOT/'scripts/simutil.py',folder/'weights.mem']
 (folder/'verification.json').write_text(json.dumps(dict(result='PASS',scope='Actual keys+snapshot+controller guarded APB commit and real debounced KEY0 timing; no image/CPU/physical board acceptance',sources_sha256={str(p):sha(p) for p in bound},logs_sha256={str(p):sha(p) for p in folder.glob('*.log')}),indent=2),encoding='utf-8')
if __name__=='__main__':main()
