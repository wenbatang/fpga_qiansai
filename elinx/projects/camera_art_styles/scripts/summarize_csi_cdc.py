"""Summarize ordinary licensed STA exports; no protected-body inspection."""
from pathlib import Path
import collections
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build/csi_cdc_515'


def rows(path):
    result = []
    for line in path.read_text(encoding='utf-8').splitlines():
        if not re.match(r'^\s*\d+\s*\|\s*-?\d+\.\d+\s*\|', line):
            continue
        parts = [x.strip() for x in line.split('|')]
        assert len(parts) == 8, (path.name, line)
        result.append({'slack_ns': float(parts[1]), 'source': parts[2]+'|'+parts[3],
                       'destination': parts[4]+'|'+parts[5], 'launch': parts[6], 'capture': parts[7]})
    return result


def classify(row):
    dest = row['destination']
    if 'pixel_bits_cnt[' in dest and '/word_count[' in row['source']:
        return 'raw_word_count_to_pixel_bits_cnt_requires_stable_window'
    if 'addr_sync/' in dest:
        return 'fifo_gray_first_stage'
    if '/syncreg' in dest and '/async_reg[0]' in dest:
        return 'named_sideband_first_stage'
    if dest.endswith(('RxHS_settle_1P~FF|D', 'RxStopState_1P~FF|D')):
        return 'dphy_control_first_stage'
    return 'REVIEW'


def main():
    report = {'status': 'INVESTIGATED_NOT_SIGNED_OFF', 'production_constraints_modified': False,
              'bit_generated': False, 'board_programmed': False,
              'official_timing_section': {'url': 'https://www.efinixinc.com/docs/mipi-csi2-rx-core-ug-v3.3.pdf',
                                         'page': 21, 'revision_item': 'DOC-2988', 'ip_version': '5.16',
                                         'current_ip': '5.15', 'backward_applicability_confirmed': False},
              'paths': {}, 'control_chain_checks': {}, 'fingerprints': {}}
    inputs = []
    for prefix in ('', 'scoped_', 'production_'):
        for direction in ('byte_to_core', 'core_to_byte'):
            path = BUILD / 'outflow' / (prefix+direction+'.rpt')
            inputs.append(path)
            data = rows(path)
            assert data and len(data) < 2000, 'Report missing or truncated'
            report['paths'][prefix+direction] = {
                'reported_unique_endpoints': len(data), 'worst_slack_ns': min(x['slack_ns'] for x in data),
                'classes': dict(collections.Counter(classify(x) for x in data)), 'rows': data}
            if prefix == 'scoped_':
                assert all(x['slack_ns'] >= 0 or classify(x) == 'raw_word_count_to_pixel_bits_cnt_requires_stable_window' for x in data)
        chains = []
        for lane in range(4):
            for signal in ('RxHS_settle', 'RxStopState'):
                path = BUILD / 'outflow' / f'{prefix}lane{lane}_{signal}_fanout.rpt'
                inputs.append(path)
                data = rows(path)
                assert len(data) == 1, (path.name, data)
                row = data[0]
                assert row['destination'] == row['source'].replace('_1P~FF|CLK', '_2P~FF|D'), row
                assert row['launch'] == row['capture'] == 'i_cam_ck_CLKOUT (RISE)', row
                assert row['slack_ns'] > 0 and re.search(r'Logic Levels\s*:\s*0', path.read_text()), row
                chains.append(row)
        report['control_chain_checks'][prefix or 'isolated'] = {'verified_first_to_second_chains': len(chains),
            'each_first_stage_has_one_reported_register_endpoint': True,
            'minimum_interstage_setup_slack_ns': min(x['slack_ns'] for x in chains), 'chains': chains}
    stress_path = ROOT / 'sim/csi_cdc_stress/verification.json'
    stress = json.loads(stress_path.read_text())
    assert stress['result'] == 'PASS' and len(stress['cases']) == 7
    report['public_port_stress'] = stress
    inputs += [stress_path, BUILD/'scoped_experiment_only.sdc', ROOT/'vendor/camera_csi.sv', ROOT/'scripts/camera_constraints.py',
               ROOT/'build/camera_vga/ti60_camera.sdc', ROOT/'build/camera_vga/manifest.json']
    for path in inputs:
        report['fingerprints'][path.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    (BUILD / 'investigation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in ('paths','control_chain_checks','fingerprints','public_port_stress')}, indent=2))
    for label, item in report['paths'].items():
        print(label, item['reported_unique_endpoints'], item['worst_slack_ns'], item['classes'])
    for label, item in report['control_chain_checks'].items():
        print(label, 'verified chains', item['verified_first_to_second_chains'], 'min slack', item['minimum_interstage_setup_slack_ns'])


if __name__ == '__main__':
    main()
