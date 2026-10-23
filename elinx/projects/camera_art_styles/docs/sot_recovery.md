# 行间SoT状态与完整帧恢复

2026-10-23。用户CAM2实板记录把当前丢帧原因定位到SoT分支：E和sot_records均49628，Control、header、format、CRC、包中断、FE、timeout、FS overlap等计数均0；捕获错误594，帧起点595，完整C/I为0。首错 `0x22000400` 表示SoT、WAIT状态、VS有效、HS无效、完成4行、RAW暂存0、无部分lane同步。记录没有lane队列内容或模拟波形，不能据此把物理错误称为假报。

原始记录与解析为 `build/board_log_20261023/camera_cam2_user.txt` 和 `cam2_analysis.json`。

官方定义中，真正SoT同步失败也不会带RxValidHS/RxSyncHS，因此不能用valid/sync简单相与过滤错误。[Efinix D-PHY RX指南v2.0，第8页](https://www.efinixinc.com/docs/mipi-dphy-rx-core-ug-v2.0.pdf)。本轮采用包边界受限的恢复策略，同时保留故障统计与完整帧拒绝条件。

SoT是一次MIPI高速传输的同步事件，CSI的FS/FE才是图像帧边界。本工程每行RAW按一包/HS处理；旧策略会让一次独立SoT记录持续污染整帧。新策略不会补出丢失的行，也不请求摄像头重传，只在整帧本来仍完整且校验通过时允许发布。

## 恢复边界

仅在以下条件全部成立时，将单独SoT状态计为可恢复告警，不立即永久置整帧bad：

```text
收到SoT错误记录
AND 状态为WAIT_SOT
AND sync_seen为0
AND 四个lane字节队列全部为空
AND 本记录无valid、无sync
```

此时没有正在解析或排队的包。允许继续等待后续同步，但并不因此提交图像。实际丢失RAW行仍会在FE精确行数、预处理像素/高度和DDR EOF检查中失败；缺FS的RAW不接收，缺FE由下一FS重叠或超时拒绝。HEADER/PAYLOAD/CRC、部分lane已同步、队列非空、含valid/sync的SoT仍是硬错误。control、lane/FIFO溢出、ECC、CRC、WC、VC、尺寸、FE及timeout的原处理保持。

总sot_records仍统计所有SoT错误，不能清零掩盖；新增soft_sot_records记录符合边界的告警。当前协议仍为CAM2/24字段/223字节/115200，低15位flags及字段顺序保持；原保留flags[15]改为“本轮软计数非零”，flags[31:16]为累计可恢复记录的16位饱和值。底层软计数为32位无符号数，回卷后诊断高位重新计数，不是永久sticky状态；该回卷不影响恢复条件或帧发布。总SoT可继续增加，不要求归零。

## 当前独立版本

目录 `build/camera_sot_recover60/`，原CAM1/CAM2及所有其他发布保留。仅新增 `rtl/sot_recovery/csi_ppi_bridge_recover.sv` 和独立构建/签核工具；CPU固件、四条BootRAM、模型、sensor配置、DDR、HDMI、79脚和全部Bank电压保持。

状态：**独立全CAD、79脚/12Bank电气及原生CDC签核通过，signoff.json为PASS。**

- [当前SoT恢复版bit](../build/camera_sot_recover60/outflow/ti60_camera.bit) · [工程](../build/camera_sot_recover60/ti60_camera.xml) · [签核](../build/camera_sot_recover60/signoff.json) · [最终复核](../build/camera_sot_recover60/final_review.json)
- RAM248/256、DSP148/160、XLR42423/60800；最小setup **+0.445ns**、hold **+0.026ns**。
- 最终8条D-PHY首级均唯一对应第二级、0级组合逻辑，级间最小setup **+13.478ns**；17个标量首级、136条Gray、14条FPS束和8个精确D-PHY首级例外保持，无整组切跨域。
- 同次bit SHA256：`177031364a8352fb59670fe8ba7b817d2535132f561b2a6a29dc39a5ae63f65a`。
- 最终独立重审与签核一致、12个复位同步FF属性、SDC异地重建一致和十二套旧发布指纹复核通过。实际原理图、电气方向/Bank/电平及整份peri与旧版保持，不调整PHY延迟/摄像头模式。

本轮仅生成本地文件，未打开串口或JTAG、未下载或写Flash；实板恢复是否命中、实际出图和C/I仍须用户验证。

单位验证26场景、109项检查、31470次逐拍比较，实际厂商FIFO；包含空闲边界、非空队列、有效/sync记录、各解析状态、CRC/ECC/尺寸/超时/溢出等。下述真实写帧链路为9场景、75项检查，生产恢复RTL直接参与；没有用接0或简单AND替身作为修复证据。

## 已做的链路复现

独立 `sim/sot_idle_repro/` 使用真实Bayer、packer、厂商FIFO、writer、source_frame_pool，以及有AW/W背压、延迟B的DDR模型：

- 第4行后注入7个空闲SoT记录：旧桥产生 `22000400`、8条CRC好行，却不发布原画。连续3帧旧captures0/errors3；实际恢复桥captures3/errors0，soft21。
- 停止/恢复byte时钟后3条残留记录，同样旧版丢帧、恢复版发布完整帧。
- 缺RAW行、缺FS、缺FE/超时、部分lane同步或包内仅错误不带valid/sync，仍不得发布；后续完整帧可恢复。
- 每次发布前确认实际writer的最终DDR B全部完成；EOF到达时B延迟200周期，必须等待。写入RGB565逐字节与独立Python参考一致。
- 简单“error AND(valid OR sync)”对包内SoT的反例会错误发布，明确不用于交付。

这些为数字模型复现，不是当前实板修复已经确认，也未在该复现中运行真实DDR/CNN/CPU。完整神经网络、CPU及显示按原同字节证据绑定，资源/时序仍须本轮实际实现。

## 使用与判断

仅用上方恢复版bit做Programmer/JTAG临时下载。摄像头自动采集，仍为1920×1080 RAW10→640×480处理→720p60居中显示，不需要上传图片或另烧固件。串口保持115200/8N1，可继续用 `pc/camera_trace.py` 或串口助手。

观察C是否开始增长、I是否完成并切换风格画，同时记录CAM2。flags[15]和高16位能说明恢复边界是否实际命中。如果C仍0、E或硬错误上下文继续出现，保留连续记录继续定位，不能无依据放宽条件或调电平。旧CLI不单独显示新增高位含义，原始记录和JSONL中的flags完整保留。

没有CSI行号、FS/FE帧号关联时，丢行又重复另一行或多处故障恰好拼成相同高度，不能仅靠CRC/行数理论排除。因此不宣称任意故障下图像来源可证明，也不以恢复代替MIPI信号质量验收。本轮不改PHY时序参数、引脚或供电；保留原HDMI耦合和未知Flash启动边界，不代为下载或固化。

本地只读复核入口 `scripts/sot_recovery/build.py audit`。新候选依次prepare、相关仿真、compile；构建单任务四线程，不运行中改源/权重，不覆盖当前发布。模型/CPU/显示与原证据同字节绑定，完整摄像头实物和>15fps赛题指标仍未完成验收。
