// Diagnostic-only overlay. Metrics cross in one acknowledged mailbox tuple; decimal conversion
// uses 128 pixel clocks at frame start and is finished before OSD line104.
module style_perf_overlay(
    input wire core_clk,core_rst_n,pixel_clk,pixel_rst_n,async_rst_n,
    input wire [1023:0] snapshot,
    input wire snapshot_valid,
    input wire [15:0] x,y,
    input wire [23:0] input_rgb,
    output reg [23:0] rgb
);
    function [31:0] limit32(input [63:0] v);
        limit32=|v[63:32]?32'hffffffff:v[31:0];
    endfunction
    wire [607:0] selected={snapshot[32+:32],snapshot[30*32+:32],snapshot[29*32+:32],snapshot[28*32+:32],
        snapshot[27*32+:32],snapshot[26*32+:32],snapshot[25*32+:32],snapshot[24*32+:32],
        snapshot[23*32+:32],snapshot[22*32+:32],limit32(snapshot[18*32+:64]),
        limit32(snapshot[20*32+:64]),limit32(snapshot[16*32+:64]),snapshot[10*32+:32],
        snapshot[9*32+:32],snapshot[7*32+:32],snapshot[5*32+:32],snapshot[4*32+:32],snapshot[3*32+:32]};
    // Bundled-data mailbox: the source holds every payload bit unchanged until
    // a two-flop-synchronized acknowledgement returns. The destination samples
    // only after the request passed two flops, then acknowledges that capture.
    wire src_rst_n=core_rst_n && async_rst_n;
    wire dst_rst_n=pixel_rst_n && async_rst_n;
    reg [607:0] newest,mailbox_data;
    reg dirty,request_toggle;
    reg acknowledge_toggle;
    (* async_reg="true" *) reg ack_meta,ack_sync,request_meta,request_sync;
    always @(posedge core_clk or negedge src_rst_n) begin
        if(!src_rst_n) begin ack_meta<=0;ack_sync<=0;end
        else begin ack_meta<=acknowledge_toggle;ack_sync<=ack_meta;end
    end
    always @(posedge pixel_clk or negedge dst_rst_n) begin
        if(!dst_rst_n) begin request_meta<=0;request_sync<=0;end
        else begin request_meta<=request_toggle;request_sync<=request_meta;end
    end
    always @(posedge core_clk or negedge src_rst_n) begin
        if(!src_rst_n) begin newest<=0;mailbox_data<=0;dirty<=0;request_toggle<=0;end
        else begin
            if(request_toggle==ack_sync && dirty) begin
                mailbox_data<=newest;request_toggle<=~request_toggle;dirty<=0;
            end
            if(snapshot_valid) begin newest<=selected;dirty<=1;end
        end
    end
    reg [607:0] latest,shown;
    reg seen,shown_valid,decimal_ready;
    reg [6:0] frames;
    reg [1:0] page,field;
    wire [1:0] next_page=frames==119?page+2'd1:page;
    reg busy;
    reg [5:0] step;
    reg [31:0] binary;
    reg [39:0] bcd,digits[0:3],adjusted;
    wire [39:0] next_bcd={adjusted[38:0],binary[31]};
    integer i;
    function [31:0] metric(input [607:0] v,input [1:0] p,input [1:0] n);
        begin
            case(p)
                0:metric=v[(2+n)*32+:32];
                1:case(n) 0:metric=v[6*32+:32];1:metric=v[8*32+:32];2:metric=v[7*32+:32];default:metric=v[10*32+:32];endcase
                2:case(n) 0:metric=v[9*32+:32];1:metric=v[11*32+:32];2:metric=v[13*32+:32];default:metric=v[14*32+:32];endcase
                default:case(n) 0:metric={16'b0,v[17*32+:16]};1:metric={16'b0,v[17*32+16+:16]};2:metric=v[15*32+:32];default:metric=v[16*32+:32];endcase
            endcase
        end
    endfunction
    always @* begin
        adjusted=bcd;
        for(integer d=0;d<10;d=d+1) if(bcd[d*4+:4]>=5) adjusted[d*4+:4]=bcd[d*4+:4]+4'd3;
    end
    always @(posedge pixel_clk or negedge dst_rst_n) begin
        if(!dst_rst_n) begin
            acknowledge_toggle<=0;latest<=0;shown<=0;seen<=0;shown_valid<=0;decimal_ready<=0;frames<=0;page<=0;
            field<=0;busy<=0;step<=0;binary<=0;bcd<=0;
            for(i=0;i<4;i=i+1)digits[i]<=0;
        end else begin
            if(request_sync!=acknowledge_toggle) begin latest<=mailbox_data;seen<=1;acknowledge_toggle<=request_sync;end
            if(x==0 && y==0) begin
                shown<=latest;shown_valid<=seen;page<=next_page;frames<=frames==119?0:frames+1'b1;
                field<=0;step<=0;bcd<=0;binary<=metric(latest,next_page,0);busy<=1;decimal_ready<=0;
            end else if(busy) begin
                binary<={binary[30:0],1'b0};bcd<=next_bcd;
                if(step==31) begin
                    digits[field]<=next_bcd;step<=0;bcd<=0;
                    if(field==3) begin busy<=0;decimal_ready<=1;end
                    else begin field<=field+1'b1;binary<=metric(shown,page,field+2'd1);end
                end else step<=step+1'b1;
            end
        end
    end
    function [34:0] glyph;
        input [7:0] c;
        begin
            case(c)
                "A":glyph=35'b01110_10001_10001_11111_10001_10001_10001;
                "B":glyph=35'b11110_10001_10001_11110_10001_10001_11110;
                "C":glyph=35'b01111_10000_10000_10000_10000_10000_01111;
                "D":glyph=35'b11110_10001_10001_10001_10001_10001_11110;
                "E":glyph=35'b11111_10000_10000_11110_10000_10000_11111;
                "F":glyph=35'b11111_10000_10000_11110_10000_10000_10000;
                "G":glyph=35'b01111_10000_10000_10111_10001_10001_01111;
                "H":glyph=35'b10001_10001_10001_11111_10001_10001_10001;
                "I":glyph=35'b11111_00100_00100_00100_00100_00100_11111;
                "K":glyph=35'b10001_10010_10100_11000_10100_10010_10001;
                "L":glyph=35'b10000_10000_10000_10000_10000_10000_11111;
                "N":glyph=35'b10001_11001_10101_10011_10001_10001_10001;
                "O":glyph=35'b01110_10001_10001_10001_10001_10001_01110;
                "P":glyph=35'b11110_10001_10001_11110_10000_10000_10000;
                "R":glyph=35'b11110_10001_10001_11110_10100_10010_10001;
                "S":glyph=35'b01111_10000_10000_01110_00001_00001_11110;
                "T":glyph=35'b11111_00100_00100_00100_00100_00100_00100;
                "Y":glyph=35'b10001_10001_01010_00100_00100_00100_00100;
                "0":glyph=35'b01110_10001_10011_10101_11001_10001_01110;
                "1":glyph=35'b00100_01100_00100_00100_00100_00100_01110;
                "2":glyph=35'b01110_10001_00001_00010_00100_01000_11111;
                "3":glyph=35'b11110_00001_00001_01110_00001_00001_11110;
                "4":glyph=35'b00010_00110_01010_10010_11111_00010_00010;
                "5":glyph=35'b11111_10000_10000_11110_00001_00001_11110;
                "6":glyph=35'b01110_10000_10000_11110_10001_10001_01110;
                "7":glyph=35'b11111_00001_00010_00100_01000_01000_01000;
                "8":glyph=35'b01110_10001_10001_01110_10001_10001_01110;
                "9":glyph=35'b01110_10001_10001_01111_00001_00001_01110;
                ":":glyph=35'b00000_00100_00100_00000_00100_00100_00000;
                ".":glyph=35'b00000_00000_00000_00000_00000_00100_00100;
                "-":glyph=35'b00000_00000_00000_11111_00000_00000_00000;
                "J":glyph=35'b00111_00010_00010_00010_10010_10010_01100;
                "M":glyph=35'b10001_11011_10101_10101_10001_10001_10001;
                "U":glyph=35'b10001_10001_10001_10001_10001_10001_01110;
                "W":glyph=35'b10001_10001_10001_10101_10101_11011_10001;
                "Q":glyph=35'b01110_10001_10001_10001_10101_10010_01101;
                "X":glyph=35'b10001_10001_01010_00100_01010_10001_10001;
                default:glyph=0;
            endcase
        end
    endfunction
    function [7:0] hex_char;
        input [3:0] nibble;
        begin hex_char=nibble<10 ? 8'd48+nibble : 8'd65+nibble-10; end
    endfunction


    function [47:0] label(input [1:0] p,input [1:0] n);
        begin case(p)
            0:case(n) 0:label="CAP US";1:label="JOB US";2:label="QUE US";default:label="TOT US";endcase
            1:case(n) 0:label="WIN CY";1:label="RD B  ";2:label="WR B  ";default:label="RWAIT ";endcase
            2:case(n) 0:label="ARWAIT";1:label="RBACK ";2:label="WSTALL";default:label="BWAIT ";endcase
            default:case(n) 0:label="CAM HI";1:label="DIS HI";2:label="RMAXCY";default:label="WMAXCY";endcase
        endcase end
    endfunction
    integer lx,ly,index,pos,col,row,n;
    reg [111:0] heading;
    reg [47:0] name;
    reg [31:0] ident;
    reg [7:0] ch;
    reg [34:0] dots;
    reg [3:0] digit;
    always @* begin
        case(page) 0:heading="PERF 01 LAT F:";1:heading="PERF 01 DDR S:";2:heading="PERF 01 BUS S:";default:heading="PERF 01 MAX S:";endcase
        ident=page==0?shown[32+:32]:shown[18*32+:32];
        rgb=input_rgb;lx=0;ly=0;index=0;pos=0;col=0;row=0;n=0;ch=" ";dots=0;name=0;digit=0;
        if(y>=104 && y<118 && x>=8 && x<8+95*12) begin
            lx=x-8;ly=y-104;index=lx/12;col=(lx%12)/2;row=ly/2;
            if(index<14)ch=heading >> ((13-index)*8);
            else if(index<22)ch=hex_char((ident >> ((21-index)*4)) & 15);
            else if(index>=23)begin
                n=(index-23)/18;pos=(index-23)%18;name=label(page,n[1:0]);
                if(pos<6)ch=name >> ((5-pos)*8);
                else if(pos==6)ch=":";
                else if(pos<17)begin
                    digit=digits[n][(16-pos)*4+:4];
                    ch=shown_valid && decimal_ready && (page!=0 || shown[0])?8'd48+digit:"-";
                end
            end
            dots=glyph(ch);rgb=0;
            if(col<5 && row<7 && dots[34-row*5-col])rgb=24'h80FFFF;
        end
    end
endmodule
