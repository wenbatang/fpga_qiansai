# 首次摄像头实板问题与 VS 极性修复

最新状态：旧BLC位流已获遮镜纯黑、RIGHT1.00最自然、CAP/COPY30与UF/ERR/DROP0反馈，仍轻微偏绿。用户白纸RAW09C/0F5/0F5/0A0扣黑后RGB93/179/91；当前固定WB候选采用Q8增益493/256/504与物理启动对比度1.00，已有实屏反馈，室外天空微红待诊断。旧BLC硬件记录保留，新WB已有独立用户反馈：不发绿、30fps/零错误，但室外天空微红；整体颜色与清晰度未验收。

## 2026-10-14：首次上板观察

用户报告首次 Ti60 视频平台测试：

- 摄像头接 J5，显示器能看到 OSD，说明显示扫描和输出已有可见结果。
- `FRAME`、采集/处理 FPS 一直为 0，没有发布摄像头图像。
- LED0 闪烁，D2 亮、D3 灭。

按当前顶层 LED 映射，LED0 是 DDR `cal_done` 条件下的核心心跳，D2 对应阶段错误计数非零，D3 对应 DMA fatal 或 abort 事件队列故障。该观察符合“运行且发生图像协议错误，没有锁存 fatal”的情况。它不能证明传感器 ID/I²C 应答、完整帧 DDR 写读或摄像头显示已验收。

GUI显示的20:53是旧 `efinity/outflow/style_video.bit` 文件时间，不是确定的实际下载时间。用户没有提供当时运行中bit的SHA256，运行版本身份未独立核实。这里保留首次失败观察，不把OSD可见或旧构建成功记为摄像头验收通过。

## 已确认的适配错误

预处理原默认 `VS_ACTIVE=0`，以 VS 下降沿为开始、上升沿为结束。但原生 Efinix CSI-2 RX 输出 `vsync/hsync` 为高有效，正确边界为：

| 信号/事件 | 原生 CSI 约定 |
|---|---|
| VS 高 | 帧有效范围 |
| VS 上升沿 | 帧开始 |
| VS 下降沿 | 帧结束 |
| HS 高 | 行有效范围 |
| `pixel_data_valid` | 有效 RAW 数据拍 |

原始依据：Efinix《MIPI CSI-2 RX Core User Guide》v2.1，第 7 页端口说明、第 15 页输出时序图。本地文件路径：`E:/Desktop/DEMO/_work/docs/mipi-csi2-rx-core-ug-v2.1.pdf`。

此前依据旧 `frame_info_det.v` 的 `neg_vs` 注释直接推断了 CSI 极性，这是错误依据。旧模块会结合 valid 自动判定帧开始/结束，注释不能代表原始 CSI 输出就是低有效。

低极性预处理在真实VS高的数据区无法按原生帧边界正确验证，合法数据可能落在它认为的帧外，真实帧开始可能被当作结束，因而没有合法整帧EOF。原RTL的极性错误是确定问题，与首次观察相符；当时运行bit指纹未知，不能据此断言这是全部实物问题或唯一原因，修复后仍需重测。

## 当前修复

- `style_camera_preprocess.sv` 默认改为 `VS_ACTIVE=1`。
- 独立 Ti60 物理顶层显式实例化 `.VS_ACTIVE(1)`，避免以后参数默认变化造成接口含糊。
- 物理预处理输入 `s_valid=w_mipi_rx_de & w_mipi_rx_hs`，与已验证官方frame_buffer一致，只在HS有效行范围接受RAW拍。
- 泛用低极性输入仍通过显式 `.VS_ACTIVE(0)` 支持，不删除该兼容模式。
- 厂商 CSI IP、摄像头 1920×1080 RAW10 寄存器表和物理引脚没有因此升级或猜测重配。

当前初始化仍只把 164 个 ROM 事务结束记为 `config_done`，没有验证 NACK、传感器 ID 或寄存器读回。这个条件经核心域同步后，与 DDR 就绪和 abort 队列健康共同允许采集 DMA 接新帧。

## 第一轮高极性候选的历史构建记录

第一轮VS高极性及DE&HS门控候选来自 `build/efinity/20261014_212628/` 快照。map/interface/pnr/pgm全部退出0，WNS +0.432ns、WHS +0.026ns，95个引脚与V4/J5配置匹配；当时35项源码绑定回归通过，包括显式低极性兼容、原生高极性及默认1920×1080输入。该段是历史构建事实；当前候选使用下面的新命名文件和回执。厂商输入/引脚审阅仍保留既有告警边界，不等于实物通过。

第一轮历史候选文件是 [style_video_camera_vs_high.bit](../build/style_video_camera_vs_high.bit)，SHA256为 `395fcb40e91e21b6a591d8459e5e618ec279e03ffbdbe4bd81941eabc916a514`，大小2,403,456字节。身份、源码审阅及其失败的硬件反馈见 [camera_fix_receipt.json](../build/camera_fix_receipt.json)。不要将当前 `build/efinity_receipt.json` 或 `build/validation_receipt.json` 当作该历史文件的原始构建记录。

初始化寄存器切换期间，过渡帧可能累计错误，使D2在后续正常帧到来后仍持续亮；不要求D2必须熄灭。重点观察完整图像、CAP/COPY FPS及FRAME持续增长、是否有fatal/欠载与配对稳定性。若错误持续增长或FPS仍为0，需要继续排查。COPY路径不是CNN风格化处理。

## 第一轮VS修复候选重测：采集已开始，显示尚未通过

用户随后确认下载稳定修复候选并报告：左右摄像头画面出现，但只有上半部分；下半部分抖动并呈紫色，CAP/COPY均约13，FRAME持续递增。该反馈表明完整帧采集/复制开始发布，但显示连续读出仍有问题。紫色与当前RTL欠载标记FF00FF一致，需要继续核对显示FIFO与DDR供数。不能将此结果标记为完整显示通过。

运行中bit哈希仍未独立读回核实，正式状态应结合后续回执。

## 第二轮显示吞吐候选：128拍读突发和累计诊断

当时稳定文件为 [style_video_display_burst128.bit](../build/style_video_display_burst128.bit)，身份及13fps用户反馈见 [display_fix_receipt.json](../build/display_fix_receipt.json)。该历史文件保留原生VS高有效和RAW DE&HS门控，将平台计算/显示读突发从16拍改为128拍；写仍16拍，读DMA仍验证完整burst再输出，没有改变AXI错误处理算法。当前30fps文件另见短曝光回执，不误选GUI旧efinity/outflow。

OSD在y88增加八位十六进制 `RAW/DROP/ERR/UF` 累计诊断。RAW是输入帧总数，不是FPS；DROP/ERR是阶段事件合计，同一坏帧可能被多次记录；UF是图像区首次空FIFO事件数，每个被标粉的显示帧只增加一次。配置/核心统计按bundle握手锁存，UF在像素域接纳刷新时锁存。继续观察两个完整640×480画面、CAP/COPY FPS及UF/DROP趋势；D2可能保留过渡帧累计错误，不能要求它必灭。

`20261014_215130`快照实现构建全部退出0，WNS +0.547ns、WHS +0.026ns、95个引脚复核；bit大小2,416,836字节，SHA256 `eff8f25afaa78674ea11cabd5585f82fb37e683c931fcb11db5f8b11b07f0d7a`。这些是该构建快照的记录，当前软硬件状态以稳定文件回执为准；SDC继承模板及LVDS距离告警仍需复核。

实际复现：16拍读、首R等待48核心周期的640×48实验在第一帧x1088/y40出现欠载，剩余34,752像素为FF00FF且停止消费，回执明确 `passed=false`、`expected_failure_observed=true`。128拍读、首R等待96周期、标准720p60与640×480双图、30fps输入的完整负载测试已比较3,072,000像素：3次采集/复制/配对交换、5次完整HDMI扫描，UF/drop/error均0，编译及运行退出0；原始回执在 [full_96_128_3cam](../build/performance_latency/full_96_128_3cam/receipt.json)，当前聚合使用 [performance/receipt.json](../build/performance/receipt.json)。该行为模型的通过不能代替实板DDR吞吐验证。

另一个持续密集COPY的无限读请求模型在96周期/128拍时平均56.728M像素/秒，低于双图显示在图像区域期间所需57.6M像素/秒，仍是带宽边界失败。不要把正常帧调度的负载测试通过扩展成任意延迟/连续满负载均可通过；本板真实读延迟与带宽仍待测量。

## 128拍读文件的实物反馈：短时显示功能确认

用户针对 `style_video_display_burst128.bit` 重测后回复：“稳定，CAP/COPY FPS13，UF DROP一直是0。”可将本轮记为用户确认短时显示功能通过：第一轮的下半幅紫色抖动在这次观察中没有再报告，UF与DROP保持0。

当次观察任务要求约10秒，用户未给出精确计时；这不是长时间稳定性测试。当次尚未给出RAW、ERR及FRAME读数，后续RAW/ERR观察记录在下节；此前FRAME递增属于第一轮观察，不能替代本轮具体读数。

当时CAP/COPY均13fps未达到30fps采集目标；COPY是直通占位，不是CNN。视觉功能确认不是DDR读延迟、实测吞吐或电气签核，因此 `build/performance/receipt.json` 的 `hardware_bandwidth_verified=false` 保持正确。当时53项回归与完整尺寸压力结果作为历史记录保留，后续短曝光新增测试记录另见最新回执。

## 后续入口观察与短曝光A/B候选

用户随后给出RAW累计 `0x38E→0x429`，差为155十进制帧，间隔约10秒；ERR为0，UF/DROP保持0，CAP/COPY仍13。计时不精确，因此约15.5是粗略CSI输出SOF速率；不能据此声称传感器内部精确15.5fps，也不能将其当作已达30fps。这个观察支持先核对摄像头曝光配置；平台没有固定13Hz采集或任务定时器，现有DDR压力模型已覆盖30fps适配器输入，但不能替代实板供数测量。

官方SC431HAI《数据手册V1.1》第23页给出线性曝光半行约束 `4 ≤ E ≤ 2×VTS−11`，编码 `E=((3E00&0xF)<<12)|(3E01<<4)|(3E02>>4)`；默认VTS1500对应最大2989。当前v6 ROM为01/BB/F0，即7103半行；同PLL、4lane及1920×1080模式的v1为00/BA/D0，即2989半行。曝光超过默认帧长允许范围有降低输出帧率的依据，但当前没有实际寄存器读回，不能确认为唯一实物原因或证明传感器实际VTS/曝光。

来源：本地官方 `D:/QQ/摄像头SC431HAI_数据手册_V1.1.pdf` 第23页；官方v1 `elinx/elinxdemo/Ti60F225_DemoBoard_v4/10_Ti60f225_sc431hai2hdmi_demo/Ti60f225_sc431hai2hdmi_v1/rtl/cam_i2c_ctrl/i2c/i2c_master_reg_rom.v` 与保留v6 `efinity/vendor/rtl/cam_i2c_ctrl/i2c/i2c_master_reg_rom.v` 的第198–200行。精确路径及ROI/追加寄存器核对见 [camera.md](camera.md)。v1前161项与v6前161项除三个曝光字外相同；实验保留v6追加的增益、方向和全部164项顺序。

项目新增自己的 `style_camera_reg_rom.v`、`style_camera_reg_set.v`，不编辑厂商ROM。准备脚本camera_profile可选verified基线与short_exposure实验，默认short_exposure；只恢复三个曝光数据为00/BA/D0，DDR/CSI/裁剪缩小及其他寄存器不改。当前profile、来源SHA和三项差异见 [camera_profile_receipt.json](../build/camera_profile_receipt.json)。本次不增加RAW FPS、芯片ID、HTS/VTS或曝光读回；原controller读数据dout未驱动，不能以rd_done冒充真实读回。

短曝光文件为 [style_video_camera_short_exposure.bit](../build/style_video_camera_short_exposure.bit)，构建、回归、打包及最新30fps用户反馈见 [camera_short_exposure_receipt.json](../build/camera_short_exposure_receipt.json)。历史A/B对照为已接受的13fps稳定 [style_video_display_burst128.bit](../build/style_video_display_burst128.bit)，其旧回执及第一轮VS修复半幅紫色失败均保留。

短曝光可能使画面更暗，因此当时安排CAP/COPY、UF/DROP/ERR、画面完整与亮度重测；30fps结论由下节用户实物反馈支持，不由寄存器替换或编译成功推定。神经推理>15fps仍未验证。

## 短曝光构建与IDE缓存源列表

短曝光文件来自 `build/efinity/20261014_225018/efinity/style_video.xml`，56项源码绑定测试通过，map/interface/pnr/pgm退出0，WNS +0.547ns、WHS +0.026ns。该文件SHA256为 `eaba8e5740939f5dc9f5f51de78d5b123bea17fd65df8a160ef30a6e396d673b`，2,416,833字节；具体入口同时记录于候选回执project。

首编224612曾使用IDE保存回主XML的76项旧清单，报新增module unknown。225018独立构建快照补入style_camera_reg_rom/set两项，共78项源，检查所有路径存在且清单不重复后通过。主prepare按全部项目RTL生成完整清单；问题来自旧已打开工程的缓存/保存，不是两模块缺失于代码。

稳定bit直接用Programmer下载即可。需要IDE重新综合时优先打开当次回执project指定的完整快照；若改用主XML，先关闭旧工程，再prepare，再重新打开生成XML并核对新模块。关闭时也可能保存旧清单，顺序不能反过来；不要在旧缓存工程中直接Compile并假定新源已加载。

## 2026-10-15实物重测：30fps稳定，颜色问题仍未解决

用户针对短曝光文件报告CAP/COPY均30fps，UF、ERR、DROP均0，画面稳定、亮度可接受；随后描述整体偏绿或偏紫。当次反馈后的active marker指向短曝光文件；后续GBRG失败反馈见下节，当前正常版本状态见文末，13fps旧基线仍存档。用户没有精确测量观察时长，运行中bit身份未独立读回；这是采集/COPY帧率的实物功能证据，不是长期稳定性、DDR实测吞吐或电气签核，也不是CNN推理性能。

颜色优先核对物理Bayer相位：RGB→DDR→COPY→HDMI通道顺序一致，RAW10取高8位与官方例程相同；若绿色位置被错误解释，红/绿色块可能变成绿/紫。这是代码与症状的推断，仍须红/蓝/白色块实拍。

当时独立颜色候选命名 [style_video_camera_gbrg.bit](../build/style_video_camera_gbrg.bit)，状态见 [camera_color_phase_receipt.json](../build/camera_color_phase_receipt.json)。相对已确认30fps短曝光基线，仅物理顶层RTL显式GBRG=2；通用默认RGGB=0保留，曝光/增益、DDR/COPY/HDMI和白平衡均不改。公开offset与flip定义的推导、3200..3207未公开窗口定义的不确定性见 [相位审计](../build/camera_color_phase/profile_receipt.json)。当时尚无颜色修复通过反馈，不能将候选相位或构建完成写成颜色已修好；active marker仍是当前有用户证据的运行文件。


## GBRG实物失败与COLOR PROBE 01诊断

2026-10-15用户针对GBRG文件报告红色物体显示绿色、蓝色显示黑色、绿色显示粉紫；CAP/COPY30，UF/ERR/DROP保持0。此候选颜色测试失败。094400映射网表实际使用top偶列+bottom奇列求G，R来自bottom偶列、B来自top奇列，命名bit与构建bit的SHA一致，证实本地BAYER2配置进入产物；运行FPGA身份仍未独立读回。上节待测状态被本次反馈更新，不能继续把公开ROI/flip推导视为物理相位已确定。

当时准备COLOR PROBE01：左RGGB0、右交换R/B对照BGGR3，旁路测四RAW均值并显示黄框/版本/标准参考条，不改曝光和DDR。GBRG失败及原短曝光文件保留；当时active marker更新为诊断文件，当前正式版本记录见文末。操作见[color_probe.md](color_probe.md)，诊断位流与回执分别为build/style_video_color_probe.bit和build/color_probe_receipt.json。

## PROBE01实物确认：有效BGGR3，右图偏暗

用户确认COLOR PROBE01标记和RGB白灰条正确，右侧颜色正确但偏暗，CAP/COPY30、UF/ERR/DROP0。右图在此诊断中只对phase0输入交换R/B，等效BGGR3，所以当前传感器/ROI/方向的有效Bayer3已获观察支持；GBRG2的公开offset/flip推导被实物否定，保留为失败历史。用户未提供四RAW数值或精确观察时长，运行bit身份没有独立读回。

本次证据记录于[color_probe_receipt.json](../build/color_probe_receipt.json)和[active marker](../build/active_hardware_image.json)。它确认诊断右图颜色，不意味着诊断左图正确，也不等于正式双图或亮度已验收。

## 正式BGGR+gamma：颜色已确认，图像质量待优化

文件命名[style_video_bggr_gamma.bit](../build/style_video_bggr_gamma.bit)，状态见[bggr_gamma_receipt.json](../build/bggr_gamma_receipt.json)。正常物理顶层显式Bayer3，去掉probe/右图交换/黄框/参考条，曝光和DDR不改。在camera_preprocess输出到camera_cdc入包之前加入纯组合style_rgb_gamma，原握手与帧标志保持。

gamma22是离线256×8 LUT：`y=floor(255*(x/255)^(1/2.2)+0.5)`，三通道同函数，ENABLE=0透传，无硬件浮点或新增流水拍。官方2P2.mem为x^2.2压暗，不能反向复用。该历史版本默认gamma22、Bayer3；当前新候选默认gamma18；color-probe要求显式Bayer0，tone默认linear，color-probe+gamma18或gamma22会拒绝。需要线性输入的队友用--tone-profile linear。

由于gamma位于CDC前，该gamma22历史版本的DDR/COPY及未来CNN输入均成为近似gamma2.2编码RGB888；位宽/字节序/握手不变，亮度数值语义改变。它不是精确sRGB、白平衡或完整ISP，正式版本颜色已获用户确认，但模糊、低对比仍待排查，不能写成全面验收。Efinity项目入口、源数量和补入项以当次实现回执动态记录为准，历史78项不是当前固定数目。


## 最新照片反馈：颜色正确，图像质量待优化

用户确认正常BGGR+gamma版本颜色正确，但图像模糊。显示器照片中OSD相对清楚、摄像头画面边缘软且低对比，CAP/COPY为30、UF/ERR/DROP为0；这些数值来自单张照片，不构成新增持续稳定性证明。位流身份按会话关联，未独立读回；亮度和锐度尚未验收，状态见[bggr_gamma_receipt.json](../build/bggr_gamma_receipt.json)。

镜头离魔方约10cm，用户已确认镜头可手动对焦，尚无调焦后清晰度或50–100cm远距对比，先通过远距目标检查焦点。当前2×2半分辨率Debayer从1920×1080得到960×540，再最近邻缩至640×480；16:9到4:3属于非等比缩放，横向相对压缩25%。该旧gamma22链路没有黑电平校准或锐化，但不能据此断言传感器内部没有BLC。Gamma只逐像素映射、不混合邻域；失焦、采样细节损失、黑电平和Gamma各自贡献尚未测量，不凭两张拍摄条件不同的照片确定单一原因。


## gamma18实物反馈：仍明显发灰，遮镜也灰

针对原gamma22画面偏灰、低对比，本轮仅把Gamma从2.2减为1.8；BGGR3、曝光、DDR和HDMI保持。新候选名为[style_video_bggr_gamma18.bit](../build/style_video_bggr_gamma18.bit)，当次构建和实物状态以[bggr_gamma18_receipt.json](../build/bggr_gamma18_receipt.json)为准。原style_video_bggr_gamma.bit及其颜色正确但灰/糊的反馈保留，不能把旧版反馈当成新候选通过。

style_rgb_gamma新增GAMMA_TENTHS=18（支持18/22），ENABLE=0仍透传，LUT按`floor(255*(x/255)^(10/GAMMA_TENTHS)+0.5)`离线生成。prepare支持`--tone-profile linear/gamma18/gamma22`，普通默认gamma18，color-probe仍须Bayer0和linear。RGB位宽、顺序与握手不变，DDR/COPY及未来CNN的数值语义随tone变化，队友需匹配训练输入；这是构建选项，不是在线寄存器开关。

gamma18比gamma22少提升中暗部，仍是逐像素组合映射，无新增流水拍；没有实现独立对比度、FPGA黑电平校准或锐化，用户已反馈仍明显发灰，CAP/COPY30、UF/ERR/DROP0，完全遮镜后仍明显灰；尚无数值黑位测量。用户已确认手动对焦镜头，尚未给出调焦后的清晰度结论；不将Gamma调节当作失焦修复。


## CONTRAST PROBE01实物：暗场读数与1.50倍偏好

gamma18实物反馈仍灰，完全遮镜也明显灰；这说明需要测量暗场，但尚未确定灰位来自传感器、黑电平、显示映射或其他环节。新诊断保持gamma18摄像头与DDR内容，左图是基线，仅右图x640..1279、y120..599在显示端调节对比度。KEY1依次循环1.00/1.25/1.50/1.75/2.00倍，默认1.50倍；20ms消抖、帧边界生效。映射不回写DDR，也不改变未来CNN输入。

底部出现CONTRAST PROBE01、RAW A/B/C/D均值、档位/KEY1提示和参考色条。复用中心128×128区的四奇偶位置统计，只有完整合法帧发布40bit整组结果，经异步FIFO和像素域整组锁存；并非与显示前台逐帧绑定。请完全遮镜、等待读数稳定后记录A/B/C/D，再打开镜头比较各档和左图。本次遮镜测得65/66/66/67，成为后续固定黑位候选的依据；旧诊断本身没有自动BLC、锐化或CNN处理。

使用`python scripts/prepare_efinity.py --camera-profile short_exposure --bayer-pattern 3 --tone-profile gamma18 --black-level-profile none --contrast-probe`复现旧未扣黑诊断；它与`--color-probe`互斥并要求Bayer3/gamma18，普通版本仍默认gamma18，旧color-probe要求Bayer0/linear。候选名为[style_video_contrast_probe.bit](../build/style_video_contrast_probe.bit)，完成状态见[contrast_probe_receipt.json](../build/contrast_probe_receipt.json)。原gamma18/22位流和实物历史保留；该诊断已获用户标记/KEY1正常，CAP/COPY30、UF/ERR/DROP0；遮镜A041/B042/C042/D043，右侧1.50倍较自然。正式画质仍没有通过验收。


## 当前BLC实物反馈：黑灰底解决，轻微绿偏待测

用户确认CONTRAST PROBE01标记和KEY1正常、CAP/COPY30且UF/ERR/DROP0；完全遮镜后A041/B042/C042/D043，即65/66/66/67，右侧1.50倍较自然。新[style_video_black_level.bit](../build/style_video_black_level.bit)及[black_level_receipt.json](../build/black_level_receipt.json)独立保存，旧位流和实物记录保留。BLC位流已获用户遮镜“纯黑”、RIGHT1.00最自然、CAP/COPY30及UF/ERR/DROP0反馈；标记仍为同一CONTRAST PROBE01，不能唯一识别BLC版本，务必选择新文件，运行身份仍按会话关联。

预处理新增BLACK_LEVEL_A/B/C/D，通用默认0；物理measured为65/66/66/67。A/B/C/D固定指2×2左上/右上/左下/右下，每个RAW10先`max(raw-offset,0)`，再按Bayer选色、两G均值、最后截取8bit，后接gamma18。BGGR3对应蓝A65、红D67、两G各66。没有白点拉伸、曝光或白平衡更改。旧黑样本截到8bit约16，gamma18后55，可解释灰底；理想等于偏置的样本扣后0→0，用户遮镜观感已为纯黑，按本次反馈黑灰底问题已解决；未测量每个数字像素是否恒为0，剩余噪声与画质不能据此全面验收。

`--black-level-profile none/measured`中普通默认measured，仅支持short_exposure/Bayer3；color-probe强制none。复现该已测BLC为`python scripts/prepare_efinity.py --camera-profile short_exposure --bayer-pattern 3 --tone-profile gamma18 --black-level-profile measured --white-balance-profile none --contrast-probe --contrast-initial-level 2`。复现旧gamma18/22或旧contrast需显式none。DDR/COPY/未来CNN接收扣黑后gamma18像素，位宽、字节序、握手不变但数值语义更新。

右侧KEY1对比度界面保持，已测BLC位流启动1.50，但用户校正后选择RIGHT1.00最自然；原始RAW统计仍取自BLC前，因此遮镜A/B/C/D仍可能041..043，不应要求变为0。这是此次配置下的固定偏置，不是自动黑位跟踪，不代表全幅、全温度或其他曝光已校准。


最新颜色反馈：用户认为魔方颜色大致正确，但画面仍轻微偏绿。后续白纸RAW A09C/B0F5/C0F5/D0A0已收到；该BLC历史位流未加入白平衡增益，当前固定WB已实测不发绿与30fps/零错误，但室外天空微红；白平衡与清晰度未验收。当前WB版本物理顶层已显式设置对比度启动档0（1.00），通用style_contrast_probe的INITIAL_LEVEL默认2（1.50）保持；用户已确认WB版不发绿，CAP/COPY均30、UF/ERR/DROP均0；直接拍室外天空微红，隔玻璃更红，整体颜色适应性和清晰度仍待验证；启动档位未单独读回。


## 当前固定白平衡实测：室外天空微红待诊断

白纸原始A09C/B0F5/C0F5/D0A0=156/245/245/160，扣黑后按BGGR3得到R93/G179/B91。以G为基准，固定Q8增益R493/G256/B504约为1.926/1/1.969；原始证据在[white_balance_measurement.json](../build/white_balance_measurement.json)。新文件[style_video_white_balance.bit](../build/style_video_white_balance.bit)及[white_balance_receipt.json](../build/white_balance_receipt.json)单独记录，旧BLC黑底已通过的实物结论保留，用户已确认WB版不发绿，CAP/COPY均30、UF/ERR/DROP均0；直接拍室外天空微红，隔玻璃更红，整体颜色适应性和清晰度仍待验证。

处理顺序为物理RAW10各点钳位扣黑→Bayer选R/B和floor两G均值→`min(1023,(raw10*gain_q8+128)>>8)`→RGB8截高8位→gamma18。乘加为21bit无符号，Q8半向上舍入，10bit饱和；通用WB_GAIN_R/G/B_Q8均256，物理measured为493/256/504。代入此次均值预测RGB10各179、gamma前RGB8各44，不保证每个像素一致。没有修改曝光、传感器增益或白点拉伸。

`--white-balance-profile none/measured`默认随BLC选择：measured BLC默认measured WB，其他默认none；measured WB只适用于BGGR3/short_exposure/measured BLC。当前准备：`python scripts/prepare_efinity.py --camera-profile short_exposure --bayer-pattern 3 --tone-profile gamma18 --black-level-profile measured --white-balance-profile measured --contrast-probe --contrast-initial-level 0`。复现旧BLC必须显式WB none及contrast初档2；旧无BLC对比度默认WB none/初档2。

本候选物理对比度启动0即1.00，通用INITIAL_LEVEL默认2仍保留，KEY1五档不变。左图是BLC+固定WB+gamma18基线，右图启动1.00时透传。RAW统计仍在BLC/WB前，因此白纸A/B/C/D不必相等；UI仍CONTRAST PROBE01，需选择新位流文件，不能靠复用标题认定版本。DDR/CNN输入数值语义变为扣黑、固定WB、近似gamma1.8，队友应匹配训练预处理。

这是当前光照一次测量的固定校准，不是AWB或完整ISP；R/B增益可能放大噪声、造成高光饱和及改变整体亮度。用户已确认WB版不发绿，CAP/COPY均30、UF/ERR/DROP均0；直接拍室外天空微红，隔玻璃更红，整体颜色适应性和清晰度仍待验证。

### 室外中性色复测

较暗白纸059/071/071/05C已确认不隔玻璃测量。新增较亮白纸0A9/110/110/0AD扣黑后RGB106/206/104，按现有Q8增益493/256/504及Gamma1.8计算约为RGB104/104/104；天空0BE/0FB/0FB/0BE扣黑后RGB123/185/125，计算约为RGB113/98/115。用户确认天空肉眼呈白色或灰白云层。以上是对中心ROI均值套用处理公式的预测，不是逐像素输出实测；两次采样照明光谱及最新两组是否均无玻璃未独立确认。两组通道比例不同，仅换一组全局增益不能同时使这两个均值中性；偏色物理原因仍未确定。当前RTL、白平衡增益和位流保持不变。见[配对测量记录](../build/neutral_scene_pair.json)。
