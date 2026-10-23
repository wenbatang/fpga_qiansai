"""Read-only CAM3 packet trace; never transmits serial data or changes hardware.

Wire format: @CAM3, + 33 HEX32 fields separated by commas + CR LF (304 bytes).
The first 12 fields and their helpers come from the unchanged CAM1 parser.
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

from camera_diagnostics import (
    DiagnosticSample, FIELD_NAMES as BASE_FIELD_NAMES, FLAG_NAMES, FAIL_REASONS,
    boot_description,
    counter_delta, counter_deltas as base_counter_deltas,
    decode_flags, diagnosis, format_sample as base_format_sample,
)

MAGIC = b"@CAM3,"
FRAME_BYTES = 304
TRACE_FIELD_NAMES = (
    "control_cycles", "control_rises", "sot_records", "lane_overflows",
    "header_errors", "format_errors", "crc_errors", "packet_interrupts",
    "fe_errors", "timeout_errors", "fs_overlaps", "first_error_context",
)
VIEW_FIELD_NAMES = ("source_pixels", "source_r_sum", "source_g_sum", "source_b_sum",
                    "output_pixels", "output_r_sum", "output_g_sum", "output_b_sum", "view_mode")
FIELD_NAMES = BASE_FIELD_NAMES + TRACE_FIELD_NAMES + VIEW_FIELD_NAMES
RECORD = re.compile(rb"@CAM3,([0-9A-Fa-f]{8}(?:,[0-9A-Fa-f]{8}){32})\r\n")


@dataclass(frozen=True)
class TraceSample(DiagnosticSample):
    control_cycles: int
    control_rises: int
    sot_records: int
    lane_overflows: int
    header_errors: int
    format_errors: int
    crc_errors: int
    packet_interrupts: int
    fe_errors: int
    timeout_errors: int
    fs_overlaps: int
    first_error_context: int

    source_pixels: int
    source_r_sum: int
    source_g_sum: int
    source_b_sum: int
    output_pixels: int
    output_r_sum: int
    output_g_sum: int
    output_b_sum: int
    view_mode: int

    def as_dict(self) -> dict[str, int]:
        return {name: getattr(self, name) for name in FIELD_NAMES}


def parse_line(line: bytes | str) -> TraceSample | None:
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
    return TraceSample(*(int(word, 16) for word in match[1].split(b",")))


class FrameStreamParser:
    """Reassemble arbitrary chunks, discarding corrupt/truncated earlier records."""
    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes) -> list[TraceSample]:
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


def counter_deltas(sample: TraceSample, previous: TraceSample | None) -> dict[str, int]:
    result = base_counter_deltas(sample, previous)
    if previous is not None:
        result.update({name: counter_delta(getattr(sample, name), getattr(previous, name))
                       for name in TRACE_FIELD_NAMES[:-1]})
    return result


def decode_context(value: int) -> dict[str, int | str]:
    """Most recent frame's first transition into bad; not a cumulative counter."""
    cause = (value >> 28) & 15
    return {
        "cause": cause,
        "cause_name": {
            0: "尚未记录", 1: "LP控制/逃逸状态", 2: "SoT同步错误", 3: "lane队列溢出",
            4: "传输FIFO故障", 5: "包头ECC或VC错误", 6: "格式/尺寸/包类型错误",
            7: "CRC/RAW余数字节错误", 8: "包未完成时遇到新SoT", 9: "FE行数或状态错误",
            10: "帧超时", 11: "重复的部分lane SoT", 12: "未结束帧内收到FS",
        }.get(cause, "保留原因"),
        "state": (value >> 26) & 3,
        "state_name": ("WAIT", "HEADER", "PAYLOAD", "CRC")[(value >> 26) & 3],
        "vs": (value >> 25) & 1,
        "hs": (value >> 24) & 1,
        "line_count": (value >> 8) & 0xFFFF,
        "raw_bytes": (value >> 4) & 15,
        "sync_seen": value & 15,
    }


def format_trace_sample(sample: TraceSample, previous: TraceSample | None = None) -> str:
    delta = counter_deltas(sample, previous)
    trace = " ".join(f"{name}={getattr(sample, name)}" for name in TRACE_FIELD_NAMES[:-1])
    changes = "首条记录，无相邻细分差值" if previous is None else " ".join(
        f"Δ{name}={delta[name]}" for name in TRACE_FIELD_NAMES[:-1])
    context = decode_context(sample.first_error_context)
    return "\n".join((base_format_sample(sample, previous), trace, changes,
                      f"first_error_context=0x{sample.first_error_context:08X}",
                      f"首错={context['cause_name']} state={context['state_name']} "
                      f"VS={context['vs']} HS={context['hs']} line={context['line_count']} "
                      f"raw_bytes={context['raw_bytes']} sync_seen=0x{context['sync_seen']:X}",
                      "细分计数包含错误条件成立的周期或记录，不能相加视为独立坏包数；"
                      "first_error_context 保持最近进入坏帧时的首错上下文。"))


def image_statistics(sample: TraceSample) -> dict:
    result = {}
    for kind in ("source", "output"):
        n = getattr(sample, kind + "_pixels")
        result[kind] = {"pixels": n, "mean_rgb": None if not n else
                        [round(getattr(sample, kind + "_" + c + "_sum") / n, 3) for c in "rgb"]}
    mode = sample.view_mode
    result["mode"] = {"requested_raw": bool(mode & 1), "engine_raw": bool(mode & 2),
                      "loaded_style": (mode >> 2) & 3, "requested_style": (mode >> 4) & 3,
                      "front_raw": bool(mode & 64)}
    return result


def format_sample(sample: TraceSample, previous: TraceSample | None = None) -> str:
    stats = image_statistics(sample)
    lines = [format_trace_sample(sample, previous)]
    for kind, label in (("source", "原图"), ("output", "输出")):
        row = stats[kind]
        lines.append(f"{label} pixels={row['pixels']} RGB均值={row['mean_rgb']}（0..255）")
    mode = stats["mode"]
    lines.append(f"已提交画面={'原画' if mode['front_raw'] else '风格画'}；"
                 f"引擎={'原画复制' if mode['engine_raw'] else 'CNN'}；"
                 f"已加载风格={mode['loaded_style']}，请求风格={mode['requested_style']}")
    lines.append("原图统计为最近完整预处理帧，输出统计为最近成功作业；两者未绑定同一帧，不能当逐像素误差。"
                 "Ixx只数CNN完成，不计原画复制。红黄棋盘表示显示欠载。")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="只读 Ti60 CAM3 包错误追踪；不发送指令，不下载 FPGA。")
    parser.add_argument("--list", action="store_true", help="列出串口后退出")
    parser.add_argument("--port", help="板载串口，例如 COM31；先关闭占用它的程序")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--log", type=Path, help="追加 JSONL 文件")
    args = parser.parse_args(argv)
    if args.baud <= 0:
        parser.error("波特率必须大于 0")
    if not args.list and not args.port:
        parser.error("请用 --list 或 --port COMx")
    try:
        import serial
        from serial.tools import list_ports
    except ImportError:
        print("缺少 pyserial：python -m pip install pyserial", file=sys.stderr)
        return 2
    if args.list:
        ports = list(list_ports.comports())
        for port in ports:
            print(f"{port.device}: {port.description} [{port.hwid}]")
        if not ports:
            print("未找到串口。")
        return 0
    log = None
    link = None
    try:
        if args.log:
            args.log.parent.mkdir(parents=True, exist_ok=True)
            log = args.log.open("a", encoding="utf-8")
        # Set DTR / RTS low before opening; never transmit or toggle them.
        # Driver / adapter opening transients cannot be controlled by this tool.
        link = serial.Serial(port=None, baudrate=args.baud, bytesize=serial.EIGHTBITS,
                             parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
                             timeout=0.5, xonxoff=False, rtscts=False, dsrdtr=False)
        link.dtr = False
        link.rts = False
        link.port = args.port
        link.open()
        print(f"只读 {args.port}，{args.baud} 8N1，DTR/RTS=False；Ctrl+C 停止。")
        print("只接收独立 camera_view60 诊断 bit 的 @CAM3；旧 @CAM1/@CAM2 不兼容。")
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
                             "first_error_context": decode_context(sample.first_error_context),
                             "raw_frame": raw, "image_statistics": image_statistics(sample), "advice": diagnosis(sample, previous)}
                    log.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    log.flush()
                previous, previous_time = sample, now
                last_warning = now
            if now - last_warning >= 5:
                print("5秒未收到合法 @CAM3：核对 camera_view60 bit、端口和115200；未发送任何请求。", flush=True)
                last_warning = now
    except KeyboardInterrupt:
        print("\n已停止只读追踪。")
        return 0
    except (serial.SerialException, OSError) as exc:
        print(f"读取失败：{exc}；检查串口占用。", file=sys.stderr)
        return 1
    finally:
        if link is not None:
            link.close()
        if log is not None:
            log.close()


if __name__ == "__main__":
    raise SystemExit(main())
