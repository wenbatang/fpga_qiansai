// One raw-frame commit owns conversion until the completed display is swapped.
// Writer keeps commit_valid high; wait for its release before another start.
module style_frame_control(
    input wire clk, reset, writer_commit_valid,
    input wire [31:0] writer_commit_frame,
    input wire front_bank, engine_done, engine_error, display_commit_ack,
    input wire [31:0] engine_cycles,
    output reg engine_start, writer_commit_ack, writer_commit_fail,
    output reg display_commit_valid, output_bank,
    output reg [31:0] output_frame, last_inference_cycles,
    output reg [31:0] inference_frames, inference_errors,
    output wire write_owner
);
    localparam IDLE=0, PROCESS=1, PUBLISH=2, RELEASE=3;
    reg [1:0] state;
    assign write_owner=state!=IDLE;
    always @(posedge clk) begin
        engine_start<=0;writer_commit_ack<=0;writer_commit_fail<=0;
        if(reset) begin
            state<=IDLE;display_commit_valid<=0;output_bank<=0;output_frame<=0;
            last_inference_cycles<=0;inference_frames<=0;inference_errors<=0;
        end else case(state)
            IDLE: if(writer_commit_valid) begin
                output_bank<=~front_bank;output_frame<=writer_commit_frame;
                engine_start<=1;state<=PROCESS;
            end
            PROCESS: if(engine_error) begin
                inference_errors<=inference_errors+1;writer_commit_fail<=1;state<=RELEASE;
            end else if(engine_done) begin
                last_inference_cycles<=engine_cycles;inference_frames<=inference_frames+1;
                display_commit_valid<=1;state<=PUBLISH;
            end
            PUBLISH: if(display_commit_ack) begin
                display_commit_valid<=0;writer_commit_ack<=1;state<=RELEASE;
            end
            RELEASE: if(!writer_commit_valid) state<=IDLE;
            default: state<=IDLE;
        endcase
    end
endmodule
