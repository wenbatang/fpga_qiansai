"""Send 1280x720 RGB565 images to the UART/DDR3/HDMI FPGA design."""
from __future__ import annotations

import argparse
from array import array
from dataclasses import dataclass
from pathlib import Path
import struct
import sys
import time
import zlib
from threading import Event
from typing import Callable

from PIL import Image, ImageOps
try:
    import numpy as _np
except ImportError:
    _np = None

ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT = 1280, 720
FRAME_BYTES = WIDTH * HEIGHT * 2
CHUNK_BYTES = 1024
MAX_CHUNK_BYTES = 16384
HEADER = struct.Struct("<BBHIIHHHBB")
BEGIN, DATA, END, ABORT, QUERY = range(1, 6)
STATUS = {0: "OK", 1: "invalid header/size", 2: "packet CRC/framing error",
          3: "frame/offset order error", 4: "receiver busy", 5: "DDR AXI error",
          6: "whole-frame CRC mismatch", 7: "session timeout", 8: "DDR not calibrated"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


def select_image(images: list[Path], choice: str) -> Path:
    """Accept a displayed filename, absolute path, or a one-based list number."""
    choice = choice.strip()
    if len(choice) >= 2 and choice[0] == choice[-1] and choice[0] in "\"'":
        choice = choice[1:-1]
    for path in images:
        if choice.casefold() in (path.name.casefold(), str(path).casefold(),
                                  str(path.resolve()).casefold()):
            return path
    if choice.isascii() and choice.isdecimal():
        number = int(choice)
        if 1 <= number <= len(images):
            return images[number - 1]
    raise ValueError("请输入列表中的图片编号或文件名，例如 1 或 0001.png")


class TransferCancelled(RuntimeError):
    """Stop waiting/sending; already published frames are not rolled back."""


def console_log(message: str):
    print(message, flush=True)


@dataclass(frozen=True)
class Packet:
    command: int
    sequence: int
    frame: int
    offset: int = 0
    payload: bytes = b""

    def encode(self) -> bytes:
        if len(self.payload) > MAX_CHUNK_BYTES:
            raise ValueError("Payload exceeds supported packet size")
        body = HEADER.pack(1, self.command, self.sequence, self.frame, self.offset,
                           len(self.payload), WIDTH, HEIGHT, 1, 0) + self.payload
        body += struct.pack("<I", zlib.crc32(body))
        escaped = bytearray(b"\x7e")
        for value in body:
            if value in (0x7E, 0x7D):
                escaped.extend((0x7D, value ^ 0x20))
            else:
                escaped.append(value)
        escaped.append(0x7E)
        return bytes(escaped)

    @staticmethod
    def decode(body: bytes) -> Packet:
        if len(body) < HEADER.size + 4:
            raise ValueError("Truncated packet")
        version, command, seq, frame, offset, length, width, height, fmt, reserved = HEADER.unpack_from(body)
        if (version, width, height, fmt, reserved) != (1, WIDTH, HEIGHT, 1, 0):
            raise ValueError("Unsupported packet header")
        if length > MAX_CHUNK_BYTES or len(body) != HEADER.size + length + 4:
            raise ValueError("Invalid packet length")
        if zlib.crc32(body[:-4]) != struct.unpack_from("<I", body, len(body)-4)[0]:
            raise ValueError("Bad CRC32")
        return Packet(command, seq, frame, offset, body[HEADER.size:-4])


class PacketStream:
    def __init__(self):
        self.started = False
        self.escaped = False
        self.buffer = bytearray()

    def feed(self, data: bytes) -> list[Packet]:
        packets = []
        for value in data:
            if value == 0x7E:
                if self.started and self.buffer and not self.escaped:
                    try:
                        packets.append(Packet.decode(bytes(self.buffer)))
                    except ValueError:
                        pass  # Invalid reply is discarded; delimiter restores synchronization.
                self.started = True
                self.escaped = False
                self.buffer.clear()
            elif self.started:
                if self.escaped:
                    self.buffer.append(value ^ 0x20)
                    self.escaped = False
                elif value == 0x7D:
                    self.escaped = True
                else:
                    self.buffer.append(value)
                if len(self.buffer) > HEADER.size + MAX_CHUNK_BYTES + 4:
                    self.started = False
                    self.buffer.clear()
        return packets


def pack_rgb565(image: Image.Image) -> bytes:
    """Identical little-endian RGB565 via optional NumPy or the portable fallback."""
    if _np is not None:
        rgb = _np.asarray(image, dtype=_np.uint8)
        r = rgb[..., 0].astype(_np.uint16)
        g = rgb[..., 1].astype(_np.uint16)
        b = rgb[..., 2].astype(_np.uint16)
        words = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
        return words.astype('<u2', copy=False).tobytes(order='C')
    rgb = image.tobytes()
    words = array("H", (((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
                        for r, g, b in zip(rgb[0::3], rgb[1::3], rgb[2::3])))
    if sys.byteorder != "little":
        words.byteswap()
    return words.tobytes()


def load_rgb565(path: Path, resize: bool = False) -> bytes:
    with Image.open(path) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
    if image.size != (WIDTH, HEIGHT):
        if not resize:
            raise ValueError(f"{path.name}: expected {WIDTH}x{HEIGHT}, got {image.size}; use --resize explicitly")
        image = ImageOps.pad(image, (WIDTH, HEIGHT), Image.Resampling.LANCZOS, color=(0, 0, 0))
    return pack_rgb565(image)


class Link:
    def __init__(self, port, retries: int = 3, timeout: float = 2.,
                 log: Callable[[str], None] | None = None, cancel: Event | None = None,
                 chunk_bytes: int = CHUNK_BYTES):
        if not 16 <= chunk_bytes <= MAX_CHUNK_BYTES or chunk_bytes % 16:
            raise ValueError("chunk_bytes must be a multiple of 16 between 16 and 16384")
        self.port, self.retries, self.timeout = port, retries, timeout
        self.chunk_bytes = chunk_bytes
        self.stream = PacketStream()
        self.sequence = 0
        self.log = console_log if log is None else log
        self.cancel = cancel

    def check_cancel(self):
        if self.cancel is not None and self.cancel.is_set():
            raise TransferCancelled("已停止传输；已发布的图片不会回滚，下次发送会重新建立会话。")

    def transact(self, command: int, frame: int, offset: int = 0, payload: bytes = b"",
                 expected_offset: int | None = None) -> Packet:
        if len(payload) > self.chunk_bytes:
            raise ValueError("Payload exceeds selected FPGA packet capacity")
        self.sequence = (self.sequence + 1) & 0xFFFF
        packet = Packet(command, self.sequence, frame, offset, payload)
        encoded = packet.encode()
        reason = "ACK timeout"
        for attempt in range(self.retries + 1):
            self.check_cancel()
            remaining = memoryview(encoded)
            while remaining:
                self.check_cancel()
                written = self.port.write(remaining)
                if written is None or written <= 0:
                    raise OSError("Serial write made no progress")
                remaining = remaining[written:]
            # ACK itself proves the request left the OS/UART buffer. Avoid
            # flush()/read(256) polling delays on every short Windows ACK.
            wire_seconds = len(encoded) * 10 / getattr(self.port, "baudrate", 115200)
            deadline = time.monotonic() + self.timeout + wire_seconds
            retry = False
            while time.monotonic() < deadline:
                self.check_cancel()
                available = max(1, min(256, getattr(self.port, "in_waiting", 1)))
                for reply in self.stream.feed(self.port.read(available)):
                    generic = reply.command == 0x80 and reply.sequence == 0xFFFF
                    if not generic and (reply.sequence != packet.sequence or reply.frame != frame or
                                        reply.command != (command | 0x80)):
                        continue
                    if len(reply.payload) != 1:
                        continue
                    status = reply.payload[0]
                    if status:
                        reason = STATUS.get(status, f"status {status}")
                        if status in (2, 4, 8):
                            retry = True
                            break
                        raise RuntimeError(f"FPGA rejected command {command}: {reason}, accepted offset {reply.offset}")
                    if generic:
                        continue
                    if expected_offset is not None and reply.offset != expected_offset:
                        raise RuntimeError(f"ACK offset {reply.offset}, expected {expected_offset}")
                    return reply
                if retry:
                    break
            self.check_cancel()
            if attempt < self.retries:
                self.log(f"  Retrying seq={packet.sequence}: {reason} ({attempt+1}/{self.retries})")
                if self.cancel is None:
                    time.sleep(.05)
                else:
                    self.cancel.wait(.05)
        raise TimeoutError(f"No valid ACK after {self.retries+1} attempts: {reason}")

    def send_frame(self, payload: bytes, frame: int,
                   progress: Callable[[int, int, float], None] | None = None):
        if len(payload) != FRAME_BYTES:
            raise ValueError("Frame byte length does not match 720p RGB565")
        self.check_cancel()
        self.transact(ABORT, frame, expected_offset=0)
        self.transact(BEGIN, frame, payload=struct.pack("<I", zlib.crc32(payload)), expected_offset=0)
        started = time.monotonic()
        if progress is not None:
            progress(0, len(payload), 0.)
        printed = started - 2
        for offset in range(0, len(payload), self.chunk_bytes):
            block = payload[offset:offset + self.chunk_bytes]
            self.transact(DATA, frame, offset, block, offset + len(block))
            now = time.monotonic()
            done = offset + len(block)
            if progress is not None:
                progress(done, len(payload), now - started)
            if now - printed >= 1 or offset + len(block) == len(payload):
                self.log(f"  {done/len(payload):6.1%}  {done:,}/{len(payload):,} bytes  {now-started:.1f}s")
                printed = now
        self.transact(END, frame, len(payload), expected_offset=len(payload))
        self.log(f"FPGA acknowledged frame {frame}; DDR complete and front buffer published ({time.monotonic()-started:.1f}s)")


def serial_module():
    try:
        import serial
        from serial.tools import list_ports
        return serial, list_ports
    except ImportError as error:
        raise RuntimeError("Install pyserial in this Python environment: python -m pip install pyserial Pillow") from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, help="Explicit image path; otherwise select from images/")
    parser.add_argument("--folder", type=Path, default=ROOT / "images")
    parser.add_argument("--port", help="Serial port, e.g. COM5")
    parser.add_argument("--baud", type=int, default=115200, help="Must match UART_BAUD in the FPGA bitstream")
    parser.add_argument("--chunk-bytes", type=int, choices=(1024, 4096, 8192, 16384), default=1024,
                        help="Must not exceed FPGA UART_PAYLOAD_BYTES; fast profile uses 16384")
    parser.add_argument("--all", action="store_true", help="Send folder images sequentially")
    parser.add_argument("--interval", type=float, default=0., help="Seconds to keep each image before sending the next")
    parser.add_argument("--resize", action="store_true", help="Letterbox non-720p images; default rejects wrong sizes")
    parser.add_argument("--list", action="store_true", help="List the reserved image folder")
    parser.add_argument("--list-ports", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Validate/encode image without opening a serial port")
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=2.)
    args = parser.parse_args()
    if args.baud < 1 or args.timeout <= 0 or args.retries < 0 or args.interval < 0:
        parser.error("Invalid baud/timeout/retries/interval")
    if args.list_ports:
        _, ports = serial_module()
        for port in ports.comports():
            print(f"{port.device}: {port.description}")
        return
    args.folder.mkdir(parents=True, exist_ok=True)
    images = ([args.image] if args.image else sorted(p for p in args.folder.iterdir()
              if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES))
    if args.list or not images:
        print(f"Image folder: {args.folder.resolve()}")
        for i, path in enumerate(images, 1):
            print(f"{i:3}. {path.name}")
        if not images:
            print("Copy your 1280x720 pictures into this folder.")
        return
    if not args.all and len(images) > 1:
        for i, path in enumerate(images, 1):
            print(f"{i:3}. {path.name}")
        images = [select_image(images, input("Image number or filename (e.g. 1 / 0001.png): "))]
    if args.dry_run:
        for path in images:
            payload = load_rgb565(path, args.resize)
            print(f"{path.name}: 1280x720 RGB565-LE, {len(payload):,} bytes, CRC32={zlib.crc32(payload):08X}; minimum pixel wire time {len(payload)*10/args.baud:.1f}s")
        return
    serial, ports = serial_module()
    if not args.port:
        available = list(ports.comports())
        for port in available:
            print(f"{port.device}: {port.description}")
        args.port = input("Serial port (e.g. COM5): ").strip()
    with serial.Serial(args.port, args.baud, timeout=.05, write_timeout=3., rtscts=False, dsrdtr=False) as port:
        port.reset_input_buffer()
        link = Link(port, args.retries, args.timeout, chunk_bytes=args.chunk_bytes)
        for i, path in enumerate(images):
            if i:
                time.sleep(args.interval)
            payload = load_rgb565(path, args.resize)
            frame = time.time_ns() & 0xFFFFFFFF
            print(f"Sending {path.name} to {args.port} at {args.baud}; raw-pixel minimum {len(payload)*10/args.baud:.1f}s", flush=True)
            link.send_frame(payload, frame)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
