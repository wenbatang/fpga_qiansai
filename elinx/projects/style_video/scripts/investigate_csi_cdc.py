"""Build an isolated CSI 5.15 timing reproducer. Never generates/programs a bit.

All generated files stay in this project's build/csi_cdc_515 directory. The
production RTL, IP, SDC and candidate reports are read-only inputs.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build/csi_cdc_515'
PROD = ROOT / 'build/camera_vga'
NAME = 'csi_cdc_515'
NS = 'http://www.efinixinc.com/enf_proj'
PT = 'http://www.efinixinc.com/peri_design_db'


def prepare():
    BUILD.mkdir(parents=True, exist_ok=True)
    source = (ROOT / 'rtl/ti60_camera_top.sv').read_text(encoding='utf-8')
    lanes = '\n'.join(f'''input wire [7:0] cam_d{i}_HS_IN,
input wire cam_d{i}_LP_P_IN,cam_d{i}_LP_N_IN,cam_d{i}_FIFO_EMPTY,
output wire cam_d{i}_HS_TERM,cam_d{i}_HS_ENA,cam_d{i}_RST,cam_d{i}_FIFO_RD,''' for i in range(4))
    instance = source[source.index('camera_csi inst_efx_csi2_rx'):source.index(' wire[15:0] paddr;')]
    top = f'''// Timing investigation ONLY; not a board application or deliverable bit.
module {NAME}(
input wire CLK_25M,core_clk,core_pll_locked,
input wire [3:0] style_keys_n,
output wire CORE_PLL_RSTN,uart_tx,
input wire i_cam_ck_LP_P_IN,i_cam_ck_LP_N_IN,i_cam_ck_CLKOUT,
output wire o_cam_ck_HS_TERM,o_cam_ck_HS_ENA,
{lanes.rstrip(',')}
);
wire reset_ui,reset_byte;
assign CORE_PLL_RSTN=style_keys_n[0];
reset_sync rst_ui(.clk(core_clk),.async_reset(!style_keys_n[0] || !core_pll_locked),.reset(reset_ui));
reset_sync rst_byte(.clk(i_cam_ck_CLKOUT),.async_reset(reset_ui),.reset(reset_byte));
assign cam_d0_RST=reset_byte;assign cam_d1_RST=reset_byte;
assign cam_d2_RST=reset_byte;assign cam_d3_RST=reset_byte;
wire cam_vs,cam_hs,cam_valid;
wire [63:0] cam_pixels;wire [31:0] cam_debug;
wire [5:0] cam_datatype,cam_pixel_datatype;wire [3:0] cam_ppc;
wire [15:0] cam_pixel_wordcount;
wire csi_awvalid,csi_awready,csi_wvalid,csi_wready,csi_bvalid,csi_bready;
assign csi_awvalid=1'b0;assign csi_wvalid=1'b0;assign csi_bready=1'b1;
{instance}
// Keep pixel conversion and both public metadata interfaces observable.
reg checksum=0;
always @(posedge core_clk) if(reset_ui)checksum<=0;
else if(cam_valid)checksum<=checksum ^ ^{{cam_pixels,cam_debug,cam_ppc,cam_hs,cam_vs,cam_pixel_datatype,cam_pixel_wordcount}};
assign uart_tx=checksum;
endmodule
'''
    (BUILD / (NAME + '.sv')).write_text(top, encoding='utf-8')
    ET.register_namespace('efx', NS)
    tree = ET.parse(PROD / 'ti60_camera.xml')
    root = tree.getroot()
    root.set('name', NAME)
    root.set('last_run_state', 'fail')
    design = root.find(f'{{{NS}}}design_info')
    design.find(f'{{{NS}}}top_module').set('name', NAME)
    for item in list(design):
        if item.tag == f'{{{NS}}}design_file':
            design.remove(item)
    files = [BUILD / (NAME + '.sv'), ROOT / 'rtl/reset_sync.sv', ROOT / 'vendor/camera_csi.sv']
    for index, path in enumerate(files, 1):
        item = ET.Element(f'{{{NS}}}design_file', name=path.as_posix(), version='default', library='default')
        design.insert(index, item)
    for item in root.iter():
        if item.tag.endswith('peri_file'):
            item.set('name', NAME + '.peri.xml')
        if item.tag.endswith('sdc_file'):
            item.set('name', NAME + '.sdc')
        if item.tag.endswith('param') and item.get('name') in ('generate_bit', 'generate_hex'):
            item.set('value', 'off')
    tree.write(BUILD / (NAME + '.xml'), encoding='utf-8', xml_declaration=True)
    ET.register_namespace('efxpt', PT)
    tree = ET.parse(PROD / 'ti60_camera.peri.xml')
    tree.getroot().set('name', NAME)
    for group in tree.getroot():
        kind = group.tag.rsplit('}', 1)[-1]
        if kind == 'gpio_info':
            for item in list(group):
                if item.tag.rsplit('}', 1)[-1] == 'global_unused_config':
                    continue
                if item.tag.rsplit('}', 1)[-1] == 'bus' and item.get('name') == 'style_keys_n':
                    continue
                if item.get('name') not in ('CLK_25M', 'uart_tx') and not item.get('name', '').startswith('style_keys_n['):
                    group.remove(item)
        elif kind == 'pll_info':
            for item in list(group):
                if item.get('name') != 'CORE_PLL':
                    group.remove(item)
        elif kind in ('lvds_info', 'jtag_info', 'osc_info'):
            group.clear()
    tree.write(BUILD / (NAME + '.peri.xml'), encoding='utf-8', xml_declaration=True)
    (BUILD / (NAME + '.sdc')).write_text(
        'create_clock -name CLK_25M -period 40 [get_ports CLK_25M]\n'
        'create_clock -name i_cam_ck_CLKOUT -period 14.285714 [get_ports i_cam_ck_CLKOUT]\n', encoding='utf-8')
    manifest = {'scope': 'CSI-only STA reproducer, NOT signoff; no configuration generation',
                'production_untouched': True, 'ip_version': '5.15',
                'sources_sha256': {p.as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    (BUILD / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')


def route_constraints():
    # Only unrelated reset assertions are exempt. Leave both disputed clock
    # directions fully timed to reproduce the issue independently of the SoC.
    sdc = ('create_clock -name CLK_25M -period 40 [get_ports CLK_25M]\n'
           'create_clock -name i_cam_ck_CLKOUT -period 14.285714 [get_ports i_cam_ck_CLKOUT]\n')
    pt = (BUILD / 'outflow' / (NAME + '.pt.sdc')).read_text(encoding='utf-8')
    sdc += '\n'.join(line for line in pt.splitlines() if '<USER' not in line) + '\n'
    sdc += 'set_false_path -to [get_pins {*|SR}]\n'
    (BUILD / (NAME + '.sdc')).write_text(sdc, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--flow', choices=['prepare', 'map', 'interface', 'route', 'sta', 'scoped-sta', 'production-sta'], default='prepare')
    args = parser.parse_args()
    if args.flow == 'prepare':
        prepare()
        print('Prepared', BUILD)
        return
    sys.path.append(str(ROOT / 'scripts'))
    from tool_run import environment, run
    environment()
    python = 'E:/software/efinity/python311/bin/python.exe'
    if args.flow == 'interface':
        command = [python, 'E:/software/efinity/scripts/efx_run_pt_unified.py', NAME, 'Titanium', 'Ti60F225',
                   '--output_dir', 'outflow', '--timing_model', 'I3', '--project_xml', NAME + '.xml']
    else:
        if args.flow == 'route':
            route_constraints()
        stage = {'map': 'map', 'route': 'pnr', 'sta': 'sta_tclsh', 'scoped-sta': 'sta_tclsh', 'production-sta': 'sta_tclsh'}[args.flow]
        name = 'ti60_camera' if args.flow == 'production-sta' else NAME
        command = [python, 'E:/software/efinity/scripts/efx_run.py', name, '--prj', '--flow', stage, '--output_dir', 'outflow']
        if args.flow in ('sta', 'scoped-sta', 'production-sta'):
            prefix_file = {'sta': '', 'scoped-sta': 'scoped_', 'production-sta': 'production_'}[args.flow]
            tcl = BUILD / (args.flow + '_paths.tcl')
            commands = []
            if args.flow == 'scoped-sta':
                # Diagnostic experiment only. Leave every direct word_count
                # bundle path timed; no cross-clock group or multicycle cut.
                from summarize_csi_cdc import rows, classify
                for direction in ('byte_to_core', 'core_to_byte'):
                    for row in rows(BUILD / 'outflow' / (direction+'.rpt')):
                        kind = classify(row)
                        if kind == 'fifo_gray_first_stage':
                            commands.append(f"set_max_delay 9.800 -from [get_pins {{{row['source']}}}] -to [get_pins {{{row['destination']}}}]")
                        elif kind == 'named_sideband_first_stage':
                            commands.append(f"set_false_path -to [get_pins {{{row['destination']}}}]")
                        elif kind == 'dphy_control_first_stage':
                            dest = row['destination']
                            match = re.search(r'genblk2\[(\d)\].*genblk1\.(RxHS_settle|RxStopState)_1P', dest)
                            assert match
                            proof = rows(BUILD / 'outflow' / f'lane{match[1]}_{match[2]}_fanout.rpt')
                            assert len(proof)==1 and proof[0]['destination']==dest.replace('_1P~FF|D', '_2P~FF|D')
                            commands.append(f'set_false_path -to [get_pins {{{dest}}}]')
                (BUILD / 'scoped_experiment_only.sdc').write_text('\n'.join(commands)+'\n', encoding='utf-8')
            commands += [f'report_timing -from_clock i_cam_ck_CLKOUT -to_clock core_clk -npaths 2000 -nworst 1 -file {{{prefix_file}byte_to_core.rpt}}',
                        f'report_timing -from_clock core_clk -to_clock i_cam_ck_CLKOUT -npaths 2000 -nworst 1 -file {{{prefix_file}core_to_byte.rpt}}']
            for lane in range(4):
                prefix = f'inst_efx_csi2_rx/u_efx_csi2_rx/dphy_rx_inst/genblk2[{lane}].rx_dword_align_inst/genblk1.'
                for signal in ('RxHS_settle', 'RxStopState'):
                    commands.append(f'report_timing -from {{{prefix}{signal}_1P~FF}} -npaths 200 -nworst 1 -file {{{prefix_file}lane{lane}_{signal}_fanout.rpt}}')
            tcl.write_text('\n'.join(commands)+'\n', encoding='utf-8')
            command += ['--tcl_script', str(tcl)]
    folder = PROD if args.flow == 'production-sta' else BUILD
    code = run(command, folder, BUILD / (args.flow + '_console.log'))
    log = (BUILD / (args.flow + '_console.log')).read_text(errors='replace')
    if any(x in log for x in ('Failed to run command', 'Unable to generate slack report', 'Fail to open file')):
        raise RuntimeError('STA command failed; process exit status alone is insufficient')
    if args.flow == 'production-sta' and code == 0:
        for report in (PROD / 'outflow').glob('production_*.rpt'):
            shutil.copyfile(report, BUILD / 'outflow' / report.name)
    raise SystemExit(code)


if __name__ == '__main__':
    main()
