// UI-domain, on-demand complete-frame 64x64 RGB565 hand ROI snapshot.
// One immutable CPU-owned buffer: REQUEST -> next SOF -> good EOF -> ACK.
// Preserve color: no fixed skin threshold can discard green-cast hands here.
module gesture_snapshot #(
 parameter WIDTH=1280,HEIGHT=720,ROI_X=0,ROI_Y=40,STEP=10,SIDE=64
)(input wire clk,reset,enable,cancel,input wire learn_event,capture_event,
 input wire frame_start,frame_end,frame_bad,pixel_valid,input wire[31:0]pixels,
 input wire[15:0]paddr,input wire psel,penable,pwrite,input wire[31:0]pwdata,
 output reg[31:0]prdata,output wire selected,output reg pslverror,
 output reg[10:0]cpu_status,output wire[255:0]diagnostics,output wire guard_event,output wire[5:0]guard_style);
 localparam N=SIDE*SIDE,WORDS=N/2;
 reg pending,active,ready,enabled_d;reg[10:0]x,y;
 localparam PHASE_BITS=$clog2(STEP+1);reg[PHASE_BITS-1:0]x_phase,y_phase;
 reg[12:0]samples;reg[15:0]low_pixel;reg[31:0]sequence_id,frame_id,epoch,cost;
 reg[31:0]reports,reason,hits,geometry,mean_rgb;
 reg[1:0]event_pending;
 reg[31:0]token_epoch,guard_result;
 (* ram_style="block" *)reg[31:0]mask[0:WORDS-1];reg[31:0]read_word;
 assign selected=(paddr>=16'h0080 && paddr<=16'h00bc) || (paddr>=16'h2000 && paddr<16'h4000);
 wire access=psel && penable && selected;
 wire write_access=access && pwrite && !pslverror;
 wire mask_selected=paddr>=16'h2000 && paddr<16'h4000;
 always @(posedge clk)if(psel && !pwrite && mask_selected)read_word<=mask[paddr[12:2]];
 assign diagnostics={sequence_id,reports,reason,hits,geometry,mean_rgb,cost,
  epoch[14:0],samples,enable,pending,active,ready};
 wire request_now=write_access && paddr==16'h008c && pwdata==1;
 wire ack_now=write_access && paddr==16'h008c && pwdata==2;
 wire guard_write=write_access && paddr==16'h00b8;
 wire guard_enabled=!reset && enable && !cancel && !cpu_status[10] && !event_pending[0] && !learn_event;
 // Combinational ACCESS strobe: control consumes the request at the same edge
 // that records accepted. Registering this pulse would reopen a one-edge race.
 assign guard_event=guard_write && pwdata<10 && token_epoch==epoch && guard_enabled;
 assign guard_style=pwdata[5:0];
 // x is the left/even pixel of a two-pixel beat. For STEP10, use offset4
 // (not5, which can never match that counter); row offset5 is unrestricted.
 wire sample_pixel=active && pixel_valid && x>=ROI_X && x<ROI_X+SIDE*STEP &&
  y>=ROI_Y && y<ROI_Y+SIDE*STEP && x_phase==(ROI_X+(STEP/2/2)*2)%STEP && y_phase==(ROI_Y+STEP/2)%STEP;
 always @*begin
  prdata=0;pslverror=access && paddr[1:0]!=0;
  case(paddr)
   16'h0080:prdata={28'd0,enable,pending,active,ready};
   16'h0084:prdata=sequence_id;
   16'h0088:prdata=epoch;
   16'h008c:if(access && pwrite && pwdata!=1 && pwdata!=2)pslverror=1;
   16'h0090:prdata={21'd0,cpu_status};
   16'h0094:prdata=cost;
   16'h00a0:prdata=reports;
   16'h00a4:prdata=reason;
   16'h00a8:prdata=hits;
   16'h00ac:prdata=geometry;
   16'h00b0:prdata=mean_rgb;
   16'h00b4:begin prdata={30'd0,event_pending};if(access && pwrite && pwdata[31:2]!=0)pslverror=1;end
   16'h00b8:prdata=guard_result;
   16'h00bc:prdata=token_epoch;
   default:if(mask_selected && !pwrite)prdata=read_word;else if(access)pslverror=1;
  endcase
  if(access && pwrite && !(paddr==16'h008c || paddr==16'h0090 || paddr==16'h0094 ||
   paddr==16'h00a0 || paddr==16'h00a4 || paddr==16'h00a8 || paddr==16'h00ac || paddr==16'h00b0 || paddr==16'h00b4 || paddr==16'h00b8 || paddr==16'h00bc))pslverror=1;
 end
 always @(posedge clk)begin
  if(reset)begin pending<=0;active<=0;ready<=0;x<=0;y<=0;x_phase<=0;y_phase<=0;samples<=0;low_pixel<=0;sequence_id<=0;frame_id<=0;epoch<=0;enabled_d<=0;cpu_status<=0;cost<=0;reports<=0;reason<=0;hits<=0;geometry<=0;mean_rgb<=0;event_pending<=0;token_epoch<=0;guard_result<=0;end
  else begin
   enabled_d<=enable;
   if(write_access)case(paddr)
    16'h008c:if(pwdata==2)begin ready<=0;pending<=0;end else if(enable && !active && !ready)pending<=1;
    16'h0090:cpu_status<=pwdata[10:0];
    16'h0094:cost<=pwdata;
    16'h00a0:reports<=pwdata;
    16'h00a4:reason<=pwdata;
    16'h00a8:hits<=pwdata;
    16'h00ac:geometry<=pwdata;
    16'h00b0:mean_rgb<=pwdata;
    16'h00b4:event_pending<=event_pending & ~pwdata[1:0];
    16'h00bc:token_epoch<=pwdata;
    16'h00b8:guard_result<=pwdata>=10?4:token_epoch!=epoch?2:!guard_enabled?3:1;
   endcase
   if(frame_start)begin
    frame_id<=frame_id+1'b1;x<=0;y<=0;x_phase<=0;y_phase<=0;
    active<=enable && (pending || request_now) && !ready && !ack_now;pending<=0;
    if(enable && (pending || request_now) && !ready && !ack_now)begin samples<=0;low_pixel<=0;end
   end else if(pixel_valid)begin
    if(x==WIDTH-2)begin x<=0;y<=y+1'b1;x_phase<=0;y_phase<=y_phase==STEP-1?0:y_phase+1'b1;end
    else begin x<=x+2;x_phase<=x_phase>=STEP-2?x_phase-(STEP-2):x_phase+2;end
   end
   if(sample_pixel && !frame_start)begin
    samples<=samples+1'b1;
    if(!samples[0])low_pixel<=pixels[15:0];
    else mask[samples[11:1]]<={pixels[15:0],low_pixel};
   end
   if(frame_end)begin active<=0;if(active && !frame_bad && samples==N)begin ready<=1;sequence_id<=frame_id;end end
   // Mode/manual changes invalidate every old snapshot, even if CPU is reading.
   // CPU rechecks epoch+sequence+ready after its last read before classifying.
   // Learning is CPU-owned state, so mode gating clears candidates but retains
   // bit10 even while waiting for the first RAW front buffer to be committed.
   if(!enable || cancel || (write_access && paddr==16'h008c && pwdata==2))begin active<=0;pending<=0;ready<=0;if(!enable || cancel)cpu_status[9:0]<=0;end
   if(cancel || enabled_d!=enable)epoch<=epoch+1'b1;
   // CPU may read commands while recognition is disabled. Events win W1C.
   if(learn_event)event_pending[0]<=1;
   if(capture_event)event_pending[1]<=1;
  end
 end
endmodule
