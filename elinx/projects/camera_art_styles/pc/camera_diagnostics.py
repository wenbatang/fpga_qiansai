"""Read-only Ti60 camera diagnostics; this program never transmits serial data.

Wire record: @CAM1,<12 comma-separated 8-digit hexadecimal words>\r\n
Exactly 115 ASCII bytes per record. Parser helpers need only Python's standard
library. pyserial is imported only by the port listing / live reader commands.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
import sys
import time


MAGIC = b"@CAM1,"
FRAME_BYTES = 115
FIELD_NAMES = (
    "boot", "flags", "good_lines", "error_packets", "ppi_ui_events",
    "last_header", "capture_frames", "inference_frames", "capture_errors",
    "raw_groups", "vs_edges", "engine_cycles",
)
COUNTER_NAMES = (
    "good_lines", "error_packets", "ppi_ui_events", "capture_frames",
    "inference_frames", "capture_errors", "raw_groups", "vs_edges",
)
FLAG_NAMES = (
    "calibrated", "reset_ui", "soc_reset", "sensor_reset_n",
    "sda_release", "scl_release", "last_sda", "last_scl",
    "source_valid", "busy", "weights_valid", "front_valid",
    "capture_enable", "packet_error", "transport_fault",
)
RECORD = re.compile(rb"@CAM1,([0-9A-Fa-f]{8}(?:,[0-9A-Fa-f]{8}){11})\r\n")
FAIL_REASONS = {
    0x01: "APB 控制器标识错误",
    0x02: "摄像头 ID 的 I2C 读取失败（无 ACK 或总线异常）",
    0x03: "摄像头 ID 与预期 CD6B 不符",
    0x04: "摄像头配置写入失败 / NACK",
    0x05: "输出尺寸读回失败或不是 1920×1080",
    0x06: "开启摄像头输出的写入失败 / NACK",
    0x07: "VTS / 曝光寄存器读回失败",
    0x08: "读回的 VTS 小于 1080",
    0x09: "限制曝光值时写入失败",
    0x20: "加载的权重数量不是 1217",
    0x40: "CPU 收到非预期异常 / 中断",
}


@dataclass(frozen=True)
class DiagnosticSample:
    boot: int
    flags: int
    good_lines: int
    error_packets: int
    ppi_ui_events: int
    last_header: int
    capture_frames: int
    inference_frames: int
    capture_errors: int
    raw_groups: int
    vs_edges: int
    engine_cycles: int

    def as_dict(self) -> dict[str, int]:
        return {name: getattr(self, name) for name in FIELD_NAMES}


def parse_line(line: bytes | str) -> DiagnosticSample | None:
    """Accept one exact record; malformed, truncated, and extra fields return None."""
    if isinstance(line, str):
        try:
            line = line.encode("ascii")
        except UnicodeEncodeError:
            return None
    if not isinstance(line, bytes) or len(line) != FRAME_BYTES:
        return None
    match = RECORD.fullmatch(line)
    if match is None:
        return None
    return DiagnosticSample(*(int(word, 16) for word in match[1].split(b",")))


class FrameStreamParser:
    """Recover records across arbitrary read chunks and interrupted records.

    A new @CAM1 marker supersedes damaged input. At most one incomplete record
    (114 bytes) is retained after feed(), including after long runs of noise.
    """
    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes) -> list[DiagnosticSample]:
        self._buffer.extend(data)
        samples = []
        while True:
            start = self._buffer.find(MAGIC)
            if start < 0:
                keep = 0
                for length in range(1, len(MAGIC)):
                    if self._buffer.endswith(MAGIC[:length]):
                        keep = length
                if keep:
                    del self._buffer[:-keep]
                else:
                    self._buffer.clear()
                break
            if start:
                del self._buffer[:start]
            # Detect a new record even when the preceding one was truncated.
            restart = self._buffer.find(MAGIC, 1)
            if 0 < restart < FRAME_BYTES:
                del self._buffer[:restart]
                continue
            if len(self._buffer) < FRAME_BYTES:
                break
            sample = parse_line(bytes(self._buffer[:FRAME_BYTES]))
            if sample is None:
                del self._buffer[0]
            else:
                samples.append(sample)
                del self._buffer[:FRAME_BYTES]
        return samples


def decode_flags(flags: int) -> dict[str, bool]:
    return {name: bool(flags & (1 << bit)) for bit, name in enumerate(FLAG_NAMES)}


def counter_delta(current: int, previous: int) -> int:
    """Unsigned 32-bit wraparound difference; a hardware reset invalidates it."""
    return (current - previous) & 0xFFFFFFFF


def counter_deltas(sample: DiagnosticSample, previous: DiagnosticSample | None) -> dict[str, int]:
    if previous is None:
        return {}
    return {name: counter_delta(getattr(sample, name), getattr(previous, name))
            for name in COUNTER_NAMES}


def boot_description(boot: int) -> str:
    if boot & 0x80000000:
        reason = boot & 0x7FFFFFFF
        return "安全失败：" + FAIL_REASONS.get(reason, f"未知原因 0x{reason:08X}")
    return {
        0: "CPU 尚未报告启动",
        1: "CPU 已启动，正在复位 / 读取摄像头 ID",
        2: "ID 已通过，正在配置 / 读回 / 加载权重",
        3: "已发送开流命令，等待 / 处理实际图像数据",
    }.get(boot, f"未识别启动阶段 0x{boot:08X}")


def diagnosis(sample: DiagnosticSample, previous: DiagnosticSample | None = None) -> str:
    flags = decode_flags(sample.flags)
    if not flags["calibrated"]:
        return "DDR 尚未校准：优先排查 DDR / 复位；此时 HDMI 彩条仍可正常显示。"
    if flags["reset_ui"] or flags["soc_reset"]:
        return "DDR 已报校准，但 UI / CPU 仍在复位；检查复位状态是否持续或反复出现。"
    if sample.boot & 0x80000000:
        return (boot_description(sample.boot) + "；固件将停止采集、复位模组并释放 I2C，不会自动重试。"
                "先按错误阶段排查，勿带电插拔摄像头。")
    if sample.boot != 3:
        return boot_description(sample.boot) + "；比较连续记录，确认启动阶段是否推进。"
    if flags["transport_fault"]:
        return "PPI 传输故障已置位；检查接收 FIFO / 数据供给和错误记录，修正后再逻辑复位。"
    delta = counter_deltas(sample, previous)
    if (sample.ppi_ui_events == 0 and sample.good_lines == 0 and sample.error_packets == 0):
        return ("B3 / Q0 / L0 / E0：已发开流命令，但尚未看到有效 PPI 事件；"
                "检查实际输出、MIPI 时钟 / lane / 接收使能，不能据此断定传感器损坏。")
    if sample.ppi_ui_events > 0 and delta.get("error_packets", 0) > 0:
        return ("PPI 事件存在且包错误增长：检查 lane / 速率 / 包模式、RAW10、WC / 尺寸、ECC / CRC；"
                "尚不能归因为 CNN。")
    if sample.capture_frames == 0:
        return ("接收端已有事件但尚无完整 DDR 帧；核对好行数、RAW / VS、采集使能、帧尾检查和 DDR 写响应。"
                + ("已记录历史包错误，观察后续 ΔE。" if sample.error_packets else ""))
    if sample.inference_frames == 0:
        return "已有完整采集帧；若持续没有推理完成，检查权重有效、START / busy 和 CNN / DDR 响应。"
    if not flags["front_valid"]:
        return "CNN 已完成但尚未发布显示前台；若持续彩条，检查安全消隐换帧 / commit ACK。"
    return "已有完整处理帧发布；C / I 是累计数，观察相邻 ΔC / ΔI，仍需实屏检查画面。"


def format_sample(sample: DiagnosticSample, previous: DiagnosticSample | None = None) -> str:
    f = decode_flags(sample.flags)
    d = counter_deltas(sample, previous)
    delta_text = "首条记录，无相邻差值" if not d else " ".join(
        f"Δ{label}={d[name]}" for label, name in (
            ("C", "capture_frames"), ("I", "inference_frames"),
            ("L", "good_lines"), ("E", "error_packets"), ("Q", "ppi_ui_events"),
            ("WERR", "capture_errors"), ("RAW", "raw_groups"), ("VS", "vs_edges")))
    reset_note = ""
    if previous is not None and (
        f["reset_ui"] or f["soc_reset"] or sample.boot < previous.boot
    ):
        reset_note = " [检测到复位 / 启动阶段回退，计数差不可当吞吐指标]"
    return "\n".join((
        f"B=0x{sample.boot:08X} ({boot_description(sample.boot)}) "
        f"CAL={int(f['calibrated'])} UI_RST={int(f['reset_ui'])} SOC_RST={int(f['soc_reset'])}",
        f"C={sample.capture_frames} I={sample.inference_frames} L={sample.good_lines} "
        f"E={sample.error_packets} Q={sample.ppi_ui_events} WERR={sample.capture_errors} "
        f"RAW={sample.raw_groups} VS={sample.vs_edges} CYCLES={sample.engine_cycles} "
        f"HEADER=0x{sample.last_header:08X}",
        f"CAP={int(f['capture_enable'])} SRC={int(f['source_valid'])} BUSY={int(f['busy'])} "
        f"WEIGHT={int(f['weights_valid'])} FRONT={int(f['front_valid'])} "
        f"模组复位释放={int(f['sensor_reset_n'])} "
        f"I2C末次读回 SDA/SCL={int(f['last_sda'])}/{int(f['last_scl'])} "
        f"释放={int(f['sda_release'])}/{int(f['scl_release'])} "
        f"PKT_ERR={int(f['packet_error'])} TRANS_ERR={int(f['transport_fault'])}",
        delta_text + reset_note,
        "建议：" + diagnosis(sample, previous),
    ))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="只读 Ti60 摄像头诊断：不发送数据、不下载 FPGA、不修改驱动。")
    parser.add_argument("--list", action="store_true", help="列出可用串口后退出")
    parser.add_argument("--port", help="诊断串口，例如 COM31；先关闭占用该端口的 GUI")
    parser.add_argument("--baud", type=int, default=115200, help="诊断输出波特率，默认 115200，须匹配诊断 bit")
    parser.add_argument("--log", type=Path, help="追加 JSONL 日志路径；包含原始帧和解析字段")
    args = parser.parse_args(argv)
    if args.baud <= 0:
        parser.error("波特率必须大于 0")
    if not args.list and not args.port:
        parser.error("请用 --list 查看端口，或用 --port COMx 读取诊断数据")
    try:
        import serial
        from serial.tools import list_ports
    except ImportError:
        print("缺少 pyserial，请在当前 Python 环境执行：python -m pip install pyserial", file=sys.stderr)
        return 2
    if args.list:
        ports = list(list_ports.comports())
        if not ports:
            print("未找到串口。")
        for port in ports:
            print(f"{port.device}: {port.description} [{port.hwid}]")
        return 0
    log = None
    link = None
    try:
        if args.log:
            args.log.parent.mkdir(parents=True, exist_ok=True)
            log = args.log.open("a", encoding="utf-8")
        # Do not open in Serial(..., port=...) first: set both control lines
        # before opening. The application never asserts DTR or RTS. The OS /
        # adapter may briefly change a line while opening; the V4 normal UART
        # channel does not map these lines to camera reset.
        link = serial.Serial(port=None, baudrate=args.baud, bytesize=serial.EIGHTBITS,
                             parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
                             timeout=0.5, xonxoff=False, rtscts=False, dsrdtr=False)
        link.dtr = False
        link.rts = False
        link.port = args.port
        link.open()
        print(f"只读 {args.port}，{args.baud} 8N1，DTR/RTS=False；Ctrl+C 停止。")
        print("仅新诊断 bit 输出 @CAM1 帧；原 camera_ppi60 的 TX 恒高，没有日志。")
        print("C/I/L/E/Q 为累计计数；Δ 为相邻记录的32位模差，不等同于实测 FPS。")
        stream = FrameStreamParser()
        previous = None
        previous_time = None
        last_warning = time.monotonic()
        while True:
            data = link.read(512)
            now = time.monotonic()
            for sample in stream.feed(data):
                timestamp = datetime.now().astimezone().isoformat(timespec="milliseconds")
                interval = None if previous_time is None else now - previous_time
                print(f"\n[{timestamp}]" + ("" if interval is None else f" 主机采样间隔 {interval:.3f}s"))
                print(format_sample(sample, previous), flush=True)
                if log:
                    raw = MAGIC.decode("ascii") + ",".join(f"{getattr(sample, n):08X}" for n in FIELD_NAMES) + "\r\n"
                    entry = {"time": timestamp, "host_interval_seconds": interval,
                             "fields": sample.as_dict(), "flags": decode_flags(sample.flags),
                             "counter_deltas": counter_deltas(sample, previous),
                             "raw_frame": raw, "advice": diagnosis(sample, previous)}
                    log.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    log.flush()
                previous, previous_time = sample, now
                last_warning = now
            if now - last_warning >= 5:
                print("5秒未收到合法 @CAM1 记录：核对诊断 bit、端口和 115200 波特率；未发送任何请求。", flush=True)
                last_warning = now
    except KeyboardInterrupt:
        print("\n已停止只读诊断。")
        return 0
    except (serial.SerialException, OSError) as exc:
        print(f"诊断读取失败：{exc}\n检查串口是否被上传 GUI / 串口助手占用。", file=sys.stderr)
        return 1
    finally:
        if link is not None:
            link.close()
        if log is not None:
            log.close()


if __name__ == "__main__":
    raise SystemExit(main())
