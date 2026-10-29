# SC431HAI → RF33 六通道CNN → 720p60 HDMI

**最新已签核RF33版：[下载bit](build/camera_fps_rf33_srl_720/outflow/ti60_camera.bit)** · [工程](build/camera_fps_rf33_srl_720/ti60_camera.xml) · [签核](build/camera_fps_rf33_srl_720/signoff.json) · [最终复核](build/camera_fps_rf33_srl_720/final_review.json) · [完整使用和架构](docs/rf33_720.md) · [离线架构图](architecture.html)。2026-10-24。

用户已看过比较图并选择RF33。真实1280×720输入/处理，四风格梵高/剪纸/漫画/水墨；三输出缓冲解耦HDMI提交，双在途写仲裁仍等真实B，SRL压缩权重。实际整机CAD：**230RAM/130DSP/55759XLR，setup/hold +0.379/+0.027ns**，CNN166.667MHz自身setup+0.501ns，79脚/12Bank及所有电平保持。

新SRL完整720p梵高CNN/DMA全部921600像素整数一致、6007407 UI周期，模型等效 **16.646fps**，约为原720p模型1.881fps的8.85倍。**尚未下载，真实摄像头/DDR/CPU/显示并发FPS待实测**。普通FF版本`camera_fps_rf33_720`因XLR超限不可用，务必选带`srl`的目录。

启动原图；KEY0–3依次选四风格，KEY1+KEY2约0.5秒回原图，KEY0+KEY3约1秒复位；串口只读CAM3/115200，不上传图片。原图模式I00正常。按键三种显示内容和手势识别尚未接入本bit。

bit SHA256：`2a288989e1fdf84264a3579f7bd823b5f903aac50f661db0636ffd072cda2398`。旧十二通道模型/bit保留，下文均为对应旧阶段。

---

# 保留的十二通道真正720p版

**详细学习文档：[720p工程完整解读：框架、逐模块接口和实现](docs/project_guide.md)**。包含完整端口声明、DDR/CDC、RISC-V/APB、定点CNN及诊断；[中间文件清理记录](docs/cleanup_inventory.md)。

**保留的十二通道720p版：[下载bit](build/camera_720_fast/outflow/ti60_camera.bit)** · [工程](build/camera_720_fast/ti60_camera.xml) · [签核](build/camera_720_fast/signoff.json) · [最终复核](build/camera_720_fast/final_review.json) · [架构](architecture.html) · [详细说明](docs/full720.md)。用户认可的VGA偏置修复版继续保留，下文为其记录。

1920×1080 RAW10全视野插值为1280×720，再执行原四模型CNN，HDMI720p60全幅显示。CNN独立166.667MHz，DDR/UI保持原时钟；条带核心32→48，计算/舍入流水优化。四种风格、固件和按键操作保持，启动原画；KEY0–3依次梵高、剪纸、漫画、水墨；KEY1+KEY2约0.5秒回原画。

完整720p梵高CNN/DMA测试921600像素逐值通过，等效约**1.88fps**；像素吞吐约为旧VGA的2.64倍，但总FPS略低于旧VGA的2.136，仍未达到15fps，实板C/I待测。200MHz布线有负setup，因此交付166.667MHz：RAM254/256、DSP148/160、XLR45613/60800，最小setup/hold **+0.428/+0.026ns**，79脚/12Bank及电平通过，未代为下载/固化。

bit SHA256：`fbaecb588dbe01c85db920e8fdeae6a1525f5abd2f459ad913afbf163d10aa19`。清理了21个可再生中间目录约240MiB，必要IP/旧bit/模型/报告及demo保留。暗场色偏尚未调整曝光、白平衡或模型；先保留认可的效果。

## 本轮帧率实验与后续交互

完整记录见 [帧率实验、真实画质对照与后续验收](docs/fps_experiments.md)。独立六通道RF33梵高CNN/DMA已逐值完成720p，6007407个100MHz UI周期、等效 **16.646fps**。最新SRL整机bit见顶部；旧十二通道双缓冲和最初C6模型的分析属于历史过程，新版已使用三输出bank，但真实DDR并发/实板FPS仍待测。

已另训RF33/RF63各四风格，用户选择RF33，原十二通道保持。参见 [训练与画质](../../../pycode/fps_student.md)、[架构瓶颈与原模型存储实验](docs/fps_architecture_analysis.md)。普通FF实验仅core map122RAM/126DSP并不足以证明整机适配，最终使用已签核SRL权重版。

按键以后用于原图/风格/左右对比，手势1–4用于梵高/剪纸/漫画/水墨；只在原图或对比界面，持续4个完整一秒窗口才切换。当前只完成独立四秒门控RTL，尚无图像手势分类器或新交互版bit；[显示、手势和帧池设计](docs/display_gesture_design.md)。现有bit按键操作仍按下文。

---

# SC431HAI 摄像头 → 新四风格 CNN → HDMI

**保留的上一版下载：[偏置映射修复版 bit](build/camera_bias_fix60/outflow/ti60_camera.bit)。** 已在综合网表仿真复现实板剪纸输出8/125/74：首层输入/权重相同，偏置通道错位，后续计算失真。改为逐通道固定位置写入，保留原训练模型、固件、摄像头配置和960×720放大/原画切换。

之前仅RTL数值和CAD时序检查漏掉了该映射问题。本次四种实际模型的综合后完整24×40对照全部逐像素一致（3840像素），并独立核对Python整数结果；真实CNN/DMA四模型随机内容与原画/背压/错误恢复也通过。用户现已反馈该修复版画面较好，原画略绿的Bayer/白平衡未在本轮调整。

实际全CAD／79脚／12Bank／原生CDC签核PASS：RAM250/256、DSP148/160、XLR44268/60800，setup/hold **+0.228/+0.026ns**，D-PHY级间最小+13.602ns；整份peri及电平保持。未访问串口/JTAG，不代为下载或固化。

入口：[架构与工作流](architecture.html) · [根因/失败复现/修复验证](docs/bias_mapping_fix.md) · [工程](build/camera_bias_fix60/ti60_camera.xml) · [签核](build/camera_bias_fix60/signoff.json) · [最终复核](build/camera_bias_fix60/final_review.json)。

bit SHA256：`500e118bb3108d6e819877eeda2c9ce045e700be823c6300f11cb1a999cfb29e`。

## 使用

1. Ti60F225I3 DemoBoard V4，沿用已确认SC431HAI配套模组/J4、J2/J3均2–3，不带电插拔。未知Flash启动边界按[首次使用指南](../../../docs/Ti60_programming_guide.md)处理。
2. Programmer/JTAG临时下载上方**camera_bias_fix60** bit，固件和权重已包含，不另烧firmware，不需PC传图。
3. 启动先看原画；640×480处理，**960×720等比例放大**、左右160列黑边，HDMI仍标准720p60。
4. 单按KEY0梵高厚涂、KEY1彩色剪纸、KEY2复古漫画、KEY3水墨；**KEY1＋KEY2按住0.5秒回原画**。KEY0＋KEY3一秒逻辑复位保持。模式在整帧启动锁存，切换需等待忙中作业完成。
5. **红黄棋盘是显示欠载提示**。原画复制不计入I，原画模式下I最终为00正常；C数完整采集，I数CNN完成，H60为配置刷新率。
6. 若原画也暗/偏色，保留原画画面；若只有风格异常，记录对应风格。板载USB串口115200/8N1，保留`@CAM3`；旧CAM1/CAM2工具不兼容本版。

```powershell
python F:/fpga_qiansai/elinx/projects/camera_art_styles/pc/camera_view.py --list
python F:/fpga_qiansai/elinx/projects/camera_art_styles/pc/camera_view.py --port COM31 --log F:/fpga_qiansai/elinx/projects/camera_art_styles/build/camera_view.jsonl
```

COM31为示例，使用实际端口。先关闭占用同端口的GUI/串口助手；只读工具不发送数据，Ctrl+C停止。CAM3追加源/输出RGB均值统计与请求/引擎/前台模式；源和输出未配对同一帧，不能视作网络误差。J8不是UART。

## 架构和性能边界

SC431HAI 1920×1080 RAW10四lane → D-PHY5.8公开PPI → 44位原子异步FIFO → CSI包头/ECC/CRC与帧校验 → 2×2 Bayer合成960×540并裁剪640×480 → DDR三原画bank → 原画复制或十二通道五层CNN → DDR双输出bank → 最后写响应及安全消隐后提交 → 960×720等比例放大、720p60显示。

Sapphire3.4.0在32KB RAM执行25032字节固件，负责摄像头ID/模式/曝光、每风格1217次打包权重写入、START和PLIC IRQ16。模型保持art6_v2、dilation1/2/4/8/16、逐层reflect101、无XY；每帧20条、条宽96含左右各32 halo。四组学习参数和旧工程不改。

**当前未达到推理>15fps。** 100MHz结构的理论上限约3.014fps，旧640×480单模型仿真46822062周期、等效约2.136fps，此前均不是实板FPS证明；用户随后已报告旧恢复版I02，本版新显示/原画分支仍待实板验收。C为完整采集发布、I为真实推理完成；H60只是显示刷新。SoT恢复不改变CNN吞吐，也不保证任意多重故障下可证明原帧来源。

控制/按键/UART3.3V、DDR1.5V、时钟/TMDS Bank1.8V、MIPI RX1.2V，SCL/SDA开漏、模组RESET高有效。数字电气签核不能替代实物电源、温升、信号质量、Bayer和并发验收；原HDMI邻近耦合警告保留。

## 保留版本与本地依赖

- [原30Hz摄像头](build/camera_ppi/signoff.json)、[原720p60摄像头](docs/hdmi60.md)保留。
- [CAM1启动诊断](docs/camera_diagnostics.md)、[CAM2错误细分与实板记录](docs/packet_trace.md)保留，是历史入口。当前选camera_bias_fix60；原camera_view60为保留的偏置故障诊断版；SoT恢复版继续保留在[恢复说明](docs/sot_recovery.md)。
- [原训练/RTL/CPU验证与赛题差距](docs/validation.md)按各阶段来源和范围记录，不把旧CAD或数字模型称为当前实板通过。

本地复核为 `scripts/bias_fix/build.py audit`。vendor/build/sim/C/权重遵循原Git规则留本地，仓库不是完整可重建工程归档；依赖本机原厂授权和冻结模型。构建单任务四线程，禁止运行中修改源或权重。
