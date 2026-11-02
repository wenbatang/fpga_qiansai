`timescale 1ns/1ps
module tiles_tb;
reg fast_clk=0;always #3.001 fast_clk=~fast_clk;wire cfg_ready;reg clk=0;always #5 clk=~clk;reg reset=1,start=0;reg[1:0]style=0;wire busy,done,error;wire[31:0]cycles;
wire[29:0]araddr,awaddr;wire arvalid,arready,rready,awvalid,awready,wvalid,wready,bready;
wire[127:0]wdata;reg[127:0]rdata=0;reg rvalid=0,rlast=0,bvalid=0;reg[1:0]rresp=0,bresp=0;
reg[29:0]source_base=30'h00600000;reg cfg_valid=0;reg[15:0]cfg_address=0;reg[31:0]cfg_data=0;
reg raw_mode=0;wire raw_active;wire[127:0]image_stats;
reg[31:0] sr,sg,sb;reg[15:0] pp;
reg[47:0]config_words[0:4867];integer ci;
video_tile_engine_async #(.WIDTH(128),.HEIGHT(24),.TILE_CORE(48)) engine(clk,fast_clk,reset,start,style,raw_mode,raw_active,image_stats,1'b0,source_base,cfg_valid,cfg_address,cfg_data,cfg_ready,busy,done,error,cycles,
 araddr,arvalid,arready,rdata,rresp,rvalid,rlast,rready,awaddr,awvalid,awready,wdata,wvalid,wready,bresp,bvalid,bready);
integer t=0,beat=0,source_index=0,j,k,s,bdelay=0,write_index=0,write_count=0,total_b=0;
reg reading=0,have_aw=0,have_w=0;reg[127:0]saved_word;reg[15:0]raw[0:3071],result[0:3071],expected[0:12287];reg seen[0:3071];
reg[1:0]inject=0;reg injected=0;
assign arready=!reading && !rvalid && t%5!=0;
assign awready=!have_aw && !bvalid && t%7!=0;
assign wready=!have_w && !bvalid && t%3!=0;
reg ar_stalled=0,aw_stalled=0,w_stalled=0;reg[29:0]last_ar,last_aw;reg[127:0]last_w;
always @(posedge clk)begin
 t<=t+1;if(t>8000000)$fatal(1,"timeout");
 if(!reset)begin
  if(ar_stalled && (!arvalid || araddr!==last_ar))$fatal(1,"AR changed under backpressure");
  if(aw_stalled && (!awvalid || awaddr!==last_aw))$fatal(1,"AW changed under backpressure");
  if(w_stalled && (!wvalid || wdata!==last_w))$fatal(1,"W changed under backpressure");
  ar_stalled<=arvalid&&!arready;aw_stalled<=awvalid&&!awready;w_stalled<=wvalid&&!wready;
  last_ar<=araddr;last_aw<=awaddr;last_w<=wdata;
  if(arvalid && arready)begin
   if(araddr[7:0]!=0 || araddr<30'h00600000 || araddr>=30'h00600000+3072*2)$fatal(1,"read address/4KB burst boundary");
   source_index<=(araddr-30'h00600000)/2;beat<=0;reading<=1;
  end
  if(reading && !rvalid && t%4!=0)begin
   for(j=0;j<8;j=j+1)rdata[j*16+:16]<=raw[source_index+beat*8+j];
   rvalid<=1;rlast<=beat==15;
   rresp<=(inject==1 && !injected && beat==3) ? 2:0;
   if(inject==2 && !injected && beat==3)begin rlast<=1;injected<=1;end
   if(inject==1 && !injected && beat==3)injected<=1;
  end
  if(rvalid && rready)begin rvalid<=0;if(rlast)reading<=0;else beat<=beat+1;end
  if(awvalid && awready)begin
   if(awaddr[3:0]!=0 || awaddr>=3072*2)$fatal(1,"write address");
   have_aw<=1;write_index<=awaddr/2;
  end
  if(wvalid && wready)begin have_w<=1;saved_word<=wdata;end
  if(have_aw && have_w && !bvalid && bdelay==0)begin
   for(j=0;j<8;j=j+1)begin
    if(seen[write_index+j])$fatal(1,"duplicate output pixel");
    result[write_index+j]<=saved_word[j*16+:16];seen[write_index+j]<=1;
   end
   write_count<=write_count+1;bdelay<=17;
  end
  if(bdelay>0)begin bdelay<=bdelay-1;if(bdelay==1)begin bvalid<=1;bresp<=(inject==3 && !injected) ? 2:0;if(inject==3 && !injected)injected<=1;end end
  if(bvalid && bready)begin bvalid<=0;have_aw<=0;have_w<=0;total_b<=total_b+1;end
  if(done && (reading || rvalid || have_aw || have_w || bvalid || total_b!=3072/8))$fatal(1,"done preceded final write response");
 end
end
task load_style(input integer which);begin
 for(ci=0;ci<1217;ci=ci+1)begin
 @(negedge clk);cfg_valid=0;while(!cfg_ready)@(negedge clk);cfg_valid=1;{cfg_address,cfg_data}=config_words[which*1217+ci];@(negedge clk);cfg_valid=0;
 end
 @(negedge clk);cfg_valid=0;while(!cfg_ready)@(negedge clk);
end endtask
task check_stats;begin
 sr=0;sg=0;sb=0;
 for(k=0;k<3072;k=k+1)begin
  pp=result[k];sr=sr+{pp[15:11],pp[15:13]};sg=sg+{pp[10:5],pp[10:9]};sb=sb+{pp[4:0],pp[4:2]};
 end
 if(image_stats!=={32'd3072,sr,sg,sb})$fatal(1,"output RGB sum mismatch %h",image_stats);
end endtask
task launch;begin
 repeat(2)@(negedge clk);
 write_count=0;total_b=0;injected=0;
 for(k=0;k<3072;k=k+1)seen[k]=0;
 @(negedge clk);source_base=30'h00600000;start=1;@(negedge clk);start=0;source_base=30'h00800000;raw_mode=!raw_mode;
 wait(done || error);@(negedge clk);
end endtask
initial begin
 $readmemh("F:/fpga_qiansai/elinx/projects/camera_art_styles/sim/runtime/config.mem",config_words);$readmemh("F:/fpga_qiansai/elinx/projects/camera_art_styles/sim/runtime/raw.mem",raw);$readmemh("F:/fpga_qiansai/elinx/projects/camera_art_styles/sim/runtime/expected.mem",expected);
 repeat(5)@(negedge clk);reset=0;
 for(s=0;s<4;s=s+1)begin
  raw_mode=0;style=s;load_style(s);launch();if(error || write_count!=3072/8 || total_b!=3072/8)$fatal(1,"job counters");
  for(k=0;k<3072;k=k+1)if(!seen[k] || result[k]!==expected[s*3072+k])$fatal(1,"style=%0d pixel=%0d got=%h expected=%h",s,k,result[k],expected[s*3072+k]);
  check_stats();if(raw_active)$fatal(1,"style changed to raw mid-job");
  $display("PASS style %0d exact integer pixels, cycles=%0d",s,cycles);
 end
 for(s=1;s<=3;s=s+1)begin inject=s;raw_mode=0;launch();if(done || !error || reading || have_aw || have_w || rvalid || bvalid)$fatal(1,"failed transaction not drained");end
 inject=0;style=2;load_style(2);raw_mode=0;launch();if(error)$fatal(1,"recovery");
 for(k=0;k<3072;k=k+1)if(result[k]!==expected[2*3072+k])$fatal(1,"recovery pixels");
 check_stats();
 raw_mode=1;launch();if(error || !raw_active)$fatal(1,"raw job");
 for(k=0;k<3072;k=k+1)if(!seen[k] || result[k]!==raw[k])$fatal(1,"raw copy mismatch %0d",k);
 check_stats();
 for(s=1;s<=3;s=s+1)begin inject=s;raw_mode=1;launch();if(done || !error || reading || have_aw || have_w || rvalid || bvalid)$fatal(1,"raw failed transaction not drained");end
 inject=0;raw_mode=1;launch();if(error)$fatal(1,"raw recovery");
 for(k=0;k<3072;k=k+1)if(result[k]!==raw[k])$fatal(1,"raw recovery pixels");
 check_stats();
 $display("PASS strip engine: real four models, every seam/edge, global phase, read/write backpressure, final B barrier, RRESP/early RLAST/BRESP errors and next-job recovery; raw preview copy, mode lock across strips, exact output sums and raw fault recovery");$finish;
end
endmodule
