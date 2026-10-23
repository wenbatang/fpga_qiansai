// Sapphire APB3 control plane. Pixel traffic never passes through the CPU.
// Single active weight set, modified only while the engine/display commit is idle.
module video_control_apb(input wire clk,reset,
 input wire [15:0] paddr,input wire psel,penable,pwrite,input wire[31:0] pwdata,
 output reg[31:0] prdata,output wire pready,output reg pslverror,
 input wire busy,source_valid,input wire[31:0] source_frame,engine_cycles,inference_frames,capture_frames,dropped_frames,
 input wire completed,failed,camera_fault,key_event,input wire[1:0] key_style,
 input wire scl_in,sda_in,
 output reg capture_enable,sensor_reset_n,overlay_enable,
 output reg scl_release,sda_release,output reg start,
 output reg cfg_valid,output reg[15:0] cfg_address,output reg[31:0] cfg_data,
 output reg weights_valid,output reg[1:0] loaded_style,requested_style,
 output wire irq);
 localparam integer WEIGHT_WRITES=1436;
 reg[31:0] irq_pending,irq_mask,boot_status,ticks;
 reg[15:0] cfg_count;
 reg[15:0] weight_address;
 reg[1:0] load_target;
 (* async_reg="true",syn_srlstyle="registers" *) reg[1:0] scl_sync,sda_sync;
 wire access=psel && penable;
 wire write_access=access && pwrite;
 wire config_legal=weight_address[13:11]<5 &&
  ((weight_address[15:14]==0 && weight_address[10:7]<9 &&
    weight_address[6:0]<(weight_address[13:11]==0 ? 30:weight_address[13:11]==4 ? 18:36)) ||
   (weight_address[15:14]==1 && weight_address[10:7]==0 &&
    weight_address[6:0]<(weight_address[13:11]==4 ? 3:6)) ||
   (weight_address[15:14]==2 && weight_address[10:0]==0 && pwdata<=31));
 assign pready=1'b1;
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
   16'h0028:prdata={30'd0,requested_style};
   16'h002c:prdata={29'd0,weights_valid,loaded_style};
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
   default:if(access)pslverror=1;
  endcase
 end
 always @(posedge clk)begin
  if(reset)begin
   capture_enable<=0;sensor_reset_n<=0;overlay_enable<=1;scl_release<=1;sda_release<=1;
   start<=0;cfg_valid<=0;cfg_address<=0;cfg_data<=0;weight_address<=0;cfg_count<=0;
   weights_valid<=0;loaded_style<=0;requested_style<=0;load_target<=0;irq_pending<=0;irq_mask<=0;boot_status<=0;ticks<=0;
   scl_sync<=3;sda_sync<=3;
  end else begin
   scl_sync<={scl_sync[0],scl_in};sda_sync<={sda_sync[0],sda_in};ticks<=ticks+1;
   start<=0;cfg_valid<=0;
   if(write_access && !pslverror)case(paddr)
    16'h0004:begin capture_enable<=pwdata[0];sensor_reset_n<=pwdata[1];overlay_enable<=pwdata[2];end
    16'h000c:irq_pending<=irq_pending & ~pwdata;
    16'h0010:irq_mask<=pwdata;
    16'h0028:requested_style<=pwdata[1:0];
    16'h002c:if(!busy)load_target<=pwdata[1:0];
    16'h0030:begin
     if(pwdata[0])start<=1;
     if(pwdata[1])begin weights_valid<=0;cfg_count<=0;end
     if(pwdata[2])begin weights_valid<=1;loaded_style<=load_target;end
    end
    16'h0040:begin scl_release<=pwdata[1];sda_release<=pwdata[0];end
    16'h0050:weight_address<=pwdata[15:0];
    16'h0054:begin cfg_valid<=1;cfg_address<=weight_address;cfg_data<=pwdata;cfg_count<=cfg_count+1;end
    16'h0060:boot_status<=pwdata;
    default:begin end
   endcase
   // Events win over a simultaneous W1C (no lost completion interrupt).
   if(completed)irq_pending[0]<=1;
   if(failed)irq_pending[1]<=1;
   if(camera_fault)irq_pending[2]<=1;
   if(key_event)begin requested_style<=key_style;irq_pending[3]<=1;end
  end
 end
endmodule
