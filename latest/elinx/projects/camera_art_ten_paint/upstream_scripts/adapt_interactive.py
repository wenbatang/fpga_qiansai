"""One-time checked modifications of this independent clone only."""
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]


def replace(path,pairs):
    text=path.read_text(encoding='utf-8')
    for before,after in pairs:
        assert before in text,(path,before);text=text.replace(before,after)
    path.write_text(text,encoding='utf-8')
def main():
    p=ROOT/'rtl/full_pointwise.sv';text=p.read_text(encoding='utf-8')
    start=text.index(' generate if(HEAD)begin:shared');end=text.index(' reg[CONTEXTS-1:0]occupied')
    text=text[:start]+''' full_parameter_bank #(.LAYER(LAYER),.NW(NW),.COUT(COUT)) parameters(.clk(clk),.cfg_valid(cfg_valid),.cfg_address(cfg_address),.cfg_data(cfg_data),.weights(fw),.biases(fb),.shifts(fs));
 genvar n,c,l,k,s;
 generate for(n=0;n<NW;n=n+1)begin:weight_output assign weight[n]=fw[n*8+:8];end
 for(c=0;c<COUT;c=c+1)begin:channel_output assign bias[c]=fb[c*24+:24];assign shift[c]=fs[c*5+:5];end endgenerate
'''+text[end:];p.write_text(text,encoding='utf-8')
    replace(ROOT/'rtl/full_dw3x3.sv',[
      ('full_shared_params #(.LAYER(LAYER),.NW(CHANNELS*9),.COUT(CHANNELS)) constants(.weights(weights),.biases(biases),.shifts(shifts));','full_parameter_bank #(.LAYER(LAYER),.NW(CHANNELS*9),.COUT(CHANNELS)) parameters(.clk(clk),.cfg_valid(cfg_valid),.cfg_address(cfg_address),.cfg_data(cfg_data),.weights(weights),.biases(biases),.shifts(shifts));'),
      ('wire signed[7:0]w=weights[(c*9+rd_row*3+t)*8+:8];','reg signed[7:0]w;\n   always @(posedge clk)if(step && state==READ)w<=weights[(c*9+row_select*3+t)*8+:8];')])
    replace(ROOT/'rtl/full_kernel.sv',[
      ('input wire cfg_valid,input wire[15:0]cfg_address,input wire[31:0]cfg_data);','input wire cfg_valid,input wire[15:0]cfg_address,input wire[31:0]cfg_data,input wire split_mode);'),
      ('reg[31:0]input_count,output_count;reg[15:0]input_x;reg signed[15:0]origin;','reg[31:0]input_count,output_count;reg[15:0]input_x,output_x;reg signed[15:0]origin;\n reg split_active;reg signed[17:0]split_limit;'),
      ('assign out_rgb={clip(blue),clip(green),clip(red)};','wire left_half=$signed({1\'b0,output_x})<$signed(split_limit);\n assign out_rgb=split_active && left_half?raw_word:{clip(blue),clip(green),clip(red)};'),
      ('if(take)begin output_count<=output_count+1;','if(take)begin output_x<=output_x==WIDTH-1?0:output_x+1\'b1;output_count<=output_count+1;'),
      ('input_x<=0;origin<=origin_x;','input_x<=0;output_x<=0;origin<=origin_x;split_active<=split_mode;split_limit<=FRAME_WIDTH/2-$signed(origin_x);')])
    replace(ROOT/'rtl/full_view.sv',[
      ('input wire cfg_valid,input wire[15:0]cfg_address,input wire[31:0]cfg_data);','input wire cfg_valid,input wire[15:0]cfg_address,input wire[31:0]cfg_data,input wire split_mode);'),
      ('.cfg_data(cfg_data));','.cfg_data(cfg_data),.split_mode(split_mode));')])
    replace(ROOT/'rtl/p720/video_cnn_async.sv',[
      ('.raw_mode(fast_start[0]),.origin_x(fast_start[22:7]),','.raw_mode(fast_start[0]),.split_mode(fast_start[6]),.origin_x(fast_start[22:7]),')])
    replace(ROOT/'rtl/p720/video_system_720.sv',[
      ('wire key_event,busy,completed,failed,raw_mode,engine_raw;','wire key_event,busy,completed,failed,raw_mode,engine_raw,split_mode;\n wire[1:0]display_mode;reg[1:0]job_mode,front_mode,front_style,job_style;reg[1:0]bank_modes[0:2],bank_styles[0:2];integer mode_index;'),
      ('.event_style(key_style),.raw_mode(raw_mode));','.event_style(key_style),.raw_mode(raw_mode),.display_mode(display_mode),.split_mode(split_mode));'),
      ('.style(loaded_style),.raw_mode(raw_mode)',".style({split_mode,3'b000,loaded_style[1:0]}),.raw_mode(raw_mode)"),
      ('if(reset)begin neural_frames<=0;front_raw<=1;end','if(reset)begin neural_frames<=0;front_raw<=1;job_mode<=0;front_mode<=0;job_style<=0;front_style<=0;for(mode_index=0;mode_index<3;mode_index=mode_index+1)begin bank_modes[mode_index]<=0;bank_styles[mode_index]<=0;end end'),
      ('if(engine_done && !engine_raw)neural_frames<=neural_frames+1\'b1;',"if(engine_start)begin job_mode<=display_mode;job_style<=loaded_style[1:0];end\n   if(engine_done)begin bank_modes[output_bank]<=job_mode;bank_styles[output_bank]<=job_style;end\n   if(engine_done && !engine_raw)neural_frames<=neural_frames+1'b1;"),
      ('if(commit_ack)front_raw<=commit_raw;','if(commit_ack)begin front_raw<=commit_raw;front_mode<=bank_modes[commit_bank];front_style<=bank_styles[commit_bank];end'),
      ("{17'd0,front_raw,requested_style,loaded_style,engine_raw,raw_mode}","{9'd0,front_style,job_mode,front_mode,display_mode,front_raw,requested_style,loaded_style,engine_raw,raw_mode}")])
    replace(ROOT/'rtl/board_boot.sv',[("if(!sync_keys[0] && !sync_keys[3])begin","if(!sync_keys[3])begin"),('// All four V4 keys select styles. KEY0+KEY3 held for one second reset','// KEY0 display / KEY1 next / KEY2 previous. KEY3 held for one second resets')])
    replace(ROOT/'scripts/native_constraints.py',[("for i in (0,3)","for i in (3,)"),("len(report['scalar_first_stages'])==24","len(report['scalar_first_stages'])==23")])
    p=ROOT/'rtl/view/camera_view_uart.sv';text=p.read_text(encoding='utf-8');assert "8'h34" in text or '"4"' in text
    text=text.replace("8'h34","8'h35").replace('"4"','"5"').replace('CAM4','CAM5');p.write_text(text,encoding='utf-8')
    ns='http://www.efinixinc.com/enf_proj';path=ROOT/'build/720p/ti60_camera.xml';tree=ET.parse(path);info=tree.find('{'+ns+'}design_info')
    for node in list(info):
        if node.tag=='{'+ns+'}design_file' and Path(node.get('name')).name=='full_shared_params.sv':info.remove(node)
    info.insert(1,ET.Element('{'+ns+'}design_file',name=(ROOT/'rtl/full_parameter_bank.sv').as_posix(),version='default',library='default'))
    ET.register_namespace('efx',ns);tree.write(path,encoding='utf-8');print('Runtime DW/head and same-frame split renderer adapted')


if __name__=='__main__':main()
