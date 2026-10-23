"""Latest-only host-camera snapshots, serialized over the existing raw frame protocol."""
from __future__ import annotations
import argparse
from dataclasses import dataclass
from threading import Condition, Event, Thread
import time,math
from PIL import Image, ImageOps
from send_image import Link, TransferCancelled, pack_rgb565, serial_module
from send_style import PROFILES


def opencv():
    try:
        import cv2
        return cv2
    except ImportError as error:
        raise RuntimeError('请安装摄像头依赖：python -m pip install -r pc/requirements.txt') from error


@dataclass(frozen=True)
class CameraSettings:
    index: int = 0
    backend: str = 'DSHOW'
    width: int = 1280
    height: int = 720
    fps: float = 15.

    def validate(self):
        if self.index < 0 or self.width < 1 or self.height < 1 or not 0 < self.fps <= 120:
            raise ValueError('摄像头编号/分辨率/FPS无效')
        if self.backend not in ('DSHOW', 'MSMF', 'AUTO'):
            raise ValueError('Unsupported capture backend')


class LatestCamera:
    """Capture owns its handle; consumers copy one slot, never an unbounded queue."""
    def __init__(self, settings=CameraSettings(), capture_factory=None):
        settings.validate()
        self.settings=settings;self.factory=capture_factory
        self.condition=Condition();self.stop_event=Event()
        self.thread=None;self.frame=None;self.count=0;self.error=None
        self.opened_at=0.;self.timestamp=0.

    def start(self):
        if self.thread is not None:raise RuntimeError('Camera object cannot be restarted')
        self.thread=Thread(target=self._capture,daemon=True,name='latest-camera');self.thread.start()
        return self

    def _capture(self):
        camera=None
        try:
            cv=opencv();s=self.settings
            backend={'DSHOW':cv.CAP_DSHOW,'MSMF':cv.CAP_MSMF,'AUTO':cv.CAP_ANY}[s.backend]
            camera=(self.factory or cv.VideoCapture)(s.index,backend)
            if not camera.isOpened():raise RuntimeError(f'摄像头{s.index}无法打开；可尝试其他编号或后端')
            camera.set(cv.CAP_PROP_FRAME_WIDTH,s.width);camera.set(cv.CAP_PROP_FRAME_HEIGHT,s.height)
            camera.set(cv.CAP_PROP_FPS,s.fps)
            self.opened_at=time.monotonic()
            while not self.stop_event.is_set():
                began=time.monotonic();ok,bgr=camera.read()
                if not ok or bgr is None:raise RuntimeError('摄像头读取失败/已断开')
                if bgr.ndim!=3 or bgr.shape[2]!=3:raise RuntimeError('摄像头没有返回BGR三通道图像')
                with self.condition:
                    self.frame=bgr.copy();self.count+=1;self.timestamp=time.monotonic();self.condition.notify_all()
                self.stop_event.wait(max(0.,1/s.fps-(time.monotonic()-began)))
        except Exception as error:
            with self.condition:self.error=error;self.condition.notify_all()
        finally:
            if camera is not None:camera.release()
            with self.condition:self.condition.notify_all()

    def snapshot(self, after=0, cancel=None, timeout=10.):
        deadline=time.monotonic()+timeout
        with self.condition:
            while True:
                if cancel is not None and cancel.is_set():raise TransferCancelled('已停止摄像头上传')
                if self.error is not None:raise self.error
                if self.stop_event.is_set():raise TransferCancelled('摄像头已停止')
                if self.frame is not None and self.count>after:
                    return self.frame.copy(),self.count,self.timestamp
                remaining=deadline-time.monotonic()
                if remaining<=0:raise TimeoutError('等待摄像头新画面超时')
                self.condition.wait(min(.1,remaining))

    def preview(self):
        with self.condition:
            if self.frame is None:return None
            return self.frame.copy(),self.count,self.timestamp

    def stop(self):
        self.stop_event.set()
        with self.condition:self.condition.notify_all()
        if self.thread is not None:
            self.thread.join(3.)
            if self.thread.is_alive():raise RuntimeError('摄像头驱动仍在阻塞读取，等待其退出后才能再次开始')


def camera_image(bgr, profile):
    """Explicit BGR -> RGB; aspect-preserving padding to the selected wire profile."""
    if profile not in PROFILES:raise ValueError('Unsupported bitstream profile')
    rgb=Image.fromarray(bgr[...,::-1].copy())
    return ImageOps.pad(rgb,PROFILES[profile],Image.Resampling.LANCZOS,color=(0,0,0))


def stream(camera, port_name, baud=2000000, profile='720p', interval=2.,
           cancel=None, log=print, progress=None, on_frame=None, max_frames=0,
           serial_factory=None, frame_start=1, stop_after_frame=None):
    """One connection, one frame in flight; count success only after END ACK."""
    if not math.isfinite(interval) or interval<0 or baud<=0 or max_frames<0 or not 1<=frame_start<=0xffffffff:
        raise ValueError('Invalid transmission settings')
    cancel=cancel or Event();width,height=PROFILES[profile]
    if cancel.is_set():raise TransferCancelled('已停止摄像头上传')
    if serial_factory is None:serial_factory=serial_module()[0].Serial
    completed=0;last_capture=0;skipped=0;began=time.monotonic()
    with serial_factory(port_name,baud,timeout=.02,write_timeout=3.) as port:
        port.reset_input_buffer()
        link=Link(port,timeout=3.,chunk_bytes=16384,cancel=cancel,log=log,width=width,height=height)
        try:
            while not cancel.is_set() and not (stop_after_frame is not None and stop_after_frame.is_set()) and (not max_frames or completed<max_frames):
                bgr,number,captured=camera.snapshot(last_capture,cancel)
                skipped+=max(0,number-last_capture-1);last_capture=number
                image=camera_image(bgr,profile);payload=pack_rgb565(image)
                frame=(frame_start+completed)&0xffffffff
                start=time.monotonic()
                log(f'采集#{number} → 帧#{frame}：相机{bgr.shape[1]}×{bgr.shape[0]}，上传{width}×{height} RGB565')
                link.send_frame(payload,frame,progress)
                ack=time.monotonic();completed+=1
                # This is the last completed inference, potentially a local key job.
                inference_cycles=None
                if not cancel.is_set():
                    try:inference_cycles=link.transact(7,frame).offset
                    except TransferCancelled:pass
                    except (TimeoutError,RuntimeError) as error:log(f'完整帧已发布，但最近推理计数读取失败：{error}')
                result={'frame_id':frame,'capture_number':number,'completed_frames':completed,
                        'skipped_capture_frames':skipped,'upload_to_end_ack_seconds':ack-start,
                        'capture_age_at_ack_seconds':ack-captured,'wall_seconds':ack-began,
                        'actual_completed_upload_fps':completed/(ack-began),
                        'last_inference_cycles':inference_cycles,'last_inference_seconds':None if inference_cycles is None else inference_cycles/1e8,
                        'width':width,'height':height,'profile':profile}
                log(f'完整帧#{frame}已确认：{ack-start:.2f}s；累计{completed}张；实际上传更新{result["actual_completed_upload_fps"]:.3f}fps')
                if on_frame is not None:on_frame(result)
                if max_frames and completed>=max_frames:break
                deadline=time.monotonic()+interval
                while time.monotonic()<deadline:
                    if stop_after_frame is not None and stop_after_frame.is_set():break
                    if cancel.wait(min(.1,deadline-time.monotonic())):break
        finally:
            if cancel.is_set():
                # Discard OS queued bytes; board rejects incomplete frames and a
                # future send_frame begins with ABORT and a fresh COBS delimiter.
                try:port.reset_output_buffer()
                except (AttributeError,OSError):pass
    return {'completed_frames':completed,'skipped_capture_frames':skipped,'wall_seconds':time.monotonic()-began}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',required=True);parser.add_argument('--baud',type=int,default=2000000)
    parser.add_argument('--profile',choices=PROFILES,default='720p')
    parser.add_argument('--camera',type=int,default=0);parser.add_argument('--backend',choices=('DSHOW','MSMF','AUTO'),default='DSHOW')
    parser.add_argument('--capture-fps',type=float,default=15.);parser.add_argument('--interval',type=float,default=2.)
    parser.add_argument('--frames',type=int,default=0,help='0: continue until Ctrl+C')
    args=parser.parse_args();cancel=Event();camera=LatestCamera(CameraSettings(index=args.camera,backend=args.backend,fps=args.capture_fps))
    import signal
    signal.signal(signal.SIGINT,lambda *_:cancel.set())
    try:
        camera.start();stream(camera,args.port,args.baud,args.profile,args.interval,cancel,max_frames=args.frames)
    except TransferCancelled:print('已停止；已提交的完整帧可能继续转换，不回滚显示。')
    finally:cancel.set();camera.stop()


if __name__=='__main__':main()

