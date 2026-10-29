// CSI debug/error status lives on axi_clk, which is the UI clock here.
// Clear W1C errors only after frame-end, so EOF validation sees sticky errors.
// AW and W handshakes are independent; keep each VALID until acknowledged.
module csi_status_clear(input wire clk,reset,vs,
 output wire awvalid,input wire awready,output wire wvalid,input wire wready,
 input wire bvalid,output wire bready);
 reg vs_d,pending,active,aw_done,w_done;
 assign awvalid=active && !aw_done;
 assign wvalid=active && !w_done;
 assign bready=active && aw_done && w_done;
 always @(posedge clk)begin
  if(reset)begin vs_d<=0;pending<=1;active<=0;aw_done<=0;w_done<=0;end
  else begin
   vs_d<=vs;
   if(!active && pending)begin active<=1;pending<=0;aw_done<=0;w_done<=0;end
   if(vs_d && !vs)pending<=1;
   if(awvalid && awready)aw_done<=1;
   if(wvalid && wready)w_done<=1;
   if(bvalid && bready)active<=0;
  end
 end
endmodule
