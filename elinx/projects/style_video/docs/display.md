# 显示模块：接口、时序与恢复

## 本阶段功能

`style_video_timing.sv`、`style_display_sink.sv`、`style_osd.sv` 为手写、可综合 SystemVerilog，语法兼容 Efinity 的 `sv_09` 及 Icarus `-g2009`。显示模块接受一行先原图再结果的 RGB888 数据，通过真正的异步 FIFO 从核心时钟域转到像素时钟域，输出同步对齐的 RGB、DE、HS 和 VS。它不包含厂商 PLL、TMDS 编码、LVDS 串化或引脚配置，这些属于顶层的平台封装。

默认布局是标准 1280×720 显示区，两张 640×480 图像 1:1 并排，图像行位于 `y=120..599`。`y<120` 是标题和计数，`y>=600` 是底部说明区。输入只有 `1280*480` 个图像像素，没有显示消隐区的占位数据。

当前算法为直通复制，OSD 的处理计数标签明确写作 `COPY FPS`，不能用它宣称完成 CNN。摄像头采集 FPS、复制完成 FPS、HDMI 刷新率是三种不同计数。

## 文件职责

| 文件 | 实现 |
|---|---|
| `rtl/style_video_timing.sv` | 水平/垂直计数、正极性同步、DE、显示帧起点及安全窗口 |
| `rtl/style_display_sink.sv` | 配置跨域握手、FIFO 清空、像素选择、欠载保护和 OSD 合成 |
| `rtl/style_osd.sv` | 5×7 字符放大两倍，输出文字像素和命中信号，不增加时序延迟 |
| `rtl/style_async_fifo.sv` | 核心域到像素域的双时钟 FIFO，注册预取，`ready/valid` 交付 |
| `rtl/style_reset_sync.sv` | FIFO 两域共同异步复位，各自同步释放 |

## 时钟与默认视频时序

像素时钟必须由 Efinity Interface Designer / PLL 配成 **74.25 MHz**。参数默认如下：

| 项目 | 有效 | 前肩 | 同步 | 后肩 | 总计 |
|---|---:|---:|---:|---:|---:|
| 水平 | 1280 | 110 | 40 | 220 | 1650 |
| 垂直 | 720 | 5 | 5 | 20 | 750 |

`74,250,000/(1650*750)=60 Hz`。坐标原点是有效显示区左上角，`x=0..1279,y=0..719` 时 DE 为 1；正 HS 位于 `x=1390..1429`，正 VS 位于 `y=725..729`。计数器覆盖整个显示扫描，包括消隐区。

RGB 是 FIFO 已预取头部数据的组合选择，OSD 也是组合选择，没有新增整拍延迟。因此 RGB 与同一拍的 DE/HS/VS 配对。TMDS/高速输出若增加寄存级，须让数据和时序一起增加相同延迟。

## `style_display_sink` 参数

| 参数 | 默认 | 说明 |
|---|---:|---|
| `H_ACTIVE/H_FRONT/H_SYNC/H_BACK` | 1280/110/40/220 | 水平时序 |
| `V_ACTIVE/V_FRONT/V_SYNC/V_BACK` | 720/5/5/20 | 垂直时序 |
| `IMAGE_WIDTH/IMAGE_HEIGHT` | 640/480 | 每个图像的尺寸 |
| `IMAGE_Y` | 120 | 图像起始显示行 |
| `SAFE_END` | 100 | 新帧预取窗口结束行，不包含这一行 |
| `FIFO_ADDR_BITS` | 12 | 4096 个 RAM 像素槽，加一个读端注册预取槽 |
| `ENABLE_OSD` | 1 | 为 0 时关闭全部文字，便于像素级仿真 |

修改布局时必须满足 `2*IMAGE_WIDTH<=H_ACTIVE`、`IMAGE_Y+IMAGE_HEIGHT<=V_ACTIVE`、`SAFE_END<IMAGE_Y`。扫描计数为 16 位，水平/垂直总计不得超过 65536。图像起始行前应留出足够预取保护间隔；小参数仅用于仿真。

## 输入接口

| 端口 | 位宽/域 | 约定 |
|---|---|---|
| `core_clk/core_rst_n` | 核心域 | 复位低有效，顶层按本域同步释放 |
| `pixel_clk/pixel_rst_n` | 像素域 | 74.25 MHz，复位低有效，顶层按本域同步释放 |
| `s_rgb` | 24 / 核心域 | `{R[7:0],G[7:0],B[7:0]}`，不作字节翻转 |
| `s_valid/s_ready` | 1 / 核心域 | 两者均为 1 的上升沿接受一个像素；等待时源保持像素不变 |
| `core_flush` | 1 / 核心域 | 刷新 FIFO，单周期输入也扩展为最后一个高电平后 16 个核心时钟 |
| `core_front_valid` | 1 / 核心域 | 当前有没有可显示的完整原图/结果对 |
| `core_frame_id` | 32 / 核心域 | 配对的源图编号 |
| `core_mode` | 2 / 核心域 | 0 两侧显示；1 左原图右黑；2 左黑右结果；3 按两侧显示处理 |
| `capture_fps/process_fps` | 16 / 核心域 | 捕获和复制完成 FPS；显示十进制，超过 9999 时显示 9999 |
| `bypass_active` | 1 / 核心域 | 1 时底部显示 `BYPASS COPY` |
| `refresh_ack` | 1 / 核心域 | 核心处理完刷新/配置后保持为 1，直到请求同步撤回；之后降为 0 |

输入每行先 `IMAGE_WIDTH` 个原图像素，再 `IMAGE_WIDTH` 个结果像素，然后开始下一行；一帧总计 `2*IMAGE_WIDTH*IMAGE_HEIGHT` 个 tokens。没有 SOF/EOL 输入，帧长度和次序由显示读出 DMA 保证。隐藏某一侧时也必须传递并消耗这一侧全部像素，不能改变输入序列。

## 输出接口

| 端口 | 位宽/域 | 约定 |
|---|---|---|
| `video_rgb` | 24 / 像素域 | 与输出时序同拍的 RGB888 |
| `video_de/video_hs/video_vs` | 1 / 像素域 | 有效和正极性同步 |
| `video_x/video_y` | 16 / 像素域 | 整个扫描计数，含消隐区 |
| `refresh_request` | 1 / 像素域 | 四阶段握手请求；启动时及每帧图像区结束 `x=0,y=600` 拉高 |
| `safe_window` | 1 / 像素域 | `y=600..749` 或 `y=0..99`；`100..119` 是预取保护间隔 |
| `underflow_count` | 32 / 像素域 | 每次发生图像欠载累计一次，不是坏像素数 |

`refresh_request` 和 `safe_window` 是像素域电平，顶层核心域需至少两级同步。`underflow_count` 是多位像素域计数，跨到寄存器域须使用 Gray 编码同步或读数握手，不能直接逐位采样。图像更新窗口包含图像之外的有效底部区域，并非只在 HDMI VS 消隐期间。

## 刷新握手与配置跨域

1. 像素域拉高 `refresh_request` 并保持。
2. 核心域同步看到请求后停止旧读流，等待已有 AXI 读事务结束，触发 `core_flush` 清空共同 FIFO。
3. 等待 flush 与两域复位释放，再重新预取整帧，准备 `frame_id/mode/front_valid/FPS/bypass`。
4. 核心域拉高 `refresh_ack`，同时保持所有配置不变。sink 注册配置快照及内部 ACK，再经两级像素域同步。
5. 像素域仅在 `safe_window=1` 时锁存快照并撤回请求。若 ACK 到得晚，保持请求和 ACK 到下一安全窗口；不能在图像有效区半途换配置。
6. 核心域看到请求降为 0，再降 ACK。下一刷新前不修改本次锁存的配置快照。

正常时每个显示帧都重新读取同一组前台图像。60 Hz 重复扫描不应算作 60 次算法完成。顶层须在发 ACK 前保证剩余预取时间与 FIFO 深度足够；安全 ACK仅代表配置和刷新被接纳，不是 DDR 带宽保证。

FIFO 共同复位为 `core_rst_n & pixel_rst_n & ~flush_active`，复位有效期间 `s_ready=0`。核心 DMA 不得假设 flush 输入下降立即可写；须依据 `s_ready` 接受数据。本项目核心顶层预留 64 个核心周期等待，之后仍遵守 ready/valid。

## 欠载和空前台

- 没有完整前台时，图像区域输出黑色，不报告欠载、不读 FIFO。
- 非图像区域和消隐期不消费 FIFO；OSD 不需要输入像素。
- 有完整前台时，第一个取不到像素的位置立即输出 `FF00FF`，计数加一，并将剩余图像区域全部标粉。
- 发生欠载后停止读 FIFO；之后迟到的数据不再造成画面错位。下一刷新必须清空并重新读整帧；刷新 ACK 后才重新显示。
- 模式 1/2 隐藏的一侧仍然消费 tokens，发生欠载仍报告并标粉，保证两个图像序列始终对齐。

平台核心通过同步后的 `underflow_count` 变化，在欠载发生后立即进入 `D_DRAIN`，取消显示读 DMA 并清除本地解包输出，按 AXI 规则排空已经接受的读事务。不能等下一次刷新才取消：像素端标粉后停止消费，默认图像区剩余扫描可达 10.67ms，比默认 100MHz 核心域读 DMA 的 10ms 无进展看门狗更长。这种等待会把正常的欠载保护误变成 sticky fatal。

立即排空不等于立即清 FIFO 或释放帧槽。共同 FIFO flush、旧 pair 释放和新 pair 发布仍等待安全窗口；像素端保持本帧剩余图像粉色，下一轮从完整帧起点恢复。

`underflow_count` 在显示域按每次坏显示帧增加一次；平台的 `drop_count/error_count` 则是各处理阶段事件合计，同一源坏帧可能被不同阶段重复记录，不能当作按 frame_id 去重的唯一丢帧/错误帧数量。

## 已运行验证与限制

运行入口：`D:\python3.11\python.exe sim\display\run.py`，编译 `-g2009`。脚本寻找 PATH 中的 Icarus，当前本机备用路径为 `D:\vscode\iverilog\iverilog\bin`。日志和 vvp 仅写入 `build/display`。

已通过：

- 标准完整 1650×750 扫描，921600 个有效像素，HS/VS宽度/极性、帧周期、安全窗口逐拍核对。
- 小参数布局模拟跨时钟 FIFO、原图/结果顺序、左右隐藏模式仍完整消费 tokens。
- 截短一帧后只累计一次欠载，余下图像全部粉色，刷新恢复；空前台黑屏不累计欠载。
- ACK 在窗口外到达时请求保持、配置不改，直到安全窗口接纳。
- OSD 标签、十进制 FPS、十六进制 frame ID、`BYPASS COPY` 字形取样。

以上测试验证 RTL 行为；Efinity布局布线状态以 `build/efinity_receipt.json` 为准。本机沙箱中的旧 MinGW Icarus 可能在生成 vvp 后异常退出；实际测试使用获准的本地进程运行，所有编译和仿真均严格检查返回值，未忽略异常退出。

## 实板观察与性能边界

第一轮 `style_video_camera_vs_high.bit` 用户反馈为左右画面只有上半部分、下半紫色抖动，CAP/COPY约13且FRAME递增，显示功能当时未通过。随后平台读burst由16拍改为128拍（写仍16），保留欠载后标粉、停止消费和安全刷新恢复逻辑，并增加y88的RAW/DROP/ERR/UF诊断。

当前 [style_video_display_burst128.bit](../build/style_video_display_burst128.bit) 获用户最新回复：“稳定，CAP/COPY FPS13，UF DROP一直是0。”本轮可记为用户确认短时显示功能通过；完整身份和硬件记录见 [display_fix_receipt.json](../build/display_fix_receipt.json)。观察任务要求约10秒，用户未精确计时。最新RAW传感器帧率、ERR和FRAME值未报告，不能填0；D2可能保留初始化过渡帧的累计错误，不要求它必灭。

这次视觉确认不代表长期稳定性或DDR实测吞吐/电气签核。完整尺寸首R96周期/读128拍的3帧输入、5次HDMI扫描压力已检查3,072,000像素且UF/drop/error0；但模型仍是可背压的适配器输入与预设AXI延迟，`hardware_bandwidth_verified=false` 保持正确。另一个持续密集COPY无限请求模型平均56.728M像素/秒，低于图像区双图显示所需57.6M，仍是带宽边界失败。当前实板COPY13fps未满足30fps采集目标；CNN尚未接入，神经推理>15fps尚未验证。
