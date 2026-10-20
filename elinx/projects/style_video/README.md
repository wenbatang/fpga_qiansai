# Ti60 赛题一视频平台

当前阶段完成你负责的视频基础平台：摄像头RAW10预处理、RGB流、CDC、DDR DMA、帧所有权和720p显示。队友的Sapphire/RISC-V和CNN尚未接入，默认使用COPY占位；不能据此宣称完成神经风格迁移赛题。

**本次GitHub模块交付入口：[三模块交付说明](docs/module_delivery.md)**。包含采集/DDR/显示职责、左原图/右黑布局、RISC-V与CNN接入位置、2026-10-20本地验证摘要及未上传的Efinity/IP/仿真依赖说明。

最新新增[按键白平衡校准](docs/wb_calibration.md)：KEY2对白纸采四个新完整帧、在摄像头SOF锁存增益，KEY3恢复默认，KEY1保留对比度。底部标记WB CAL 01；新版候选见[构建回执](build/wb_calibration_receipt.json)，实板待测。重建需显式运行`python scripts/prepare_efinity.py --contrast-probe --wb-calibration`。

- [独立采集模块](docs/camera_capture.md)：`style_camera_capture`封装RAW10预处理、Gamma、图像/取消CDC和计数，统一core域RGB888接口。MIPI接收IP、I²C和DDR DMA独立保留；封装版未上板，构建状态见`build/camera_capture_receipt.json`。顶层连接由`scripts/camera_capture_shell.py`维护，原图像参数保持。当前带全部诊断功能的重建命令仍为`python scripts/prepare_efinity.py --contrast-probe --wb-calibration --performance-monitor`。
- [DDR/显示独立模块及RISC-V接线](docs/ddr_display_modules.md)：`style_ddr_framebuffer`提供APB/IRQ、CNN流口、AXI128和帧管理；`style_hdmi_display`完成显示FIFO/时序/诊断/HDMI编码。默认左原图、右图像区黑色预留CNN；`--show-result`解除预留，未接CNN时右图仍是COPY。模块版构建见`build/ddr_display_modules_receipt.json`，实板待测。

- [被动性能监测与延迟说明](architecture.html#performance-monitor)：同帧CAP/JOB/QUEUE/TOTAL、平台AXI流量/等待及FIFO高水位，详见0x100..17C寄存器表。启用命令为`python scripts/prepare_efinity.py --contrast-probe --wb-calibration --performance-monitor`。独立候选为`build/style_video_performance.bit`，实板待验收。
- [可离线打开的架构和代码解释](architecture.html)：点击模块、搜索全部实际端口/源码、查看实现与恢复逻辑。
- [队友接口契约与APB寄存器](docs/interface_contract.md)
- [摄像头预处理](docs/camera.md)、[DMA与帧池](docs/memory.md)、[显示与OSD](docs/display.md)
- [首次硬件问题与高极性修复记录](docs/camera_hardware_fix.md)

## Efinity IDE

```powershell
python scripts/run_checks.py
python scripts/build_efinity.py --build
python scripts/build_docs.py
```

稳定bit可直接交给Programmer，无需重新综合。IDE再次综合推荐打开当次完整构建快照XML，入口见本文末尾的efinity_receipt.project链接。若用主`efinity/style_video.xml`开发，先关闭旧工程，再prepare并重开生成XML，核对Design Files包含style_camera_reg_rom与style_camera_reg_set；不要在旧已打开的缓存工程里直接Compile。IDE曾将76项旧源清单保存回主XML，使新增模块unknown；225018构建快照补齐2项到78项并检查源路径存在、清单无重复。关闭也可能保存旧清单，故必须先关闭、再prepare、再重开。主prepare本身按全部项目RTL完整生成清单。

器件Ti60F225I3，SystemVerilog语言sv_09，物理顶层`style_ti60_top`。Efinity工具基线2026.1.132.4.5，复用官方V4/J5物理配置；像素时钟74.25MHz、串化371.25MHz。必须检查当次setup/hold与错误；独立工程保留官方加密IP和配置，不更改原厂例程。

实际综合CSI RTL是原已验证5.15版本（HS_BYTECLK参数70），同包settings.json记录5.16/50。保持源版本，不在IP Manager自动升级或重生成。未使用的fabric USER1调试JTAG已移除，下载器硬件JTAG不变。

## 默认数据与分工

处理流640×480 RGB888，显示两张640×480 1:1并排于720p画面。DDR采用RGBX8888 LE字0x00RRGGBB，stride2560，每帧1,228,800字节；4输入槽+2结果槽，每槽2MiB，基址0x01000000。输入保留至配对显示结束。外部DDR为AXI128/ID4；图像读写DMA由平台提供。

Efinix原生CSI输出VS/HS高有效：VS上升沿开始帧、下降沿结束帧；默认和物理顶层显式VS_ACTIVE=1，物理s_valid=CSI DE&HS，与已验证官方frame_buffer一致。低极性通用输入仍可显式设置0。原低极性RTL错误已确认；第一轮VS修复bit曾出现下半图紫色，当前128拍读候选已获用户短时画面稳定确认。

控制接口是APB3 byte offsets，未来SoC寄存器基址由RISC-V队友分配；软件目录仍为原有占位，不包含可运行驱动。卷积队友需接RGB流式整网模块，若交付AXI主机需先重定义接入方案。当前FORCE_BYPASS=1，CONTROL复位enable/auto/bypass都开启；上板前使用COPY连通摄像头、DDR和显示。

采集DMA启动要求DDR校准就绪、摄像头164个ROM事务完成并经核心域同步、abort队列正常。`config_done`只表示命令序列完成；当前没有NACK或ID检查，不能证明传感器应答、型号和寄存器值正确。后续RISC-V接管I²C时必须选择单一主机。

## 验证状态

当次行为仿真与Efinity结果分别保存build/validation_receipt.json和build/efinity_receipt.json。历史包括无图、半幅紫色、13fps、短曝光30fps偏色、GBRG2实物失败；最新用户确认COLOR PROBE01标记及RGB白灰条正确，右BGGR3颜色正确但暗，CAP/COPY30、UF/ERR/DROP0。当前摄像头/ROI/方向的有效Bayer3已获观察，正式gamma版本颜色已获确认，图像质量待优化。没有精确观察时长或运行bit独立读回，COPY不是CNN，神经推理>15fps未验证。

历史实物诊断：[style_video_color_probe.bit](build/style_video_color_probe.bit)的版本标记和RGB白灰条正确，右BGGR3颜色正确但偏暗，CAP/COPY30、UF/ERR/DROP0；依据[probe回执](build/color_probe_receipt.json)及[active marker](build/active_hardware_image.json)，有效Bayer3针对当前摄像头/ROI/方向已获观察。正式候选[style_video_bggr_gamma.bit](build/style_video_bggr_gamma.bit)与[候选回执](build/bggr_gamma_receipt.json)另记，颜色已获确认，亮度和锐度仍未验收。历史13fps、短曝光30fps、GBRG2失败和早期半幅紫色记录均保留；用户观察不等于长期稳定性、DDR实测吞吐或电气签核。

短曝光恢复同模式v1三个曝光字后已获30fps反馈，曝光和DDR不再改变。原BGGR3+gamma22基线去掉probe/右图交换/黄框/标准条，camera_preprocess→style_rgb_gamma→camera_cdc，三通道使用同一离线256×8 LUT：round(255*(x/255)^(1/2.2))。没有运行浮点、白平衡或完整ISP；官方2P2.mem为x^2.2压暗，不能复用。该gamma22基线的DDR和未来CNN输入是近似gamma2.2编码RGB888；当前gamma18候选则为近似gamma1.8编码，非精确sRGB；需要线性输入时用--tone-profile linear。

历史GBRG2文件红变绿、蓝变黑、绿变粉紫，颜色失败，见[原回执](build/camera_color_phase_receipt.json)。随后COLOR PROBE01以左RGGB0/右BGGR3完成实物对照，右图正确但暗；诊断本身左图不是正式正确颜色输出，也没有提供RAW四位置数值。操作和历史见[docs/color_probe.md](docs/color_probe.md)。正式BGGR+gamma已获颜色正确反馈，但模糊和低对比仍待排查，不能写成图像质量全面验收。

gamma18文件为[style_video_bggr_gamma18.bit](build/style_video_bggr_gamma18.bit)，实物反馈仍明显发灰且完全遮镜也灰，CAP/COPY30、UF/ERR/DROP0，见[gamma18回执](build/bggr_gamma18_receipt.json)；原gamma22文件及实物记录保留。style_rgb_gamma支持GAMMA_TENTHS=18/22，普通默认18，ENABLE=0透传。1.8减弱中暗部提亮，未新增独立对比度、黑电平或锐化；不预先保证灰感改善。用户已确认镜头可手动对焦，尚无调焦后清晰度结论。

旧[style_video_contrast_probe.bit](build/style_video_contrast_probe.bit)已获标记/KEY1正常、CAP/COPY30及零错误反馈；遮镜A041/B042/C042/D043、右1.50较自然，见[contrast_probe回执](build/contrast_probe_receipt.json)。使用`--contrast-probe`、Bayer3和gamma18准备，与`--color-probe`互斥。左图保留基线，右图KEY1循环五档对比度（默认1.50倍，20ms消抖、帧边界应用）；RAW A/B/C/D均值用于遮镜观察，现已测得暗场65/66/66/67，但该显示模块不自动BLC。仅显示端改变，不回写DDR/CNN输入；不保证根治灰感，详见[诊断说明](docs/color_probe.md)。

当前实物文件[style_video_black_level.bit](build/style_video_black_level.bit)已获遮镜纯黑、RIGHT1.00最自然、CAP/COPY30及UF/ERR/DROP0反馈，状态见[黑位回执](build/black_level_receipt.json)。用户仍报告轻微偏绿、魔方大致正确，白平衡和清晰度未验收；后续白纸RAW09C/0F5/0F5/0A0已收到；该BLC历史位流尚无WB，新固定WB候选待实屏。物理2×2 RAW10四位置固定扣除实测65/66/66/67并钳位0，再Debayer/缩小/gamma18；DDR和CNN输入数值随之改变。复用CONTRAST PROBE01标题，不能据标记唯一识别新版，需选择新文件；原始RAW统计在BLC前，遮镜仍可显示041..043。复现该已测BLC命令为`python scripts/prepare_efinity.py --camera-profile short_exposure --bayer-pattern 3 --tone-profile gamma18 --black-level-profile measured --white-balance-profile none --contrast-probe --contrast-initial-level 2`；需要复现旧gamma18/22或旧contrast时显式`--black-level-profile none`。普通默认measured仅配short_exposure/Bayer3，color-probe强制none。无白点拉伸、曝光/白平衡更改；已测位流启动1.50，用户改选1.00；当前WB版本物理启动默认1.00，尚未实板通过，通用模块默认仍1.50。

新候选为[style_video_white_balance.bit](build/style_video_white_balance.bit)，见[固定WB回执](build/white_balance_receipt.json)，已实测不发绿及30fps，室外天空微红待诊断。白纸RAW156/245/245/160扣黑后RGB93/179/91，按当前光照固定Q8增益493/256/504，在G均值后、RGB8/gamma前21bit乘加舍入饱和；均值预测RGB10各179、RGB8各44，不保证每个像素相等。物理启动对比度1.00、KEY1保留，RAW统计仍在BLC/WB前。它不是AWB或完整ISP，R/B增益可能放大噪声或造成高光饱和；DDR/CNN数值语义变为扣黑+固定WB+gamma18。当前准备：`python scripts/prepare_efinity.py --camera-profile short_exposure --bayer-pattern 3 --tone-profile gamma18 --black-level-profile measured --white-balance-profile measured --contrast-probe --contrast-initial-level 0`。measured WB仅支持当前BGGR3/短曝光/measured BLC；旧BLC须WB none和初档2，旧无BLC诊断默认WB none/初档2。

普通gamma18准备：`python scripts/prepare_efinity.py --camera-profile short_exposure --bayer-pattern 3 --tone-profile gamma18`，再回归及`python scripts/build_efinity.py --build`。当前正常默认Bayer3/gamma18，原gamma22需显式选择；诊断需显式`--bayer-pattern 0 --color-probe`，未给tone时默认linear，color-probe+gamma18或gamma22会被拒绝。正常linear可用--tone-profile linear关闭gamma，位宽/握手/字节序不变但亮度数值语义不同，队友输入须匹配。实际源配置见source_receipt.json的tone_profile和camera_rgb_encoding；位流不随源码准备自动更新，必须核对当次回执身份。

性能证据分两类：原16拍读、首R等待48周期的紧凑640×48实验实际复现了中途欠载和剩余粉色像素，其回执明确不通过；全640×480双图、720p60、30fps输入的首R等待96周期/读128拍测试按当前性能回执判断。另一个持续密集COPY的无限读请求模型在96周期/128拍时平均56.728M像素/秒，低于双图显示在图像区域期间所需57.6M像素/秒，仍是带宽边界失败，不能把它写成通过。正常帧调度负载与持续无限请求假设不同，均不能替代实际DDR带宽和显示验收。

显示欠载后核心立即abort/drain旧读，FIFO清空与帧释放仍等安全窗口，避免本帧停止消费误触发读DMA看门狗。DROP_COUNT和ERROR_COUNT为阶段事件合计，可能多次记录同一坏帧，不是按frame_id去重的唯一坏帧数。

## 修改与重新生成

`rtl/style_platform_core.sv`由`scripts/generate_core.py`生成，核心逻辑应维护生成器；修改后先运行`python scripts/generate_core.py`，再运行仿真及Efinity构建。`rtl/style_ti60_top.v`、`rtl/style_camera_initializer.v`由`scripts/prepare_efinity.py`生成；物理PHY宏参数来自已验证参考包，物理封装/时钟/peri/SDC的定制维护在准备脚本中。不直接批改厂商加密IP或outflow。

README、architecture.html和接口契约由build_docs.py生成；调整说明时维护生成器，再按最新源码和收据刷新。重新生成代码后必须重新验证相应快照，旧bitstream不自动覆盖新源码的验证状态。

最新Efinity记录：map/interface/pnr/pgm退出0，bitstream已生成，WNS 0.399ns、WHS 0.026ns；95个引脚复核，SDC警告225条、接口告警1条。不是零告警或板级物理签核。详细状态以收据和网页为准，修改源码后必须重新验证对应快照。

当次IDE综合入口：[build/efinity/20261020_131834/efinity/style_video.xml](build/efinity/20261020_131834/efinity/style_video.xml)，来自efinity_receipt.project；构建完成=True，已核对源条目89项、快照补入0项。稳定bit可直接交给Programmer，无需重新综合。若改用主efinity/style_video.xml，先关闭旧工程，再prepare并重新打开，避免IDE保存的旧源列表覆盖新列表。
