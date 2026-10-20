// APB3 slave for the future Sapphire SoC. Addresses are offsets, NOT a guessed
// CPU address map. Local standalone mode uses reset defaults (enable/auto/copy).
module style_control_regs #(
    parameter integer WIDTH=640,HEIGHT=480
)(
    input wire clk,rst_n,
    input wire [11:0] paddr,input wire psel,penable,pwrite,
    input wire [31:0] pwdata,output reg [31:0] prdata,
    output wire pready,output reg pslverr,
    output reg enable,auto_run,bypass,
    output reg [1:0] display_mode,output reg start_pulse,
    input wire [31:0] status,camera_frames,captured_count,processed_count,
    input wire [31:0] displayed_count,drop_count,error_count,underflow_count,
    input wire [31:0] front_id,input wire [3:0] ready_mask,
    input wire [3:0] event_set,output wire irq,
    output reg [15:0] capture_fps,process_fps,
    input wire fps_tick
);
    reg [3:0] irq_status,irq_enable;
    reg [31:0] previous_capture,previous_process;
    wire access=psel && penable;
    wire [3:0] irq_clear=(access && pwrite && paddr==12'h018)?pwdata[3:0]:4'b0;
    assign pready=1'b1;
    assign irq=|(irq_status & irq_enable);
    always @* begin
        prdata=0;pslverr=0;
        case(paddr)
            12'h000:prdata=32'h53565931; // SVY1
            12'h004:prdata={29'b0,bypass,auto_run,enable};
            12'h008:prdata=0;
            12'h00c:prdata=status;
            12'h010:prdata={28'b0,irq_status};
            12'h014:prdata={28'b0,irq_enable};
            12'h018:prdata=0;
            12'h020:prdata={30'b0,display_mode};
            12'h030:prdata=WIDTH;
            12'h034:prdata=HEIGHT;
            12'h038:prdata=WIDTH*4;
            12'h03c:prdata=32'h00000001; // RGBX8888 LE word0x00RRGGBB
            12'h040:prdata=32'h01000000;
            12'h044:prdata=32'h00200000;
            12'h048:prdata=32'h00000204; // 4 input slots, 2 result slots
            12'h050:prdata={28'b0,ready_mask};
            12'h054:prdata=front_id;
            12'h060:prdata=camera_frames;
            12'h064:prdata=captured_count;
            12'h068:prdata=processed_count;
            12'h06c:prdata=displayed_count;
            12'h070:prdata=drop_count;
            12'h074:prdata=error_count;
            12'h078:prdata=underflow_count;
            12'h080:prdata={process_fps,capture_fps};
            default:begin prdata=0;pslverr=access;end
        endcase
        if(access && pwrite) case(paddr)
            12'h004,12'h008,12'h014,12'h018,12'h020:;
            default:pslverr=1'b1;
        endcase
    end
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            enable<=1;auto_run<=1;bypass<=1;display_mode<=0;start_pulse<=0;
            irq_status<=0;irq_enable<=0;previous_capture<=0;previous_process<=0;
            capture_fps<=0;process_fps<=0;
        end else begin
            start_pulse<=0;
            irq_status<=(irq_status & ~irq_clear)|event_set; // event wins W1C
            if(access && pwrite && !pslverr) case(paddr)
                12'h004:begin enable<=pwdata[0];auto_run<=pwdata[1];bypass<=pwdata[2];end
                12'h008:start_pulse<=pwdata[0];
                12'h014:irq_enable<=pwdata[3:0];
                12'h020:display_mode<=pwdata[1:0];
                default:;
            endcase
            if(fps_tick) begin
                capture_fps<=(captured_count-previous_capture)>65535?16'hffff:captured_count-previous_capture;
                process_fps<=(processed_count-previous_process)>65535?16'hffff:processed_count-previous_process;
                previous_capture<=captured_count;previous_process<=processed_count;
            end
        end
    end
endmodule
