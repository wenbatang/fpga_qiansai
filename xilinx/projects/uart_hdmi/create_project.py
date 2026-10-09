"""Prepare independent MIG configuration and a reproducible local Vivado project."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parents[2]
REFERENCE = WORKSPACE / "xilinx" / "xc7k325tffg_base"
DEFAULT_VIVADO = Path("E:/softare_FPGA/vivado2023/Vivado/2023.2/bin/vivado.bat")
sys.path.insert(0, str(ROOT / "scripts"))
from desktop_process import run as run_desktop


def write_if_changed(path: Path, content: str | bytes):
    data = content.encode("utf-8") if isinstance(content, str) else content
    if not path.exists() or path.read_bytes() != data:
        path.write_bytes(data)


def prepare(baud: int, payload_bytes: int = 1024, profile: str = "standard"):
    project_folder = "vivado_fast" if profile == "fast" else "vivado"
    mig_source = REFERENCE / "17ddr3_axi_read_write/17ddr3_axi_read_write.srcs/sources_1/ip/mig_7series_0/mig_a.prj"
    config = ET.parse(mig_source)
    root = config.getroot()
    expected = {"TargetFPGA": "xc7k325t-ffg676/-2", "MemoryDevice": "DDR3_SDRAM/Components/MT41K256M16XX-107",
                "DataWidth": "32", "InputClkFreq": "800", "PortInterface": "AXI",
                "C0_S_AXI_ADDR_WIDTH": "30", "C0_S_AXI_DATA_WIDTH": "128", "C0_S_AXI_ID_WIDTH": "4"}
    for tag, value in expected.items():
        if root.findtext(f".//{tag}") != value:
            raise ValueError(f"Reference MIG {tag} differs from verified baseline")
    # Memory pin assignments checked against BaseC schematic pages 4-5.
    control = root.find(".//System_Control")
    for pin in control:
        if pin.tag == "Pin" and pin.attrib.get("PADName") != "No connect":
            raise ValueError("Unexpected top-level pin binding inside the MIG configuration")
    root.find("ModuleName").text = "uart_mig"
    # BaseC FMC schematic p2: VCCAUX_IO_G0 = 1.8 V, not 2.0 V.
    # DS182 table 18 limits -2 / HP / 1.8 V to DDR3-1333. Use DDR3-800
    # (400 MHz memory / 100 MHz UI) for this static-image validation design.
    # MIG input and IDELAY reference remain at a legal 200 MHz.
    root.find(".//InputClkFreq").text = "200"
    for tag, value in {"TimePeriod": "2500", "VccAuxIO": "1.8V",
                       "MMCM_VCO": "800", "mrCasLatency": "6",
                       "mr2CasWriteLatency": "5"}.items():
        node = root.find(f".//{tag}")
        if node is None:
            raise ValueError(f"Missing MIG parameter: {tag}")
        node.text = value
    for pin in root.findall(".//PinSelection/Pin"):
        pin.set("VCCAUX_IO", "NORMAL")
    (ROOT / "ip").mkdir(exist_ok=True)
    (ROOT / "constraints").mkdir(exist_ok=True)
    (ROOT / "scripts").mkdir(exist_ok=True)
    write_if_changed(ROOT / "ip/mig.prj", ET.tostring(root, encoding="utf-8", xml_declaration=True))
    provenance = {"mig_source": str(mig_source.relative_to(WORKSPACE)),
                  "mig_sha256": hashlib.sha256(mig_source.read_bytes()).hexdigest(), "rtl": {},
                  "local_mig_changes": {"ModuleName": "uart_mig", "InputClkFreq": "800 -> 200 MHz",
                    "VCCAUX_IO": "2.0V/HIGH -> schematic 1.8V/NORMAL",
                    "TimePeriod": "1250 -> 2500 ps; DDR 400 MHz, UI 100 MHz",
                    "CAS": "CL6/CWL5 at DDR3-800"}}
    for filename in ["hdmi_encoder.sv", "hdmi_serializer10to1.sv"]:
        source = REFERENCE / "hdmi/rtl" / filename
        destination = ROOT / "rtl" / filename
        if destination.exists() and destination.read_bytes() != source.read_bytes():
            raise ValueError(f"Refusing to overwrite modified reused RTL: {destination}")
        if not destination.exists():
            shutil.copyfile(source, destination)
        provenance["rtl"][filename] = hashlib.sha256(source.read_bytes()).hexdigest()
    write_if_changed(ROOT / "ip/reference_manifest.json", json.dumps(provenance, ensure_ascii=False, indent=2))
    pins = {"sys_clk": "G22", "sys_rst_n": "D26", "uart_rx": "B20", "uart_tx": "C22", "tmds_out_en": "E22",
            "tmds_clk_p": "F17", "tmds_clk_n": "E17",
            "tmds_data_p[0]": "J15", "tmds_data_n[0]": "J16",
            "tmds_data_p[1]": "E15", "tmds_data_n[1]": "E16",
            "tmds_data_p[2]": "G17", "tmds_data_n[2]": "F18"}
    constraints = ["# BaseC schematic pages 4-7; DDR pins are supplied by MIG.",
                   "# 50 MHz input clock is constrained by uart_ddr_clocks.xdc."]
    for port, pin in pins.items():
        constraints += [f"set_property PACKAGE_PIN {pin} [get_ports {{{port}}}]",
                        f"set_property IOSTANDARD {'TMDS_33' if port.startswith('tmds_') and port!='tmds_out_en' else 'LVCMOS33'} [get_ports {{{port}}}]"]
    write_if_changed(ROOT / "constraints/cdc.xdc", "\n".join([
                    "# Apply to mapped flip-flop endpoints during implementation only.",
                    "set_false_path -to [get_pins -hier -filter {REF_PIN_NAME == CLR || REF_PIN_NAME == PRE}]",
                    r"set uart_first [get_cells -hier -regexp {.*receiver/sync_rx_reg\[0\]}]",
                    "set_false_path -from [get_ports uart_rx] -to [get_pins -of_objects $uart_first -filter {REF_PIN_NAME == D}]",
                    r"set cdc_first [get_cells -hier -regexp {.*(request_sync|window_sync|rd_busy_sync|ack_sync|valid_sync)_reg\[0\]}]",
                    "set_false_path -to [get_pins -of_objects $cdc_first -filter {REF_PIN_NAME == D}]"
                    ])+"\n")
    constraints += ["set_property CFGBVS VCCO [current_design]", "set_property CONFIG_VOLTAGE 3.3 [current_design]"]
    write_if_changed(ROOT / "constraints/board.xdc", "\n".join(constraints)+"\n")
    tcl = fr'''# Generated by create_project.py; source from any working directory.
set root [file normalize [file join [file dirname [info script]] ..]]
set project_dir [file join $root {project_folder}]
if {{[file exists [file join $project_dir uart_hdmi.xpr]]}} {{
    if {{[lsearch -exact $argv --resume]<0}} {{error "Existing project: use --resume to continue"}}
    open_project [file join $project_dir uart_hdmi.xpr]
    if {{![llength [get_files -quiet */cdc.xdc]]}} {{add_files -fileset constrs_1 [file join $root constraints cdc.xdc]}}
    set_property USED_IN_SYNTHESIS false [get_files */cdc.xdc]
    if {{[lsearch -exact $argv --update-ip]>=0}} {{
        set_property -dict [list CONFIG.CLKOUT1_REQUESTED_OUT_FREQ {{200.000}} CONFIG.CLKOUT2_USED {{false}}] [get_ips uart_ddr_clocks]
        set_property CONFIG.XML_INPUT_FILE [file join $root ip mig.prj] [get_ips uart_mig]
        reset_target all [get_ips uart_mig]
        generate_target all [get_ips]
        reset_runs uart_ddr_clocks_synth_1
        reset_runs uart_mig_synth_1
        report_ip_status -file [file join $root vivado ip_status.rpt]
    }}
}} else {{
create_project uart_hdmi $project_dir -part xc7k325tffg676-2
set_property target_language Verilog [current_project]
set_property XPM_LIBRARIES {{XPM_CDC XPM_MEMORY XPM_FIFO}} [current_project]
set_property include_dirs [list [file join $root rtl]] [get_filesets sources_1]
add_files [glob [file join $root rtl *.sv]]
add_files [glob [file join $root rtl *.svh]]
set_property top uart_hdmi_top [get_filesets sources_1]
set_property generic {{UART_BAUD={baud} UART_PAYLOAD_BYTES={payload_bytes}}} [get_filesets sources_1]
add_files -fileset constrs_1 [file join $root constraints board.xdc]
add_files -fileset constrs_1 [file join $root constraints cdc.xdc]
set_property USED_IN_SYNTHESIS false [get_files */cdc.xdc]
create_ip -name clk_wiz -vendor xilinx.com -library ip -version 6.0 -module_name uart_ddr_clocks
set_property -dict [list CONFIG.PRIM_IN_FREQ {{50.000}} CONFIG.CLKOUT1_REQUESTED_OUT_FREQ {{200.000}} CONFIG.CLKOUT2_USED {{false}} CONFIG.RESET_TYPE {{ACTIVE_LOW}} CONFIG.RESET_PORT {{resetn}} CONFIG.USE_LOCKED {{true}}] [get_ips uart_ddr_clocks]
create_ip -name mig_7series -vendor xilinx.com -library ip -version 4.2 -module_name uart_mig
set_property CONFIG.XML_INPUT_FILE [file join $root ip mig.prj] [get_ips uart_mig]
generate_target all [get_ips]
update_compile_order -fileset sources_1
report_ip_status -file [file join $root vivado ip_status.rpt]
}}
if {{[lsearch -exact $argv --build]>=0}} {{
    if {{[lsearch -exact $argv --reset-synth]>=0}} {{reset_runs synth_1}}
    if {{[get_property NEEDS_REFRESH [get_runs synth_1]]}} {{reset_runs synth_1}}
    if {{[get_property PROGRESS [get_runs synth_1]] ne "100%"}} {{
        launch_runs synth_1 -jobs 4
        wait_on_run synth_1
    }}
    if {{[get_property PROGRESS [get_runs synth_1]] ne "100%"}} {{error "Synthesis failed"}}
    if {{[get_property NEEDS_REFRESH [get_runs impl_1]]}} {{reset_runs impl_1}}
    if {{[get_property PROGRESS [get_runs impl_1]] ne "100%"}} {{
        launch_runs impl_1 -to_step write_bitstream -jobs 4
        wait_on_run impl_1
    }}
    if {{[get_property PROGRESS [get_runs impl_1]] ne "100%"}} {{error "Implementation failed"}}
    open_run impl_1
    report_timing_summary -file [file join $root vivado timing_summary.rpt]
    report_utilization -file [file join $root vivado utilization.rpt]
    report_drc -file [file join $root vivado drc.rpt]
    report_cdc -details -file [file join $root vivado cdc.rpt]
    report_bus_skew -file [file join $root vivado bus_skew.rpt]
    report_methodology -file [file join $root vivado methodology.rpt]
    report_clock_interaction -file [file join $root vivado clock_interaction.rpt]
    report_io -file [file join $root vivado io.rpt]
    set clock_fd [open [file join $root vivado clocks.tsv] w]
    puts $clock_fd "clock\tperiod_ns"
    foreach clk [lsort [get_clocks]] {{puts $clock_fd "$clk\t[get_property PERIOD $clk]"}}
    close $clock_fd
    set settings_fd [open [file join $root vivado build_settings.tsv] w]
    puts $settings_fd "part\t[get_property PART [current_project]]"
    puts $settings_fd "generic\t[get_property GENERIC [get_filesets sources_1]]"
    puts $settings_fd "tool\t[version -short]"
    close $settings_fd
    set io_fd [open [file join $root vivado pin_audit.tsv] w]
    puts $io_fd "port\tpackage_pin\tbank\tdirection\tiostandard\tvccaux_io"
    foreach port [lsort [get_ports]] {{
        set pad [get_property PACKAGE_PIN $port]
        set bank [get_property BANK [get_package_pins $pad]]
        puts $io_fd "$port\t$pad\t$bank\t[get_property DIRECTION $port]\t[get_property IOSTANDARD $port]\t[get_property VCCAUX_IO $port]"
        if {{[string match ddr3_* $port] && [get_property VCCAUX_IO $port] ne "NORMAL"}} {{error "DDR auxiliary voltage mismatch on $port"}}
    }}
    close $io_fd
    if {{[get_property CFGBVS [current_design]] ne "VCCO" || [get_property CONFIG_VOLTAGE [current_design]] != 3.3}} {{error "Configuration bank voltage does not match the schematic"}}
    # Isolated Python ignores Vivado's bundled PYTHONHOME/PYTHONPATH.
    puts [exec {{{Path(sys.executable).as_posix()}}} -I [file join $root scripts check_board.py] --project-dir $project_dir]
    check_timing -verbose -file [file join $root vivado check_timing.rpt]
    set timing_fd [open [file join $root vivado timing_summary.rpt] r]
    set timing_text [read $timing_fd]
    close $timing_fd
    if {{![regexp -line {{^\s*(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(\d+)\s+(\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(\d+)\s+(\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(\d+)\s+(\d+)\s*$}} $timing_text row wns tns sfail stotal whs ths hfail htotal wpws tpws pfail ptotal]}} {{error "Timing summary could not be parsed"}}
    if {{$wns<0 || $whs<0 || $wpws<0}} {{error "Setup/hold/pulse-width timing violations remain"}}
    if {{[llength [get_drc_violations -filter {{SEVERITY == Error}}]]}} {{error "DRC errors remain"}}
    if {{[llength [get_timing_paths -delay_type max -slack_lesser_than 0 -max_paths 1]] || [llength [get_timing_paths -delay_type min -slack_lesser_than 0 -max_paths 1]]}} {{error "Timing violations remain: inspect timing_summary.rpt"}}
    puts "BUILD PASS: WNS=$wns WHS=$whs WPWS=$wpws; inspect CDC and external IO constraints before board testing"
}}
'''
    tcl = tcl.replace("[file join $root vivado ", "[file join $project_dir ")
    script = ROOT / ("scripts/create_project_fast.tcl" if profile == "fast" else "scripts/create_project.tcl")
    write_if_changed(script, tcl)
    return script


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("standard", "fast"), default="standard",
                        help="fast: separate vivado_fast project, 2Mbps and 16KB packets")
    parser.add_argument("--baud", type=int)
    parser.add_argument("--payload-bytes", type=int, choices=(1024, 4096, 8192, 16384))
    parser.add_argument("--vivado", type=Path, default=DEFAULT_VIVADO)
    parser.add_argument("--run", action="store_true", help="Create the .xpr using Vivado batch mode")
    parser.add_argument("--build", action="store_true", help="Also synthesize, implement and generate bitstream")
    parser.add_argument("--resume", action="store_true", help="Open and continue the existing project")
    parser.add_argument("--reset-synth", action="store_true", help="Reset synthesis before rebuilding an existing project")
    parser.add_argument("--update-ip", action="store_true", help="Regenerate configured clock/MIG IP and their synthesis runs")
    args = parser.parse_args()
    args.baud = args.baud if args.baud is not None else (2000000 if args.profile == "fast" else 115200)
    args.payload_bytes = args.payload_bytes if args.payload_bytes is not None else (16384 if args.profile == "fast" else 1024)
    if args.baud <= 0:
        parser.error("baud must be positive")
    project_dir = ROOT / ("vivado_fast" if args.profile == "fast" else "vivado")
    if (args.run or args.build) and not args.resume and (project_dir / "uart_hdmi.xpr").exists():
        raise FileExistsError("Existing Vivado project: open it directly; choose a new output directory before regeneration")
    script = prepare(args.baud, args.payload_bytes, args.profile)
    print(f"Prepared {script}; UART_BAUD={args.baud}, UART_PAYLOAD_BYTES={args.payload_bytes}, profile={args.profile}")
    if args.run or args.build:
        build = ROOT / ("build/fast" if args.profile == "fast" else "build")
        (build / "logs").mkdir(parents=True, exist_ok=True)
        command = [str(args.vivado), "-mode", "batch", "-source", str(script), "-log", str(build/"logs/vivado_batch.log"), "-journal", str(build/"logs/vivado_batch.jou")]
        flags = [name for name in ("--build", "--resume", "--reset-synth", "--update-ip") if getattr(args, name[2:].replace('-', '_'))]
        if flags:
            command += ["-tclargs"] + flags
        inputs = sorted(list((ROOT / "rtl").glob("*.sv")) + list((ROOT / "rtl").glob("*.svh")) +
                        list((ROOT / "constraints").glob("*.xdc")) +
                        [ROOT / "ip/mig.prj", script, ROOT / "scripts/check_board.py", Path(__file__).resolve()])
        def fingerprints():
            return {str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in inputs}
        before = fingerprints()
        result = run_desktop(command, build, build / "logs/launcher_stdout.log")
        if result:
            code = result & 0xFFFFFFFF
            detail = "Windows runtime dependency could not be loaded" if code == 0xC0000135 else "Vivado exited before completing the requested action"
            raise RuntimeError(f"{detail} (0x{code:08X}). Project sources are preserved. Run {script} in a working Vivado installation.")
        if args.build:
            if before != fingerprints():
                raise RuntimeError("Build inputs changed while Vivado was running; rebuild before using the bitstream")
            bitstream = project_dir / "uart_hdmi.runs/impl_1/uart_hdmi_top.bit"
            receipt = {"inputs": before, "bitstream_sha256": hashlib.sha256(bitstream.read_bytes()).hexdigest(),
                       "settings": (project_dir / "build_settings.tsv").read_text(encoding="utf-8"),
                       "profile": args.profile, "bitstream": str(bitstream)}
            write_if_changed(build / "build_receipt.json", json.dumps(receipt, indent=2))
            print("BUILD RECEIPT: unchanged inputs and final bitstream SHA256 recorded")


if __name__ == "__main__":
    main()
