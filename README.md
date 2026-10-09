# FPGA 实时绘画赛题

本工作区完成易灵思赛题一的风格化视频系统。当前包含 PC 风格迁移训练基线，以及 Xilinx 的串口传图、DDR3 双缓冲、720p HDMI 辅助验证工程。最终参赛平台为易灵思 Ti60F225；Xilinx 静态图显示与 PC 模型训练不代表摄像头实时系统已经完成。

## 项目入口

| 目录 | 用途 | 说明 |
| --- | --- | --- |
| `pycode/` | 浮世绘、梵高、水墨、油墨版画四个前馈网络 | [训练、评估和转换](pycode/README.md) |
| `xilinx/projects/uart_hdmi/` | PC UART → DDR3 → 720p HDMI | [使用说明](xilinx/projects/uart_hdmi/README.md) · [详细离线架构图](xilinx/projects/uart_hdmi/architecture.html) |
| `xilinx/xc7k325tffg_base/` | Xilinx 原理图及参考例程 | 手写 RTL、PDF 参考资料 |
| `elinx/` | 易灵思平台资料及后续参赛实现 | 保留原目录拼写 |
| `docs/` | 赛题拆解与实施步骤 | [赛题一实施计划](docs/赛题一实施计划.md) |

架构 HTML 自带图表、样式和交互，下载仓库后用浏览器打开。源码链接随仓库保留；本地工程、报告与 bitstream 链接只有在本机生成或取得对应文件后才有效。

## 队友使用

- PC 串口工具依赖见 [pc/requirements.txt](xilinx/projects/uart_hdmi/pc/requirements.txt)。图片放到 `xilinx/projects/uart_hdmi/images/`；GUI 波特率、分包上限必须匹配 FPGA 的 bitstream。
- 训练依赖见 [pycode/requirements.txt](pycode/requirements.txt)。选择与机器匹配的 PyTorch CPU/CUDA 环境，照片放到 `pycode/convertpic/val2017/`。风格参考图由 `prepare_styles.py` 获取，VGG 权重和训练出的模型需另行准备。
- 当前提速配置为 2Mbps / 16KB、1280×720 RGB565；综合、实现与相关仿真已完成。实际串口、DDR 校准、HDMI 和 10 秒传图目标仍待实板验证。

## 仓库收录范围

保留 RTL、Python、PDF、Markdown、项目 `architecture.html` 和 `requirements.txt`。数据集、输入/输出图片、模型权重、训练日志、仿真、Python 环境、Vivado/Efinity 生成产物和本地缓存不上传。

FPGA 工程文件、XDC/SDC、IP 配置、初始化数据和 bitstream 仍按用户指定范围留在本地。因此仓库是源码与资料共享包，不能把克隆成功视作已经取得完整、可直接烧写的 FPGA 工程。使用和电气依据见各项目说明。

工作区规则见 [AGENTS.md](AGENTS.md)，上传范围由 [.gitignore](.gitignore) 控制。忽略文件只影响 Git 收录，不删除本地资料。
