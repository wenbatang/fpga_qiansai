# Xilinx 六风格图像转换

独立项目 `uart_style_six`，保留原 `uart_style_keys` 四风格版、旧权重及 bit。六种顺序为 **梵高厚涂 → 莫奈印象派 → 浮世绘 → 彩色剪纸 → 复古漫画 → 水墨**；去掉水彩绘本。

入口：[离线架构图](architecture.html)、[训练与素材](docs/training.md)、[验证记录](docs/validation.md)。2026-10-19镜像去框版已完成完整尺寸软件/核心RTL及两套新CAD签核，bit已更新；学习参数不变，未下载或固化。

[六风格实际720p软件预测](../../../pycode/results/art6_v2/board_preview/six_720p_comparison.png) 使用本轮最终模型与用户0001.png，已经过RGB565和整数参考核对；不是之前的AI概念图，也不是实板照片。剪纸和漫画仍是小网络的近似，不能保证概念图的大尺度造型重绘。

## 使用

- 板卡：Kindex Base7 FMC，`xc7k325tffg676-2`。KEY1/D26 复位，默认梵高；KEY2/J26 下一种、KEY3/E26 上一种，循环六种。KEY4/G26、KEY5/H26 保留为输入。
- 图片仍通过串口上传。运行 `python pc/send_style_gui.py`，选实际串口、2,000,000 波特率和匹配 bit 的尺寸配置。
- 默认 `720p` 为 **1280×720 输入与 CNN 处理**；另有显式 `vga` 为 640×480、720p60 居中显示。尺寸不符可显式勾选软件缩放，不能静默降低默认分辨率。
- 完整图像留在 DDR，按键换风格无需重传；处理中保留最新请求，当前作业的模型编号不变。新 BEGIN 后半帧无效，ABORT 不恢复旧源图。
- 主机摄像头自动逐张上传可用 `python pc/camera_gui.py`。仍是 RGB565 停等传图，不能当作 UART 实时视频。

## 首次上板入口

1. 在Vivado 2023.2的Hardware Manager中Open Target → Auto Connect，确认目标是本机Kindex Base7 FMC的 `xc7k325t`，Program Device选择下表对应的 `.bit`。本项目没有代为下载，也没有写Flash。
2. 默认先选720p，运行本项目 `pc/send_style_gui.py`，选择实际COM口、2,000,000波特率及 `720p`；示例图片在本项目 `images/0001.png`，自己的图片也可放入该文件夹。
3. 上传完整图片并等待END确认，观察HDMI；KEY2下一种，KEY3上一种，KEY1复位并回到梵高。复位会使DDR源图无效，须重新上传。
4. 需要VGA时下载VGA bit，GUI同时改为 `vga`。按键作业无需重传图片。连接串口前关闭占用同一COM口的其他软件。

| bit | 输入/CNN | GUI配置 | 最终setup / hold裕量 |
|---|---|---|---|
| [默认720p](vivado/uart_style.runs/impl_1/uart_style_top.bit) | 1280×720 | 720p | +0.206 / +0.053ns |
| [显式VGA](vivado_vga/uart_style.runs/impl_1/uart_style_top.bit) | 640×480 | vga | +0.461 / +0.050ns |

两套均保持720p60 HDMI，88脚及Bank配置核对通过。资源：DSP 750/840；RAM默认720p为367/445，VGA为184/445。完整指纹和警告审查见[验证记录](docs/validation.md)。启动后真实效果、上传用时与FPS仍需实板记录。

## 2026-10-19彩色边框修复

[边框原因、镜像规则与对照](docs/border_fix_20261019.md)。当前版本逐层镜像延伸，六组学习参数保持不变；图片不裁剪。新软件预测使用 `pycode/render_border_art6.py`，输出在 `pycode/results/art6_border_v1/`。原 `art6_v2` 和补零版bit已快照保留。两套去框bit已重新签核，下载入口见下表；详细指纹见验证记录。

## 模型与硬件

参考素材 `pycode/styles/art6_v1/`；本轮有效实验 `pycode/runs/art6_v2/`。`art6_v1` 保留第一轮退化学生的诊断结果，不作为交付模型。新版学生五层、12 隐通道、膨胀率 1/2/4/8/16，感受野 63×63，不使用绝对 X/Y 相位输入；int8 权重、逐层 uint8 激活、折叠 BN、有符号累加、舍入和饱和。六组真实学习参数编译在独立 ROM 中；这不等于 RISC-V 动态加载权重。

本项目复制并独立扩展卷积 RTL，原 `common/rtl`、四风格项目与易灵思工程不修改。12 通道 MAC 增加一级寄存求和，六模型编号扩为 3 位，保留编号 6/7 回退到默认模型。串口/DDR/显示原有握手和电气配置沿用经审查的 BaseC FMC 版本。

## 构建

使用 Vivado 2023.2、MIG 4.2、Clock Wizard 6.0。先完成六模型训练/整数检查及本项目仿真，之后顺序构建：

```powershell
python create_project.py --profile 720p --build --resume
python scripts/signoff.py --profile 720p
python create_project.py --profile vga --build
python scripts/signoff.py --profile vga
```

`--resume` 适用于本机已提前创建 IP 的 720p 工程；首次从空目录创建时省略。两配置共用 `build/weights`，另一构建运行时不得修改权重。手写 RTL 在 `rtl/`，仿真在 `sim/`，工程/IP 在 `vivado*/`，报告和数据在 `build/`。不自动下载 FPGA 或写 Flash。

镜像版本完整本地验收入口为 `python scripts/finish_border.py`。它执行六模型边界及联合链路检查，再顺序构建；最终签核须有下列命令生成的完整720p镜像CNN回执。可先启动完整CNN仿真，再运行此入口。它始终不调用板卡。首次准备工程可运行 `python scripts/prepare_ips.py`。完整CNN验证命令示例：

```powershell
python sim/check_cnn.py --single-export F:/fpga_qiansai/pycode/runs/art6_v2/export/vangogh --depth 5 --styles 1 --width 1280 --height 720 --name border_720_core --simulator xsim
```

当前Git策略继续忽略模型、仿真、约束/IP、工程和生成权重include，仓库不是完整可重建归档，需要保留本地依赖。

电气基线：Bank14/15 为 3.3V、Bank32/33 为 1.5V，DDR VCCAUX_IO 为 1.8V/NORMAL；DDR3-800，100MHz UI，HDMI 74.25/371.25MHz。必须以新布局布线的 88 脚审查与最终时序为依据，不能用旧四风格签核替代。
