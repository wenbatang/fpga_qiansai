# 最新交付 2026-11-03

基线为 **camera_art_ten_paint**：SC431HAI → 全1280×720六通道神经风格转换 → DDR3 → HDMI720p60，RISC-V控制、十风格、三视图和个人手势模板。**免本人录入通用手势模型未达标，未装入此bit。** 这次整理不改变生产RTL、固件、电平、模型或已签核bit，不自动下载、Flash或改驱动。

## 先使用现成程序

1. 在本目录执行 `python relocate.py`，再执行 `python verify_release.py`。前者只改工程/数据路径，后者核对归档完整性、模型、bit、79引脚和12Bank，**不是重新做CAD或物理电压测量**。
2. 板卡Ti60F225I3 DemoBoard V4、demo10配套SC431HAI接J4。既有接法为J2/J3均2–3，MIPI Bank选择1.2V；控制线3.3V开漏。J8不是UART座，串口使用板载USB。不同板卡/裸传感器不能套用。
3. Efinity Programmer选择正确Ti60F225器件，用JTAG加载 [release/ti60_camera.bit](elinx/projects/camera_art_ten_paint/release/ti60_camera.bit)。本交付不操作Flash；固化应另做启动和Flash核对。
4. KEY0原图→风格→左原右风格，KEY1下一风格、KEY2上一风格，KEY3显示/隐藏文字和青框。进入原图或对比后才能采手势。
5. 手势仍需个人录入：KEY1+KEY2长按约1秒进入学习；手移出框，KEY0采3张背景；L0开始每类KEY0采四份模板，保持1–2秒并轻微改变角度；十类完成自动退出。模板只在RAM，断电丢失。0是五指弯成O，3是中/无名/小指，7是拇/食/小指；全映射见下表。确认需约5秒，RAW成功自动转STYLE；STYLE暂停识别，回RAW/SPLIT可继续。

|槽/手势|原风格编号|风格|手形|
|---|---|---|---|
|0|0|梵高旋涡厚涂|五指弯曲围成O|
|1|2|浮世绘海浪|食指|
|2|3|彩色剪纸|食指、中指|
|3|4|复古漫画|中指、无名指、小指|
|4|34|竹林水墨|除拇指四指|
|5|7|阿什维尔抽象|五指张开|
|6|9|形体对比|拇指、小指|
|7|15|蒙德里安几何|拇指、食指、小指|
|8|31|彩色马赛克|拇指、食指|
|9|40|雨夜厚涂|食指弯钩|

bit SHA256：`75766d7cdd66154d2d8da1db7a800ed49f38864ae52316c97b2dadaab959a2de`。模型SHA256：`7250b683772fdd9c3756f9f062ce639aadfcbfbc49eb64e6ac2e15588e489e86`。

## 目录与工程重建

- `elinx/projects/camera_art_ten_paint/rtl,firmware,vendor,parameters`：生产源码、C/ASM/链接脚本、必需厂商IP和十组学习参数，保留原版权/保护内容。
- `elinx/projects/camera_art_ten_paint/build/720p/ti60_camera.xml`：Efinity工程入口，配套peri、SDC、Sapphire、四条Boot RAM初始化和weights.mem都已带上。先relocate再打开。原工具为Efinity2026.1.132、Ti60F225、I3；厂商工具/授权和RISC-V编译器需自行安装。
- `release/evidence`：原签核、资源/时序/引脚和回归回执，保留原始路径作来源记录；本次只是归档，不把历史PASS冒充新目录重新布局布线通过。
- `upstream_scripts`与`verification_sources`：原构建/检查源码。历史严格signoff引用旧项目链，不能直接在本归档里冒充已恢复全部历史环境。当前独立构建入口见 `rebuild_project.py`，会重建映射和精确CDC，默认停止于新时序审查，不自动生成或下载未经签核的新bit。
- `source_provenance.json`、`bundle_manifest.json`：来源、536图划分与整包指纹；改代码/重训后应建立新版本，不覆盖归档指纹。

## 模型推理与训练

`pycode/ten_style`包含网络、训练、量化、整数参考、导出、最终model.pt、训练日志、十组硬件包及必要暖启动；`painterly_style`含四绘画教师；`style_model`仅带所选C8教师与参考。内容训练512张、验证24张已按既有划分附入，未包含用户私人展示照片。通用VGG权重574MB不存入Git，可由官方地址获取，**FPGA使用不需要VGG或Python**。

```powershell
python -m pip install -r requirements.txt
python infer_style.py your_picture.jpg --style 0 --out results/demo.png
python download_vgg.py
python train_styles.py --run reproduce_painterly --steps 12000
```

推理命令固定720p并居中裁剪输入，使用实际整数运算；CPU较慢。训练需CUDA环境，起点为已保留的梵高1500步试训checkpoint，在新run目录重做12000步绘画微调；不同GPU/库不承诺逐位复现优化轨迹。风格训练原理、QAT、画质和局限见报告，原训练步数与模型step不能混算。

## 当前测量范围

原签核RAM230/256、DSP142/160，setup/hold +0.108/+0.026ns；slot0完整720p CNN/DMA模型39.085fps，**不是实板持续FPS**。HDMI60Hz、采集FPS和推理FPS分别统计。个人手势真实准确率仍待测；权重目前是从预置ROM运行时装载，外部在线下载新权重为预期功能。

[架构入口](architecture.html) · [详细模块说明](elinx/projects/camera_art_ten_paint/docs/project.md) · [技术报告](report.pdf)
