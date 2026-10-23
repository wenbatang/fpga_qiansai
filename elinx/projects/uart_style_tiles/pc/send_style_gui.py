"""Threaded Tk serial sender for the hardware style-transfer project."""
import queue
import threading
import tkinter as tk
from tkinter import filedialog,messagebox,ttk
from pathlib import Path
from send_style import send,STYLES,LABELS,PROFILES
from send_image import serial_module


class App:
    def __init__(self,window):
        self.window=window;window.title('FPGA 图像风格转换');window.geometry('760x560')
        self.events=queue.Queue();self.cancel=threading.Event();self.worker=None;self.frame=0
        self.image=tk.StringVar();self.port=tk.StringVar();self.baud=tk.StringVar(value='2000000')
        self.resize=tk.BooleanVar(value=False)
        self.profile=tk.StringVar(value='720p')
        body=ttk.Frame(window,padding=16);body.pack(fill='both',expand=True)
        ttk.Label(body,text='uart_style_tiles · 串口上传原图 · KEY0星空 / KEY1浮世绘 / KEY2水墨 / KEY3油画',wraplength=700).grid(row=0,column=0,columnspan=3,sticky='w')
        ttk.Entry(body,textvariable=self.image).grid(row=1,column=0,columnspan=2,sticky='ew')
        ttk.Button(body,text='选择图片',command=self.browse).grid(row=1,column=2,padx=5)
        for row,label,var,values in ((2,'串口',self.port,()),(3,'波特率',self.baud,('2000000',)),
                                     (5,'输入配置（须匹配 bitstream）',self.profile,tuple(PROFILES))):
            ttk.Label(body,text=label).grid(row=row,column=0,sticky='w',pady=6)
            box=ttk.Combobox(body,textvariable=var,values=values,state='readonly')
            box.grid(row=row,column=1,sticky='ew')
            if row==2:self.ports=box
        ttk.Button(body,text='刷新串口',command=self.refresh).grid(row=2,column=2,padx=5)
        ttk.Checkbutton(body,text='图片与输入配置不一致时缩放并补黑边',variable=self.resize).grid(row=6,column=0,columnspan=3,sticky='w')
        self.go=ttk.Button(body,text='上传并转换',command=self.start);self.go.grid(row=7,column=0,pady=10)
        ttk.Button(body,text='停止',command=self.cancel.set).grid(row=7,column=1)
        self.progress=ttk.Progressbar(body,maximum=100);self.progress.grid(row=8,column=0,columnspan=3,sticky='ew')
        self.text=tk.Text(body,height=13,wrap='word');self.text.grid(row=9,column=0,columnspan=3,sticky='nsew',pady=8)
        body.columnconfigure(1,weight=1);body.rowconfigure(9,weight=1)
        window.protocol('WM_DELETE_WINDOW',self.close)
        self.refresh();self.poll()

    def browse(self):
        path=filedialog.askopenfilename(initialdir=str(Path(__file__).resolve().parents[1]/'images'),
            filetypes=[('图片','*.png *.jpg *.jpeg *.bmp *.webp')])
        if path:self.image.set(path)

    def refresh(self):
        try:
            _,ports=serial_module();devices=[p.device for p in ports.comports()]
            self.ports.configure(values=devices)
            if self.port.get() not in devices:self.port.set(devices[0] if devices else '')
        except Exception as error:self.events.put(('log',str(error)))

    def start(self):
        if self.worker and self.worker.is_alive():return
        if not self.port.get() or not Path(self.image.get()).is_file():
            messagebox.showerror('缺少输入','请选择可用串口和图片');return
        settings=(self.port.get(),self.image.get(),int(self.baud.get()),16384)
        resize=self.resize.get();profile=self.profile.get();self.frame+=1;frame=self.frame
        self.cancel.clear();self.go.configure(state='disabled');self.progress['value']=0
        def task():
            try:
                send(*settings,frame=frame,resize=resize,profile=profile,cancel=self.cancel,
                    log=lambda s:self.events.put(('log',s)),
                    progress=lambda done,total,elapsed:self.events.put(('progress',100*done/total)))
            except Exception as error:self.events.put(('log',f'{type(error).__name__}: {error}'))
            finally:self.events.put(('done',None))
        self.worker=threading.Thread(target=task,daemon=True);self.worker.start()

    def poll(self):
        while True:
            try:kind,value=self.events.get_nowait()
            except queue.Empty:break
            if kind=='log':self.text.insert('end',str(value)+'\n');self.text.see('end')
            elif kind=='progress':self.progress['value']=value
            elif kind=='done':self.go.configure(state='normal')
        self.window.after(80,self.poll)

    def close(self):
        self.cancel.set()
        if self.worker and self.worker.is_alive():self.window.after(100,self.close)
        else:self.window.destroy()


if __name__=='__main__':
    root=tk.Tk();App(root);root.mainloop()

