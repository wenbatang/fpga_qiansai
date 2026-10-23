"""Bind a newly routed bitstream to actual learned weights and reviewed pins."""
from pathlib import Path
import argparse,datetime,hashlib,json,re,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];WORKSPACE=ROOT.parents[2]


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-dir',type=Path)
    parser.add_argument('--profile',choices=('720p','vga'),default='720p')
    args=parser.parse_args()
    build=ROOT/'build' if args.profile=='720p' else ROOT/'build/vga'
    project=(args.project_dir or ROOT/('vivado' if args.profile=='720p' else 'vivado_vga')).resolve()
    script='create_project.tcl' if args.profile=='720p' else 'create_project_vga.tcl'
    manifest_path=build/'source_manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    for relative,expected in manifest['source_sha256'].items():
        if digest(WORKSPACE/relative)!=expected:raise ValueError(f'Source changed after preparation: {relative}')
    for name,expected in manifest['compiled_weights_sha256'].items():
        if digest(ROOT/'build/weights'/name)!=expected:raise ValueError(f'Compiled weight changed: {name}')
    if digest(ROOT/'scripts'/script)!=manifest['generated_tcl_sha256']:
        raise ValueError('Generated build script changed')
    bit=project/'uart_style.runs/impl_1/uart_style_top.bit'
    if not bit.exists() or bit.stat().st_mtime_ns<manifest_path.stat().st_mtime_ns:
        raise ValueError('No newly generated bitstream after this preparation')
    settings=dict(line.split('\t',1) for line in (project/'build_settings.tsv').read_text().splitlines())
    if settings['part']!='xc7k325tffg676-2' or settings['tool']!='2023.2':raise ValueError(settings)
    width,height=(1280,720) if args.profile=='720p' else (640,480)
    expected=f'UART_BAUD=2000000 UART_PAYLOAD_BYTES=16384 PROC_WIDTH={width} PROC_HEIGHT={height}'
    if settings['generic']!=expected:raise ValueError('Unexpected UART/image profile')
    if (manifest['scope']['width'],manifest['scope']['height'])!=(width,height):raise ValueError('Manifest profile mismatch')
    report=(project/'timing_summary.rpt').read_text(errors='replace')
    match=re.search(r'^\s*(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(\d+)\s+(\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(\d+)\s+(\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(\d+)\s+(\d+)\s*$',report,re.M)
    if not match:raise ValueError('Timing summary row missing')
    values=match.groups();wns,whs,wpws=map(float,(values[0],values[4],values[8]))
    if min(wns,whs,wpws)<0 or any(int(values[i]) for i in (2,6,10)):
        raise ValueError('Setup/hold/pulse-width timing failed')
    console=(build/'vivado_console.log').read_text(errors='replace')
    if not re.search(r'^BUILD PASS: WNS=',console,re.M) or re.search(r'^ERROR:',console,re.M):
        raise ValueError('Full build did not pass its gates')
    audit=subprocess.run([sys.executable,'-I',str(ROOT/'scripts/check_board.py'),'--project-dir',str(project)],
                         capture_output=True,text=True,check=True)
    reports={name:digest(project/name) for name in ('timing_summary.rpt','utilization.rpt','drc.rpt','cdc.rpt',
             'bus_skew.rpt','methodology.rpt','clock_interaction.rpt','pin_audit.tsv','clocks.tsv','build_settings.tsv','check_timing.rpt')}
    if any((project/name).stat().st_mtime_ns<manifest_path.stat().st_mtime_ns for name in reports):
        raise ValueError('A report predates the current prepared sources')
    receipt={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'scope':f'Xilinx static {width}x{height} RGB565 UART input -> learned FPGA CNN -> 720p HDMI; compilation/electrical audit only',
             'bitstream':str(bit),'bitstream_sha256':digest(bit),'source_manifest_sha256':digest(manifest_path),
             'wns_ns':wns,'whs_ns':whs,'wpws_ns':wpws,'build_settings':settings,'board_audit':audit.stdout.strip(),
             'report_sha256':reports,'models':manifest['models'],'compiled_weights_sha256':manifest['compiled_weights_sha256'],
             'not_measured':['real USB UART END ACK total time','real board inference FPS/HDMI','Ti60 full placement/routing',
                             'MIPI camera/RISC-V/FPS overlay','hardware programming']}
    (build/'signoff.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(audit.stdout,end='');print(f'PASS new bitstream: {bit}\nSHA256={receipt["bitstream_sha256"]}\nWNS={wns} WHS={whs} WPWS={wpws}')


if __name__=='__main__':main()
