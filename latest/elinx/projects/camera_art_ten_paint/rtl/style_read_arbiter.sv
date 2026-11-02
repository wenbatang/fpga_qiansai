// Two fixed 16-beat AXI read masters; one outstanding burst, display priority.
// Selection is latched before driving AR and held until accepted RLAST.
module style_read_arbiter(
    input wire clk,reset,
    input wire [29:0] display_addr,input wire display_valid,output wire display_ready,
    input wire [29:0] style_addr,input wire style_valid,output wire style_ready,
    output wire [29:0] araddr,output wire arvalid,input wire arready,
    input wire [127:0] rdata,input wire [1:0] rresp,input wire rvalid,rlast,output wire rready,
    output wire [127:0] display_data,output wire [1:0] display_resp,
    output wire display_rvalid,display_last,input wire display_rready,
    output wire [127:0] style_data,output wire [1:0] style_resp,
    output wire style_rvalid,style_last,input wire style_rready);
    localparam IDLE=0,ADDRESS=1,DATA=2;
    reg [1:0] state;
    reg owner;
    reg [29:0] saved_addr;
    assign araddr=saved_addr;
    assign arvalid=state==ADDRESS;
    assign display_ready=state==ADDRESS && !owner && arready;
    assign style_ready=state==ADDRESS && owner && arready;
    assign rready=state==DATA && (owner ? style_rready : display_rready);
    assign display_data=rdata;assign style_data=rdata;
    assign display_resp=rresp;assign style_resp=rresp;
    assign display_last=rlast;assign style_last=rlast;
    assign display_rvalid=state==DATA && !owner && rvalid;
    assign style_rvalid=state==DATA && owner && rvalid;
    always @(posedge clk) begin
        if(reset) begin state<=IDLE;owner<=0;saved_addr<=0;end
        else case(state)
            IDLE: if(display_valid) begin owner<=0;saved_addr<=display_addr;state<=ADDRESS;end
                  else if(style_valid) begin owner<=1;saved_addr<=style_addr;state<=ADDRESS;end
            ADDRESS: if(arready) state<=DATA;
            DATA: if(rvalid && rready && rlast) state<=IDLE;
            default: state<=IDLE;
        endcase
    end
endmodule
