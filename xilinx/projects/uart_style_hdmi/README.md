# 串口传图与 FPGA 神经网络风格转换

本项目在 `uart_hdmi` 的已核对链路上增加实际训练的定点 CNN。与原始显示工程分开，保留其 bitstream 和源码。入口为 [architecture.html](architecture.html)。

数据流：PC 解码并打包 1280×720 RGB565 → 2Mbps UART/CRC → DDR 原图区 → FPGA 卷积、折叠 BN、饱和激活 → DDR 显示后台 → 垂直消隐发布 → 720p60 HDMI。

本项目 PC 请求使用 **COBS + 00 分隔**，限制数据转义开销；FPGA ACK 保留 SLIP 7E/7D，CRC 和 20 字节帧头保持一致。发送工具与此项目 bitstream 必须配套，不能混用旧工程的 SLIP 请求端。COBS 解帧仿真已覆盖最大包、全零、全 7D/7E、CRC、截断、溢出及超时。

## 最终模型与验证状态

- 软件教师从原模型继续各12轮；五层六通道学生各18轮，再加X/Y周期特征继续各12轮。48张留出图片用于回归，不能视为盲测。
- 最终学生：RGB+X/Y相位→6→6→6→6→RGB，膨胀率1/1/2/4/8、感受野33×33。位置特征内部生成，精确移位加法省去额外12个DSP，不增加串口数据量。
- 所有激活为 uint8，权重为 int8，累加为 int32，BN 统计及仿射参数折叠，逐层舍入和饱和；模型训练后导出实际权重。
- 四种真实权重通过整数参考、RTL逐像素和完整链路比对。640×480含显示仲裁/背压仿真为5,135,297周期，100MHz下51.35ms/帧，等效19.47fps；实际连续视频仍需上板验证。
- 两套完整工程均生成bitstream并通过源/权重/时序/电气签核，**尚未烧写或实屏验证**。详见 [验证记录](docs/validation.md) 与 [协议](docs/protocol.md)。

| 配置 | 输入/CNN尺寸 | HDMI | LUT / FF / BRAM Tile / DSP | WNS / WHS |
| --- | --- | --- | --- | --- |
| 默认720p | 1280×720 RGB565 | 720p60全屏 | 18464 / 11888 / 97.5 / 213 | +0.799 / +0.059ns |
| 可选vga | 640×480 RGB565 | 720p60居中、黑边 | 18483 / 11940 / 50.5 / 213 | +0.649 / +0.052ns |

上述为Xilinx完整系统；Ti60四风格CNN核心map为144 DSP、161 RAM10，工具和范围不同，不能相互替代。

## 文件与本地构建

`rtl/` 为可编辑工程源，`common/rtl/` 为跨平台 CNN，`pc/` 为串口发送软件；`sim/`、`build/`、`vivado/` 为本地验证与产物。IP 和约束从已复核的 `uart_hdmi` 复用，MIG 4.2、Clock Wizard 6.0、Vivado 2023.2；来源 SHA 记录在 `build/source_manifest.json`。参考原理图仍为 Kintex7 BaseC FMC，84 个外部端口不增加或改变电压。

先运行 `pycode/export_hardware.py` 导出已训练且经过 QAT 的四组模型，再执行：

```powershell
python create_project.py --export ../../../pycode/runs/fpga_student_phase/export --build --resume
python create_project.py --export ../../../pycode/runs/fpga_student_phase/export --profile vga --build --resume
python scripts/signoff.py
python scripts/signoff.py --profile vga
```

首次创建去掉`--resume`。默认权重目录是最终位置特征模型；缺权重直接报错。video_720p是有记录的居中窗口分叉，原工程不修改。两配置共用生成权重，切换模型后都需重建签核，不要在另一构建运行期间改权重。

本地默认工程/bit入口为`vivado/uart_style.xpr`和`vivado/uart_style.runs/impl_1/uart_style_top.bit`；VGA为`vivado_vga/`下对应文件。签核指纹在`build/signoff.json`和`build/vga/signoff.json`。原V3快照保存在`build/v3_baseline_720p/`，原`uart_hdmi`也保留。

当前 Git 上传规则忽略 IP、XDC、Tcl、权重与 bitstream，仓库不是完整可重建工程归档。本地必需文件仍需保留。

## 使用

在板卡下载**本项目最终签核的 bitstream**之后启动`pc/send_style_gui.py`，选择串口、2Mbps、图片、风格及输入配置。默认`720p`；`vga`仅用于对应VGA bitstream。也可：

```powershell
python pc/send_style.py --port COM29 --image images/0001.png --style vangogh
python pc/send_style.py --port COM29 --image images/0001.png --style vangogh --profile vga --resize
```

COM29仅为示例，请选自己的空闲串口。VGA命令显式缩放补黑边至640×480；默认不缩放。工具会指出错误尺寸的ACK。此程序上传原图，转换发生在FPGA；旧`uart_hdmi`bitstream没有CNN且请求编码不同。

原图放 `images/`。第三种“油墨”按用户要求分为水墨国画与油墨版画，共四种风格。CLI 使用 `ukiyoe / vangogh / inkwash / inkprint`。

## 验收边界

串口全帧上传 10 秒目标，需要实际 USB/UART 完整 END ACK 计时；640×480 推理 >15fps，需要真实权重、实际时钟和整帧吞吐测试。720p HDMI 的 60Hz 刷新不能当作推理帧率。

Xilinx 静态图链路为辅助验证。最终易灵思赛题的摄像头、RAW/RGB、DDR 帧所有权、RISC-V 驱动、实际 FPS 叠加和实时视频验收须另外完成；SC432HAI 与 SC431HAI 不能未经核对共用配置。
