# UART 原图上传 + 四键风格转换 + DDR3 + 720p HDMI

本工程 `uart_style_keys` 保留串口上传原图，用板上四键选择并重新转换已经缓存的原图。旧工程和旧参数保留在 `../uart_style_hdmi/`，旧版完整备份位于它的 `build/phase_baseline_20261012/`。

入口：[完整离线架构图](architecture.html) · [按键、引脚与数据流](docs/key_control.md) · [验证记录](docs/validation.md) · [训练方案](../../../pycode/docs/distinct_styles.md)。

新增 [主机摄像头自动上传](docs/host_camera.md)：运行 `python pc/camera_gui.py`，支持原图预览、只取最新帧、自动逐张上传、“本张完成后暂停”和“立即停止”。使用现有bitstream，风格参数保持不变；不要把相机预览FPS当作串口更新FPS。

| 按键 | 引脚 | 风格 |
|---|---|---|
| KEY1 | D26 | 原复位 |
| KEY2 | J26 | 梵高星空，槽 0，默认 |
| KEY3 | E26 | 浮世绘，槽 1 |
| KEY4 | G26 | 水墨，槽 2 |
| KEY5 | H26 | 彩色油画，槽 3 |

按键为 Bank14 / 3.3V / LVCMOS33 输入，低有效。实际依据为 BaseC FMC 原理图第 4、11 页。新工程共 88 个外部端口，完整审查 DDR、HDMI、UART、时钟与按键；不可用旧版 84 端口报告代替。

## 图片上传

运行 `pc/send_style_gui.py`，选串口、2Mbps 波特率、图片以及匹配 bitstream 的配置。原图可放 `images/`；也可直接选原 `uart_hdmi/images/0001.png`。默认 720p 使用 1280×720 原图；VGA 使用 640×480 原图并居中显示在 720p60 屏幕上。

上传完成后按 KEY2–KEY5 即可重新转换，无需再次上传。处理中连续按键保留最后一次选择；没有完整原图则仅预选风格。新 BEGIN 会使原图区失效，半帧、错误或中止不会被按键读取。推理期间新的 BEGIN 返回忙，应待切换结束后上传。

CLI 示例（在项目根目录执行，替换 Python 与串口路径）：

```powershell
python pc/send_style.py --port COM29 --image ../uart_hdmi/images/0001.png --profile 720p
```

GUI 和 CLI 不发送串口风格命令。输入仍是 RGB565 小端、逐行、无 padding；COBS 请求、SLIP ACK、最大包 16KB。该软件与新 bitstream 配套，旧风格槽顺序不同。

## 新参数与本地构建

新参考：`pycode/styles/distinct_v1/`；教师：`pycode/runs/distinct_teacher_v2/`；学生与导出：`pycode/runs/distinct_student_v1/`。都留本地，不覆盖旧文件。

复用已审查的 `uart_hdmi` UART/显示读取/TMDS/MIG 可编辑源文件；按键控制、frame_writer、top、约束及引脚审查在本项目独立修改。Vivado 固定 2023.2，MIG 4.2、Clock Wizard 6.0；DDR3-800、1.5V DDR、1.8V/NORMAL VCCAUX_IO，HDMI 74.25/371.25MHz。`common/rtl` 卷积沿用已验证的五层结构。

```powershell
python create_project.py --profile 720p --build
python scripts/signoff.py --profile 720p
python create_project.py --profile vga --build
python scripts/signoff.py --profile vga
```

已有本工程项目时使用 `--resume`。两配置共享 `build/weights`；禁止构建过程中改变权重，按顺序构建。所有仿真在本项目 `sim/`，Vivado/IP 在 `vivado/` 或 `vivado_vga/`，日志/报告在 `build/`。不自动下载 FPGA，不固化 Flash。

训练、整数一致性、模块与全帧仿真、布局布线、时序及电气审查的最终结果见验证记录；当前不能将旧 bitstream 或旧上板反馈视作本版本验证。仓库按既定范围只上传源码与说明，约束/IP/权重/bitstream 等本地依赖不上传，克隆仓库不等于完整构建包。

## 本机最终产物

两配置已完成布局布线、时序与88端口电气审查，新版本未下载实板。

| 配置 | 本地bitstream | 输入尺寸 | WNS / WHS |
|---|---|---|---|
| 默认720p | [720p四按键版](vivado/uart_style.runs/impl_1/uart_style_top.bit) | 1280×720 | +0.689 / +0.049ns |
| VGA推理 | [VGA四按键版](vivado_vga/uart_style.runs/impl_1/uart_style_top.bit) | 640×480，720p居中显示 | +0.731 / +0.053ns |

默认720p可直接上传用户原 `0001.png`；切换任意风格无需重传。VGA需显式提供640×480输入或选择软件缩放，不悄悄降低默认720p分辨率。仿真推理时间分别约151.53ms、51.35ms；实际按键到出图还包括去抖和消隐等待。完整SHA256、资源、工具警告、整数与RTL检查范围见 [验证记录](docs/validation.md)。
