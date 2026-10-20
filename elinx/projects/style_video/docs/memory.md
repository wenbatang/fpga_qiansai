# DDR 访问模块与接口

三个手写 RTL 使用 SystemVerilog 2009 可综合子集，不包含 Vivado 原语，适合 Efinity 的 `sv_09` 源文件类型。`clk` 是 DDR AXI 用户时钟，`rst_n` 低有效并要求该时钟域同步释放。物理 DDR、校准、引脚、PLL 和 Interface Designer 设置由平台封装提供，以下模块不能代替 DDR PHY。

## DMA 共同端口

参数：`ADDR_WIDTH=32, DATA_WIDTH=128, ID_WIDTH=6, BURST_BEATS=16, AXI_ID=0, TIMEOUT_CYCLES=1000000`。Ti60 官方 DDR 接口 ID 宽度为 4 时应实例化 `ID_WIDTH=4`。数据字节数须为 2 的幂且不超过 4096；`ADDR_WIDTH>=12`；`1<=BURST_BEATS<=256`。

通用 DMA 默认仍为 16 拍。当前 `style_platform_core` 通过 `READ_BURST_BEATS=128` 将显示读、处理读实例配置为最多 128 拍；采集写、处理结果写仍为 16 拍。增加读突发用于摊薄 DDR 首拍延迟，端口、整突发校验、单 outstanding、错误排空和发布规则没有改变。128 拍为 2048 字节；碰到 4 KiB 边界或命令尾时会缩短。

| 端口 | 方向/位宽 | 约定 |
|---|---|---|
| `clk, rst_n` | 输入/1 | DDR 用户时钟与复位 |
| `cmd_valid, cmd_ready` | 输入、输出/1 | 同拍为 1 接受一条连续传输命令；处理为整帧，显示为半行 |
| `cmd_addr` | 输入/ADDR_WIDTH | DDR 起始字节地址，按 DATA_WIDTH/8 对齐 |
| `cmd_beats` | 输入/32 | 总数据拍数，非零；128 位默认每拍 16 字节 |
| `abort` | 输入/1 | 终止任务；已提供 AXI valid 的事务继续完成/排空 |
| `busy` | 输出/1 | 有命令正在执行或排空 |
| `done` | 输出/1 | 任务终结单周期脉冲，包括失败 |
| `error` | 输出/1 | 与失败 `done` 同拍；成功为零 |
| `error_code` | 输出/8 | 最后任务错误，接受新命令清零 |
| `sticky_fault` | 输出/1 | 无进展超时锁存；阻止新命令，复位清除 |

错误码：`01` 无效/未对齐命令，`02` abort，`03` last 长度不匹配，`04` AXI 非 OKAY 响应，`05` 返回 ID 不匹配，`06` 无进展超时。看门狗统计连续无握手周期，不是整帧最大耗时。超时不是取消 AXI 的办法：已拉高 AW/AR/WVALID 的通道仍保持，未结束响应仍排空；`sticky_fault` 后须协调 DDR 与互连复位，不能只复位 DMA 再复用仍有旧响应的总线。

## 写 DMA `style_axi_write_dma`

输入像素打包流：`s_data[DATA_WIDTH-1:0], s_valid, s_ready, s_last`。`s_last` 只在命令最后一拍为 1，不能标记每个 AXI 突发末拍；平台两路写命令均为完整图像帧。数据必须已包含布局规定的 padding。无字节尾掩码，本版本 `WSTRB` 全 1。

AXI master 精确端口：

```
m_axi_awid[ID_WIDTH-1:0], m_axi_awaddr[ADDR_WIDTH-1:0],
m_axi_awlen[7:0], m_axi_awsize[2:0], m_axi_awburst[1:0],
m_axi_awvalid, m_axi_awready,
m_axi_wdata[DATA_WIDTH-1:0], m_axi_wstrb[DATA_WIDTH/8-1:0],
m_axi_wlast, m_axi_wvalid, m_axi_wready,
m_axi_bid[ID_WIDTH-1:0], m_axi_bresp[1:0], m_axi_bvalid, m_axi_bready
```

状态：`IDLE → FILL → ISSUE → RESPONSE`。先收集一个小突发，AW 与 W 独立握手且在背压时保持；收到正确 BID、OKAY B 响应后才开始下个突发。短尾、4 KiB 边界自动拆分。最后 B 结束才成功 `done`，上层只能据此发布完整帧。流 last 错误、B 错误或中止的帧可能已经部分写入，必须丢弃并保留原前台。

## 读 DMA `style_axi_read_dma`

输出打包流：`m_data[DATA_WIDTH-1:0], m_valid, m_ready, m_last`，`m_last` 为命令结束；平台处理读为整帧，显示读为 640 像素半行。接收每个突发至完整 RLAST，校验所有 RID/RRESP/RLAST 后才输出整个突发，避免错误突发被写入显示 FIFO。先前已输出的正确突发不会回滚，上层须在失败时丢弃剩余帧并恢复显示状态。

AXI master 精确端口：

```
m_axi_arid[ID_WIDTH-1:0], m_axi_araddr[ADDR_WIDTH-1:0],
m_axi_arlen[7:0], m_axi_arsize[2:0], m_axi_arburst[1:0],
m_axi_arvalid, m_axi_arready,
m_axi_rid[ID_WIDTH-1:0], m_axi_rdata[DATA_WIDTH-1:0],
m_axi_rresp[1:0], m_axi_rlast, m_axi_rvalid, m_axi_rready
```

状态：`IDLE → ADDRESS → RECEIVE → OUTPUT`。异常或 abort 后仍接受 R 至实际 RLAST；缺失 RLAST 时不会提前重用通道。输出 valid 已提供而下游背压时保持到握手后再结束 abort，不突然撤销数据。

`RECEIVE` 与 `OUTPUT` 串行，当前实现没有双缓存重叠；只有本突发全部输出后才发下一个 AR。RGBX8888 每拍含 4 个像素，实际解包器连续输出一像素/核心周期，故一个 B 拍突发的输出阶段约需 `4B` 个周期。扩大突发减少了 AR 首拍延迟次数，但 COPY 读已获得总线后仍须到 RLAST 才让路显示，较长 COPY 突发可能增加短显示尾突发后的等待。

## 双客户端仲裁 `style_axi_arbiter`

参数：`ADDR_WIDTH=32, DATA_WIDTH=128, ID_WIDTH=6, READ_CLIENT1_LIMIT=4`。所有 `s_axi_*` 为两个客户端拼接的 packed vector，客户端 0 在最低位。

Slave 的 AW/AR：`id[2*ID_WIDTH-1:0], addr[2*ADDR_WIDTH-1:0], len[15:0], size[5:0], burst[3:0], valid[1:0], ready[1:0]`。

Slave W：`data[2*DATA_WIDTH-1:0], strb[2*(DATA_WIDTH/8)-1:0], last/valid/ready[1:0]`。

Slave B：`id[2*ID_WIDTH-1:0], resp[3:0], valid/ready[1:0]`。

Slave R：`id[2*ID_WIDTH-1:0], data[2*DATA_WIDTH-1:0], resp[3:0], last/valid/ready[1:0]`。

端口加前缀均为 `s_axi_awid` 等。Master `m_axi_*` 为上文写/读 DMA 合并后的标准单客户端接口。写方向在选择 AW 请求时锁定所有者，AW 与整段 W 完成且 B 握手后释放；读方向 AR 到实际 RLAST 锁定所有者。两个方向可并行，各一个 outstanding。ID 原样发送与返回，不增加宽度，不依据 ID 选择返回客户端。

写采用轮转公平仲裁；读 client 1 为显示端，连续最多 `READ_CLIENT1_LIMIT` 个显示突发后，如果 client 0 持续请求，则必须服务一次 client 0。启动请求在输出 valid 之前先寄存所有者，新的竞争请求不能改变被背压的地址与数据。

## Efinity 集成边界

DDR 校准成功、用户时钟与复位稳定后才能提交命令。外部客户端遵守 valid 在 ready 前保持数据的规则；两种 DMA 已遵守该规则。每拍是连续的 16 字节，不含像素格式语义；RGB565 8 像素/拍、RGB888 的跨拍打包由上层负责。地址区、帧槽所有权以及显示消隐切换由帧管理器负责。

实际带宽需 Efinity 布局布线与实板测速。正常读写吞吐还受完整突发收集/校验、B 响应、解包速度、单 outstanding 和共享物理 DDR 延迟影响；128 拍改动没有消除这些限制。

## 显示持续供数的压力边界

640×480 原图和结果拼为每行 1280 像素，在 720p60 时序中每整行耗时 `1650 / 74.25 MHz = 22.222 µs`。图像占用的 480 行期间，平均供数须达到 `57.6 Mpx/s`；每条 640 像素半行命令平均可用 `1111.111` 个 100 MHz 核心周期。不能用整帧平均 `36.864 Mpx/s` 替代此门槛，4096 像素显示 FIFO 装不下完整图像。

`sim/memory/tb_read_throughput.sv` 使用真实 DMA、仲裁器、RGBX 解包器和 960 条半行命令，覆盖 2560 字节行步长的全部跨页相位。设定 AR 至首 R 握手延迟为 48/96 周期，每 13 个 R 拍有一个空周期，AR 有确定性背压；连续 COPY 读使用解包器但没有写端停顿。所得供数均值如下，单位 Mpx/s：

| 读突发上限 | 首拍 48，独占 | 首拍 48，COPY 竞争 | 首拍 96，独占 | 首拍 96，COPY 竞争 |
|---|---:|---:|---:|---:|
| 16 | 50.235 | 48.120 | 36.523 | 27.989 |
| 64 | 67.258 | 66.554 | 58.483 | 51.016 |
| 128 | 70.692 | 65.260 | 63.936 | 56.728 |

128 拍在 48 周期模型的竞争条件下越过均值门槛，但这不能代替端到端 FIFO 欠载检查；半行的瞬时最大耗时仍可超过平均预算。96 周期加连续 COPY 的 128 拍均值 `56.728` 低于门槛，不能宣称此压力条件连续显示通过。增大 FIFO 只能延缓持续不足引发的欠载；若实板延迟达到该条件，可进一步缩短处理读独占时间，或用经过整突发校验的双读缓存重叠接收与输出。

上述是指定延迟的行为模型：未模拟 DDR 写争用、DRAM 刷新/行与银行冲突，COPY 又省去了结果写停顿，因此既不能当作真实 PHY 的上限，也不能单凭此表判定实板必然欠载。端到端压力证据应查当前 RTL 对应的 `sim/performance` 结果；早期 6 周期首 R 的正常路径 PASS 不能覆盖 48/96 周期压力。

## 已运行的模块仿真

运行 `D:\python3.11\python.exe sim/memory/run.py`（可通过 `--iverilog`、`--vvp` 指定工具）。2026-10-14 使用 Icarus 的 `-g2009`，16/64/128 DMA 和仲裁分别以 `20261014 / 51 / 11993` 三个种子独立运行，另有 12 项上述吞吐模型，共 24 项协议/数据检查全部 PASS；各压力的带宽门槛另存为 `performance_target_met`，不能将协议 PASS 解释成带宽通过。新编译产物、日志和含 RTL/bench SHA256 的机器可读结果在 `build/memory/receipt.json`。脚本先删旧 vvp，编译/运行返回码必须为 0，且必须出现对应 PASS 标记。

- DMA：分别跨 4 KiB 拆为 `1+16+3`、`1+64+3`、`1+128+3`；AW、W 独立及 R、输出随机背压；命令 last、BRESP、BID、RID、RRESP、提前/延迟 RLAST 错误；错误突发零输出；非法地址/零长度；写缓存中止、已拉 AWVALID 后中止、读 AR/R/输出阶段中止；AW/W/收集输入/AR/缺失 RLAST 超时；超时不提前释放 AXI，恢复响应后仍需复位。已发行中止、B/R 响应错误和事务超时也分别覆盖整段 16/64/128 拍。
- 仲裁：两个写端与两个读端竞争，总共 20 个写突发、20 个读突发；读写同时在途；背压时 AW/AR/W 保持；返回 ID 和错误响应原样路由；显示最多连续 4 个突发后让路 CNN。
- 吞吐：三档突发 × 两档首拍延迟 × 独占/连续 COPY 竞争，逐个像素校验原图/结果半行地址顺序及命令 last，检查返回所有者、4 KiB 边界、fault 为零，报告总周期、平均/最大半行周期及读仲裁等待。

仿真模型不包含物理 DDR 校准、易灵思加密 IP、电气接口和实现后的时序；上述 PASS 不代表综合、实板带宽或真实摄像头已经验证。
