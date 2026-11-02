"""Apply the on-board ROI/CPU gesture integration to this independent clone."""
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'build/720p'


def main():
    path=ROOT/'rtl/p720/video_system_720.sv';text=path.read_text(encoding='utf-8');assert 'gesture_snapshot' not in text
    text=text.replace('wire latest_valid;', '''wire latest_valid;
 wire gesture_selected,gesture_error,control_error,control_ready;wire[31:0]gesture_read,control_read;wire[8:0]gesture_status;
 wire gesture_enable=front_valid && (front_mode==0 || front_mode==2) && display_mode==front_mode;
 assign prdata=gesture_selected?gesture_read:control_read;
 assign pslverror=gesture_selected?gesture_error:control_error;
 assign pready=gesture_selected?1'b1:control_ready;''')
    text=text.replace('.keys_n(keys_n),.event_valid(key_event)', '.keys_n(keys_n),.current_style(requested_style[1:0]),.event_valid(key_event)')
    text=text.replace('.paddr(paddr),.psel(psel),.penable(penable)', '.paddr(paddr),.psel(psel && !gesture_selected),.penable(penable)')
    text=text.replace('.prdata(prdata),.pready(pready),.pslverror(pslverror)', '.prdata(control_read),.pready(control_ready),.pslverror(control_error)')
    at=' wire capture_fifo_full,capture_fifo_empty,capture_fifo_write,capture_fifo_read;'
    added=''' gesture_snapshot gesture(.clk(clk),.reset(reset),.enable(gesture_enable),.cancel(key_event),
  .frame_start(camera_start),.frame_end(camera_end),.frame_bad(camera_bad),.pixel_valid(camera_pixel_valid),.pixels(camera_pixels),
  .paddr(paddr),.psel(psel),.penable(penable),.pwrite(pwrite),.pwdata(pwdata),
  .prdata(gesture_read),.selected(gesture_selected),.pslverror(gesture_error),.cpu_status(gesture_status));
'''
    assert at in text;text=text.replace(at,added+at)
    text=text.replace('.rgb(rgb),.out_rgb(display_rgb)', '.rgb(rgb),.out_rgb(overlaid_rgb)')
    at=' fps_overlay60 overlay('
    added=''' wire[23:0]overlaid_rgb;
 (* async_reg="true",syn_srlstyle="registers" *)reg[1:0]gesture_visible_sync;
 always @(posedge pixel_clk)if(pixel_reset)gesture_visible_sync<=0;else gesture_visible_sync<={gesture_visible_sync[0],gesture_enable};
 wire roi_edge=((x==64 || x==575) && y>=96 && y<=607) || ((y==96 || y==607) && x>=64 && x<=575);
 assign display_rgb=de && gesture_visible_sync[1] && roi_edge?24'h30d9ec:overlaid_rgb;
'''
    assert at in text;text=text.replace(at,added+at)
    text=text.replace("{9'd0,front_style",'{gesture_status,front_style')
    path.write_text(text,encoding='utf-8')
    path=ROOT/'rtl/style_keys47.sv';text=path.read_text(encoding='utf-8').replace('input wire clk,reset,input wire[3:0]keys_n,','input wire clk,reset,input wire[3:0]keys_n,input wire[1:0]current_style,')
    text=text.replace('event_style==3?0:event_style+1\'b1','current_style==3?0:current_style+1\'b1').replace('event_style==0?3:event_style-1\'b1','current_style==0?3:current_style-1\'b1');path.write_text(text,encoding='utf-8')
    path=ROOT/'firmware/main.c';text=path.read_text(encoding='utf-8').replace('int main(void) {','#include "gesture_runtime.c"\nint main(void) {').replace('  uint32_t status=REG(0x08);','  gesture_poll();\n  uint32_t status=REG(0x08);');path.write_text(text,encoding='utf-8')
    # New scalar display-overlay crossing, same physical IO/PLL configuration.
    path=ROOT/'scripts/native_constraints.py';text=path.read_text(encoding='utf-8').replace("'system/overlay_sync[0]~FF'","'system/gesture_visible_sync[0]~FF','system/overlay_sync[0]~FF'").replace("len(report['scalar_first_stages'])==23","len(report['scalar_first_stages'])==24");path.write_text(text,encoding='utf-8')
    ns='http://www.efinixinc.com/enf_proj';tree=ET.parse(B/'ti60_camera.xml');info=tree.find('{'+ns+'}design_info');info.insert(1,ET.Element('{'+ns+'}design_file',name=(ROOT/'rtl/gesture_snapshot.sv').as_posix(),version='default',library='default'));ET.register_namespace('efx',ns);tree.write(B/'ti60_camera.xml',encoding='utf-8')
    print('Integrated on-board mask snapshot, CPU gesture runtime, current-style keys and static ROI overlay')


if __name__=='__main__':main()
