# Ti60 V4：两套工程下载与使用

> **新四风格与三界面（2026-10-30）：** 独立[camera_art_interactive](../elinx/projects/camera_art_interactive/README.md)，[最终bit](../elinx/projects/camera_art_interactive/build/720p/outflow/ti60_camera.bit)、[XML](../elinx/projects/camera_art_interactive/build/720p/ti60_camera.xml)、[架构](../elinx/projects/camera_art_interactive/architecture.html)。新独立空间层模型17000步；KEY0循环原图/风格/左原右风格，KEY1下一风格、KEY2上一风格、KEY3按住约1秒复位，默认原图。真正720p处理、720p60显示；RAM220/256、DSP142/160、XLR58593/60800；setup/hold +0.084/+0.026ns；最低CNN/DMA模型吞吐39.084974fps，实板持续30fps待测。Programmer/JTAG临时测试，不另烧固件或串口传图；本轮未下载/Flash。CAM5/115200只读诊断；电脑手势见[独立演示](../pycode/gesture_demo/README.md)，不发板端命令。bit SHA256 `9c6d490b2354fa84202c07772671aea949b5cde4768cc04f959418ec1e26858c`。下方旧版本继续保留。

> **真正全720p轻量网络入口（2026-10-30）：** 新建独立[camera_full720_30](../elinx/projects/camera_full720_30/README.md)，[bit](../elinx/projects/camera_full720_30/build/720p/outflow/ti60_camera.bit)、[XML](../elinx/projects/camera_full720_30/build/720p/ti60_camera.xml)及[架构图](../elinx/projects/camera_full720_30/architecture.html)。重新训练C6四风格，**输入、所有逻辑特征层和输出均1280×720，无池化或2×2放大**；每风格396卷积权重，比C8少49.49%。四模型完整CNN/DMA逐像素误差0，最低39.084974fps模型吞吐，**实板持续30fps待测**。RAM220/256、DSP142/160、XLR52326/60800，setup/hold +0.043/+0.026ns，79脚12Bank电平保持；同次bit SHA256 `fe53fe766aa0e6b7c97c63c06aa1d0777b74d68d105e8817cb487f3a9938925b`。Programmer/JTAG临时测试，不另烧固件、不串口传图。启动原图，KEY0–3选四风格，KEY1+KEY2约0.5秒回原图，KEY0+KEY3约1秒复位；UART115200/CAM4。先看[真实画质对照](../elinx/projects/camera_full720_30/docs/model.md)与[验证范围](../elinx/projects/camera_full720_30/docs/validation.md)。本轮只生成文件，未下载/Flash；下方C8/RF33保留，画质不等同于无损提速。

> **四风格30fps新候选（2026-10-30）：** 独立工程[camera_art_30](../elinx/projects/camera_art_30/README.md)，[bit](../elinx/projects/camera_art_30/build/720p/outflow/ti60_camera.bit)与[XML](../elinx/projects/camera_art_30/build/720p/ti60_camera.xml)，供用户用Programmer/JTAG测试，不另烧固件或串口传图。720p输入/输出、内部640×360特征残差分支、HDMI720p60；四风格完整CNN/DMA模型最低35.478367fps，**实板持续30fps待测**。174RAM/100DSP/53603XLR，setup/hold +0.309/+0.026ns，79脚12Bank电平与原版保持。启动原图，KEY0–3选四风格、KEY1+KEY2约0.5秒原画、KEY0+KEY3长按复位，CAM4/115200。C8画质与下方保留RF33不同，[看实际对照](../elinx/projects/camera_art_30/docs/model_quality.md)及[完整使用/验证范围](../elinx/projects/camera_art_30/docs/validation.md)。本轮只生成文件，未下载或写Flash。

> **最新RF33摄像头入口（2026-10-24）：** 用户已比较画质并选择六通道RF33。使用[新SRL版bit](../elinx/projects/camera_art_styles/build/camera_fps_rf33_srl_720/outflow/ti60_camera.bit)，对应[工程](../elinx/projects/camera_art_styles/build/camera_fps_rf33_srl_720/ti60_camera.xml)，Programmer/JTAG临时测试，不另烧固件/传图。本轮只生成文件，未代为下载或Flash。真正1280×720处理、720p60显示；三输出bank、两写请求在途；230RAM/130DSP/55759XLR，setup/hold +0.379/+0.027ns，79脚/12Bank与电平保持。完整CNN/DMA模型16.646fps，真实整机FPS待实测。启动原图，KEY0–3选四风格、KEY1+KEY2约0.5秒回原图，原画I00正常；尚无手势/对半界面。[完整操作和验证边界](../elinx/projects/camera_art_styles/docs/rf33_720.md)。不要选XLR超限的无`srl`版本。

> **保留的十二通道720p入口（2026-10-23）：** 用户认可VGA偏置修复版后新增真正1280×720处理：[720p bit](../elinx/projects/camera_art_styles/build/camera_720_fast/outflow/ti60_camera.bit)，Programmer选JTAG临时下载，不另烧固件/传图。全视野Bayer→720p CNN→720p60全幅显示；CNN166.667MHz，DDR/UI/所有引脚电平保持。79脚/12Bank与最终时序PASS（+0.428/+0.026ns），完整720p梵高模型仿真约1.88fps，尚非实板FPS或15fps达标。[详细使用与验证](../elinx/projects/camera_art_styles/docs/full720.md)。四键及原画组合键不变，原VGA版本继续保留；下方旧“当前”均为历史阶段。

> **保留的VGA摄像头入口（2026-10-23偏置修复）：** 真实CAM3的剪纸纯色已在综合网表中复现，定位首层偏置通道错位；固定通道译码后四种模型的映射后完整帧数值对照全部通过。现在JTAG临时下载[偏置修复bit](../elinx/projects/camera_art_styles/build/camera_bias_fix60/outflow/ti60_camera.bit)，[根因及验证](../elinx/projects/camera_art_styles/docs/bias_mapping_fix.md)。640×480处理、960×720放大/原画切换、720p60、CAM3/115200和全部电平保持；setup/hold +0.228/+0.026ns。新bit效果待实板确认，原画略绿未在这次调整。下方各先测试入口均为历史记录，旧camera_view60仅作诊断保留。

> **历史放大诊断入口：** 用户旧SoT恢复版已实测C30/I02/H60并出图，但画质异常。现在先用[原画对照与960×720放大版 bit](../elinx/projects/camera_art_styles/build/camera_view60/outflow/ti60_camera.bit)，Programmer/JTAG临时下载；启动原画，单按四键风格，KEY1+KEY2按住0.5秒回原画。标准720p60，处理仍640×480，I只数CNN；CAM3/115200可读RGB均值。79脚/12Bank保持，setup/hold +0.326/+0.026ns。[操作与验证](../elinx/projects/camera_art_styles/docs/camera_view.md)。这是定位画质的独立版本，未确认画质根因已修复，下方各“先测试”入口均为历史阶段。

> 历史SoT阶段：用户CAM2已定位行间SoT使整帧失效，先JTAG临时测试[camera_sot_recover60恢复bit](../elinx/projects/camera_art_styles/build/camera_sot_recover60/outflow/ti60_camera.bit)。79脚电平保持、setup/hold +0.445/+0.026ns，操作及限定恢复边界见[说明](../elinx/projects/camera_art_styles/docs/sot_recovery.md)。当时实际出图仍待确认；后续用户已出图，见顶部当前入口。

> 历史CAM2诊断：CAM1记录已到B3、DDR报校准/RAW行正常解出，但C/I为0。现在先用[camera_packet_trace60 CAM2 bit](../elinx/projects/camera_art_styles/build/camera_packet_trace60/outflow/ti60_camera.bit)，115200串口，按[细分错误追踪](../elinx/projects/camera_art_styles/docs/packet_trace.md)记录。仍是诊断，未宣称摄像头无图已修复。

> 2026-10-23摄像头持续彩条排查：请先用[camera_debug60诊断bit](../elinx/projects/camera_art_styles/build/camera_debug60/outflow/ti60_camera.bit)，板载USB串口115200，按[诊断步骤](../elinx/projects/camera_art_styles/docs/camera_diagnostics.md)读取CAL/启动错误码/PPI计数。原camera_ppi60没有日志，C00/I00/H60不能确认摄像头已开流。

> **历史60Hz阶段：UART720p60已由用户确认可以显示，摄像头版也已改60Hz。** 摄像头试验使用 [camera_ppi60 bit](../elinx/projects/camera_art_styles/build/camera_ppi60/outflow/ti60_camera.bit)，Programmer/JTAG；不需要PC串口传图或另烧固件。先彩条、初始化和首帧推理完成后显示640×480居中风格画，H60标记刷新率。79脚电平和摄像头控制保护不变，setup/hold +0.319/+0.026ns；[当前使用与验证](../elinx/projects/camera_art_styles/docs/hdmi60.md)。下方“摄像头未改”及30Hz入口是此前阶段的历史记录。

> **UART当前入口：恢复720p60。** 用户反馈UART两份30Hz程序均提示输入不支持，现明确恢复60Hz。先JTAG下载 [720p60_hdmi bit](../elinx/projects/uart_art_styles/build/720p60_hdmi/outflow/ti60_style.bit)，不传图先看彩条；再用原GUI选720p／2Mbps传图。66脚电平／时序签核通过（+0.437/+0.030ns），不写Flash。[当前使用说明](../elinx/projects/uart_art_styles/docs/hdmi_720p60.md)。本轮摄像头版本未改；下方30Hz入口均为历史记录。

> **2026-10-22 显示故障诊断入口：** 用户运行 UART 版后提示「输入不支持」。现在先用 [720p30 彩条＋V7 AVI 诊断 bit](../elinx/projects/uart_art_styles/build/720p30_diag/outflow/ti60_style.bit)，JTAG 下载后先不传图片，观察启动彩条，再用原 GUI 选720p／2Mbps上传。新 bit 已完成66脚电气／时序签核（setup/hold +0.449/+0.029ns）；屏幕实际锁定仍待验证。引脚、电平、PLL频率、处理尺寸和四模型均不改，旧版保留；[详细排查与使用](../elinx/projects/uart_art_styles/docs/hdmi_720p30_diagnosis.md)。下方首次顺序是此前未加入诊断显示路径的记录。

> **2026-10-22 首次测试顺序更新：** 先用新四风格UART工程 [uart_art_styles 720p bit](../elinx/projects/uart_art_styles/build/720p/outflow/ti60_style.bit)，通过串口上传原图验证DDR/HDMI；再测试新摄像头工程 [camera_art_styles bit](../elinx/projects/camera_art_styles/build/camera_ppi/outflow/ti60_camera.bit)。两套使用Programmer的 **JTAG + .bit**，不写Flash。新风格均为KEY0梵高、KEY1剪纸、KEY2漫画、KEY3水墨。下文旧style_video/uart_style_tiles链接仍是保留的旧四风格工程，不是本次新风格首次入口。
>
> 本次再次核对66/79脚、12Bank、全部时序关系和源码/固件/bit指纹，并重跑新摄像头顶层保护及八项固件故障退出，均通过。UART720p setup/hold +0.376/+0.028ns；新摄像头+0.444/+0.026ns；实物供电/温升/实际出图未测量。UART测试前应在断电状态取下摄像头；后续带摄像头重新上电前，仍须先明确未知Flash的启动内容或厂家确认的启动方式。临时JTAG不会改变下次上电的Flash程序。

> **2026-10-19修正：正确原理图的KEY1=P14、KEY2=N14；J8不是串口。** 两套配置已重新CAD/电气签核，当前bit指纹与时序请查看[最新复核](Ti60_correct_schematic_review.md)。本指南的2026-10-17审查数值为修正前记录，下载路径保持不变、文件内容已更新。


2026-10-17。用户确认两套都在同一块 **Ti60F225 DemoBoard V4** 上依次测试。本轮重新核对已构建文件、源码/权重/配置指纹、引脚和时序，没有重新综合，也没有连接JTAG、打开串口、下载或写Flash。

补充：[demo10 V7/V9 复查](../elinx/projects/style_video/docs/demo_v7_v9_review.md)。只参考V7、V9，demo未修改；V9的Bayer/数据对齐修复已逐项对照独立实现。现有摄像头bit仍使用V7采集配置，不要单独替换成V9寄存器表或把V9整套原始工程当作本项目。

## 1. 本次用哪两套

| 用途 | Efinity工程入口 | 首次JTAG下载文件 | 图像处理与显示 |
|---|---|---|---|
| 串口照片/主机摄像头 → FPGA四风格 → HDMI | [ti60_style.xml](../elinx/projects/uart_style_tiles/build/720p/ti60_style.xml) | [ti60_style.bit](../elinx/projects/uart_style_tiles/build/720p/outflow/ti60_style.bit) | 输入/CNN 1280×720，HDMI720p30 |
| SC431HAI → FPGA四风格 → HDMI，RISC-V控制 | [ti60_camera.xml](../elinx/projects/style_video/build/camera_ppi/ti60_camera.xml) | [ti60_camera.bit](../elinx/projects/style_video/build/camera_ppi/outflow/ti60_camera.bit) | 1920×1080 RAW10 → 640×480预处理/CNN，720p30居中显示 |

第一套选用新分条项目`uart_style_tiles`的 **720p** 配置；不要误选旧`uart_style_keys`的VGA文件。第二套使用 **camera_ppi**；不要选仍未签核的`camera_vga`或CSI调查最小工程。

两个完整目录：

```text
F:\fpga_qiansai\elinx\projects\uart_style_tiles\build\720p\
F:\fpga_qiansai\elinx\projects\style_video\build\camera_ppi\
```

一块FPGA每次只运行一套配置，第二次JTAG下载会替换当前运行的配置。将两套文件都放在PC上不等于板上已实现双程序切换；当前没有实现多镜像启动。

只想下载现成通过文件时，不需要重新综合，也不需要升级IP。若查看工程，使用Efinity2026.1.132打开表中的XML；这不是Vivado工程。已有工程引用本地vendor/IP/ROM/固件资料，请保留现有目录。当前Git上传策略不是完整可重建工程归档，不能只下载仓库中的RTL就假定全部依赖齐备。

## 2. 本轮复查结果

| 项目 | 串口720p版 | 摄像头PPI版 |
|---|---|---|
| 实际封装脚 | 66个，独立板级检查通过 | 79个，独立板级检查通过 |
| I3最小setup / hold | +0.387 / +0.026 ns | +0.289 / +0.026 ns |
| RAM10 / DSP | 171/256，144/160 | 204/256，148/160 |
| bit SHA256 | `6d1f54b73989ab51ba641c7c8c52ce801806ee552eca34961e4195ee2a8cacf3` | `c82a9b2c0b2b14d03b0c5055d747b7de98e651a579b0f0b9c3ea53fd0b0c577c` |

两套的12个Bank电压配置完全一致，动态电压切换关闭：

- BL/BR/TL/TR：3.3V。UART RX R4输入、TX R14输出，四按键都是输入。不能把这些实际供电3.3V的Bank改成1.8V配置。
- 3B/4A/4B：DDR 1.5V SSTL。DQ/DQS双向，输出使能接原厂控制器；未发现额外强制驱动。
- 3A：HDMI专用LVDS输出，1.8V，保持原V4串化与P/N反接补偿。
- 1A/1B：1.8V，含25/27MHz输入时钟及配置接口。
- 2A/2B：1.2V。串口版未启用MIPI；摄像头版五组MIPI均为专用RX，无MIPI TX。

摄像头版SCL/SDA为3.3V开漏，OUT恒0、只拉低或释放，复位时释放；模组RESET沿用V7高有效。PLL失锁/校准失败/停钟保护测试、八项摄像头初始化故障退出模型均已通过。当前bit、源码、模型、时序与约束指纹仍匹配。

物理电压/电流/温升、实屏、实际采集和推理FPS仍未测量，两套保留原V4的HDMI邻近耦合警告。CAD通过不能承诺零硬件风险。详细证据见[串口电气复查](../elinx/projects/uart_style_tiles/docs/electrical_logic_review.md)和[摄像头复查](../elinx/projects/style_video/docs/preflight_review_20261016.md)。

可复跑只读检查，输出到项目自己的build，不生成bit、不访问硬件、不替换原signoff：

```powershell
python F:/fpga_qiansai/elinx/projects/style_video/scripts/check_download_pair.py
```

本轮结果：[pair_720p.json](../elinx/projects/style_video/build/programming_review_20261017/pair_720p.json)。其中`.hex`另记录SHA、同次生成头和配置主体对应关系；SPI启动前缀不同于JTAG，未把`.hex`称为已完成实板Flash验证。首次测试使用表中的已签核`.bit`。

## 3. 接线与首次上电条件

你已确认摄像头接 **J4**，**J2/J3均2–3短接选择1.2V**，不需要来回改跳线。只在断电时插拔摄像头或调整跳帽。两套都连接板载Type-C下载口和板上 **HDMI TX/OUT**，不要接HDMI RX/IN。

第一套UART测试可先在断电时取下摄像头。只使用板载FT4232链路，无需外接5V TTL/RS-232串口。USB Target用于JTAG，Windows的UART COM用于发图片，两者不是同一个选择框。

**现有Flash内容未知：**直接上电可能先运行原Flash程序，新bit尚未下载，不能用新bit的检查结论保证那份未知程序的引脚配置安全。进入带摄像头测试前，先明确上电启动配置和实际供电；一种路径是先在不接摄像头时完成UART版验证，再将验证通过的UART版固化为已知启动程序，之后断电连接摄像头，再临时下载摄像头版。另一种路径是按板卡厂家确认的启动方式绕过未知Flash。不要凭猜测短接配置引脚。

软件不能代替实测1.2V/1.5V/1.8V/3.3V、电流和温升。若尚无法确认启动配置或实际供电匹配，先完成这些条件再操作带模组上电。

## 4. 两套通用的JTAG临时下载步骤

1. 打开 **Efinity Programmer**。可以从Efinity软件中打开，也可使用独立Programmer；第一次用现成bit不需要先运行Compile。
2. 在 **USB Target** 中刷新，选择板载FT4232对应的JTAG目标。不要在这里填COM29等串口号。扫描/选择的FPGA应为Ti60，官方JTAG ID为`0x10660A79`。
3. **Image / Select Image File**选第一节对应的`.bit`完整路径，核对界面识别器件为Ti60。
4. **Programming Mode选`JTAG`**。不要选SPI Active/JTAG Bridge，因为那是写Flash的路径。
5. 点 **Start Program / Program FPGA**，等待工具报告下载和配置成功，保留日志。失败时不要当成程序已运行；先看USB Target、器件ID、文件路径和驱动占用。
6. 保持板卡供电，按下一节使用该版本。要换另一套，在同一操作流程中换选另一份bit再下载。

JTAG临时配置不改Flash；断电、硬件重新配置或按板上CRESET_N配置复位后，可能重新加载原Flash。它与工程中的KEY0+KEY3逻辑复位不同：**已运行工程的组合键复位不会改为另一个bit**。

上述文件格式和操作按钮依据[Efinity Programmer官方指南第18–21页](https://www.efinixinc.com/docs/efinity-pgm-v4.3.pdf)。本机随Efinity安装的Programmer指南为v4.2，JTAG单镜像步骤相同。

## 5. 第一套：串口＋HDMI怎么用

### 上传一张照片

依赖可在你使用的Python环境安装一次：

```powershell
python -m pip install -r F:/fpga_qiansai/elinx/projects/uart_style_tiles/pc/requirements.txt
python F:/fpga_qiansai/elinx/projects/uart_style_tiles/pc/send_style_gui.py
```

本机已验证`E:/software/anaconda/envs/yolo/python.exe`可导入GUI依赖；如果普通`python`指向其他环境，可用该完整路径替换命令中的`python`。

GUI中依次操作：

1. 图片放入`F:/fpga_qiansai/elinx/projects/uart_style_tiles/images/`，也可以直接选择其他目录的图片。
2. 刷新串口，选板载FT4232实际UART COM。关闭其他串口助手、另一个发送GUI或占用该COM的程序。
3. 波特率 **2000000**；输入配置 **720p**，与本次bit一致。它不是VGA配置。
4. 选择1280×720图片；其他尺寸勾选“图片与输入配置不一致时缩放并补黑边”。图片解码由PC完成，发送原始RGB565小端数据，FPGA不解PNG/JPEG。
5. 点“上传并转换”，等完整END ACK和转换完成日志。首次完整帧到达前HDMI黑屏可以是正常状态。
6. 图片完成后使用下表的四按键切换风格，原图保留在DDR，不需要再次上传。

| 板上按键 | 风格 |
|---|---|
| KEY0 | 星空，默认 |
| KEY1 | 浮世绘 |
| KEY2 | 水墨 |
| KEY3 | 彩色油画 |

KEY0+KEY3同时长按约1秒为整机逻辑复位；复位后原图失效，需重新上传。忙时按键只保留最新请求，切换不一定立即显示。

720p RGB565单帧1,843,200字节，2Mbps/8N1纯线速至少约9.216秒，包校验、停等、软件和转换还有开销；不能承诺当前实板总用时10秒内。

### 主机摄像头自动逐张上传

```powershell
python -m pip install -r F:/fpga_qiansai/elinx/projects/uart_style_tiles/pc/camera/requirements.txt
python F:/fpga_qiansai/elinx/projects/uart_style_tiles/pc/camera_gui.py
```

关闭照片发送GUI释放串口后，选相同COM、2000000和720p。摄像头编号通常先试0，Windows后端默认DSHOW；打开“开始自动采集与上传”。“本张完成后暂停”保留最后完整图片，便于按键比较；“立即停止”使半帧源图无效，已完整提交的帧不回滚。PC预览是最新采集帧，HDMI是最近完整上传并转换的照片，二者不会保持实时同步。

## 6. 第二套：板载摄像头＋RISC-V＋HDMI怎么用

1. 先关闭PC串口发送工具。使用已确认的SC431HAI配套模组、J4和1.2V跳线；接排线必须断电，并先满足第三节的已知启动配置条件。
2. 在Programmer中按第四节下载`style_video/build/camera_ppi/outflow/ti60_camera.bit`。
3. **不需要启动任何PC传图脚本，不需要再单独烧C程序或权重。** 当前bit已包含正确的Sapphire RAM初始化固件和四组学习参数。
4. 配置成功后，等待PLL、DDR校准和固件初始化。RISC-V自动复位模组、读取`0x3107/0x3108=CD/6B`、配置1920×1080 RAW10、检查尺寸/VTS、加载默认星空模型、开启采集并调度CNN。
5. HDMI输出720p30，640×480处理结果居中显示，四键含义与第一套相同。KEY0+KEY3长按复位后会重新初始化摄像头，无需串口重传图。
6. `Cxx`是DDR发布的完整采集帧率，`Ixx`是CNN成功完成帧率，`H30`是配置刷新率。H30不表示摄像头30fps或推理30fps；真实C/I仍需上板测量。

当前限制：单包/一次HS的CSI解析范围、BGGR/Bayer与曝光亮度、摄像头实际帧率和整机DDR/HDMI并发未验收；完整ISP/AE/白平衡未完成。即便Programmer配置成功，也不等于摄像头已成功出图。此版本UART TX为空闲高，没有实现串口启动日志；打开串口助手不会得到CPU启动状态。

## 7. 如果要断电保存：Flash固化与切换

JTAG测试通过后，可选择固化一个已验证版本。V4原理图PDF第9页的配置Flash为 **U14 / GD25LQ64 / 64Mbit（8MiB）/1.8V**；这是原理图标注，未读取你实板的Flash ID，Programmer识别应与实物相符。它不是外部DDR3，DDR不保存上电启动程序。

两套同目录均有工具生成的SPI `.hex`：

```text
UART:   F:\fpga_qiansai\elinx\projects\uart_style_tiles\build\720p\outflow\ti60_style.hex
Camera: F:\fpga_qiansai\elinx\projects\style_video\build\camera_ppi\outflow\ti60_camera.hex
```

使用本机Efinity Programmer，Image换选目标`.hex`，模式选 **SPI Active using JTAG Bridge**，启用 **Auto configure JTAG Bridge Image**，目标Ti60。Starting Flash Address使用默认启动地址 **0x00000000**，启用Erase和 **Normal verify**；当前应用为SPI x1，勿改为x8或依赖quad的Fast verify。JTAG Bridge Image使用工具自动提供的Ti60加载器，**不要把应用bit填到Bridge Image栏**。

核对Flash识别、目标文件与覆盖范围后，Start Program执行写入并验证。需要保留原Flash内容时先按工具提供的读回方式备份，再擦除。只有验证成功后，才按工具提示重新加载或断电重启检查启动。工具生成`.hex`不等于Flash已经写入或验证，本轮没有执行这一步。

两套都写默认地址时，**后写的版本覆盖前一个启动版本**。想来回比较，直接JTAG换bit即可；想上电默认运行哪套，最后固化哪套。当前没有设计双镜像选择开关，不要自行猜测第二镜像地址。

## 8. 常见现象

| 现象 | 先检查 |
|---|---|
| Efinity找不到USB Target | Type-C数据线、板载FT4232驱动、其他下载软件占用；不要只凭出现COM口判断JTAG驱动可用 |
| JTAG配置成功但UART版黑屏 | 是否完整传完图片、GUI是否720p、HDMI是否TX；下载成功本身不产生原图 |
| COM拒绝访问 | 关闭串口助手/另一个GUI，刷新选实际UART通道；不要硬编码之前的COM29 |
| ACK尺寸不匹配 | 选错bit或GUI配置；本次应720p。保持尺寸校验，不改代码绕过 |
| 720p30屏幕不锁定 | 确认屏幕支持720p30、HDMI TX与线缆；不要临时改PLL/IP参数后继续使用旧签核结论 |
| 摄像头版C0/I0或黑屏 | 看是否有HDMI叠加；确认当前bit为camera_ppi、模组与J4接法、实际供电。可能是I²C/ID/模式/包格式/DDR问题，需进一步观测，不是靠重复上电判断 |
| 串口GUI不能控制摄像头版 | 预期行为；摄像头版不接收串口图片 |
| 临时下载后断电变回原程序 | 预期行为；JTAG配置是易失性的，Flash未改变 |
| FPGA/模组明显异常发热或电流异常 | 立即断电，检查电源/排线/接法，不继续反复下载尝试 |

入口：[串口架构图](../elinx/projects/uart_style_tiles/architecture.html)、[摄像头架构图](../elinx/projects/style_video/architecture.html)、[摄像头控制寄存器](../elinx/projects/style_video/docs/control_registers.md)。当前未接入PC可读的APB调试通路，寄存器文档不能当作现成的串口调试功能。
