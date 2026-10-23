// A complete DDR source is retained for key-triggered reprocessing. BEGIN
// invalidates it before partial overwrite; inference excludes new uploads.
module style_key_control(
 input wire clk,reset,writer_commit_valid,input wire [31:0] writer_commit_frame,
 input wire writer_idle,source_invalidate,key_event,input wire [1:0] key_style,
 input wire front_bank,engine_done,engine_error,display_commit_ack,
 input wire [31:0] engine_cycles,
 output reg engine_start,writer_commit_ack,writer_commit_fail,
 output reg display_commit_valid,output_bank,
 output reg [31:0] output_frame,last_inference_cycles,inference_frames,inference_errors,
 output reg [1:0] requested_style,engine_style,output reg source_valid,
 output wire write_owner);
    localparam IDLE=0,PROCESS=1,PUBLISH=2,RELEASE=3;
    reg [1:0] state;reg upload_job,pending_key;reg [31:0] source_frame;
    assign write_owner=state!=IDLE;
    always @(posedge clk)begin
        engine_start<=0;writer_commit_ack<=0;writer_commit_fail<=0;
        if(reset)begin
            state<=IDLE;display_commit_valid<=0;output_bank<=0;output_frame<=0;
            last_inference_cycles<=0;inference_frames<=0;inference_errors<=0;
            requested_style<=0;engine_style<=0;source_valid<=0;source_frame<=0;
            upload_job<=0;pending_key<=0;
        end else begin
            if(source_invalidate)source_valid<=0;
            if(key_event)begin requested_style<=key_style;pending_key<=1;end
            case(state)
            IDLE: if(writer_commit_valid)begin
                source_valid<=1;source_frame<=writer_commit_frame;
                output_bank<=~front_bank;output_frame<=writer_commit_frame;
                engine_style<=key_event ? key_style:requested_style;
                pending_key<=0;upload_job<=1;engine_start<=1;state<=PROCESS;
            end else if(source_valid && !source_invalidate && writer_idle && (pending_key || key_event))begin
                output_bank<=~front_bank;output_frame<=source_frame;
                engine_style<=key_event ? key_style:requested_style;
                pending_key<=0;upload_job<=0;engine_start<=1;state<=PROCESS;
            end
            PROCESS: if(engine_error)begin
                inference_errors<=inference_errors+1;
                if(upload_job)writer_commit_fail<=1;
                state<=RELEASE;
            end else if(engine_done)begin
                last_inference_cycles<=engine_cycles;inference_frames<=inference_frames+1;
                display_commit_valid<=1;state<=PUBLISH;
            end
            PUBLISH: if(display_commit_ack)begin
                display_commit_valid<=0;if(upload_job)writer_commit_ack<=1;state<=RELEASE;
            end
            RELEASE: if(!upload_job || !writer_commit_valid)state<=IDLE;
            default:state<=IDLE;
            endcase
        end
    end
endmodule
