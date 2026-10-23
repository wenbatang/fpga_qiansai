"""Read-only telemetry variant: preserve the signed camera60 data/control path."""
from pathlib import Path
import hashlib, importlib.util, json, sys

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'build/camera_ppi60'
BUILD = ROOT / 'build/camera_debug60'
WS = ROOT.parents[2]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def parent_audit():
    # The parent's signoff imports its own contract by module name. Temporarily
    # resolve that exact module, then restore the caller's import environment.
    saved = sys.modules.get('contract')
    folder = ROOT / 'scripts/hdmi60'
    spec = importlib.util.spec_from_file_location('camera60_contract', folder/'contract.py')
    parent_contract = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parent_contract)
    sys.modules['contract'] = parent_contract
    try:
        spec = importlib.util.spec_from_file_location('camera60_signoff', folder/'signoff.py')
        parent_signoff = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(parent_signoff)
        current = parent_signoff.audit(True)
        assert json.loads(json.dumps(current)) == read(BASE/'signoff.json'), 'Parent camera60 release changed'
        return current
    finally:
        if saved is None:
            sys.modules.pop('contract', None)
        else:
            sys.modules['contract'] = saved

def system_text():
    source = (ROOT/'rtl/hdmi60/video_system60.sv').read_text(encoding='utf-8')
    old = 'output wire[23:0] display_rgb,output wire hsync,vsync,de);'
    new = ('output wire[23:0] display_rgb,output wire hsync,vsync,de,\n'
           ' output wire[31:0] diag_capture_frames,diag_inference_frames,diag_capture_errors,diag_engine_cycles,\n'
           ' output wire[3:0] diag_status);')
    assert source.count(old) == 1
    source = source.replace('module video_system60 #(', 'module video_system_debug #(').replace(old, new)
    return source.replace('endmodule', '''// Observations only; no new ready, enable, reset, or command driver.
 assign diag_capture_frames=captured_frames;
 assign diag_inference_frames=inference_frames;
 assign diag_capture_errors=capture_errors;
 assign diag_engine_cycles=engine_cycles;
 assign diag_status={front_valid,weights_valid,busy,latest_valid};
endmodule''')

def bridge_text():
    source = (ROOT/'rtl/csi_ppi_bridge.sv').read_text(encoding='utf-8')
    source = source.replace('module csi_ppi_bridge #(', 'module csi_ppi_bridge_debug #(')
    old = 'output wire transport_fault);'
    new = ('output wire transport_fault,\n'
           ' output reg[31:0] debug_events,debug_header);')
    assert source.count(old) == 1
    source = source.replace(old, new)
    # Both observations are in the FIFO read/UI domain. No metadata bus is
    # sampled directly from the stopped/resumed byte clock domain.
    return source.replace('endmodule', '''always @(posedge ui_clk)begin
  if(ui_reset)begin debug_events<=0;debug_header<=0;end
  else begin
   if(!fifo_empty)debug_events<=debug_events+1;
   if(state==HEADER && all_bytes && !control_error && !in_error &&
      !lane_overflow && !transport_fault && !(|in_sync))debug_header<=word_data;
  end
 end
endmodule''')

def top_text():
    source = (BASE/'rtl/ti60_camera_ppi_top.sv').read_text(encoding='utf-8')
    source = source.replace(" assign uart_tx=1'b1;", ''' wire[31:0] diag_lines,diag_packets,diag_events,diag_header;
 wire[31:0] diag_captured,diag_inferred,diag_capture_errors,diag_cycles;
 wire[3:0] diag_status;''')
    source = source.replace('csi_ppi_bridge bridge(', 'csi_ppi_bridge_debug bridge(')
    source = source.replace('.good_lines(),.error_packets());',
                            '.good_lines(diag_lines),.error_packets(diag_packets),\n'
                            '  .debug_events(diag_events),.debug_header(diag_header));')
    source = source.replace('video_system60 #(', 'video_system_debug #(')
    old = '.display_rgb(rgb),.hsync(hsync),.vsync(vsync),.de(de));'
    assert source.count(old) == 1
    source = source.replace(old, '.display_rgb(rgb),.hsync(hsync),.vsync(vsync),.de(de),\n'
                           '  .diag_capture_frames(diag_captured),.diag_inference_frames(diag_inferred),\n'
                           '  .diag_capture_errors(diag_capture_errors),.diag_engine_cycles(diag_cycles),.diag_status(diag_status));')
    source = source.replace('endmodule', '''// Snoop completed APB transactions. This observer cannot acknowledge,
 // stall, issue, or modify any CPU/sensor/accelerator operation.
 reg[31:0] diag_boot,diag_raw_groups,diag_frames;
 reg[2:0] diag_control;
 reg[1:0] diag_last_wires;
 reg diag_vs_previous;
 always @(posedge ui_clk)begin
  if(reset_ui || soc_reset)begin
   diag_boot<=0;diag_control<=0;diag_last_wires<=0;
   diag_raw_groups<=0;diag_frames<=0;diag_vs_previous<=0;
  end else begin
   diag_vs_previous<=cam_vs;
   if(cam_vs && !diag_vs_previous)diag_frames<=diag_frames+1;
   if(cam_valid)diag_raw_groups<=diag_raw_groups+1;
   if(psel && penable && pready && !pslverror)begin
    if(pwrite && paddr==16'h0060)diag_boot<=pwdata;
    if(pwrite && paddr==16'h0004)diag_control<=pwdata[2:0];
    if(!pwrite && paddr==16'h0044)diag_last_wires<=prdata[1:0];
   end
  end
 end
 // bit0 CAL, 1 UI_RESET, 2 SOC_RESET, 3 SENSOR_RELEASE, 4/5 SDA/SCL
 // release, 6/7 last APB pin sample, 8 SOURCE, 9 BUSY, 10 WEIGHTS,
 // 11 FRONT, 12 CAPTURE_ENABLE, 13 PACKET_ERROR, 14 TRANSPORT_FAULT.
 wire[31:0] diag_flags={17'd0,bridge_transport_fault,bridge_error,diag_control[0],
  diag_status,diag_last_wires,scl_release,sda_release,sensor_reset_n,soc_reset,reset_ui,calibrated};
 // Intentionally independent of DDR calibration and CPU reset: a healthy UI
 // clock can report a calibration/boot failure. All payload fields are UI-domain.
 camera_diag_uart diagnostics(.clk(ui_clk),.reset(ddr_reset),
  .fields({diag_boot,diag_flags,diag_lines,diag_packets,diag_events,diag_header,
           diag_captured,diag_inferred,diag_capture_errors,diag_raw_groups,diag_frames,diag_cycles}),.tx(uart_tx));
endmodule''')
    return source

def audit_contract():
    old = parent_audit()
    manifest = read(BUILD/'manifest.json')
    for name, value in manifest['parent_camera60'].items():
        assert sha(BASE/name) == value, name
    for name in ['ti60_camera.peri.xml', 'firmware_manifest.json', 'firmware.bin', *manifest['boot_ram']]:
        assert (BUILD/name).read_bytes() == (BASE/name).read_bytes(), name
    expected = {
        BUILD/'rtl/ti60_camera_ppi_top.sv': top_text(),
        ROOT/'rtl/diagnostics/video_system_debug.sv': system_text(),
        ROOT/'rtl/diagnostics/csi_ppi_bridge_debug.sv': bridge_text(),
    }
    for path, text in expected.items():
        assert path.read_text(encoding='utf-8') == text, 'Telemetry-only derivation differs: '+str(path)
    assert manifest['process'] == [640,480] and manifest['camera'] == [1920,1080]
    assert manifest['display'] == read(BASE/'manifest.json')['display']
    for name,value in manifest['diagnostic_tools'].items():
        assert sha(ROOT/name) == value, name
    simulations = {}
    for name in ['sim/diagnostics_uart/verification.json','sim/top_safety_debug/verification.json',
                 'sim/diagnostics_observer/verification.json','sim/diagnostics_parser/verification.json']:
        data = read(ROOT/name)
        assert data['result'] == 'PASS', name
        for path,value in data.get('sources_sha256',{}).items():
            assert sha(Path(path)) == value, path
        for path,value in data.get('logs_sha256',{}).items():
            assert sha(Path(path)) == value, path
        for key in ('sources', 'source_sha256', 'logs'):
            for path,value in data.get(key,{}).items():
                assert sha(ROOT/path) == value, path
        for path,value in data.get('log_sha256',{}).items():
            assert sha((ROOT/name).parent/path) == value, path
        simulations[name] = {'sha256':sha(ROOT/name),'scope':data['scope']}
    return {'result':'PASS','parent_camera60_bit_sha256':old['bitstream_sha256'],
            'telemetry_uart_baud':115200,'telemetry_fields':12,
            'new_cross_clock_payloads':0,'sensor_firmware_weights_and_peri_unchanged':True,
            'simulations':simulations,'scope':'Read-only APB/CSI/UI observation, not camera hardware root cause proof',
            'board_programmed':False}
