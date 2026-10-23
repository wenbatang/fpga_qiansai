"""Upload raw RGB565; select and reprocess styles using physical KEY2..KEY5."""
from __future__ import annotations
import argparse
from pathlib import Path
import time
from threading import Event
from send_image import Link, load_rgb565, serial_module, ABORT, ROOT

STYLES={'vangogh':0,'ukiyoe':1,'inkwash':2,'oilpainting':3}
LABELS={'vangogh':'梵高·星月夜','ukiyoe':'浮世绘','inkwash':'水墨国画','oilpainting':'彩色油画'}
PROFILES={'720p':(1280,720),'vga':(640,480)}


def send(port_name,image,baud=2000000,chunk_bytes=16384,frame=1,
         resize=False,log=print,progress=None,cancel:Event|None=None,profile='720p'):
    began=time.monotonic()
    width,height=PROFILES[profile]
    payload=load_rgb565(Path(image),resize,width,height)
    serial,_=serial_module()
    with serial.Serial(port_name,baud,timeout=.02,write_timeout=3.) as port:
        port.reset_input_buffer()
        link=Link(port,timeout=3.,chunk_bytes=chunk_bytes,log=log,cancel=cancel,width=width,height=height)
        link.transact(ABORT,frame,expected_offset=0)
        transfer_start=time.monotonic()
        link.send_frame(payload,frame,progress)
        acknowledged=time.monotonic()
        metrics=link.transact(7,frame)
    inference_seconds=metrics.offset/100000000
    result={'total_seconds':time.monotonic()-began,'data_to_end_ack_seconds':acknowledged-transfer_start,
            'fpga_inference_seconds':inference_seconds,'fpga_inference_cycles':metrics.offset,
            'width':width,'height':height,'style':'physical keys','profile':profile,
            'single_frame_equivalent_fps':1/inference_seconds if inference_seconds>0 else None}
    log(f"图片上传完成：总用时 {result['total_seconds']:.3f}s；最近一次 FPGA {width}×{height} 转换 {inference_seconds*1000:.3f}ms；KEY2–KEY5 切换风格，无需再次上传。")
    if inference_seconds>0:log(f'单帧推理等效速度 {1/inference_seconds:.2f}fps；连续摄像头处理 FPS 仍需移植后验证。')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',type=Path,required=True)
    parser.add_argument('--port',required=True)
    parser.add_argument('--baud',type=int,default=2000000)
    parser.add_argument('--chunk-bytes',type=int,default=16384)
    parser.add_argument('--frame',type=int,default=1)
    parser.add_argument('--resize',action='store_true')
    parser.add_argument('--profile',choices=PROFILES,default='720p',help='Must match the programmed bitstream')
    args=parser.parse_args()
    send(args.port,args.image,args.baud,args.chunk_bytes,args.frame,args.resize,profile=args.profile)


if __name__=='__main__':main()
