// Sapphire APB3 control plane. Pixel traffic never passes through the CPU.
// Single active weight set, modified only while the accelerator is idle. Pending display buffers retain their own frame ownership.
module video_control_apb_fast(input wire clk,reset,
 input wire [15:0] paddr,input wire psel,penable,pwrite,input wire[31:0] pwdata,
 output reg[31:0] prdata,output wire pready,output reg pslverror,
 input wire cfg_ready,busy,source_valid,input wire[31:0] source_frame,engine_cycles,inference_frames,capture_frames,dropped_frames,
 input wire completed,failed,camera_fault,key_event,input wire[5:0] key_style,
 input wire scl_in,sda_in,
 output reg capture_enable,sensor_reset_n,overlay_enable,
 output reg scl_release,sda_release,output reg start,
 output reg cfg_valid,output reg[15:0] cfg_address,output reg[31:0] cfg_data,
 output reg weights_valid,output reg[5:0] loaded_style,requested_style,
 output wire irq);
 localparam integer WEIGHT_WRITES=346;
 reg[31:0] irq_pending,irq_mask,boot_status,ticks;
 reg[15:0] cfg_count;
 reg[15:0] weight_address;
 reg[5:0] load_target;
 (* async_reg="true",syn_srlstyle="registers" *) reg[1:0] scl_sync,sda_sync;
 wire access=psel && penable;
 wire write_access=access && pwrite && pready;
 reg[3:0]load_layer;reg[9:0]load_item;reg[1:0]load_kind;
 wire[9:0]weight_count=load_layer==0?216:load_layer==9?24:load_layer[0]?72:64;
 wire[9:0]channel_count=load_layer==9?3:8;
 wire[15:0]expected_address={load_layer,load_kind,load_item};
 wire config_legal=weight_address==expected_address && load_layer<10 &&
   (load_kind!=2 || pwdata<=20) && (load_kind!=1 || pwdata[31:23]=={9{pwdata[23]}});
 (* syn_romstyle="block_rom" *)reg[31:0]parameter_rom[0:1215];reg[31:0]parameter_word;
 initial $readmemh("weights47.mem",parameter_rom);
 wire rom_selected=paddr>=16'h1000 && paddr<16'h2300;
 always @(posedge clk)if(psel && !pwrite && rom_selected)parameter_word<=parameter_rom[(paddr-16'h1000)>>2];
 // Wait for the previous atomic parameter write to reach the CNN clock.
 assign pready=!(access && pwrite && (paddr==16'h0054 || paddr==16'h0030) && (!cfg_ready || cfg_valid));
 assign irq=|(irq_pending & irq_mask);
 always @* begin
  prdata=0;pslverror=0;
  case(paddr)
   16'h0000:prdata=32'h53565931;
   16'h0004:prdata={29'd0,overlay_enable,sensor_reset_n,capture_enable};
   16'h0008:prdata={28'd0,weights_valid,source_valid,1'b0,busy};
   16'h000c:prdata=irq_pending;
   16'h0010:prdata=irq_mask;
   16'h0014:prdata=source_frame;
   16'h0018:prdata=engine_cycles;
   16'h001c:prdata=inference_frames;
   16'h0020:prdata=capture_frames;
   16'h0024:prdata=dropped_frames;
   16'h0028:prdata={26'd0,requested_style};
   16'h002c:prdata={25'd0,weights_valid,loaded_style};
   16'h0030:begin
    if(write_access && ((pwdata[0] && (busy || !weights_valid || !source_valid)) ||
      ((pwdata[1] || pwdata[2]) && busy) || (pwdata[2] && cfg_count!=WEIGHT_WRITES)))pslverror=1;
   end
   16'h0040:prdata={30'd0,scl_release,sda_release};
   16'h0044:prdata={30'd0,scl_sync[1],sda_sync[1]};
   16'h0048:prdata=ticks;
   16'h0050:prdata={16'd0,weight_address};
   16'h0054:if(write_access && (busy || weights_valid || !config_legal || cfg_count>=WEIGHT_WRITES))pslverror=1;
   16'h0058:prdata={16'd0,cfg_count};
   16'h0060:prdata=boot_status;
   default:if(rom_selected && !pwrite)prdata=parameter_word;else if(access)pslverror=1;
  endcase
 end
 always @(posedge clk)begin
  if(reset)begin
   capture_enable<=0;sensor_reset_n<=0;overlay_enable<=1;scl_release<=1;sda_release<=1;
   start<=0;cfg_valid<=0;cfg_address<=0;cfg_data<=0;weight_address<=0;cfg_count<=0;
   load_layer<=0;load_item<=0;load_kind<=0;weights_valid<=0;loaded_style<=0;requested_style<=0;load_target<=0;irq_pending<=0;irq_mask<=0;boot_status<=0;ticks<=0;
   scl_sync<=3;sda_sync<=3;
  end else begin
   scl_sync<={scl_sync[0],scl_in};sda_sync<={sda_sync[0],sda_in};ticks<=ticks+1;
   start<=0;cfg_valid<=0;
   if(write_access && !pslverror)case(paddr)
    16'h0004:begin capture_enable<=pwdata[0];sensor_reset_n<=pwdata[1];overlay_enable<=pwdata[2];end
    16'h000c:irq_pending<=irq_pending & ~pwdata;
    16'h0010:irq_mask<=pwdata;
    16'h0028:requested_style<=pwdata<4?pwdata[5:0]:0;
    16'h002c:if(!busy)load_target<=pwdata<4?pwdata[5:0]:0;
    16'h0030:begin
     if(pwdata[0])start<=1;
     if(pwdata[1])begin weights_valid<=0;cfg_count<=0;load_layer<=0;load_item<=0;load_kind<=0;end
     if(pwdata[2])begin weights_valid<=1;loaded_style<=load_target;end
    end
    16'h0040:begin scl_release<=pwdata[1];sda_release<=pwdata[0];end
    16'h0050:weight_address<=pwdata[15:0];
    16'h0054:begin cfg_valid<=1;cfg_address<=weight_address;cfg_data<=pwdata;cfg_count<=cfg_count+1;
     if(load_kind==0)begin
      if(load_item==weight_count-4)begin load_item<=0;load_kind<=1;end else load_item<=load_item+4;
     end else if(load_item==channel_count-1)begin
      load_item<=0;
      if(load_kind==1)load_kind<=2;else begin load_kind<=0;load_layer<=load_layer+1;end
     end else load_item<=load_item+1;
    end
    16'h0060:boot_status<=pwdata;
    default:begin end
   endcase
   // Events win over a simultaneous W1C (no lost completion interrupt).
   if(completed)irq_pending[0]<=1;
   if(failed)irq_pending[1]<=1;
   if(camera_fault)irq_pending[2]<=1;
   if(key_event)begin requested_style<=key_style<4?key_style:0;irq_pending[3]<=1;end
  end
 end
endmodule
