# 独立摄像头采集模块

入口为 `rtl/style_camera_capture.sv`，板级实例名为 `camera_capture`。它封装此前散落在 `style_ti60_top.v` 中的 RAW 预处理、Gamma、图像/取消通知 CDC、计数 CDC 和可选 RAW 均值统计。它是解包后的采集模块，不包含传感器引脚、D-PHY/CSI 接收 IP、I²C 初始化或 DDR DMA。

## 数据通路和分工

```text
传感器 ── MIPI D-PHY / 官方 CSI 接收器（板级）
                            │ camera_clk：VS、HS、DE、RAW10×4
┌────────────────── style_camera_capture ──────────────────┐
│ 按物理位置扣黑 → Bayer 转 RGB / 白平衡 / 缩放 → Gamma    │
│                       │                                 │
│               图像异步 FIFO → core_clk RGB888 流         │
│ 坏帧取消 → 取消异步 FIFO → core_clk abort + frame_id      │
│ 帧/丢弃/错误计数 → Gray 同步 → core_clk 状态             │
│ 原始 RAW → 可选 ROI A/B/C/D 均值（camera_clk）            │
└─────────────────────────────────────────────────────────┘
                            │
               style_platform_core → 采集写 DMA → DDR
```

I²C 配置主机仍在顶层；当前完成 164 条配置命令后，将 `config_done` 同步到 core_clk，并与 DDR 校准、取消队列健康条件共同允许平台采集。Sapphire 接管 I²C 时要移交单一主机所有权，无须重写采集模块。当前 config_done 只表示命令序列结束，不代表型号/NACK/寄存器读回验证。

## 全部接口

|接口|方向/位宽|时钟域|约定|
|---|---|---|---|
|camera_clk / camera_rst_n|输入/各1|摄像头|当前 50MHz；低有效复位，同步释放|
|core_clk / core_rst_n|输入/各1|平台|当前 100MHz；低有效复位，同步释放|
|async_rst_n|输入/1|共同异步断言|两个异步 FIFO 的共同复位；其内部各自同步释放|
|s_vs / s_hs|输入/各1|camera_clk|帧/行高有效。VS 上升开始帧，下降结束帧|
|s_valid|输入/1|camera_clk|CSI 的 DE；模块内部与 s_hs 相与；无输入 ready|
|s_raw|输入/40|camera_clk|四个连续 RAW10：第一个在 bits9:0，随后19:10、29:20、39:30|
|wb_r_q8 / wb_g_q8 / wb_b_q8|输入/各11|camera_clk|Q8 增益，256=1倍；DYNAMIC_WB=1 时下一个输入 SOF 锁存。不得直接接 CPU 跨域总线|
|m_rgb|输出/24|core_clk|RGB888：bits23:16=R、15:8=G、7:0=B|
|m_valid / m_ready|输出/输入，各1|core_clk|valid&&ready 的上升沿传输一个像素；等待期间数据、标志、编号均保持|
|m_sof / m_eol / m_eof|输出/各1|core_clk|与像素同行传递；首像素/每行末像素/整帧末像素；仅随有效像素解释|
|m_frame_id|输出/32|core_clk|一帧的所有像素使用同一编号，复位后从1开始；编号按32位回绕|
|m_abort / m_abort_frame_id|输出/1+32|core_clk|取消事件与编号；接收方每个有效拍都要处理，无 ready；可能连续有效多拍|
|input_frames|输出/32|core_clk|输入 SOF 数，不是写入 DDR 的成功帧数；跨域后有延迟|
|drop_frames / error_frames|输出/各32|core_clk|预处理丢弃/错误累计，不含平台后续 DMA/帧池错误；按32位回绕|
|abort_queue_fault|输出/1|core_clk|取消 FIFO 写满导致通知丢失的锁存故障；阻止平台领取新采集帧，需协调复位恢复|
|camera_fifo_level|输出/FIFO_ADDR_BITS+1|camera_clk|图像 FIFO 写域占用，具有指针同步延迟|
|core_fifo_level|输出/FIFO_ADDR_BITS+1|core_clk|图像 FIFO 读域占用，包含读预取寄存器和指针同步影响|
|raw_mean_valid / raw_mean_data|输出/1+40|camera_clk|可选统计单拍。A=data9:0、B=19:10、C=29:20、D=39:30；位于扣黑、白平衡、Gamma 之前|

取消通知与像素走不同 FIFO，不保证两条通道的到达先后。接收方按 frame_id 作废整帧，丢弃已存储或随后到达的同编号残余像素，不能把坏帧发布给显示。当前 `style_platform_core` 已提供配套帧管理。raw_mean 没有 ready 和 frame_id，只用于诊断/白纸校准；下游跨域必须整组握手或 FIFO，拥塞应报告而不是直接采样多位数据。

## 参数

|参数|通用默认|当前物理工程|
|---|---|---|
|CAM_WIDTH / CAM_HEIGHT|1920 / 1080|1920 / 1080|
|OUT_WIDTH / OUT_HEIGHT|640 / 480|640 / 480|
|BAYER_PATTERN|0（RGGB）|3（BGGR，已由用户颜色对照确认）|
|QUEUE_DEPTH|256|256 个预处理包，每包最多2像素|
|BLACK_LEVEL_A/B/C/D|全部0|65 / 66 / 66 / 67|
|WB_GAIN_R/G/B_Q8|全部256|493 / 256 / 504|
|DYNAMIC_WB|0|当前白纸校准候选为1；旧固定版为0|
|TONE_ENABLE / GAMMA_TENTHS|1 / 18|Gamma1.8；linear 选择 TONE_ENABLE=0|
|FIFO_ADDR_BITS / ABORT_ADDR_BITS|10 / 4|1024 个图像 RAM 项 / 16 个取消 RAM 项，各另有一项读预取|
|STATS_ENABLE|0|启用颜色/对比度诊断时为1|
|ROI_X / ROI_Y / ROI_SIZE|896 / 476 / 128|原始1920×1080帧中央128×128|

尺寸须满足底层模块规则：源宽是4的倍数，源高是偶数，仅支持从半分辨率 Bayer 网格向下缩放；该实现先做2×2 Bayer单元重建，再做 floor 坐标最近邻缩放。修改尺寸不自动配置摄像头寄存器、DDR 帧槽或 HDMI 布局。启用统计时 ROI 必须在源帧内，SIZE 为至少4的2次幂，X为4的倍数，Y为偶数。

## 最小接入示例

```systemverilog
style_camera_capture #(
    .BAYER_PATTERN(3),
    .BLACK_LEVEL_A(65), .BLACK_LEVEL_B(66),
    .BLACK_LEVEL_C(66), .BLACK_LEVEL_D(67),
    .WB_GAIN_R_Q8(493), .WB_GAIN_G_Q8(256), .WB_GAIN_B_Q8(504)
) camera_capture (
    .camera_clk(camera_clk), .camera_rst_n(camera_rst_n),
    .core_clk(core_clk), .core_rst_n(core_rst_n), .async_rst_n(common_rst_n),
    .s_vs(csi_vs), .s_hs(csi_hs), .s_valid(csi_de), .s_raw(csi_raw[39:0]),
    .wb_r_q8(11'd256), .wb_g_q8(11'd256), .wb_b_q8(11'd256), // ignored: DYNAMIC_WB=0
    .m_rgb(cam_rgb), .m_valid(cam_valid), .m_ready(cam_ready),
    .m_sof(cam_sof), .m_eol(cam_eol), .m_eof(cam_eof), .m_frame_id(cam_id),
    .m_abort(cam_abort), .m_abort_frame_id(cam_abort_id),
    .input_frames(camera_frames), .drop_frames(camera_drops), .error_frames(camera_errors),
    .abort_queue_fault(camera_fault),
    .camera_fifo_level(), .core_fifo_level(), .raw_mean_valid(), .raw_mean_data()
);
```

这里列出的黑位和增益只适用于目前已测摄像头模式/照明，移植其他摄像头应重新标定。m_* 接到平台 core 的 cam_*；统计和故障接对应状态入口。单独使用该模块须同时编译：style_camera_preprocess、style_rgb_gamma、style_async_fifo、style_reset_sync、style_cdc_counter、style_cfa_stats。SDC 中 FIFO/计数 Gray 总线约束也必须随实例层级更新，不能只复制一个 SV 文件。

## 复位、丢帧和性能边界

- async_rst_n、camera_rst_n、core_rst_n 来自同一全局复位事件，协调断言；camera/core 复位在各自时钟域同步释放。单独复位一个 FIFO 域不受支持。WB请求必须先在 camera_clk 域稳定。
- 输入不能反压；输出短时堵塞由队列/FIFO吸收，长时堵塞会按帧取消并计数，不能无限缓存。
- 不对外承诺固定端到端延迟；缩放、真实 VS 结束验证、FIFO、背压都会影响到达时间。
- 此次是接口封装，未提高传感器帧率，未加入 CNN。旧版本用户已反馈 CAP/COPY30、UF/ERR/DROP0；本次版本的实板验证待拿到板子后进行。

## Efinity 与验证

先关闭 IDE 中的旧缓存工程，再在项目目录运行：

```text
python scripts/prepare_efinity.py --contrast-probe --wb-calibration --performance-monitor
python sim/capture/run.py
python scripts/run_checks.py --collect
python scripts/build_efinity.py --build
python scripts/build_docs.py
```

重新打开 `efinity/style_video.xml`，确认 Design Files 有 `style_camera_capture.sv`，顶层 `style_ti60_top`、器件 Ti60F225I3、语言 sv_09。物理顶层由生成脚本维护，封装连接维护在 `scripts/camera_capture_shell.py`；模块本体为手写 RTL。

新的 SDC 层级为 `camera_capture/camera_cdc`、`camera_capture/abort_cdc`、`camera_capture/stat_camera`、`camera_capture/stat_drops`、`camera_capture/stat_errors`。项目脚本已同步修改，MIPI/DDR/HDMI 引脚与时钟配置保持原样。

采集仿真覆盖独立像素参考（全 RAW10 灰阶/混合色、动态增益帧内保持、Gamma/线性、分数缩放、输出背压）、短帧、真实 FIFO 溢出、取消编号、停止核心时钟后的取消队列故障、共同复位清空及新完整帧恢复；配置生成检查覆盖普通/颜色诊断/对比度/白纸校准/性能监测五种组合。构建与实板状态见 `build/camera_capture_receipt.json`；当前 Efinity 工程构建状态同时见 `build/efinity_receipt.json`。
