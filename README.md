# FPGA 实时绘画赛题

本工作区完成易灵思赛题一的风格化视频系统。当前包含 PC 风格迁移训练基线，以及 Xilinx 的串口传图、DDR3 双缓冲、720p HDMI 辅助验证工程。最终参赛平台为易灵思 Ti60F225；Xilinx 静态图显示与 PC 模型训练不代表摄像头实时系统已经完成。

## 项目入口

| 目录 | 用途 | 说明 |
| --- | --- | --- |
| `pycode/` | 星空、浮世绘、水墨、彩色油画；原版版画保留 | [训练、评估和转换](pycode/README.md) |
| `xilinx/projects/uart_hdmi/` | PC UART → DDR3 → 720p HDMI | [使用说明](xilinx/projects/uart_hdmi/README.md) · [详细离线架构图](xilinx/projects/uart_hdmi/architecture.html) |
| `xilinx/projects/uart_style_hdmi/` | 原图上传 → FPGA 定点 CNN → DDR → HDMI | [使用说明](xilinx/projects/uart_style_hdmi/README.md) · [架构与验证边界](xilinx/projects/uart_style_hdmi/architecture.html) |
| `xilinx/projects/uart_style_keys/` | 串口上传一次原图，四键重新处理星空/浮世绘/水墨/彩色油画 | [使用说明](xilinx/projects/uart_style_keys/README.md) · [完整架构图](xilinx/projects/uart_style_keys/architecture.html) |
| `xilinx/projects/uart_style_six/` | 六风格新实验：梵高/莫奈/浮世绘/剪纸/漫画/水墨；KEY2下一种、KEY3上一种 | [使用与当前状态](xilinx/projects/uart_style_six/README.md) · [架构图](xilinx/projects/uart_style_six/architecture.html) |
| `elinx/projects/style_video/` | Ti60 核心资源映射与实时视频集成入口 | [状态与后续工作](elinx/projects/style_video/README.md) · [架构图](elinx/projects/style_video/architecture.html) |
| `elinx/projects/camera_art_styles/` | SC431HAI/RISC-V四风格：真正720p、独立166.667MHz CNN、HDMI720p60；CAD通过，实板FPS待测且15fps未达标 | [使用与验证](elinx/projects/camera_art_styles/README.md) · [架构图及新bit](elinx/projects/camera_art_styles/architecture.html) · [详细逐模块解读](elinx/projects/camera_art_styles/docs/project_guide.md) |
| `elinx/projects/uart_style_tiles/` | 真正720p四风格重叠分条CNN，171/256 RAM，720p30显示 | [使用与签核](elinx/projects/uart_style_tiles/README.md) · [架构图](elinx/projects/uart_style_tiles/architecture.html) |
| `elinx/projects/uart_art_styles/` | 新选四风格：梵高厚涂、剪纸、漫画、水墨；十二通道复用 CNN、串口、按键、720p30 | [使用与当前验证](elinx/projects/uart_art_styles/README.md) · [架构图](elinx/projects/uart_art_styles/architecture.html) |
| `elinx/projects/uart_style_keys/` | Ti60 V4 串口原图、DDR、四键CNN、720p显示完整移植 | [使用与签核](elinx/projects/uart_style_keys/README.md) · [架构图](elinx/projects/uart_style_keys/architecture.html) |
| `xilinx/xc7k325tffg_base/` | Xilinx 原理图及参考例程 | 手写 RTL、PDF 参考资料 |
| `elinx/` | 易灵思平台资料及后续参赛实现 | 保留原目录拼写 |
| `docs/` | 赛题拆解与实施步骤 | [赛题一实施计划](docs/赛题一实施计划.md) |

架构 HTML 自带图表、样式和交互，下载仓库后用浏览器打开。源码链接随仓库保留；本地工程、报告与 bitstream 链接只有在本机生成或取得对应文件后才有效。

2026-10-17首次下载入口：[Ti60 V4两套工程下载与使用](docs/Ti60_programming_guide.md)。本次两套都在易灵思V4依次测试：UART使用`uart_style_tiles/build/720p`，摄像头使用`style_video/build/camera_ppi`；说明包含对应工程/bit、电平复核、JTAG临时下载、PC GUI、四键、摄像头自动运行和可选Flash固化。当前Flash内容仍未知，本轮未下载或固化。

## 队友使用

- PC 串口工具依赖见 [pc/requirements.txt](xilinx/projects/uart_hdmi/pc/requirements.txt)。图片放到 `xilinx/projects/uart_hdmi/images/`；GUI 波特率、分包上限必须匹配 FPGA 的 bitstream。
- 训练依赖见 [pycode/requirements.txt](pycode/requirements.txt)。选择与机器匹配的 PyTorch CPU/CUDA 环境，照片放到 `pycode/convertpic/val2017/`。风格参考图由 `prepare_styles.py` 获取，VGG 权重和训练出的模型需另行准备。
- 当前提速配置为 2Mbps / 16KB、1280×720 RGB565；综合、实现与相关仿真已完成。实际串口、DDR 校准、HDMI 和 10 秒传图目标仍待实板验证。
- 新风格工程的请求改用 COBS，ACK 保留 SLIP。PC 工具必须与 `uart_style_hdmi` 配套；新旧项目的请求编码不能混用。算法训练、定点导出和各项目架构图记录本轮状态。
- 新风格工程两套完整bitstream均已生成并签核：默认720p输入，另有显式VGA输入/CNN、720p居中显示配置。实际四种训练权重已验证，640×480含显示仲裁仿真约51.35ms/帧；板上FPS、十秒上传与实屏仍未实测。图片放新工程自己的`images/`，GUI输入配置须匹配bitstream。
- 用户反馈旧风格转换在板上成功，旧参数及两套 bitstream 已另行备份。新的四键版使用独立训练参考与工程，验证状态单独记录于其架构图与文档；旧版反馈不能代替新版本验收。新版 GUI 仅上传原图，KEY2–KEY5 选择风格，无需重复传图。
- 用户认可当前四种新画风，参数保持不变。新增主机摄像头GUI，持续采集、每次一张完整原图在途，支持完整帧后暂停与立即停止，默认不保存照片；用现有Xilinx bitstream即可。Ti60 V4独立工程为显式640×480输入、按用户要求720p30居中显示，KEY0–KEY3选择风格。实测与CAD签核分开记录，MIPI/RISC-V实时赛题仍待集成。

## 仓库收录范围

保留 RTL、Python、PDF、Markdown、项目 `architecture.html` 和 `requirements.txt`。数据集、输入/输出图片、模型权重、训练日志、仿真、Python 环境、Vivado/Efinity 生成产物和本地缓存不上传。

FPGA 工程文件、XDC/SDC、IP 配置、初始化数据和 bitstream 仍按用户指定范围留在本地。因此仓库是源码与资料共享包，不能把克隆成功视作已经取得完整、可直接烧写的 FPGA 工程。使用和电气依据见各项目说明。

工作区规则见 [AGENTS.md](AGENTS.md)，上传范围由 [.gitignore](.gitignore) 控制。忽略文件只影响 Git 收录，不删除本地资料。

- 2026-10-13新增Ti60真正720p分条工程：四种原权重保持不变，720p/VGA两套完整构建签核、完整尺寸软件整数对照零误差；RAM由旧整机240块降为171块。实物摄像头已纠正为SC431HAI，V1.1手册已提供。未下载实板，MIPI/RISC-V实时链路继续按新工程文档实施。

- 2026-10-15新增[摄像头与RISC-V独立工程](elinx/projects/style_video/README.md)：参考demo10 V7，接入MIPI、三原画缓存、动态四模型CNN、Sapphire C控制与实际帧计数叠加。[架构图](elinx/projects/style_video/architecture.html)说明完整流程。模块/固件模型及综合已通过，最终时序与实板验收仍有待完成，未生成已签核可下载的新bit。C固件依现有白名单仅留本地。

- 2026-10-16[复查](elinx/projects/style_video/docs/review_20261016.md)：易灵思串口VGA/720p现有签核与电气指纹复核通过；摄像头新增真实CSI/Sapphire RTL仿真，修复VS极性，完整1080p RAW到640×480及640×360预处理验证通过。默认仍640×480，360仅为模块调试验证；此轮旧CSI5.15候选未签核，新替代工程状态见下一项。

- 2026-10-16新增[公共PPI替代实现](elinx/projects/style_video/docs/ppi_camera.md)：独立`style_video/build/camera_ppi/`使用D-PHY5.8与44bit异步FIFO，将CSI解析放在100MHz UI域，结构上移除旧word_count争议跨域。RAM204/256、DSP148/160，I3最小setup+0.289ns、hold+0.026ns，79脚配置和当前指纹核对通过；已生成CAD签核bit，未下载实板。当前一个CSI包/一次HS传输的限制尚需与实物确认，真实颜色、FPS、供电跳线与整机并发未验收。旧CSI5.15候选继续保留且未放行。

- 2026-10-19按用户指定的正确Ti60原理图[复核全部六配置](docs/Ti60_correct_schematic_review.md)：修正KEY1/KEY2至P14/N14，特别更正J8并非UART。所有配置重新生成本地bit并检查电平/方向/时序，未烧录；旧bit/报告保存在各项目快照。
