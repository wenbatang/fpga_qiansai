// datatype is CSI BYTE-domain sideband, not associated pixel-domain metadata.
// Unexpected RAW encoding latches a fault until the complete CSI reset. Only
// this stable single-bit status crosses to UI. Debug/ppc already use UI clocks.
module camera_format_guard(input wire byte_clk,byte_reset,
 input wire[5:0] datatype,input wire ui_clk,ui_reset,output wire fault);
 reg byte_fault;
 (* async_reg="true",syn_srlstyle="registers" *) reg[1:0] fault_sync;
 always @(posedge byte_clk or posedge byte_reset)
  if(byte_reset)byte_fault<=0;
  else if(datatype>=6'h28 && datatype<=6'h2f && datatype!=6'h2b)byte_fault<=1;
 always @(posedge ui_clk)
  if(ui_reset)fault_sync<=0;
  else fault_sync<={fault_sync[0],byte_fault};
 assign fault=fault_sync[1];
endmodule
