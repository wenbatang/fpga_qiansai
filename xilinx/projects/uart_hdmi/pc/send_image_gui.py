"""Desktop image sender sharing the exact CLI UART/RGB565 protocol."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Thread
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
import zlib

from PIL import Image, ImageOps, ImageTk

from send_image import (FRAME_BYTES, HEIGHT, IMAGE_SUFFIXES, ROOT, WIDTH, Link,
                        TransferCancelled, load_rgb565, serial_module)


@dataclass(frozen=True)
class Settings:
    image: Path
    port: str
    baud: int
    resize: bool = False
    dry_run: bool = False
    chunk_bytes: int = 1024


def transfer_image(settings: Settings, events: Queue, cancel: Event):
    """Worker owns the serial port; UI updates are delivered through a queue."""
    log = lambda message: events.put(('log', message))
    progress = lambda done, total, elapsed: events.put(('progress', (done, total, elapsed)))
    started = time.monotonic()
    try:
        if cancel.is_set():
            raise TransferCancelled('已停止。')
        log(f'解码图片：{settings.image.name}')
        payload = load_rgb565(settings.image, settings.resize)
        if cancel.is_set():
            raise TransferCancelled('已停止。')
        log(f'RGB565-LE：{WIDTH}×{HEIGHT}，{len(payload):,} 字节，CRC32={zlib.crc32(payload):08X}')
        if settings.dry_run:
            events.put(('finished', ('checked', '图片检查通过，未打开串口。')))
            return
        serial, _ = serial_module()
        log(f'打开 {settings.port} · {settings.baud} baud · 8N1')
        with serial.Serial(settings.port, settings.baud, timeout=.05, write_timeout=3.,
                           rtscts=False, dsrdtr=False) as port:
            port.reset_input_buffer()
            log(f'数据包上限 {settings.chunk_bytes:,} 字节；必须与 FPGA 配置匹配。')
            link = Link(port, log=log, cancel=cancel, chunk_bytes=settings.chunk_bytes)
            frame = time.time_ns() & 0xFFFFFFFF
            link.send_frame(payload, frame, progress=progress)
        elapsed = time.monotonic() - started
        log(f'总用时 {elapsed:.3f}s（含图片解码、打开串口和所有命令确认）；请以真实板卡结果判断是否小于10秒。')
        events.put(('finished', ('sent', f'FPGA 已确认完整帧发布 · 总用时 {elapsed:.2f}s；请查看 HDMI 屏幕。')))
    except TransferCancelled as error:
        events.put(('finished', ('cancelled', str(error))))
    except Exception as error:
        message = f'{type(error).__name__}: {error}'
        if 'PermissionError(13' in str(error) or isinstance(error, PermissionError):
            message += (f'\n{settings.port} 拒绝访问：常见原因是其他发送脚本、串口助手或另一份GUI已占用端口。'
                        '请先在占用程序中停止/关闭串口，再刷新并重试。改变波特率无法解除占用。')
        events.put(('finished', ('error', message)))


class SenderApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.events = Queue()
        self.cancel = Event()
        self.worker: Thread | None = None
        self.busy = False
        self.closing = False
        self.images: list[Path] = []
        self.selected: Path | None = None
        self.photo = None
        self.preview_image = None
        self.port_info = {}
        self.controls = []
        self.folder = tk.StringVar(value=str(ROOT / 'images'))
        self.port = tk.StringVar()
        self.baud = tk.StringVar(value='115200')
        self.chunk_bytes = tk.StringVar(value='1024')
        self.resize = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value='选择图片和串口，然后开始发送。')
        self.image_info = tk.StringVar(value='尚未选择图片')
        self.connection_info = tk.StringVar(value='尚未打开串口')
        self.baud_info = tk.StringVar()
        self.progress_info = tk.StringVar(value='0 / 1,843,200 字节')
        root.title('UART → DDR3 → HDMI · 图片发送器')
        root.geometry('1060x820')
        root.minsize(960, 760)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.configure(background='#f2f5fa')
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('.', font=('Microsoft YaHei UI', 10))
        style.configure('TFrame', background='#f2f5fa')
        style.configure('TLabelframe', background='#f2f5fa')
        style.configure('TLabelframe.Label', background='#f2f5fa', foreground='#27364a')
        style.configure('TLabel', background='#f2f5fa', foreground='#27364a')
        style.configure('Title.TLabel', font=('Microsoft YaHei UI', 19, 'bold'))
        style.configure('Note.TLabel', foreground='#617089', font=('Microsoft YaHei UI', 9))
        style.configure('Send.TButton', padding=(18, 9), font=('Microsoft YaHei UI', 11, 'bold'))
        style.configure('TButton', padding=(10, 5))
        style.configure('Horizontal.TProgressbar', background='#2376db', troughcolor='#dbe4f0')
        self.build_ui()
        self.baud.trace_add('write', lambda *_: self.update_baud_info())
        self.chunk_bytes.trace_add('write', lambda *_: self.update_baud_info())
        self.update_baud_info()
        self.refresh_images()
        self.refresh_ports()
        self.root.after(80, self.poll)

    def controlled(self, widget, idle_state='normal'):
        self.controls.append((widget, idle_state))
        return widget

    def build_ui(self):
        root = self.root
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        body = ttk.Frame(root, padding=20)
        body.grid(sticky='nsew')
        body.columnconfigure(0, weight=1)
        body.rowconfigure(3, weight=1)
        ttk.Label(body, text='图片发送器', style='Title.TLabel').grid(row=0, sticky='w')
        ttk.Label(body, text='PC 串口传图 → FPGA 双缓冲 → 720p HDMI',
                  style='Note.TLabel').grid(row=1, sticky='w', pady=(3, 12))

        connection = ttk.LabelFrame(body, text='串口设置', padding=12)
        connection.grid(row=2, sticky='ew', pady=(0, 12))
        connection.columnconfigure(1, weight=1)
        ttk.Label(connection, text='串口').grid(row=0, column=0, padx=(0, 8))
        self.port_combo = self.controlled(ttk.Combobox(connection, textvariable=self.port, width=18))
        self.port_combo.grid(row=0, column=1, sticky='ew')
        self.port_combo.bind('<<ComboboxSelected>>', lambda _: self.update_port_info())
        self.controlled(ttk.Button(connection, text='刷新串口', command=self.refresh_ports)).grid(
            row=0, column=2, padx=8)
        ttk.Label(connection, text='波特率').grid(row=0, column=3, padx=(16, 8))
        self.baud_combo = self.controlled(ttk.Combobox(connection, textvariable=self.baud,
             values=('115200', '230400', '460800', '921600', '1000000', '1500000', '2000000'), width=13))
        self.baud_combo.grid(row=0, column=4)
        ttk.Label(connection, text='8N1 · 无流控', style='Note.TLabel').grid(row=0, column=5, padx=(14, 0))
        ttk.Label(connection, textvariable=self.connection_info, style='Note.TLabel').grid(
            row=1, column=0, columnspan=6, sticky='w', pady=(8, 0))
        ttk.Label(connection, textvariable=self.baud_info, wraplength=920,
                  style='Note.TLabel').grid(row=2, column=0, columnspan=6, sticky='w', pady=(5, 0))
        presets = ttk.Frame(connection)
        presets.grid(row=3, column=0, columnspan=6, sticky='w', pady=(8, 0))
        ttk.Label(presets, text='每包字节').pack(side='left', padx=(0, 8))
        self.chunk_combo = self.controlled(ttk.Combobox(presets, textvariable=self.chunk_bytes,
            values=('1024', '4096', '8192', '16384'), width=9, state='readonly'), 'readonly')
        self.chunk_combo.pack(side='left')
        self.controlled(ttk.Button(presets, text='标准 115200 / 1KB',
            command=lambda: self.set_preset(115200, 1024))).pack(side='left', padx=(12, 6))
        self.controlled(ttk.Button(presets, text='提速 2Mbps / 16KB',
            command=lambda: self.set_preset(2000000, 16384))).pack(side='left')

        images_frame = ttk.LabelFrame(body, text='图片选择与预览', padding=12)
        images_frame.grid(row=3, sticky='nsew')
        images_frame.columnconfigure(1, weight=1)
        images_frame.rowconfigure(1, weight=1)
        folder_row = ttk.Frame(images_frame)
        folder_row.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 10))
        folder_row.columnconfigure(0, weight=1)
        self.controlled(ttk.Entry(folder_row, textvariable=self.folder)).grid(row=0, column=0, sticky='ew')
        self.controlled(ttk.Button(folder_row, text='选择目录', command=self.choose_folder)).grid(
            row=0, column=1, padx=6)
        self.controlled(ttk.Button(folder_row, text='刷新图片', command=self.refresh_images)).grid(row=0, column=2)
        self.controlled(ttk.Button(folder_row, text='选择文件…', command=self.choose_file)).grid(
            row=0, column=3, padx=(6, 0))
        list_frame = ttk.Frame(images_frame)
        list_frame.grid(row=1, column=0, sticky='nsew', padx=(0, 12))
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)
        self.listbox = self.controlled(tk.Listbox(list_frame, width=25, height=13,
            font=('Consolas', 11), background='white', foreground='#27364a',
            selectbackground='#2376db', selectforeground='white', exportselection=False,
            borderwidth=0, highlightthickness=1, highlightbackground='#dbe4f0'))
        self.listbox.grid(row=0, column=0, sticky='nsew')
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.listbox.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.bind('<<ListboxSelect>>', self.select_current)
        preview_frame = ttk.Frame(images_frame)
        preview_frame.grid(row=1, column=1, sticky='nsew')
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        self.preview = tk.Canvas(preview_frame, background='#111b2b', width=600, height=300,
                                 borderwidth=0, highlightthickness=0)
        self.preview.grid(sticky='nsew')
        self.preview.bind('<Configure>', self.render_preview)
        ttk.Label(preview_frame, textvariable=self.image_info, style='Note.TLabel',
                  wraplength=600).grid(row=1, sticky='w', pady=(8, 0))
        self.controlled(ttk.Checkbutton(images_frame, text='非 720p 图片等比例缩放并补黑边',
            variable=self.resize)).grid(row=2, column=0, columnspan=2, sticky='w', pady=(10, 0))

        actions = ttk.Frame(body)
        actions.grid(row=4, sticky='ew', pady=(12, 8))
        self.send_button = self.controlled(ttk.Button(actions, text='开始发送', style='Send.TButton',
                                                      command=self.start))
        self.send_button.pack(side='left')
        self.controlled(ttk.Button(actions, text='仅检查图片', command=lambda: self.start(True))).pack(
            side='left', padx=8)
        self.stop_button = ttk.Button(actions, text='停止传输', command=self.stop, state='disabled')
        self.stop_button.pack(side='left')
        ttk.Label(actions, textvariable=self.status, wraplength=580).pack(side='left', padx=16)
        self.progress = ttk.Progressbar(body, maximum=FRAME_BYTES, mode='determinate')
        self.progress.grid(row=5, sticky='ew')
        ttk.Label(body, textvariable=self.progress_info, style='Note.TLabel').grid(
            row=6, sticky='w', pady=(5, 10))
        self.log_box = ScrolledText(body, height=6, font=('Consolas', 9), background='white',
            foreground='#27364a', borderwidth=0, highlightthickness=1, highlightbackground='#dbe4f0', state='disabled')
        self.log_box.grid(row=7, sticky='ew')

    def append_log(self, message):
        self.log_box.configure(state='normal')
        self.log_box.insert('end', f'{time.strftime("%H:%M:%S")}  {message}\n')
        # Keep long interactive sessions bounded.
        if int(self.log_box.index('end-1c').split('.')[0]) > 1000:
            self.log_box.delete('1.0', '101.0')
        self.log_box.see('end')
        self.log_box.configure(state='disabled')

    def refresh_ports(self):
        try:
            _, listing = serial_module()
            found = list(listing.comports())
            self.port_info = {p.device: p.description for p in found}
            self.port_combo.configure(values=tuple(self.port_info))
            if not self.port.get():
                preferred = next((p.device for p in found if 'CH340' in p.description.upper()), None)
                self.port.set(preferred or (found[0].device if found else ''))
            self.update_port_info()
            if not found:
                self.append_log('未发现串口，请连接板卡 P2 UART；也可手动输入串口号。')
        except Exception as error:
            self.append_log(str(error))

    def update_port_info(self):
        self.connection_info.set(self.port_info.get(self.port.get(), '可手动输入串口号；发送时才打开串口。'))

    def update_baud_info(self):
        try:
            baud = int(self.baud.get())
            if baud <= 0:
                raise ValueError
            seconds = FRAME_BYTES * 10 / baud
            chunk = int(self.chunk_bytes.get())
            if chunk <= 0:
                raise ValueError
            if baud == 115200 and chunk == 1024:
                warning = '需烧写标准版 115200 / 1KB bitstream。'
            elif baud == 2000000 and chunk <= 16384:
                warning = '需烧写提速版 2Mbps / 16KB bitstream；当前选择不会自动修改 FPGA。'
            else:
                warning = '此组合需重新构建匹配的 FPGA 配置。'
            self.baud_info.set(f'{warning} 纯像素至少 {seconds:.3f} 秒，DATA {(FRAME_BYTES+chunk-1)//chunk} 包；实际另有协议及驱动等待。')
        except ValueError:
            self.baud_info.set('请输入正整数波特率，并与 FPGA 的 UART_BAUD 保持一致。')

    def set_preset(self, baud, chunk_bytes):
        self.baud.set(str(baud))
        self.chunk_bytes.set(str(chunk_bytes))

    def choose_folder(self):
        folder = filedialog.askdirectory(parent=self.root, initialdir=self.folder.get())
        if folder:
            self.folder.set(folder)
            self.refresh_images()

    def choose_file(self):
        file = filedialog.askopenfilename(parent=self.root, initialdir=self.folder.get(),
            filetypes=[('图片', '*.png *.jpg *.jpeg *.bmp *.webp'), ('所有文件', '*.*')])
        if file:
            path = Path(file)
            if path not in self.images:
                self.images.append(path)
                self.listbox.insert('end', path.name)
            self.select_index(self.images.index(path))

    def refresh_images(self):
        folder = Path(self.folder.get())
        if not folder.is_dir():
            self.append_log(f'目录不存在：{folder}')
            return
        previous = self.selected
        self.images = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)
        self.listbox.delete(0, 'end')
        for path in self.images:
            self.listbox.insert('end', path.name)
        self.append_log(f'发现 {len(self.images)} 张图片：{folder}')
        if self.images:
            self.select_index(self.images.index(previous) if previous in self.images else 0)
        else:
            self.selected = None
            self.photo = None
            self.preview_image = None
            self.render_preview()
            self.image_info.set('请将图片放入目录，或点击“选择文件…”')

    def select_index(self, index):
        self.listbox.selection_clear(0, 'end')
        self.listbox.selection_set(index)
        self.listbox.see(index)
        self.select_current()

    def select_current(self, _event=None):
        indices = self.listbox.curselection()
        if not indices or self.busy:
            return
        self.selected = self.images[indices[0]]
        try:
            with Image.open(self.selected) as source:
                image = ImageOps.exif_transpose(source).convert('RGB')
            width, height = image.size
            self.preview_image = image
            self.render_preview()
            note = '尺寸匹配' if (width, height) == (WIDTH, HEIGHT) else '尺寸不匹配：需勾选缩放或更换图片'
            self.image_info.set(f'{self.selected.name} · {width}×{height} · {note}')
        except Exception as error:
            self.photo = None
            self.preview_image = None
            self.render_preview()
            self.image_info.set(str(error))

    def render_preview(self, _event=None):
        width = max(1, self.preview.winfo_width())
        height = max(1, self.preview.winfo_height())
        self.preview.delete('all')
        if self.preview_image is None:
            self.preview.create_text(width / 2, height / 2, text='选择一张可读取的图片',
                                     fill='white', font=('Microsoft YaHei UI', 12))
        elif width > 8 and height > 8:
            image = self.preview_image.copy()
            image.thumbnail((width - 8, height - 8), Image.Resampling.LANCZOS)
            self.photo = ImageTk.PhotoImage(image, master=self.root)
            self.preview.create_image(width / 2, height / 2, image=self.photo)

    def set_busy(self, busy):
        self.busy = busy
        for widget, idle_state in self.controls:
            widget.configure(state='disabled' if busy else idle_state)
        self.stop_button.configure(state='normal' if busy else 'disabled')

    def start(self, dry_run=False):
        if self.busy:
            return
        try:
            if self.selected is None:
                raise ValueError('请先选择图片。')
            baud = int(self.baud.get())
            if baud <= 0:
                raise ValueError('波特率必须是正整数。')
            port = self.port.get().strip()
            if not dry_run and not port:
                raise ValueError('请先选择或输入串口号。')
            chunk = int(self.chunk_bytes.get())
            if chunk not in (1024, 4096, 8192, 16384):
                raise ValueError('请选择支持的数据包大小。')
            settings = Settings(self.selected, port, baud, self.resize.get(), dry_run, chunk)
        except ValueError as error:
            messagebox.showerror('输入有误', str(error), parent=self.root)
            return
        self.cancel.clear()
        self.progress['value'] = 0
        self.progress_info.set(f'0 / {FRAME_BYTES:,} 字节')
        self.status.set('正在检查图片…' if dry_run else '正在准备传输…')
        self.set_busy(True)
        self.worker = Thread(target=transfer_image, args=(settings, self.events, self.cancel), daemon=True)
        self.worker.start()

    def stop(self):
        if self.busy:
            self.cancel.set()
            self.stop_button.configure(state='disabled')
            self.status.set('正在停止，等待当前串口操作返回…')

    def poll(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == 'log':
                    self.append_log(data)
                elif kind == 'progress':
                    done, total, elapsed = data
                    self.progress['value'] = done
                    rate = done / elapsed if elapsed > 0 else 0.
                    eta = (total - done) / rate if rate > 0 else None
                    suffix = f' · 预计剩余 {eta:.0f}s' if eta is not None else ''
                    self.progress_info.set(f'{done:,} / {total:,} 字节 · {done/total:.1%} · {elapsed:.1f}s · {rate/1024:.1f} KiB/s{suffix}')
                    if not self.cancel.is_set():
                        self.status.set('像素已确认，等待完整帧发布应答…' if done == total else '正在发送，等待 FPGA 逐包确认…')
                elif kind == 'finished':
                    result, message = data
                    self.status.set(message if result != 'error' else '传输失败，详见下方日志。')
                    self.append_log(message)
                    self.set_busy(False)
                    # Completion is emitted after the serial context has closed.
                    if self.closing:
                        self.root.destroy()
                        return
        except Empty:
            pass
        self.root.after(80, self.poll)

    def close(self):
        if self.busy:
            self.closing = True
            self.stop()
        else:
            self.root.destroy()


def main():
    root = tk.Tk()
    SenderApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
