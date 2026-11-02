"""Actual integrated control wiring; image transport IP explicitly black boxed."""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from simutil import run,sha
IV=Path('E:/softare_FPGA/iverilog/iverilog/bin')
def main():
 out=ROOT/'sim/ui_system';out.mkdir(exist_ok=True)
 tb=r'''module tb;
reg clk=0,pixel_clk=0,ref_clk=0;always #5 clk=~clk;always #7 pixel_clk=~pixel_clk;always #20 ref_clk=~ref_clk;
reg reset=1;reg[3:0]keys_n=15;wire boot_reset_n;
board_boot #(.POWER_CYCLES(5),.HOLD_CYCLES(10)) boot(.clk(ref_clk),.keys_n(keys_n),.reset_n(boot_reset_n));
reg[15:0]paddr=0;reg psel=0,penable=0,pwrite=0;reg[31:0]pwdata=0;wire[31:0]prdata;wire pslverror,pready;wire[23:0]display_rgb;
video_system_720 system(.clk(clk),.fast_clk(clk),.reset(reset),.pixel_clk(pixel_clk),.pixel_reset(reset),.calibrated(1'b1),
 .keys_n(keys_n),.scl_in(1'b1),.sda_in(1'b1),.paddr(paddr),.psel(psel),.penable(penable),.pwrite(pwrite),.pwdata(pwdata),
 .prdata(prdata),.pready(pready),.pslverror(pslverror),.display_rgb(display_rgb));
defparam system.keys.DEBOUNCE_CYCLES=3,system.keys.LEARN_HOLD_CYCLES=20;
task tick(input integer n);begin repeat(n)@(negedge clk);end endtask
task press(input integer i);begin keys_n=15^(1<<i);tick(12);keys_n=15;tick(12);end endtask
task write(input[15:0]a,input[31:0]d);begin
 paddr=a;pwdata=d;psel=1;pwrite=1;penable=0;tick(1);penable=1;tick(1);
 if(!pready || pslverror)$fatal(1,"APB rejected %h",a);penable=0;psel=0;pwrite=0;tick(1);
end endtask
reg[31:0]epoch;
initial begin
 force system.front_valid=1;force system.front_mode=0;force system.capture_errors=0;
 force system.cfg_ready=1;force system.busy=0;force system.engine_done=0;force system.engine_error=0;
 force system.rgb=24'h123456;force system.de=1;force system.x=0;force system.y=40;force system.vsync=1;
 tick(8);reset=0;tick(30);
 paddr='h88;#1;epoch=prdata;
 write('hbc,epoch);write('hb8,7);
 if(system.requested_style!=7 || system.display_mode!=1)$fatal(1,"accepted RAW gesture must set slot and STYLE atomically");
 paddr='hb8;#1;if(prdata!=1)$fatal(1,"auto-view invalidated its own guard");
 // Model the completed STYLE front, then return to SPLIT for a second request.
 force system.front_mode=1;tick(8);press(0);force system.front_mode=2;tick(8);
 paddr='h88;#1;epoch=prdata;write('hbc,epoch);write('hb8,3);
 if(system.requested_style!=3 || system.display_mode!=2)$fatal(1,"SPLIT gesture changed the chosen view");
 tick(8);if(display_rgb!==24'h30d9ec)$fatal(1,"visible ROI missing %h",display_rgb);
 press(3);tick(8);if(display_rgb!==24'h123456)$fatal(1,"UI off did not hide ROI");
 force system.x=16;force system.y=16;tick(8);if(display_rgb!==24'h123456)$fatal(1,"UI off did not hide text");
 // Hold beyond the shortened old reset threshold; neither enrollment nor PLL
 // boot may be reset and the overlay toggles exactly once per debounced press.
 keys_n=7;tick(200);if(!boot_reset_n || !system.ui_visible)$fatal(1,"held KEY3 reset or repeated");
 tick(200);if(!boot_reset_n || !system.ui_visible)$fatal(1,"held KEY3 repeated toggle");
 if(display_rgb===24'h123456)$fatal(1,"UI on did not restore text");
 keys_n=15;tick(12);
 // A stale gesture after a manual view transition cannot switch the view.
 press(0);force system.front_mode=0;tick(8);write('hbc,epoch);write('hb8,9);
 paddr='hb8;#1;if(prdata!=2 || system.display_mode!=0 || system.requested_style!=3)$fatal(1,"stale guard switched view/style");
 $display("PASS integrated auto STYLE/SPLIT retention/UI text+ROI/held KEY3/stale guard");$finish;
end
initial begin #500000;$fatal(1,"timeout");end
endmodule'''
 (out/'tb.sv').write_text(tb,encoding='utf-8')
 files=[out/'tb.sv',*[ROOT/'rtl'/n for n in ['p720/video_system_720.sv','p720/video_control_apb_fast.sv','style_keys47.sv','gesture_snapshot.sv','board_boot.sv','fps_snapshot.sv','hdmi60/fps_overlay60.sv']]]
 assert run([str(IV/'iverilog.exe'),'-g2012','-i','-s','tb','-o','test.vvp',*map(str,files)],out,out/'compile.log')==0
 assert run([str(IV/'vvp.exe'),'test.vvp'],out,out/'vsim.log')==0
 assert 'PASS integrated' in (out/'vsim.log').read_text()
 (out/'verification.json').write_text(json.dumps(dict(result='PASS',auto_switch=True,ui_toggle=True,
  scope='Actual video_system/control/keys/snapshot/UI/boot wiring. Image transport black boxes, front metadata and image timing forced; not full camera SoC.',
  sources_sha256={str(p):sha(p) for p in [*files,Path(__file__),ROOT/'scripts/simutil.py']},
  logs_sha256={str(p):sha(p) for p in out.glob('*.log')}),indent=2),encoding='utf-8')
if __name__=='__main__':main()
