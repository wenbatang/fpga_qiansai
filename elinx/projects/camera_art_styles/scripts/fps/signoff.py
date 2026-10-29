"""Fail-closed signoff for the independent C6 RF33 true720 camera candidate.

audit(False) is mandatory before offline bit generation; audit(True) additionally
binds the current bit. This module never generates a bit or accesses hardware.
It does not establish physical camera/DDR concurrency or measured board FPS.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
WS = ROOT.parents[2]
BUILD = ROOT / 'build/camera_fps_rf33_srl_720'
BASE = ROOT / 'build/camera_720_fast'
REF = WS / 'elinx/elinxdemo/Ti60F225_DemoBoard_v4/10_Ti60f225_sc431hai2hdmi_demo/Ti60f225_sc431hai2hdmi_v7/Ti60f225_sc431hai2hdmi_v7'
STYLES = ('vangogh', 'papercut', 'comic', 'inkwash')
REQUIRED_SIMULATIONS = (
    'sim/fps/dma720/verification.json', 'sim/fps/engine3/verification.json',
    'sim/fps/c6_mapped/verification.json', 'sim/fps/top_safety_srl/verification.json',
    'sim/fps_sapphire/verification.json', 'sim/fps_sapphire/faults/verification.json',
    'sim/fps_jobs/verification.json', 'sim/fps_reader/verification.json',
    'sim/fps_scheduler/verification.json', 'sim/fps_write_pressure2/verification.json',
    'sim/p720/bayer/verification.json', 'sim/p720/bayer_full/verification.json',
    'sim/p720/bayer_faults/verification.json', 'sim/p720/capture/verification.json',
    'sim/ppi_faults/verification.json', 'sim/dphy_bridge/verification.json',
    'sim/dphy_full/verification.json',
)
SRL_REQUIRED_SIMULATIONS = (
    'sim/fps_srl/rtl/verification.json',
    'sim/fps_srl/mapped/verification.json',
    'sim/fps/dma720_srl/verification.json',
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bound_receipt(relative):
    path = ROOT / relative
    data = read(path)
    assert data['result'] == 'PASS', f'Failed or missing mandatory simulation: {relative}'
    for key in ('sources_sha256', 'logs_sha256'):
        for name, expected in data.get(key, {}).items():
            path_to_check = Path(name)
            # Early C6 checks accepted workspace-relative export arguments;
            # their recorded paths are relative to WS, never audit's cwd.
            if not path_to_check.is_absolute():
                path_to_check = WS / path_to_check
            assert sha(path_to_check) == expected, f'Stale {relative}: {name}'
    for name, expected in data.get('sources', {}).items():
        assert sha(WS / name) == expected, f'Stale {relative}: {name}'
    if 'log_sha256' in data:
        assert sha(path.parent / 'vsim.log') == data['log_sha256']
    return data


def electrical(manifest):
    assert (BUILD / 'ti60_camera.peri.xml').read_bytes() == (BASE / 'ti60_camera.peri.xml').read_bytes(), 'Pin/voltage/PLL delta requires separate review'
    board = load('fps_correct_board', ROOT / 'scripts/board_spec.py')
    result = board.audit(BUILD, camera=True, top=BUILD / 'rtl/ti60_camera_ppi_top.sv')
    assert result['active_pins'] == 79 and len(result['banks']) == 12
    assert (ROOT / 'vendor/rtl/ddr3_controller/ddr3_top.v').read_bytes() == (REF / 'rtl/ddr3_controller/ddr3_top.v').read_bytes()
    assert (BUILD / 'ddr3_parameter.vh').read_bytes() == (REF / 'rtl/ddr3_controller/ddr3_parameter.vh').read_bytes()
    top = (BUILD / 'rtl/ti60_camera_ppi_top.sv').read_text(encoding='utf-8')
    for fragment in ("assign io_cam_scl_OUT=1'b0", "assign io_cam_sda_OUT=1'b0",
                     'assign o_cam_rst_p=reset_ui || !sensor_reset_n',
                     '.async_reset(!sys_rst_n || !pll_locked || !core_pll_locked || !user_pll_locked)',
                     'assign cam_d0_RST=reset_byte', 'camera_dphy inst_camera_dphy', '.cam_error(bridge_error)'):
        assert fragment in top, f'Safety binding missing: {fragment}'
    assert 'camera_csi ' not in top
    assert manifest['dphy_active']['version'] == '5.8'
    assert sha(ROOT / 'vendor/camera_dphy.sv') == manifest['dphy_active']['sha256']
    return result


def firmware(manifest):
    data = read(BUILD / 'firmware_manifest.json')
    assert sha(BUILD / 'firmware_manifest.json') == manifest['firmware_manifest']
    assert data['writes_per_style'] == 365 and data['weights_per_style'] == 1296
    assert data['firmware_bytes'] == 9692 and data['firmware_bytes'] <= 32768
    assert data['mode_commands'] == 163 and data['irq'] == 16 and data['sensor_id'] == 'cd6b'
    assert data['camera_mode_header_unchanged'] and data['catalog_found_in_actual_binary']
    for name, expected in data['files'].items():
        assert sha(WS / name) == expected, 'Stale firmware source or generated artifact: ' + name
    original = (ROOT / 'firmware/main.c').read_text(encoding='utf-8')
    assert original.count('1217') == 2
    assert (BUILD / 'firmware/main.c').read_text(encoding='utf-8') == original.replace('1217', '365')
    for name in ('start.S', 'link.ld'):
        assert (BUILD / 'firmware' / name).read_bytes() == (ROOT / 'firmware' / name).read_bytes()
    assert (BUILD / 'camera_mode.h').read_bytes() == (BASE / 'camera_mode.h').read_bytes()
    assert [model['style'] for model in data['models']] == list(STYLES)
    for model in data['models']:
        path = WS / 'pycode/runs/fps_student_v1/refined/rf33' / model['style'] / 'model.pt'
        assert sha(path) == model['checkpoint_sha256'], 'Wrong RF33 model'
        export = path.parent.parent / 'export' / model['style']
        exported = read(export / 'manifest.json')
        assert exported['checkpoint_sha256'] == model['checkpoint_sha256']
        assert [layer['dilation'] for layer in exported['layers']] == [1, 1, 2, 4, 8]
        assert [layer['output_channels'] for layer in exported['layers'][:4]] == [6] * 4
        for name, expected in exported['files_sha256'].items():
            assert sha(export / name) == expected
    assert len(manifest['boot_ram']) == 4 and manifest['boot_ram'] == data['boot_ram']
    lanes = []
    for index in range(4):
        name = f'EfxSapphireSoc.v_toplevel_system_ramA_logic_ram_symbol{index}.bin'
        expected = manifest['boot_ram'][name]
        for folder in (BUILD, BUILD / 'ip/control_soc', BUILD / 'ip/control_soc/Testbench/modelsim',
                       BUILD / 'ip/control_soc/source/hardware/netlist'):
            assert sha(folder / name) == expected, f'Wrong CPU boot lane: {folder / name}'
        values = [int(line, 2) for line in (BUILD / name).read_text().splitlines()]
        assert len(values) == 8192 and all(0 <= value <= 255 for value in values)
        lanes.append(values)
    image = bytes(value for row in zip(*lanes) for value in row)
    binary = (BUILD / 'firmware.bin').read_bytes()
    assert len(binary) == 9692 and image == binary + bytes(32768 - len(binary))
    cpu_sim = ROOT / 'sim/fps_sapphire'
    assert (BUILD / 'ip/control_soc/Testbench/modelsim/control_soc.v').read_bytes() == (cpu_sim / 'control_soc.v').read_bytes()
    for name in manifest['boot_ram']:
        assert (BUILD / name).read_bytes() == (cpu_sim / name).read_bytes()
    return {'writes_per_style': 365, 'bytes': len(binary), 'boot_images_consistent': True,
            'models': {model['style']: model['checkpoint_sha256'] for model in data['models']}}


def native_records(text):
    records = {}
    for name, ports, attrs in re.findall(r'EFX_FF\s+(\S+)\s+\(([^;]*?)\)\s*/\*([^;]*?)\*/\s*;', text, re.S):
        parsed = {key: re.sub(r'\s+', '', value).lstrip('\\') for key, value in re.findall(r'\.(\w+)\(([^()]*)\)', ports)}
        records[name.lstrip('\\')] = (parsed, attrs)
    assert len(records) > 10000
    return records


def cdc_audit(mapped):
    data = read(BUILD / 'cdc_constraints.json')
    records = native_records(mapped)
    drivers = {ports['Q']: (name, ports) for name, (ports, attrs) in records.items()}
    scalar_names = {'system/control/scl_sync[0]~FF', 'system/control/sda_sync[0]~FF',
      'system/reader/request_sync[0]~FF', 'system/reader/window_sync[0]~FF', 'system/reader/rd_busy_sync[0]~FF',
      'system/video/ack_sync[0]~FF', 'system/video/valid_sync[0]~FF', 'system/pixel_fifo/rd_busy_sync[0]~FF',
      'system/fps/request_sync[0]~FF', 'system/fps/ack_sync[0]~FF', 'system/overlay_sync[0]~FF', 'bridge/overflow_sync[0]~FF'}
    scalar_names.update(f'system/keys/sync_meta[{i}]~FF' for i in range(4))
    scalar_names.update(f'boot/meta[{i}]~FF' for i in range(4))
    scalar_names.update('system/engine/cnn/' + name + '[0]~FF' for name in ('cfg_ack_sync', 'done_sync', 'cfg_request_sync', 'start_request_sync'))
    scalar_names.update('system/engine/cnn/' + name + '/rd_busy_sync[0]~FF' for name in ('in_stream', 'out_stream'))
    actual_scalars = scalar_names & set(records)
    assert set(data['scalar_first_stages']) == {name + '|D' for name in actual_scalars}
    assert len(actual_scalars) in (23, 24), 'Unexpected actual scalar synchronizer count'
    assert scalar_names - set(records) <= {'boot/meta[1]~FF', 'boot/meta[2]~FF', 'system/reader/rd_busy_sync[0]~FF'}
    chains = []
    for name in sorted(actual_scalars):
        ports, attrs = records[name]
        assert 'async_reg="true"' in attrs, name
        following = [(n, p) for n, (p, a) in records.items() if p.get('D') == ports['Q']]
        assert len(following) == 1, f'Scalar first stage is not one-to-one: {name}'
        assert following[0][1]['CLK'] == ports['CLK']
        chains.append({'first': name, 'second': following[0][0], 'clock': ports['CLK']})
    periods = {'CLK_25M': 40., 'CLK_27M': 37.037037, 'core_clk': 10., 'cnn_clk': 6.,
               'hdmi_tx_slow_clk': 13.468, 'sdram_clk': 2.5, 'rx_cal_clk': 2.5, 'tx_cal_clk': 2.5,
               'tx_cal_clk_90edge': 2.5, 'i_cam_ck_CLKOUT': 14.285714}
    expected_gray, expected_bundles, expected_resets = [], [], set()
    max_lines = set()
    for name, (ports, attrs) in records.items():
        if "SR_SYNC=1'b0" in attrs and ports.get('SR') not in (None, "1'b0", "1'b1"):
            expected_resets.add(name + '|SR')
        if 'addr_sync/' in name and 'addr_cntr_gry_r' in ports.get('D', ''):
            origin, source = drivers[ports['D']]
            bound = min(periods[source['CLK']], periods[ports['CLK']]) - .2
            expected_gray.append({'from': origin + '|CLK', 'to': name + '|D', 'bound_ns': bound})
            max_lines.add(f'set_max_delay {bound:.3f} -from [get_pins {{{origin}|CLK}}] -to [get_pins {{{name}|D}}]')
        if name.startswith(('system/engine/cnn/fast_cfg[', 'system/engine/cnn/fast_start[')):
            origin, source = drivers[ports['D']]
            assert origin.startswith('system/engine/cnn/cfg_mail[' if '/fast_cfg[' in name else 'system/engine/cnn/start_mail[')
            expected_bundles.append(name + '|D')
            max_lines.add(f'set_max_delay 4.800 -from [get_pins {{{origin}|CLK}}] -to [get_pins {{{name}|D}}]')
        if name.startswith(('system/capture_fps[', 'system/inference_fps[')):
            origin, source = drivers[ports['D']]
            assert origin.startswith('system/fps/bundle[')
            expected_bundles.append(name + '|D')
            max_lines.add(f'set_max_delay 13.000 -from [get_pins {{{origin}|CLK}}] -to [get_pins {{{name}|D}}]')
    assert len(expected_gray) == 166 and data['gray_paths'] == expected_gray
    assert data['bundle_paths'] == expected_bundles and 62 <= len(expected_bundles) <= 78
    assert not re.search(r'EFX_SRL8\s+\S*addr_sync/', mapped)
    assert data['no_csi_word_count_cdc']
    dphy = read(BUILD / 'dphy_cdc_proof.json')
    assert len(data['dphy_first_stages']) == 8
    assert set(data['dphy_first_stages']) == {item['first_stage'] + '|D' for item in dphy['first_stages']}
    assert data['dphy_proof_sha256'] == sha(BUILD / 'dphy_cdc_proof.json')
    expected_resets.update(dphy.get('async_reset_pins', []))
    assert set(data['async_reset_pins']) == expected_resets
    sdc = (BUILD / 'ti60_camera.sdc').read_text(encoding='utf-8')
    assert not any(word in sdc for word in ('set_clock_groups', 'set_multicycle_path'))
    actual_max = {line.strip() for line in sdc.splitlines() if line.startswith('set_max_delay')}
    assert actual_max == max_lines
    allowed_false = {f'set_false_path -to [get_pins {{{pin}}}]' for pin in
                     (set(data['scalar_first_stages']) | set(data['dphy_first_stages']) | expected_resets)}
    allowed_false.update(f'set_false_path -hold -to [get_pins {{{pin}}}]' for pin in expected_bundles)
    assert {line.strip() for line in sdc.splitlines() if line.startswith('set_false_path')} == allowed_false
    # Reconstruct constraints against the same actual map and public PT clocks
    # in disposable hardlinks; never rewrite the candidate SDC under audit.
    with tempfile.TemporaryDirectory(prefix='audit_sdc_', dir=BUILD) as directory:
        temporary = Path(directory).resolve()
        assert temporary.is_relative_to(BUILD.resolve())
        (temporary / 'outflow').mkdir()
        for name in ('outflow/ti60_camera.map.v', 'outflow/ti60_camera.pt.sdc', 'dphy_cdc_proof.json'):
            os.link(BUILD / name, temporary / name)
        load('fps_constraints_audit', Path(__file__).parent / 'constraints.py').assemble(temporary)
        assert (temporary / 'ti60_camera.sdc').read_bytes() == (BUILD / 'ti60_camera.sdc').read_bytes()
        assert read(temporary / 'cdc_constraints.json') == data
    return {'scalar_count': len(actual_scalars), 'scalar_chains': chains, 'gray_count': len(expected_gray),
            'bundle_count': len(expected_bundles), 'dphy_count': 8, 'sdc_rebuilt_identically': True}


def _audit(require_bit=True):
    manifest = read(BUILD / 'manifest.json')
    for name, expected in manifest['parent_720'].items():
        assert sha(BASE / name) == expected, 'Accepted parent changed: ' + name
    parent = read(BASE / 'signoff.json')
    assert parent['result'] == 'PASS'
    for name, expected in parent['configuration_sha256'].items():
        assert sha(BASE / name) == expected
    assert sha(BASE / 'outflow/ti60_camera.bit') == parent['bitstream_sha256']
    assert manifest['process'] == [1280, 720] and manifest['display'] == [1280, 720, 60]
    candidate = manifest['fps_candidate']
    assert candidate['channels'] == 6 and candidate['dilations'] == [1, 1, 2, 4, 8]
    assert candidate['core'] == 640 and candidate['halo'] == 16 and candidate['cfg_writes'] == 365
    assert candidate['output_bases'] == [0, 2097152, 10485760] and candidate['source_bases'] == [4194304, 6291456, 8388608]
    assert candidate['user_selected_rf33'] is True
    for name, expected in manifest['sources'].items():
        assert sha(WS / name) == expected, 'Stale source: ' + name
    for name, expected in manifest['fps_tools'].items():
        assert sha(ROOT / name) == expected, 'Stale candidate tool: ' + name
    assert str(Path(__file__).relative_to(ROOT)) in manifest['fps_tools'], 'New signoff tool must be bound explicitly'
    ns = {'e': 'http://www.efinixinc.com/enf_proj'}
    tree = ET.parse(BUILD / 'ti60_camera.xml')
    files = {str(Path(node.get('name')).relative_to(WS)) for node in tree.findall('.//e:design_file', ns)}
    assert files == set(manifest['sources'])
    assert sha(BUILD / 'ti60_camera.xml') == manifest['project_xml_sha256']
    assert tree.find('.//e:top_module', ns).get('name') == 'ti60_camera_ppi_top'
    assert tree.find('.//e:timing_model', ns).get('name') == 'I3'
    basenames = {Path(name).name for name in files}
    assert {'fps_cnn5_srl.sv', 'fps_conv3x3_srl.sv', 'fps_srl_weights.sv', 'fps_line_ram.sv', 'fps_tile_engine_3bank_srl.sv',
            'video_job_control_fps.sv', 'frame_reader_fps.sv', 'video_control_apb_fps.sv',
            'video_system_fps_srl.sv', 'axi_write_pair_fps.sv'} <= basenames
    assert 'axi_write_pair.sv' not in basenames
    for name, expected in manifest['cpu_generated'].items():
        assert sha(BUILD / name) == expected
    cpu = firmware(manifest)
    simulations = {name: bound_receipt(name) for name in (*REQUIRED_SIMULATIONS, *SRL_REQUIRED_SIMULATIONS)}
    for style in STYLES:
        name = f'sim/fps/rf33_{style}/verification.json'
        simulations[name] = bound_receipt(name)
    assert len(simulations['sim/fps_sapphire/faults/verification.json']['cases']) == 8
    current_top = BUILD / 'rtl/ti60_camera_ppi_top.sv'
    top_receipt = simulations['sim/fps/top_safety_srl/verification.json']
    assert top_receipt.get('sources_sha256', {}).get(str(current_top)) == sha(current_top), 'Need actual current SRL top safety regression'
    srl_covered = set().union(*(set(simulations[name].get('sources_sha256', {})) for name in SRL_REQUIRED_SIMULATIONS))
    for name in ('fps_cnn5_srl.sv', 'fps_conv3x3_srl.sv', 'fps_srl_weights.sv'):
        assert str(ROOT / 'rtl/fps' / name) in srl_covered, 'New SRL implementation must have current simulation/mapped evidence'
    assert simulations['sim/fps/c6_mapped/verification.json']['pixels'] == 3840
    for name, model in simulations['sim/fps/c6_mapped/verification.json']['models'].items():
        assert model['checkpoint_sha256'] == cpu['models'][name]
    srl_mapped = simulations['sim/fps_srl/mapped/verification.json']
    assert srl_mapped['pixels'] == 3840 and srl_mapped['runtime_writes_per_model'] == 365
    srl_full = simulations['sim/fps/dma720_srl/verification.json']
    assert srl_full['pixels'] == 921600 and srl_full['ui_cycles'] == 6007407
    for name, model in srl_mapped['models'].items():
        assert model['checkpoint_sha256'] == cpu['models'][name]
    assert simulations['sim/fps_scheduler/verification.json']['measurements']['max_done_interval'] < 6100000
    assert simulations['sim/fps_write_pressure2/verification.json']['coverage']['max_inflight'] == 2
    board = electrical(manifest)
    mapped_path = BUILD / 'outflow/ti60_camera.map.v'
    mapped = mapped_path.read_text(encoding='utf-8')
    assert 'pixel_bits_cnt' not in mapped and 'inst_efx_csi2_rx/' not in mapped
    map_inputs = [WS / name for name in manifest['sources']]
    map_inputs.extend(BUILD / name for name in manifest['boot_ram'])
    assert mapped_path.stat().st_mtime_ns > max(path.stat().st_mtime_ns for path in map_inputs), 'Map predates active RTL or boot data'
    timing_path = BUILD / 'outflow/ti60_camera.timing.rpt'
    assert timing_path.stat().st_mtime_ns > max((BUILD / name).stat().st_mtime_ns for name in ('ti60_camera.peri.xml', 'ti60_camera.sdc'))
    timing = timing_path.read_text(encoding='utf-8')
    assert 'Timing Model: I3' in timing
    for clock, period in {'core_clk': 10., 'cnn_clk': 6., 'hdmi_tx_slow_clk': 13.468, 'hdmi_tx_fast_clk': 2.694,
                           'sdram_clk': 2.5, 'rx_cal_clk': 2.5, 'tx_cal_clk': 2.5, 'tx_cal_clk_90edge': 2.5,
                           'i_cam_ck_CLKOUT': 14.286}.items():
        assert re.search(r'^\s*' + clock + r'\s+' + f'{period:.3f}' + r'\s', timing, re.M), clock
    section = timing.split('---------- 2. Clock Relationship Summary (begin) ----------')[1].split('---------- Clock Relationship Summary (end)')[0]
    setup_text, hold_text = section.split('Hold (Min) Clock Relationship')
    def rows(text):
        return [(item[1], item[2], float(item[3]), float(item[4])) for item in
                re.finditer(r'^\s*(\S+)\s+(\S+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+\(R-R\)', text, re.M)]
    setup, hold = rows(setup_text), rows(hold_text)
    assert len(setup) >= 22 and len(hold) >= 22
    assert min(row[3] for row in setup + hold) >= 0, 'Setup or hold failure; do not generate/release bit'
    place = (BUILD / 'outflow/ti60_camera.place.out').read_text(encoding='utf-8')
    assert not re.search(r'WARNING.*\[SDC|Unable to run|no vaild startpoints|Failed to run', place)
    for filename in ('dphy_cdc_proof.json', 'dphy_final_proof.json'):
        proof = read(BUILD / filename)
        assert proof['map_sha256'] == sha(mapped_path) and proof['dphy_sha256'] == sha(ROOT / 'vendor/camera_dphy.sv')
        assert len(proof['first_stages']) == 8
        for item in proof['first_stages']:
            assert item['only_second_stage_endpoint'] and item['interstage_slack_ns'] > 0
        for name, expected in proof['reports'].items():
            assert sha(BUILD / 'outflow' / name) == expected
    assert proof['vdb_sha256'] == sha(BUILD / 'outflow/ti60_camera.vdb')
    cdc = cdc_audit(mapped)
    report = (BUILD / 'outflow/ti60_camera.place.rpt').read_text(encoding='utf-8')
    resources = {}
    for label in ('Memory Blocks', 'DSP Blocks', 'XLRs'):
        item = re.search(r'^' + label + r': (\d+) / (\d+)', report, re.M)
        assert item and int(item[1]) <= int(item[2]), label
        resources[label] = [int(item[1]), int(item[2])]
    bit = BUILD / 'outflow/ti60_camera.bit'
    if require_bit:
        assert bit.exists() and bit.stat().st_mtime_ns > timing_path.stat().st_mtime_ns
    inputs = ['manifest.json', 'firmware_manifest.json', 'ti60_camera.xml', 'ti60_camera.peri.xml', 'ti60_camera.sdc',
              'cdc_constraints.json', 'dphy_cdc_proof.json', 'dphy_final_proof.json', 'outflow/ti60_camera.map.v',
              'outflow/ti60_camera.vdb', 'outflow/ti60_camera.timing.rpt', 'outflow/ti60_camera.place.rpt', 'outflow/ti60_camera.pinout.csv']
    return {'result': 'PASS', 'scope': 'CAD and listed behavioral/mapped validation; not physical camera, DDR concurrency or board FPS acceptance.',
            'architecture': 'C6 RF33 SRL weights full720, three output banks, independent CNN166.667MHz/UI100MHz, HDMI720p60',
            'resources': resources, 'setup_min_ns': min(row[3] for row in setup), 'hold_min_ns': min(row[3] for row in hold),
            'setup': setup, 'hold': hold, 'electrical': board, 'firmware': cpu, 'cdc': cdc,
            'configuration_sha256': {name: sha(BUILD / name) for name in inputs},
            'simulation_receipts_sha256': {name: sha(ROOT / name) for name in simulations},
            'simulation_evidence_scope': {'new_srl_implementation': list(SRL_REQUIRED_SIMULATIONS),
                                         'legacy_ff_core': 'Algorithm/unchanged-interface reference only; does not validate new SRL storage'},
            'bitstream_sha256': sha(bit) if require_bit else None, 'board_programmed': False,
            'packet_scope': manifest['packet_scope'], 'not_measured': ['physical supplies/current/temperature',
              'real sensor capture/ISP', 'real DDR/CPU/CNN/HDMI concurrency and FPS', 'analog CDC/metastability', 'actual gestures']}


def audit(require_bit=True, build_path=None):
    """Read-only release check; only the new SRL profile is eligible.

    The prior FF-storage candidate exceeds XLR capacity and remains unsigned.
    Global path assignment is scoped to this synchronous invocation; callers
    must not invoke this audit concurrently from multiple Python threads.
    """
    global BUILD
    previous = BUILD
    chosen = Path(build_path).resolve() if build_path is not None else BUILD
    assert chosen.is_relative_to((ROOT / 'build').resolve())
    assert chosen.name == 'camera_fps_rf33_srl_720', 'FF-storage profile failed device capacity; not releasable'
    BUILD = chosen
    try:
        return _audit(require_bit)
    finally:
        BUILD = previous


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-bit', action='store_true')
    parser.add_argument('--build', type=Path, default=BUILD)
    args = parser.parse_args()
    result = audit(args.require_bit, build_path=args.build)
    print(json.dumps(result, ensure_ascii=False, indent=2))
