// Two single-beat AXI128 masters. Round-robin transaction arbitration,
// held from selection through B; independently accepted AW and W are legal.
module axi_write_pair(input wire clk,reset,
 input wire[29:0] a_addr,b_addr,input wire a_awvalid,b_awvalid,output wire a_awready,b_awready,
 input wire[127:0] a_data,b_data,input wire a_wvalid,b_wvalid,output wire a_wready,b_wready,
 output wire a_bvalid,b_bvalid,input wire a_bready,b_bready,output wire[1:0] a_resp,b_resp,
 output wire[29:0] awaddr,output wire awvalid,input wire awready,
 output wire[127:0] wdata,output wire wvalid,input wire wready,
 input wire[1:0] bresp,input wire bvalid,output wire bready);
 reg active,owner,last_owner,aw_done,w_done;
 wire selected_aw=owner ? b_awvalid:a_awvalid;
 wire selected_w=owner ? b_wvalid:a_wvalid;
 assign awaddr=owner ? b_addr:a_addr;assign wdata=owner ? b_data:a_data;
 assign awvalid=active && !aw_done && selected_aw;
 assign wvalid=active && !w_done && selected_w;
 assign a_awready=active && !owner && !aw_done && awready;
 assign b_awready=active && owner && !aw_done && awready;
 assign a_wready=active && !owner && !w_done && wready;
 assign b_wready=active && owner && !w_done && wready;
 assign a_bvalid=active && !owner && aw_done && w_done && bvalid;
 assign b_bvalid=active && owner && aw_done && w_done && bvalid;
 assign a_resp=bresp;assign b_resp=bresp;
 assign bready=active && aw_done && w_done && (owner ? b_bready:a_bready);
 always @(posedge clk)begin
  if(reset)begin active<=0;owner<=0;last_owner<=1;aw_done<=0;w_done<=0;end
  else if(!active)begin
   if(a_awvalid || b_awvalid)begin
    owner<=a_awvalid && b_awvalid ? !last_owner:b_awvalid;
    active<=1;aw_done<=0;w_done<=0;
   end
  end else begin
   if(awvalid && awready)aw_done<=1;
   if(wvalid && wready)w_done<=1;
   if(bvalid && bready)begin active<=0;last_owner<=owner;end
  end
 end
endmodule
