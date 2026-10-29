// Two single-beat AXI128 masters, one outstanding transaction per master.
// AW/W pairs issue in grant order; the next pair may issue after BOTH channels
// have handshaken, without waiting for B. Same-ID B responses MUST be ordered.
// The two-entry owner FIFO reserves at grant and becomes response-eligible only
// after that pair's AW and W complete. Credits retire ONLY on the actual B
// handshake; no early/synthetic upstream response or final-frame publication.
module axi_write_pair_fps(input wire clk,reset,
 input wire[29:0] a_addr,b_addr,input wire a_awvalid,b_awvalid,output wire a_awready,b_awready,
 input wire[127:0] a_data,b_data,input wire a_wvalid,b_wvalid,output wire a_wready,b_wready,
 output wire a_bvalid,b_bvalid,input wire a_bready,b_bready,output wire[1:0] a_resp,b_resp,
 output wire[29:0] awaddr,output wire awvalid,input wire awready,
 output wire[127:0] wdata,output wire wvalid,input wire wready,
 input wire[1:0] bresp,input wire bvalid,output wire bready);
 reg active,owner,last_owner,aw_done,w_done,active_slot;
 reg[1:0]owned,queue_owner,queue_sent;
 reg read_ptr,write_ptr;reg[1:0]count;
 wire request_a=(a_awvalid || a_wvalid) && !owned[0];
 wire request_b=(b_awvalid || b_wvalid) && !owned[1];
 wire grant=!active && count<2 && (request_a || request_b);
 wire grant_owner=request_a && request_b ? !last_owner:request_b;
 wire selected_aw=owner ? b_awvalid:a_awvalid;
 wire selected_w=owner ? b_wvalid:a_wvalid;
 wire take_aw=awvalid && awready,take_w=wvalid && wready;
 wire pair_done=active && (aw_done || take_aw) && (w_done || take_w);
 wire response_eligible=count!=0 && queue_sent[read_ptr];
 wire response_owner=queue_owner[read_ptr];
 wire retire=bvalid && bready;
 assign awaddr=owner ? b_addr:a_addr;assign wdata=owner ? b_data:a_data;
 assign awvalid=active && !aw_done && selected_aw;
 assign wvalid=active && !w_done && selected_w;
 assign a_awready=active && !owner && !aw_done && awready;
 assign b_awready=active && owner && !aw_done && awready;
 assign a_wready=active && !owner && !w_done && wready;
 assign b_wready=active && owner && !w_done && wready;
 assign a_bvalid=response_eligible && !response_owner && bvalid;
 assign b_bvalid=response_eligible && response_owner && bvalid;
 assign a_resp=bresp;assign b_resp=bresp;
 assign bready=response_eligible && (response_owner ? b_bready:a_bready);
 always @(posedge clk)begin
  if(reset)begin
   active<=0;owner<=0;last_owner<=1;aw_done<=0;w_done<=0;active_slot<=0;
   owned<=0;queue_owner<=0;queue_sent<=0;read_ptr<=0;write_ptr<=0;count<=0;
  end else begin
   case({grant,retire})
    2'b10:count<=count+1'b1;
    2'b01:count<=count-1'b1;
    default:begin end
   endcase
   if(retire)begin
    owned[response_owner]<=0;queue_sent[read_ptr]<=0;read_ptr<=!read_ptr;
   end
   if(grant)begin
    active<=1;owner<=grant_owner;last_owner<=grant_owner;aw_done<=0;w_done<=0;
    active_slot<=write_ptr;queue_owner[write_ptr]<=grant_owner;queue_sent[write_ptr]<=0;
    write_ptr<=!write_ptr;owned[grant_owner]<=1;
   end
   if(take_aw)aw_done<=1;
   if(take_w)w_done<=1;
   if(pair_done)begin active<=0;queue_sent[active_slot]<=1;end
  end
 end
endmodule
