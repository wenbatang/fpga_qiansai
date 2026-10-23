# Ti60 V4 新选四风格

> **当前下载入口：2026-10-22 恢复标准720p60。** 使用 [720p60_hdmi bit](build/720p60_hdmi/outflow/ti60_style.bit)，JTAG下载后先看彩条，再用原GUI选720p／2Mbps上传。仅显示扫描恢复60Hz，输入／CNN仍1280×720，引脚电平和四模型不变。全CAD／66脚签核通过，setup/hold +0.437/+0.030ns；实屏结果待验证。[本次改动、签核和用法](docs/hdmi_720p60.md)。下方30Hz诊断版为历史记录，用户反馈仍不支持。

> **2026-10-22：针对「输入不支持」的独立 720p30 诊断版已签核。** 先下载 [720p30_diag bit](build/720p30_diag/outflow/ti60_style.bit)，无需上传图片应先出彩条，再用原 GUI 选 720p／2 Mbps 传图。新增 V7 HDMI AVI／VIC62，像素扫描不再等待 DDR 校准；原引脚电平、CNN 和七套旧版保留。时序 +0.449/+0.029ns，实屏结果待用户验证。详情见[720p30 排查记录](docs/hdmi_720p30_diagnosis.md)。

> **2026-10-19 资源优化与正确原理图复查均已签核。KEY1=P14、KEY2=N14；J8不是UART。** 当前两套bit/资源/时序见[优化记录](docs/resource_optimization.md)，其余Ti60工程见[统一电气复核](../../../docs/Ti60_correct_schematic_review.md)。


独立移植 Xilinx 六风格中的 0 / 3 / 4 / 5：梵高厚涂、彩色剪纸、复古漫画、水墨。串口上传原图、按键切换并由 FPGA CNN 重新转换，HDMI 持续显示完成图像。本轮先做用户确认的串口链路，不集成摄像头和 RISC-V。

入口：[离线架构与工作流](architecture.html) · [验证记录](docs/validation.md) · [Ti60 首次使用指南](../../../docs/Ti60_programming_guide.md)。新工程目录为本目录，旧四风格、Xilinx、demo V7/V9 和训练参数保留。

## 使用

1. 使用 Ti60F225 DemoBoard V4，时序模型 I3。先核对下面链接的当前签核状态；不要下载未签核候选或其他平台配置。本轮未代为下载或固化。
2. 当前工程 `build/720p60_hdmi/ti60_style.xml`，bit 为 `build/720p60_hdmi/outflow/ti60_style.bit`。输入和CNN为 **1280×720**，显示 **720p60**。旧 `build/720p/` 和 `build/vga/` 仍是30Hz历史配置；本轮未重建VGA版，不要混选。
3. 安装 [PC 依赖](pc/requirements.txt)，运行 `python pc/send_style_gui.py`，选择实际 COM 口、**2000000** 波特率、匹配的 720p / vga。图片放 [images/](images/README.md)，选择后上传。UART 接收的是 RGB565 小端原始像素，不是 PNG/JPEG 文件。
4. **KEY0 梵高、KEY1 剪纸、KEY2 漫画、KEY3 水墨**。完整原图只需上传一次，按键重新处理。忙时保留最新选择，处理中不混用权重。上电默认梵高；KEY0+KEY3 持续一秒逻辑复位，之后需重传原图。
5. 主机相机逐张上传运行 `python pc/camera_gui.py`。仅保留最新帧，完整 END ACK 后再发下一张；可完整帧后暂停或立即停止。中断半帧源图失效，已提交图像不回滚。两个 GUI 不可同时占用同一串口。

上传 720p RGB565 的纯线速下界为 9.216 秒，协议、停等和推理需另外计时。新复用 CNN 的 END 等待期限延长到至少 15 秒，DATA 保持原短超时；停止仍检查取消事件。工具显示的单帧推理等效 FPS 不是连续视频验收。本阶段不承诺完整传图十秒或 >15fps。

## 为什么选四种

风格数会增加权重容量和选择逻辑。优化后的同一核心实际综合，六风格比四风格多 639 LUT4、132 ADD、163 FF；两者 RAM10 都为 149、DSP 都为 144。按用户条件仅保留选定四种。这是核心综合范围；整机RAM245→221、DSP153→144，XLR增加，详见[优化记录](docs/resource_optimization.md)。

保留已认可的十二通道五层参数和逐层 reflect-101 边界。三个输出通道并行、其余分组复用；条带 96 列，中央 32 列有效，左右各 32 列重叠。720p 共 40 条、VGA 共 20 条；只有全图真实边缘镜像，条带内侧不反射，不改变原图处理分辨率。复用与重叠增加计算时间，用于适配 Ti60 的容量限制。

## 本地重建

当前720p60入口为 `scripts/hdmi60/build.py`，先做对应HDMI／复位仿真，再compile／audit，见[720p60说明](docs/hdmi_720p60.md)。下方命令继续记录旧30Hz配置，不能拿它们重建出本次60Hz版本。

依赖本机 Efinity、V4 V7 原厂 DDR 源码、已冻结的 `pycode/runs/art6_v2/` 模型，以及本项目本地 `vendor/`、`sim/`、`build/`。没有加密 IP 解密或升级。Git 按现有规则只保留源码和说明，不是完整可重建工程归档。

```powershell
python scripts/prepare.py --profile 720p
python scripts/build.py --profile 720p --flow compile
python scripts/signoff.py --profile 720p
python scripts/update_architecture.py
```

先完成与当前源码匹配的模块/链路仿真。所有仿真放本项目 `sim/`，日志在 `build/`。CAD 单任务、四线程；不要构建中改权重或源文件。显式 VGA 将上述 profile 换为 `vga`。`build.py` 的 pgm 阶段只生成本地配置文件，不访问 Programmer/JTAG。

V7 DDR、PLL、引脚电气配置原样保留；UART/按键 3.3 V，时钟/TMDS Bank 1.8 V，DDR 1.5 V。最终以当前 66 脚审查和签核记录为准，CAD 不能代替实物供电、DDR 校准、显示、温升和实际性能验收。未知 Flash 的上电行为不受本地新 bit 生成影响。
