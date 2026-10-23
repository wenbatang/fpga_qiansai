"""Host camera preview and start/stop automatic raw-frame uploads."""
import queue,threading,time,math
import tkinter as tk
from tkinter import ttk,messagebox
from PIL import Image,ImageTk
from camera_sender import CameraSettings,LatestCamera,stream,PROFILES
from send_image import serial_module,TransferCancelled


class App:
    def __init__(self,window):
        self.window=window;window.title('主机摄像头 → Ti60 V4 四风格');window.geometry('920x820')
        self.events=queue.Queue();self.cancel=threading.Event();self.pause=threading.Event();self.worker=None;self.source=None
        self.port=tk.StringVar();self.baud=tk.StringVar(value='2000000');self.profile=tk.StringVar(value='vga')
        self.camera=tk.StringVar(value='0');self.backend=tk.StringVar(value='DSHOW')
        self.capture_fps=tk.StringVar(value='15');self.interval=tk.StringVar(value='2')
        self.preview_number=0;self.photo=None;self.stopping=False
        body=ttk.Frame(window,padding=16);body.pack(fill='both',expand=True)
        ttk.Label(body,text='预览为最新原图，HDMI显示最近完整上传的照片；KEY0星空 / KEY1浮世绘 / KEY2水墨 / KEY3油画',wraplength=860).grid(row=0,column=0,columnspan=4,sticky='w')
        self.controls=[]
        for row,label,var,values in [(1,'串口',self.port,()),(2,'波特率',self.baud,('2000000',)),(3,'输入配置（匹配bitstream）',self.profile,tuple(PROFILES)),(4,'摄像头编号',self.camera,None),(5,'摄像头后端',self.backend,('DSHOW','MSMF','AUTO')),(6,'采集上限FPS',self.capture_fps,None),(7,'每张ACK后停留秒数',self.interval,None)]:
            ttk.Label(body,text=label).grid(row=row,column=0,sticky='w',pady=3)
            control=ttk.Entry(body,textvariable=var) if values is None else ttk.Combobox(body,textvariable=var,values=values,state='readonly')
            control.grid(row=row,column=1,sticky='ew');self.controls.append((control,'normal' if values is None else 'readonly'))
            if row==1:self.ports=control
        self.refresh_button=ttk.Button(body,text='刷新串口',command=self.refresh);self.refresh_button.grid(row=1,column=2,padx=8)
        ttk.Label(body,text='相机画面自动等比缩放/补黑边到所选输入尺寸。720p串口单张线速约9.2秒，VGA约3.1秒；不是实时视频。',wraplength=420).grid(row=3,column=2,rowspan=5,columnspan=2,sticky='nw',padx=16)
        self.go=ttk.Button(body,text='开始自动采集与上传',command=self.start);self.go.grid(row=8,column=0,pady=10)
        self.stop_button=ttk.Button(body,text='立即停止',command=self.stop,state='disabled');self.stop_button.grid(row=8,column=1)
        self.pause_button=ttk.Button(body,text='本张完成后暂停',command=self.pause.set,state='disabled');self.pause_button.grid(row=8,column=2)
        self.progress=ttk.Progressbar(body,maximum=100);self.progress.grid(row=9,column=0,columnspan=4,sticky='ew')
        self.preview_label=ttk.Label(body,text='开始后显示相机最新原图预览');self.preview_label.grid(row=10,column=0,columnspan=4,pady=8)
        self.stats=ttk.Label(body,text='完整上传0张；预览FPS与板上转换FPS分别计算',wraplength=860);self.stats.grid(row=11,column=0,columnspan=4,sticky='w')
        self.text=tk.Text(body,height=9,wrap='word');self.text.grid(row=12,column=0,columnspan=4,sticky='nsew',pady=6)
        body.columnconfigure(1,weight=1);body.rowconfigure(12,weight=1)
        window.protocol('WM_DELETE_WINDOW',self.close);self.refresh();self.poll()

    def refresh(self):
        try:
            _,ports=serial_module();items=[p.device for p in ports.comports()];self.ports.configure(values=items)
            if self.port.get() not in items:self.port.set(items[0] if items else '')
        except Exception as error:self.events.put(('log',str(error)))

    def start(self):
        if self.worker is not None and self.worker.is_alive():return
        if self.source is not None and self.source.thread is not None and self.source.thread.is_alive():
            messagebox.showerror('摄像头仍在退出','驱动仍在读取，请等待其释放后再开始');return
        try:
            if not self.port.get():raise ValueError('请选择串口')
            settings=CameraSettings(index=int(self.camera.get()),backend=self.backend.get(),fps=float(self.capture_fps.get()));settings.validate()
            interval=float(self.interval.get());baud=int(self.baud.get());profile=self.profile.get();port=self.port.get()
            if not math.isfinite(interval) or interval<0:raise ValueError('停留时间必须是有限的非负秒数')
        except (ValueError,TypeError) as error:messagebox.showerror('参数错误',str(error));return
        self.cancel.clear();self.pause.clear();self.stopping=False;self.preview_number=0;self.progress['value']=0
        self.go.configure(state='disabled');self.stop_button.configure(state='normal');self.pause_button.configure(state='normal');self.refresh_button.configure(state='disabled')
        for control,_ in self.controls:control.configure(state='disabled')
        self.source=LatestCamera(settings);source=self.source
        def task():
            try:
                source.start();stream(source,port,baud,profile,interval,self.cancel,
                    log=lambda s:self.events.put(('log',s)),
                    progress=lambda done,total,elapsed:self.events.put(('progress',100*done/total)),
                    on_frame=lambda value:self.events.put(('frame',value)),
                    frame_start=(int(time.time()*1000)&0xffffffff) or 1,stop_after_frame=self.pause)
                if self.pause.is_set():self.events.put(('log','本张已完整发布，已暂停；可继续按键比较同一张照片。'))
            except TransferCancelled:self.events.put(('log','已停止；已提交的完整帧可能继续转换，部分帧不会发布。'))
            except Exception as error:self.events.put(('log',f'{type(error).__name__}: {error}'))
            finally:
                self.cancel.set()
                try:source.stop()
                except Exception as error:self.events.put(('log',str(error)))
                self.events.put(('done',None))
        self.worker=threading.Thread(target=task,daemon=True);self.worker.start()

    def stop(self):
        self.stopping=True;self.cancel.set();self.stop_button.configure(state='disabled')
        if self.source is not None:self.source.stop_event.set()

    def poll(self):
        while True:
            try:kind,value=self.events.get_nowait()
            except queue.Empty:break
            if kind=='log':self.text.insert('end',str(value)+'\n');self.text.see('end')
            elif kind=='progress':self.progress['value']=value
            elif kind=='frame':
                inference='未读取' if value['last_inference_seconds'] is None else f"{value['last_inference_seconds']*1000:.2f}ms"
                self.stats.configure(text=f'完整上传{value["completed_frames"]}张 · 采集#{value["capture_number"]} · 照片发布延迟{value["capture_age_at_ack_seconds"]:.2f}s · 实际更新{value["actual_completed_upload_fps"]:.3f}fps · 跳过采集{value["skipped_capture_frames"]}张 · 最近一次FPGA推理{inference}')
            elif kind=='done':
                self.go.configure(state='normal');self.stop_button.configure(state='disabled');self.pause_button.configure(state='disabled');self.refresh_button.configure(state='normal')
                for control,state in self.controls:control.configure(state=state)
        if self.source is not None:
            preview=self.source.preview()
            if preview is not None and preview[1]!=self.preview_number:
                bgr,number,_=preview;self.preview_number=number
                image=Image.fromarray(bgr[...,::-1].copy());image.thumbnail((640,320))
                self.photo=ImageTk.PhotoImage(image);self.preview_label.configure(image=self.photo,text='')
        self.window.after(100,self.poll)

    def close(self):
        self.stop()
        if self.worker is not None and self.worker.is_alive():self.window.after(100,self.close)
        else:self.window.destroy()


if __name__=='__main__':
    root=tk.Tk();App(root);root.mainloop()

