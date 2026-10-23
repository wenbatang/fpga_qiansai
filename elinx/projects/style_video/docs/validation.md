# 摄像头与 RISC-V 验证

> 当前按正确20261012原理图修正KEY1=P14、KEY2=N14并重新构建；最新bit/时序/电气依据见[统一复核](../../../../docs/Ti60_correct_schematic_review.md)。下方早期构建数值若不同，以新复核为准。


2026-10-15。独立style_video实现，保留旧UART工程、模型、签核bit与demo10原例程。

已通过：

- RAW10四像素布局、BGGR合成、居中裁剪、valid气泡、错误帧及HS/EOF同拍。
- 字节域格式检查、故障位同步和复位恢复；CSI状态帧尾清除、AW/W分离与延迟B。
- APB上电禁止采集、1436项运行时配置、忙时保护、加载期间按键变化与IRQ W1C。
- 三原画bank所有权、锁定期间连续采集、最新帧替换计数、claim/publish同拍。
- 实际Efinix FIFO RTL、封包、DDR DMA与竞争写主机联合测试：满FIFO、丢EOF、下帧恢复、背压、最终B屏障、事务公平性。
- 运行时CNN四组真实模型，在缩小几何128×24每像素对照整数参考，最大误差0，覆盖分条/全局相位/AXI错误及恢复。此尺寸不用于估算VGA实际FPS。
- 编译后9468字节RV32I固件，在独立ISA/MMIO/I²C模型执行：ID、模式读回、VTS曝光限幅、实际权重加载及三次启动/中断。错误ID无传感器写入/权重加载，采集关闭且I²C释放。加速时间模型不是Sapphire RTL仿真或硬件运行记录。
- FPS稳定束握手、消隐应用、重复HDMI显示不计数、0–99饱和。
- CPU RAM四条初始化字节通道重建后，与当前固件逐字节一致。

测试入口：`sim/check_modules.py`、`sim/check_runtime.py`、`sim/check_firmware.py`。日志分别在 `build/sim/`、`sim/runtime/`、`build/camera_vga/firmware_test.json`，均留本地。

综合通过，RAM10 212/256、DSP148/160。浅层可写权重用寄存器，行缓存用块RAM。布局布线与时序的最终状态追加在本文件末尾；工具pnr PASS不等于setup/hold全非负。

未验收：物理电压/跳线、实际ID、摄像头FPS/Bayer/亮度、DDR并发、Sapphire真实启动和中断、四键/HDMI、连续丢帧率与推理>15fps。两风格缓存等待消隐可能限制端到端更新速度，须测量和优化。原画/风格对比及完整ISP/AE未完成。用户要求720p30不等同原赛题显示指标。没有JTAG下载或Flash固化。

## 本轮最终 CAD 状态：未签核

2026-10-15历史候选：RAM10 212/256、DSP148/160、FF24732、LUT24842。2026-10-16改用同版CSI5.15的RAW10专用/像素侧带配置，并修复VS极性后，重新综合与布局布线完成：RAM212/256、DSP148/160、FF24671、LUT24126、XLR48793/60800；79脚配置对照仍通过。实际物理电压未测量。

2026-10-16最终静态时序仍有两组setup负裕量：byte→UI **−0.561ns**、UI→byte **−0.528ns**，core内部setup+2.677ns；其余列出的setup/hold非负。问题为厂商CSI内部`word_count → byte2pixel/pixel_bits_cnt`元数据路径，以及`RxStopState → dphy_rx/.../RxStopState_1P`路径。两域之间按异步时钟相位分析产生极小边沿间隔，负裕量本身不直接证明功能错误，但必须核实稳定窗口、采样使能与同步结构后才能准确约束。

原V7的SDC含较宽的exclusive时钟分组；新工程没有照搬这些分组，也没有给上述元数据路径添加无依据的多周期或false path。保护IP不能通过修改其内部逻辑解决，后续应取得与CSI5.15对应的厂商CDC/时序说明，或建立可验证的替代接口封装。完整报表、指纹及失败原因保存在 `build/camera_vga/candidate_status.json`，状态 **NOT_SIGNED_OFF**。`camera_signoff.py`会拒绝当前构建，因此没有生成新bit、没有下载或写Flash。

## 2026-10-16新增真实IP联合验证

- Questa10.7c合法运行同版CSI5.15仿真模型与厂家TX模型，RAW10、四lane、70MHz byte/100MHz pixel。联合项目Bayer模块发现并修复VS极性：上升沿开始、下降沿结束，错误W1C也延后至下降沿后。小尺寸连续32帧通过，坏帧0。
- 完整1920×1080输入，分别输出640×480与640×360，各连续两完整帧、坏帧0；每帧153600/115200像素对，逐拍RAW负载与独立16位几何计数对照。厂家示例checker的10位y不能覆盖1080行，完整尺寸采用独立计数与数据对照，没有删除像素检查。
- 真实Sapphire3.4.0 RTL执行当前9468字节C固件，通过SC431HAI开漏I²C、ID、V7配置、曝光限幅、两组2872项真实学习参数、按键、START及PLIC中断测试。摄像头为I²C行为模型，加速器完成为模型，不是整机板上FPS验证。CPU仿真使用与综合一致的RAM字节通道，避免误用厂家Testbench默认示例固件。
- 360高度只验证了参数化预处理，不是完整360高度CNN/显示bit；640×480仍是当前完整工程配置。没有改原四组权重，也没有改变旧串口bit。新旧资料与验证边界见[本轮复查](review_20261016.md)。
# CSI CDC补充调查（2026-10-16）

详见[独立调查记录](csi_cdc_investigation.md)。最小CSI工程已实际完成综合/接口/布局布线/原生STA，11 RAM、0 DSP；byte→core −0.472ns、反向−0.529ns，证明可脱离整机复现。四lane共8条HS settle / StopState首级唯一后继均为对应第二级，整机级间最小setup +13.085ns。只在最小工程STA会话验证精确首级例外及Gray上限，反向+9.277ns，正向仍保留16个word_count到pixel_bits_cnt争议端点。

新增七组合法Questa公共接口压力仿真，相位/LP字节时钟停启/约60MHz像素时钟/中途复位，325个小尺寸好帧、0坏帧。既有测试的Discontinuous参数不等于已模拟接收字节时钟停振；本次显式补足。新版官方v3.3的DOC-2988异步约束章节对应IP5.16，当前5.15适用性和元数据稳定窗口未确认，不能追溯放行。当前生产RTL/SDC/IP未改、原候选状态与指纹保留，没有生成配置或访问板卡。


## 新PPI替代工程 CAD签核（2026-10-16）

旧CSI5.15候选未取得厂商稳定窗口确认，保持未签核；新目录`build/camera_ppi/`使用D-PHY5.8公共PPI、原子44bit异步FIFO和UI域CSI RAW10解析，原争议word_count到pixel_bits_cnt模块不在新映射网表。没有解密或修改保护IP，也未将5.16文档追溯套用5.15。

实际重建综合、接口、两次布局布线及最终原生STA通过。RAM204/256、DSP148/160、XLR48995/60800；全关系最小setup+0.289ns、hold+0.026ns，core内部setup+2.690ns。8条控制同步链唯一第二级后继、逻辑级数0，最终级间最小setup+13.555ns。17条标量首级、136条Gray路径最大延迟与14bit FPS稳定束逐项约束，没有整组异步或多周期掩盖。

79脚的每个已实现配置字段与既有板级审查一致，peri.xml与原V4候选字节一致；CPU四RAM通道逐字节匹配9468字节固件，四模型指纹保持。公共PPI与真实D-PHY/实际FIFO/Bayer六组压力仿真、完整1080p输入三完整帧及错误恢复测试通过；已有CNN整数参考、DDR所有权和真实Sapphire执行测试指纹复核通过。

生成`build/camera_ppi/outflow/ti60_camera.bit`，2,952,954字节；`build/camera_ppi/signoff.json`为PASS，SHA256：`7fc292efc91c6a28c1121dfb57224d63828ceb0d35fcd5dfffebae660d82bc23`。没有下载或固化。实际供电跳线、SC431HAI一个包/一次HS的兼容性、Bayer/FPS/亮度、整机DDR/HDMI并发与CPU中断未实测；CAD签核不等于实板可用或赛题验收。具体范围和重建步骤见[公共PPI摄像头实现](ppi_camera.md)。

## 同一bit的上板前复查（2026-10-16）

用户进一步确认J4接口与J2/J3均2–3短接。重新查看原理图并复核79个物理脚、12个Bank电压配置、24组DDR数据/OE接线与全部精确约束；先比较既有签核哈希，再检查现存产物，bit未更改。新增`sim/check_top_safety.py`：实际顶层/reset/boot，其他IP黑盒，覆盖开漏四状态、从机ACK、三PLL分别失锁、校准失效、UI/byte停振及按键复位，PASS。不是完整SoC或模拟电气仿真。

额外结果在`build/electrical_review_20261016/review.json`，入口`scripts/review_camera_ppi.py`。实际电压/电流/温升、端到端实屏/FPS仍未验证；保留HDMI邻近耦合警告。SC431HAI手册第14页图1-7/1-8为当前单包/HS解析范围提供支持，但未测163项配置下的实物波形。[完整记录](preflight_review_20261016.md)。

后续8项编译固件故障退出模型测试通过：错误ID、无响应、SDA/SCL常低、配置NACK、尺寸错误、VTS不足、开流NACK。全部关闭采集、保持模组复位、释放I²C且不启动CNN。入口`sim/check_camera_fault_shutdown.py`，为机器码ISA/MMIO模型，不是实板。用户同时确认现有Flash内容不清楚或未自行烧写，因此新bit的CAD签核不能覆盖正常上电可能执行的旧Flash程序；先确认启动内容/供电，再进行易失性配置验证。未下载或固化，bit指纹不变。
