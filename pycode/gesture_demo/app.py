"""Local webcam gesture/style preview. No UART/JTAG or image uploads."""
from pathlib import Path
import argparse,importlib.util,json,threading,time,traceback
import tkinter as tk
from tkinter import ttk
import cv2
import mediapipe as mp
import numpy as np
from PIL import Image,ImageTk
from gesture import HoldGate,classify
ROOT=Path(__file__).resolve().parent;PY=ROOT.parent
NAMES=['梵高','剪纸','漫画','水墨'];MODES=['摄像头原图','转换后','左原图＋右风格']
EDGES=[(0,1),(1,2),(2,3),(3,4),(0,5),(5,6),(6,7),(7,8),(5,9),(9,10),(10,11),(11,12),(9,13),(13,14),(14,15),(15,16),(13,17),(0,17),(17,18),(18,19),(19,20)]


class Renderer:
    def __init__(self,path):
        import torch
        self.torch=torch;torch.set_num_threads(2);self.device='cuda' if torch.cuda.is_available() else 'cpu'
        torch.backends.cudnn.allow_tf32=False;torch.backends.cuda.matmul.allow_tf32=False
        source=PY/'painterly_style/hardware_qat.py' if 'paint_final' in path.parts else PY/('painterly_style' if 'painterly_style' in path.parts else 'full720_style')/'network.py'
        if 'painterly_style' in path.parts:
            import sys
            sys.path.insert(0,str(PY/'painterly_style'))
        spec=importlib.util.spec_from_file_location('webcam_style_model',source);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.model,self.meta=module.load(path,self.device)
        if hasattr(module,'rgb565'):self.rgb565=module.rgb565
        else:
            from network import rgb565
            self.rgb565=rgb565
    def render(self,rgb,slot):
        torch=self.torch
        with torch.inference_mode():
            x=torch.from_numpy(np.ascontiguousarray(rgb.transpose(2,0,1)[None])).to(self.device,dtype=torch.float32)/255
            y=self.model(self.rgb565(x),slot)[0].permute(1,2,0).float().clamp(0,1)
            return (y.cpu().numpy()*255).round().astype(np.uint8)


class Session:
    def __init__(self,checkpoint):
        self.checkpoint=checkpoint;self.lock=threading.Lock();self.stop=threading.Event();self.worker=None
        self.mode=0;self.style=0;self.epoch=0;self.latest=None;self.error=None;self.events=[];self.frames=0;self.hand_frames=0;self.running=False
    def command(self,mode=None,style=None,reset=False):
        with self.lock:
            if mode is not None:self.mode=mode
            if style is not None:self.style=style%4
            if reset:self.mode=0;self.style=0;self.epoch+=1;self.events.append(dict(kind='reset',time=time.monotonic()))
    def start(self,camera):
        if self.worker and self.worker.is_alive():return
        self.stop.clear();self.error=None;self.worker=threading.Thread(target=self.run,args=(camera,),daemon=True);self.worker.start()
    def run(self,camera):
        cap=None
        try:
            path=ROOT/'assets/hand_landmarker.task'
            if not path.exists():raise FileNotFoundError('先运行setup_model.py下载官方模型')
            options=mp.tasks.vision.HandLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_path=str(path)),running_mode=mp.tasks.vision.RunningMode.VIDEO,num_hands=2,min_hand_detection_confidence=.5,min_hand_presence_confidence=.5,min_tracking_confidence=.5)
            cap=cv2.VideoCapture(camera,cv2.CAP_DSHOW)
            if not cap.isOpened():cap.release();cap=cv2.VideoCapture(camera,cv2.CAP_MSMF)
            if not cap.isOpened():raise RuntimeError(f'无法打开摄像头{camera}，请换编号或关闭占用程序')
            cap.set(cv2.CAP_PROP_FRAME_WIDTH,1280);cap.set(cv2.CAP_PROP_FRAME_HEIGHT,720);cap.set(cv2.CAP_PROP_FPS,30)
            renderer=Renderer(self.checkpoint) if self.checkpoint and self.checkpoint.exists() else None
            label=(str(self.checkpoint)+' · '+str(renderer.meta.get('step',''))+'步') if renderer else '未加载风格网络，仅原图/手势演示'
            gate=HoldGate();seen_epoch=self.epoch;seq=0;timestamp_ms=-1;previous=time.monotonic();failures=0;self.running=True
            with mp.tasks.vision.HandLandmarker.create_from_options(options) as detector:
                while not self.stop.is_set():
                    ok,bgr=cap.read();captured=time.monotonic()
                    if not ok:
                        failures+=1
                        if failures>=10:raise RuntimeError('连续10次采集失败，已停止并释放摄像头')
                        continue
                    failures=0;seq+=1;self.frames+=1
                    rgb=cv2.cvtColor(cv2.flip(bgr,1),cv2.COLOR_BGR2RGB)
                    # Classification sees the unstyled fresh frame; mirrored display is intentional.
                    with self.lock:mode=self.mode;slot=self.style;epoch=self.epoch
                    if epoch!=seen_epoch:gate=HoldGate();seen_epoch=epoch
                    points=[];gesture=None;hand_present=False;debug=dict(hands=0,reason='转换后界面，手势已暂停' if mode==1 else '没有检测到手')
                    if mode in [0,2]:
                        small=cv2.resize(rgb,(640,round(rgb.shape[0]*640/rgb.shape[1])))
                        timestamp_ms=max(timestamp_ms+1,round(captured*1000))
                        result=detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB,data=np.ascontiguousarray(small)),timestamp_ms)
                        hand_present=bool(result.hand_landmarks)
                        debug['hands']=len(result.hand_landmarks)
                        if debug['hands']>1:debug['reason']='请只举一只手'
                        if len(result.hand_landmarks)==1:
                            image_points=result.hand_landmarks[0];box=np.ptp(np.array([[p.x,p.y] for p in image_points]),axis=0)
                            debug.update(box=box.tolist(),handedness_score=float(result.handedness[0][0].score))
                            if min(box)>.04:
                                world=result.hand_world_landmarks[0];gesture=classify([[p.x,p.y,p.z] for p in world],debug);points=image_points
                            else:debug['reason']='手太小，请靠近镜头'
                        self.hand_frames+=int(hand_present)
                    state=gate.update(seq,captured,gesture,hand_present,mode in [0,2])
                    if state.triggered:
                        slot=state.triggered-1
                        with self.lock:self.style=slot;self.events.append(dict(kind='gesture',gesture=state.triggered,style=slot,frame=seq,time=captured,mode=mode))
                    image=rgb.copy()
                    if mode in [1,2] and renderer:
                        styled=renderer.render(rgb,slot)
                        if mode==1:image=styled
                        else:image[:,image.shape[1]//2:]=styled[:,image.shape[1]//2:]
                    for a,b in EDGES:
                        if points:cv2.line(image,(round(points[a].x*image.shape[1]),round(points[a].y*image.shape[0])),(round(points[b].x*image.shape[1]),round(points[b].y*image.shape[0])),(35,225,100),2)
                    for p in points:cv2.circle(image,(round(p.x*image.shape[1]),round(p.y*image.shape[0])),4,(255,90,30),-1)
                    elapsed=max(captured-previous,1e-6);previous=captured
                    payload=dict(image=image,mode=mode,style=slot,gesture=gesture,gate=state,debug=debug,frame=seq,fps=1/elapsed,model=label,styled=bool(renderer),capture_size=[image.shape[1],image.shape[0]])
                    if seq%15==0:
                        folder=ROOT/'build';folder.mkdir(exist_ok=True)
                        (folder/'live_status.json').write_text(json.dumps(dict(frame=seq,mode=mode,style=slot,gesture=gesture,windows=state.windows,seconds=state.seconds,gate_reason=state.reason,debug=debug,events=self.events,images_saved=False),ensure_ascii=False,indent=2),encoding='utf-8')
                    with self.lock:self.latest=payload
            self.save()
        except Exception as error:
            self.error=str(error);traceback.print_exc();self.save()
        finally:
            if cap is not None:cap.release()
            self.running=False
    def save(self):
        folder=ROOT/'build';folder.mkdir(exist_ok=True)
        with self.lock:events=list(self.events)
        (folder/'last_session.json').write_text(json.dumps(dict(frames=self.frames,hand_frames=self.hand_frames,events=events,error=self.error,images_saved=False,board_connected=False),ensure_ascii=False,indent=2),encoding='utf-8')


class Window:
    def __init__(self,args):
        self.args=args;self.root=tk.Tk();self.root.title('主机摄像头 · 1–4手势/四秒确认 · 本地演示');self.root.geometry('1100x800');self.session=Session(args.checkpoint);self.photo=None
        bar=ttk.Frame(self.root,padding=10);bar.pack(fill='x');ttk.Label(bar,text='摄像头编号').pack(side='left');self.camera=tk.StringVar(value=str(args.camera));ttk.Combobox(bar,textvariable=self.camera,values=['0','1','2','3','4'],width=4).pack(side='left',padx=8)
        ttk.Button(bar,text='开始采集',command=self.start).pack(side='left');ttk.Button(bar,text='停止并释放摄像头',command=self.session.stop.set).pack(side='left',padx=8)
        ttk.Button(bar,text='复位演示',command=lambda:self.session.command(reset=True)).pack(side='left')
        modes=ttk.Frame(self.root,padding=8);modes.pack(fill='x')
        for i,name in enumerate(MODES):ttk.Button(modes,text=name,command=lambda m=i:self.session.command(mode=m)).pack(side='left',padx=6)
        for i,name in enumerate(NAMES):ttk.Button(modes,text=f'{i+1} {name}',command=lambda s=i:self.session.command(style=s)).pack(side='left',padx=4)
        self.status=tk.StringVar(value='尚未打开摄像头');ttk.Label(self.root,textvariable=self.status,font=('Microsoft YaHei',13)).pack(fill='x',padx=16,pady=6)
        self.confirmation=tk.StringVar(value='1–4保持4秒；3可用拇指＋食指＋中指，确认后先移开手')
        ttk.Label(self.root,textvariable=self.confirmation,font=('Microsoft YaHei',18,'bold'),foreground='#17754d').pack(fill='x',padx=16,pady=3)
        self.progress=ttk.Progressbar(self.root,maximum=4);self.progress.pack(fill='x',padx=16)
        self.image=ttk.Label(self.root,anchor='center');self.image.pack(fill='both',expand=True,padx=10,pady=8)
        self.info=tk.StringVar(value='全部在本机运行，不发送串口命令。风格界面暂停手势；一次确认后先移开手。')
        ttk.Label(self.root,textvariable=self.info,wraplength=1060).pack(fill='x',padx=16,pady=8)
        self.root.protocol('WM_DELETE_WINDOW',self.close);self.root.after(40,self.poll)
        self.root.bind('<space>',lambda e:self.session.command(mode=(self.session.mode+1)%3))
        self.root.bind('<Right>',lambda e:self.session.command(style=self.session.style+1));self.root.bind('<Left>',lambda e:self.session.command(style=self.session.style-1))
        if args.autostart:self.root.after(250,self.start)
        if args.seconds:self.root.after(round(args.seconds*1000),self.close)
        print('GUI_READY',flush=True)
    def start(self):
        candidate=PY/'painterly_style/runs/paint_final/model.pt'
        if self.args.auto_checkpoint and candidate.exists():self.session.checkpoint=candidate
        try:self.session.start(int(self.camera.get()))
        except ValueError:self.status.set('摄像头编号必须为0–4的整数')
    def poll(self):
        with self.session.lock:data=self.session.latest
        if self.session.error:self.status.set('已停止：'+self.session.error)
        elif data:
            state=data['gate'];self.status.set(f"{MODES[data['mode']]} · 检测到{data['debug']['hands']}只手 · 手势{data['gesture'] or '—'} · {state.seconds:.1f}/4秒，{state.windows}/4窗口 · {state.reason} · {data['debug']['reason']}")
            if state.blocked:self.confirmation.set('已确认：'+NAMES[data['style']]+'；原图保持原图，可点“转换后”查看，先移开手再选')
            else:self.confirmation.set('当前风格：'+NAMES[data['style']]+'；保持4秒，3可伸拇指＋食指＋中指')
            self.progress['value']=state.seconds;im=Image.fromarray(data['image']);im.thumbnail((1060,590));self.photo=ImageTk.PhotoImage(im);self.image.configure(image=self.photo)
            self.info.set(f"主机预览{data['capture_size']}，约{data['fps']:.1f}fps；第{data['frame']}帧。模型：{data['model']}。{'主机浮点/QAT预览，不是FPGA帧率。' if data['styled'] else '当前没有风格输出。'} 摄像头图像不上传、不保存。")
        self.root.after(40,self.poll)
    def close(self):
        self.session.stop.set()
        if self.session.worker and self.session.worker.is_alive():self.root.after(80,self.close)
        else:self.session.save();self.root.destroy()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--camera',type=int,default=0);parser.add_argument('--checkpoint',type=Path);parser.add_argument('--autostart',action='store_true');parser.add_argument('--seconds',type=float,default=0);a=parser.parse_args()
    a.auto_checkpoint=a.checkpoint is None
    if a.checkpoint is None:
        candidate=PY/'painterly_style/runs/paint_final/model.pt';a.checkpoint=candidate if candidate.exists() else PY/'full720_style/runs/c6_v1/model.pt'
    Window(a).root.mainloop()


if __name__=='__main__':main()
