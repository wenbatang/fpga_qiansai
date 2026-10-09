"""Exact no-retry UART wire budget, including packet escaping and ACKs."""
from pathlib import Path
import argparse
import json
import struct
import zlib

from send_image import (ABORT, BEGIN, DATA, END, FRAME_BYTES, IMAGE_SUFFIXES,
                        ROOT, Packet, load_rgb565)


def estimate(payload: bytes, baud: int, chunk_bytes: int) -> dict:
    if len(payload) != FRAME_BYTES or baud <= 0 or chunk_bytes not in (1024, 4096, 8192, 16384):
        raise ValueError('Expected complete 720p RGB565, positive baud and supported packet size')
    sequence = 0
    tx_bytes = rx_bytes = 0

    def add(command, offset=0, data=b'', accepted=0):
        nonlocal sequence, tx_bytes, rx_bytes
        sequence += 1
        tx_bytes += len(Packet(command, sequence, 0, offset, data).encode())
        rx_bytes += len(Packet(command | 0x80, sequence, 0, accepted, b'\0').encode())

    add(ABORT)
    add(BEGIN, data=struct.pack('<I', zlib.crc32(payload)))
    for offset in range(0, len(payload), chunk_bytes):
        block = payload[offset:offset + chunk_bytes]
        add(DATA, offset, block, offset + len(block))
    add(END, offset=len(payload), accepted=len(payload))
    wire_seconds = (tx_bytes + rx_bytes) * 10 / baud
    packets = (len(payload) + chunk_bytes - 1) // chunk_bytes
    return dict(baud=baud, chunk_bytes=chunk_bytes, data_packets=packets,
                transactions=packets + 3, payload_bytes=len(payload),
                tx_wire_bytes=tx_bytes, ack_wire_bytes=rx_bytes,
                pure_pixel_seconds=len(payload)*10/baud,
                uart_wire_seconds=wire_seconds,
                remaining_budget_to_10_seconds=10 - wire_seconds,
                assumption='frame_id=0; no retries; excludes decoding, DDR writes, USB/driver/software waits and final display boundary')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=Path, default=ROOT/'images')
    parser.add_argument('--image', type=Path)
    parser.add_argument('--baud', type=int, default=2000000)
    parser.add_argument('--chunk-bytes', type=int, choices=(1024, 4096, 8192, 16384), default=16384)
    parser.add_argument('--json', type=Path)
    args = parser.parse_args()
    images = [args.image] if args.image else sorted(p for p in args.folder.iterdir()
                   if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)
    rows = []
    for path in images:
        row = {'image': str(path), **estimate(load_rgb565(path), args.baud, args.chunk_bytes)}
        rows.append(row)
        print(f'{path.name}: {row["data_packets"]} DATA packets; UART + ACK {row["uart_wire_seconds"]:.4f}s; remaining 10s budget {row["remaining_budget_to_10_seconds"]:.4f}s')
    if rows:
        bounds = [r['uart_wire_seconds'] for r in rows]
        print(f'{len(rows)} images: wire budget {min(bounds):.4f}..{max(bounds):.4f}s. USB/driver/DDR/software latency and retries are additional; this is not a board measurement.')
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
