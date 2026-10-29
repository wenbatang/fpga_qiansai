# 最终验证与使用（2026-10-30）

离线签核 PASS · 四风格完整720p CNN/DMA最低 35.47837fps · RAM10 174/256，DSP 100/160，XLR 53603/60800 · setup/hold +0.309/+0.026ns。未连接板卡、未下载、未写Flash；实板持续30fps待测。

## 使用入口

- Efinity工程：[ti60_camera.xml](../build/720p/ti60_camera.xml)。
- 用户上板测试文件：[ti60_camera.bit](../build/720p/outflow/ti60_camera.bit)，Programmer选择 **JTAG**。本轮仅生成文件，没有访问板卡。
- 完整签核：[signoff.json](../build/720p/signoff.json)；独立保留/交付审查：[final_review.json](../build/720p/final_review.json)。
- bit SHA256：`18f3fb3ffdd3d55951dfd2d38260dca726f2ba4fb38a61d2a2858b252c817c3f`。

摄像头仍为已确认的配套SC431HAI、J4与J2/J3的2–3接法，接口配置与原已核对720p版逐字节相同。不需主机上传图片或另烧CPU固件，固件和参数初始化已包含在bit中。启动先显示原画；KEY0/1/2/3选梵高/剪纸/漫画/水墨，KEY1+KEY2约0.5秒回原画，KEY0+KEY3长按逻辑复位。对照当前C8网络颜色与旧RF33存在差异，见[真实画质对照](model_quality.md)。

屏幕应保持720p60。C是DDR完整采集计数，I只在神经网络完成且最终DDR B成功后增加，原画复制和HDMI重复显示不计I。进入一种风格并稳定后，应记录至少10秒C/I、CAM4计数、错误字段和实际画面；若C约30而I低于30，仍未完成实板30fps目标。串口诊断是115200/8N1，可用`python -B pc/camera_view.py --port COMxx`；这个查看器不发送命令。

## 完整720p数值与吞吐

输入/输出1280×720 RGB565；内部2×2平均池化后的特征640×360；10条192×720条带，核心128、左右halo32。UI100MHz、CNN166.667MHz（仿真6.002ns，略慢于实现6.000ns）、HDMI74.25MHz/60Hz。每种风格各921600像素与独立整数参考比较，使用真实异步FIFO及有界AXI模型，第三输出bank、最终B、全局边界/接缝均验证。

| 风格 | UI周期 | 模型fps | 整数最大误差 |
|---|---:|---:|---:|
| 梵高 | 2818615 | 35.478418 | 0 |
| 剪纸 | 2818616 | 35.478405 | 0 |
| 漫画 | 2818619 | 35.478367 | 0 |
| 水墨 | 2818615 | 35.478418 | 0 |

这些数值不包含真实DDR控制器、摄像头、CPU与HDMI全并发。另用真实source_pool/jobs/reader/FIFO/raster及2818615周期加速器耗时模型，12个不同30Hz源帧全部完成并提交、0跳帧；23个完整HDMI帧共21196800像素逐值一致、0欠载。此项仅证明调度不会将30Hz供帧量化为20fps，不冒充完整SoC或实板测试。

## 实际CAD与板级配置

Efinity2026.1.132、Ti60F225/I3。RAM10 174/256，DSP 100/160，FF 29906，LUT4 26085，XLR 53603/60800；所有时钟关系最小setup/hold +0.309/+0.026ns。24个标量CDC首级、166条Gray最大延迟、73位稳定数据束、8条原生D-PHY唯一二级链精确约束，不使用整组时钟切断或无依据多周期。

正确20261012 V4原理图逐项审查79脚和12组Bank：MIPI专用RX1.2V、模组控制/按键/UART3.3V、DDR1.5V、参考/HDMI相关Bank1.8V。原理图SHA及每脚方向、电平、DDR OE绑定在signoff内。保持原HDMI邻近GPIO耦合警告；数字配置和CAD无法替代实际供电、电流、温升与排线状态测量。

## 功能门禁与失败修复

14类门禁包括逐点卷积、四模型核、DMA、完整720p、APB、真实Sapphire、生产核原语、DMA原语、顶层保护、按键、三bank调度、真实FIFO显示、双写仲裁及30Hz源调度。CPU实际执行3264B固件，两个模型692次真实配置、可变邮箱确认、ID/曝光/START与PLIC验证；不能称CPU已实测全部四模型上板切换。

首次动态二维局部写在原语网表中丢通道，已改固定context/channel与slot/lane唯一写者；详见[根因说明](synthesis_issue.md)。修复后生产RTL完整四风格、单核原语、DMA原语及错误恢复均通过。DMA OOC网表由固定候选源编译，候选与最终生产文件逐字节相同，原始PASS收据、编译输入、网表和日志均保留，严格别名证明禁止改结果或计数；没有冒称另跑一份不同的生产网表。

以下目录是签核必要证据，后续清理不可只因名称为实验/中间目录而删除：`build/experiments/*_fixed.sv`、`build/probe_dma/inputs.json`及实际map、`sim/dma_mapped/candidate_verification.json`及当前收据/日志。失败诊断归档`build/baseline_dynamic/`，不当作可下载版本。原47风格工程、原RF33与旧12通道bit保持；本轮没有训练、提交、推送、JTAG或Flash操作。

原模型画质选择仍由用户实板比较决定；手势分类及原图/风格/对半三界面不在本次bit内。若实板仍低于30fps，下一重点是将CNN单拍写合并为16拍突发，须连同AWLEN/WLAST和仲裁完整重验；本轮未实现，不能据理论带宽承诺。
