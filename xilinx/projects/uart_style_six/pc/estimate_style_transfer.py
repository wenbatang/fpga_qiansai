"""Exact COBS request / SLIP ACK wire budget; excludes USB/DDR/software time."""
from pathlib import Path
import argparse,struct,zlib
from send_image import Packet,load_rgb565,FRAME_BYTES


def slip_size(body):
    return 2+sum(2 if v in (0x7d,0x7e) else 1 for v in body)


def budget(payload,baud=2000000,chunk=16384,frame=1):
    sequence=0;requests=0;acks=0
    def add(command,offset=0,data=b'',accepted=0):
        nonlocal sequence,requests,acks
        sequence+=1;requests+=len(Packet(command,sequence,frame,offset,data).encode())
        body=struct.pack('<BBHIIHHHBB',1,command|0x80,sequence,frame,accepted,1,1280,720,1,0)+b'\0'
        body+=struct.pack('<I',zlib.crc32(body));acks+=slip_size(body)
    add(4) # Sender cleanup; physical keys choose the style.
    add(1,data=struct.pack('<I',zlib.crc32(payload)))
    for offset in range(0,len(payload),chunk):
        block=payload[offset:offset+chunk];add(2,offset,block,offset+len(block))
    add(3,len(payload),accepted=len(payload))
    return {'pixel_seconds':len(payload)*10/baud,'request_bytes':requests,'ack_bytes':acks,
            'exact_wire_seconds_to_end_ack':(requests+acks)*10/baud,'packets':sequence,
            'excluded':'USB/driver scheduling, Python processing, DDR/CNN latency, vertical blank, retries'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder',type=Path);parser.add_argument('--baud',type=int,default=2000000)
    args=parser.parse_args()
    for path in sorted(args.folder.glob('*.png')):
        print(path.name,budget(load_rgb565(path),args.baud))
    # Pathological SLIP input now has a bounded COBS overhead.
    for byte in (0,0x7d,0x7e,0xff):
        print(f'constant 0x{byte:02x}',budget(bytes([byte])*FRAME_BYTES,args.baud))


if __name__=='__main__':main()
