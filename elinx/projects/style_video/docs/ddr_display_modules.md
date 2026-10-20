# DDR 帧缓存与 HDMI 显示模块

工程现分成三个对外模块：`style_camera_capture`、`style_ddr_framebuffer`、`style_hdmi_display`。手写和生成的 RTL 都已加入 Efinity 工程。当前默认左侧显示预处理后的原图，右侧图像区域固定黑色，为 CNN 结果预留。

```text
MIPI/CSI → camera_capture → framebuffer ←→ Efinix DDR3控制器/PHY → DDR3
                                  │ ↑
                      CNN输入RGB流 │ │ CNN结果RGB流
                                  ↓ │
                             队友完整CNN
                                  
                     framebuffer → hdmi_display → TMDS10位字
                            ↑             │          ↓
                     APB / IRQ       换帧请求/应答   板级串化器 → HDMI
                            ↑
                   Sapphire RISC-V / C驱动
```

## 1. DDR 模块的职责与接口

源文件：`rtl/style_ddr_framebuffer.sv`。顶层实例名：`framebuffer`。

它是稳定的帧存储接口层，内部实例化原有 `style_platform_core core`，包含四个 DMA、共享 AXI 仲裁、帧槽所有权、完整帧发布、APB 控制和 CNN 流接口。原有核心逻辑本体未修改；Efinix DDR3 控制器及物理引脚仍在板级顶层，AXI 连接保持。

|端口组|时钟域|接口与约定|
|---|---|---|
|运行条件|core_clk|`clk/rst_n/cal_ready`。低有效复位；DDR校准、摄像头配置完成且采集取消队列健康后才允许新帧采集|
|采集输入|core_clk|`cam_rgb[23:0]`、`cam_valid/cam_ready`、`cam_sof/eol/eof`、`cam_frame_id[31:0]`，直接接采集模块的 m_*|
|采集取消/统计|core_clk|`cam_abort/cam_abort_id`、`camera_frames/camera_drops/camera_errors`，直接接采集模块同域输出|
|DDR AXI4主口|core_clk|`m_axi_aw* / w* / b* / ar* / r*`，128位数据、32位字节地址、可配置ID位宽，当前ID4。平台单方向一个在途事务，读写可并行|
|显示像素输出|core_clk|`display_rgb[23:0]`、`display_valid/display_ready`。逐行先640个原图像素，再640个结果像素，一帧共614400个有效像素|
|显示换帧|请求/窗口来自pixel域，由核心内部同步|`display_refresh_request/display_safe_window` 来自显示模块；`display_refresh_ack/display_flush` 返回显示模块。接入时保留现有四阶段握手，不能将脉冲跨域直连代替|
|前台与模式|core_clk|`front_valid/front_frame_id/display_mode` 以及 `capture_fps/process_fps/bypass_active`，显示模块通过原有整组握手跨域锁存|
|欠载反馈|core_clk|`underflow_count` 接显示模块 `underflows_core`，不能接像素域的 underflows|
|CPU控制|core_clk|完整 APB3 从口及 irq，见下一节|
|CNN输入输出|core_clk|`accel_input_* / accel_output_* / accel_start / accel_abort`，见第三节|
|状态与诊断|core_clk|成功采集/处理/发布计数、丢弃/错误、fatal_fault；可选性能快照1024位和快照有效脉冲|

内存布局不变：基址0x01000000，四原图槽和两结果槽，每槽2MiB。640×480 RGBX8888，每帧1,228,800字节，stride=2560，32位字为0x00RRGGBB，小端字节B/G/R/0；AXI128的低32位是最早像素。CPU/BSP须保留0x01000000–0x01BFFFFF，避免程序、堆栈或权重覆盖帧池。

## 2. RISC-V 具体从哪里接入

**位置：`style_ti60_top.v` 中的 `framebuffer` 实例。**目前 paddr/psel/penable/pwrite/pwdata 仍接常数，表示没有 Sapphire；把这些常数连接改为 Sapphire 的 APB 外设总线，并把返回值及 irq 接回 CPU 系统。

|Sapphire侧|framebuffer端口|说明|
|---|---|---|
|外设字节地址offset|paddr[11:0]|由实际SoC地址译码得到；不是DDR帧池基址|
|外设选中|psel|APB3选择|
|访问阶段|penable|APB3访问阶段|
|写使能|pwrite|1写，0读|
|写数据|pwdata[31:0]|CPU→视频平台|
|读数据|prdata[31:0]|视频平台→CPU|
|完成|pready|视频平台→CPU|
|错误|pslverr|视频平台→CPU|
|外设中断|irq|接Sapphire中断控制器，按BSP/PLIC约定处理|

建议接入初期令 APB 外设侧与 core_clk 同为100MHz。若 Sapphire 总线不同时钟，使用完整APB跨时钟桥；禁止逐位同步地址/数据/控制。CPU外设基址由实际SoC地址表/BSP分配；驱动先读 base+0x000，应该得到0x53565931。

若队友的SoC只导出AXI或AHB，应先接对应总线到APB的桥及地址译码，再连接这里的APB从口，不能把两种总线信号按名字直接连在一起。

主要寄存器：CONTROL=0x004，bit0 enable、bit1 auto_run、bit2 bypass；START=0x008写1请求一帧；STATUS=0x00C，bit2任务忙、bit5 fatal；IRQ_STATUS/ENABLE/CLEAR=0x010/014/018；DISPLAY_MODE=0x020，0左右、1左图/右黑、2左黑/右图。完整表仍在 `interface_contract.md`。

**当前显示模块 RESERVE_CNN=1，强制右侧图像黑色，优先于 APB 的 DISPLAY_MODE。**因此当前写DISPLAY_MODE=0也不会显示右图。队友接好CNN后须按第三节同时关闭这个构建时预留开关。

摄像头I²C配置不经过本DDR外设；当前顶层硬件初始化主机仍是唯一所有者。RISC-V接管摄像头时需另行连接I²C控制器并停用原主机。权重加载端口/寄存器当前仍需与CNN队友约定。

## 3. CNN 接入与打开右侧

CNN接 `framebuffer` 实例的 `accel_*`，图像规格保持640×480、RGB888、每握手一像素、同帧编号。网络输出要有准确SOF/EOL/EOF，背压期间数据/标志/编号保持；收到abort清空当前任务。平台负责DDR图像读入、结果写回及成功写响应后的完整帧发布。

需要同时完成三项：

1. 在板级生成脚本中实例化完整CNN，接好所有 accel_*，将 framebuffer 的 FORCE_BYPASS 设为0。
2. CPU在任务空闲时清CONTROL.bit2，按手动/自动策略启动任务；复位默认bit2仍为1。
3. 准备工程时加 `--show-result`，使显示模块 RESERVE_CNN=0。DISPLAY_MODE置0后左右显示同一编号原图和结果。

`--show-result`单独使用只会显示当前已有的结果；在当前未接CNN的工程里，它显示的是COPY，不能称作神经风格图像。现有默认内部仍用COPY建立完整pair、验证搬运，右侧的最终黑色遮罩不删除COPY任务、不减少右侧DDR读取流量，也不增加帧率。

## 4. 显示模块的职责与全部接口

源文件：`rtl/style_hdmi_display.sv`。顶层实例名：`hdmi_display`。

它包括显示异步FIFO、标准720p时序、前台状态跨域锁存、原有OSD、RAW/WB诊断跨域、对比度/白平衡/性能叠加和保留的官方 dvi_encoder。板级高速串化/引脚极性仍在顶层，不改厂商IP和 Interface Designer 配置。

|接口|时钟域/用途|
|---|---|
|core_clk / core_rst_n|100MHz核心域，接收DDR读出的配对RGB流；低有效复位同步释放|
|pixel_clk / pixel_rst_n|74.25MHz像素域，生成时序和视频；低有效复位同步释放|
|camera_clk / camera_rst_n|50MHz摄像头域，仅用于RAW/WB诊断来源；图像主体不再经过此域|
|async_rst_n|共同复位诊断FIFO/信箱；各域复位需协调断言与释放|
|s_rgb[23:0] / s_valid / s_ready|core域。每行先原图后结果；等待ready时像素保持。隐藏右图仍消费对应token|
|core_flush|core域单拍，清显示FIFO；底层扩展为16核心周期，两个FIFO域共同复位|
|core_front_valid / core_frame_id[31:0] / core_mode[1:0]|core域前台信息，在换帧应答时整组锁存跨域；RESERVE_CNN=1覆盖mode为左图/右黑|
|capture_fps / process_fps[15:0]|core域阶段帧率，当前process仍为COPY；不表示HDMI刷新率或CNN性能|
|core_camera_frames / core_drop_count / core_error_count[31:0]|core域诊断累计值，与前台配置整组跨域|
|bypass_active|core域前台任务类型，保留BYPASS COPY提示|
|refresh_request / refresh_ack / safe_window|与framebuffer显示换帧接口对应连接；请求/安全窗口是pixel域，ack是core域；两模块内部包含相应同步/稳定快照逻辑|
|raw_mean_valid / raw_mean_data[39:0]|camera域、无ready统计单拍；模块内40位异步FIFO跨域，溢出锁存失效标志|
|key1_n|异步物理按键，原对比度模块内部同步消抖；右图预留期间档位变化不显现在右图图像区|
|wb_state[3:0] / wb_active_r / wb_active_b[10:0]|camera域状态/已应用增益；模块内26位FIFO整组跨域；不是CPU直接写入端口|
|perf_snapshot[1023:0] / perf_snapshot_valid|core域性能快照，由原请求/应答信箱跨域；PERF_OVERLAY=1时启用|
|video_rgb[23:0] / video_de / video_hs / video_vs|pixel域视频输出观察点；RGB已包含所有叠加和最终右图遮罩|
|video_x / video_y[15:0]|pixel域扫描坐标观察点|
|tmds_data0/1/2 / tmds_clk[9:0]|每像素10位编码字，接顶层原有高速串化接口，不是直接接HDMI引脚|
|underflows[31:0]|pixel域欠载累计，供本地观察|
|underflows_core[31:0]|Gray同步后的core域欠载累计，反馈framebuffer|
|fifo_level[FIFO_ADDR_BITS:0]|core域显示FIFO水位，接性能监测|

主要参数：RESERVE_CNN默认1；ENCODE_TMDS默认1，只有通用仿真显式0；标准时序1280/110/40/220及720/5/5/20，HS/VS正极性；IMAGE_WIDTH/HEIGHT/Y=640/480/120，FIFO_ADDR_BITS=12，SAFE_END=100。COLOR_PROBE、CONTRAST_PROBE、WB_OVERLAY、PERF_OVERLAY控制可选诊断，正常可以全部关闭。

当前图像区域：左图x=0..639、y=120..599；右侧预留区x=640..1279、y=120..599。保留上下诊断区域及右上RESULT标题。最终黑色遮罩位于全部叠加和欠载保护之后，即使异常帧产生紫色保护，右侧图像区也保持黑色；左侧仍按原欠载策略显示并记录UF。关闭预留后，恢复原来的配对结果和APB模式行为。

## 5. Efinity 维护与验证边界

默认准备命令：

```text
python scripts/prepare_efinity.py --contrast-probe --wb-calibration --performance-monitor
```

上述命令生成三模块顶层及默认右黑布局；未来打开结果区时在末尾加 `--show-result`。Efinity工程仍为 `efinity/style_video.xml`，器件Ti60F225I3、语言sv_09、顶层style_ti60_top。先关闭旧IDE缓存工程、再prepare、再重新打开；确认Design Files有两个新模块。

`style_ddr_framebuffer.sv`由`scripts/generate_ddr_wrapper.py`按真实核心端口生成，prepare自动调用它；核心内部逻辑仍维护在`scripts/generate_core.py`。显示模块本体为手写RTL，顶层接线由`scripts/video_module_shell.py`生成。不要只改生成的style_ti60_top后再运行prepare。

SDC更新为`hdmi_display/sink/fifo`、`hdmi_display/raw_diagnostics.color_stats_cdc`、`hdmi_display/stat_underflow`，并为`hdmi_display/white_balance_diagnostic.wb_status_cdc`补充Gray总线偏斜约束。Efinity以点号连接generate作用域与实例名，这两处不能改成斜线。MIPI、DDR和HDMI引脚/时钟参数未调整。

新增DDR封装回归覆盖实际AXI存取、独立AW/W/B/AR/R等待、ID4/32/128、帧槽保护、取消、手动启动、APB错误/中断和外部算法流；显示封装覆盖右黑/恢复双图、坏帧保护、换帧、诊断组合及完整720p时序下的左右像素。通用仿真关闭加密HDMI编码器，以Efinity完整实现验证其连接；理想流/AXI模型不等同实板带宽。

本次最终构建记录为`build/ddr_display_modules_receipt.json`，候选比特流为`build/style_video_ddr_display_modules.bit`。用户目前没有板子，新版实际显示/帧率待上板验证，旧版30FPS观察不自动算作此版验收。
