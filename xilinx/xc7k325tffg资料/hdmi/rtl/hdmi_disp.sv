module hdmi_disp(
    input   logic           pixel_clk   ,
    input   logic           sys_rst_n   ,

    input   logic [10:0]    pixel_xpos  ,
    input   logic [10:0]    pixel_ypos  ,

    output  logic [23:0]    pixel_data
);

// 24-bit RGB counter: increments by 1 every pixel clock,
// cycles from 0x000000 to 0xffffff continuously.
//logic [23:0] rgb_cnt;

//always @(posedge pixel_clk or negedge sys_rst_n) begin
//    if (!sys_rst_n)
//        rgb_cnt <= 24'd0;
//    else
//        rgb_cnt <= rgb_cnt + 1'b1;
//end

//assign pixel_data = rgb_cnt;

 localparam  [10:0]  H_DISP  = 11'd1280      ;
 localparam  [10:0]  Y_DISP  = 11'd720       ;

 localparam  [23:0]  WHITE   = 24'hff_ffff   ;
 localparam  [23:0]  RED     = 24'hff_0000   ;
 localparam  [23:0]  GREEN   = 24'h00_ff00   ;
 localparam  [23:0]  BLUE    = 24'h00_00ff   ;
 localparam  [23:0]  BLACK   = 24'h00_0000   ;


 always @(posedge pixel_clk ) begin
     if (!sys_rst_n)
         pixel_data <= 24'd0;
     else begin
         if((pixel_xpos >= 0) && (pixel_xpos < (H_DISP/5)*1))
             pixel_data <= WHITE;
         else if((pixel_xpos >= (H_DISP/5)*1) && (pixel_xpos < (H_DISP/5)*2))
             pixel_data <= BLACK;  
         else if((pixel_xpos >= (H_DISP/5)*2) && (pixel_xpos < (H_DISP/5)*3))
             pixel_data <= RED;  
         else if((pixel_xpos >= (H_DISP/5)*3) && (pixel_xpos < (H_DISP/5)*4))
             pixel_data <= GREEN;
         else 
             pixel_data <= BLUE;
     end
 end

endmodule