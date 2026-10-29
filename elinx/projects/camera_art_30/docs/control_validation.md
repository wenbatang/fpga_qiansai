# 四风格、三输出缓冲控制与验证

本文件记录 `camera_art_30` 的控制面和缓冲管理。它们来自已经验证的 RF33 控制实现，计算部分改用本工程的 TinyStyle C8。原 `style_model/elinx` 和 `camera_art_styles` 保持不变。本文件中的 PASS 是数字仿真结果，不代表摄像头、DDR、HDMI 的实板并发帧率或模拟电气测试。

## 参数和按键

本工程保留 6 位风格编号接口，实际允许 0–3，依次为梵高、剪纸、漫画、水墨；参数来源是 47 风格模型中的 0、3、4、5。非法软件请求、非法键事件回退 0。四套参数各占 1216 字节，包括对齐填充，共 4864 字节；为减少构建入口变化，初始化文件仍名为 `weights47.mem`。APB ROM 窗口已缩至 `0x1000..0x22ff`，不是仍然保留 47 套参数。

CPU 每次按十层顺序执行 346 次参数写事务，APB 检查层、权重/偏置/移位类型、下标、偏置 24 位符号扩展及移位范围。全部事务经过 CNN 时钟邮箱 ACK 之后，才允许发布 `weights_valid/loaded_style`。忙时禁止更改当前参数身份；键请求只覆盖待执行风格。真实 C 固件仍由 Sapphire 运行，32KB 启动 RAM 的四条初始化通道必须保持一致。

四个单键直接选择四种风格。启动显示原图，KEY1+KEY2 按住约 0.5 秒返回原图；KEY0+KEY3 的原有整机逻辑复位继续由顶层处理。按键采用两级同步、10ms 消抖、释放后重新使能，持续按住不会重复提交风格。此版本没有接入手势识别，也没有新增三种显示界面。

## 三输出 bank 的所有权

三个原图 bank 仍为 `0x00400000 / 0x00600000 / 0x00800000`，分别由采集、最新完整帧和当前推理管理。三个风格输出 bank 是 `0x00000000 / 0x00200000 / 0x00a00000`；其中第三输出 bank 避开三个原图地址。

`video_job_control` 分开管理正在计算的 `output_bank`、完成队列头 `commit_bank`、可选队列尾以及已被显示器持有的 front。启动任务先锁住原图，CNN/DMA 返回完成或错误才释放原图。`engine_done` 的契约是全部条带、全部输出像素和最终真实 AXI B 响应均成功；不能用 CNN 算完提前冒充 DDR 写完。

计算完成产生 CPU 完成中断，同时将完成帧放入有序队列。队列未满且存在空闲输出 bank 时，CPU 可以启动下一帧，无需等前一帧垂直消隐提交。完成队列最多两项，满时背压；没有将占用中的显示 bank 当作空闲 bank。

`frame_reader` 只有在安全消隐窗口且旧读突发已经排空时，才能选择新 front。随后复位像素 FIFO，并等待写侧和同步后的读侧 reset-busy 都解除；完成这些步骤后才返回 `commit_ack`。调度器仅依靠该 ACK 释放旧 front，不能因 `reader.front_bank` 已提前改变就回收旧 bank。刷新错过安全窗口时等待下一次消隐。非法输出 bank ID 3 不被读控制器接受。

原图/风格标记 `front_raw` 随 `commit_ack` 更新，不能随计算完成更新。FPS 的 I 计数仍只统计真正的神经网络完成，原图拷贝和 HDMI 重复刷新不会增加 I。

## AXI 写入和像素 FIFO

`axi_write_pair` 保留每个主机最多一笔在途，采集与 CNN 合计最多两笔。前一笔 AW 和 W 都被接受后，可发另一个主机的 AW/W，而不必等前一笔 B；两项 owner FIFO 按相同 AXI ID 的顺序分发真实 B 响应。错误响应照原样返回，不生成提前 ACK。每个生产者自身仍等待它的 B 才复用该生产者的数据。

`pixel_fifo_720` 使用真实厂商异步非对称 FIFO，512 个 128 位写字，读侧每拍一个 RGB565 像素。128 位字内像素次序显式翻转以匹配厂商 FIFO 的高位优先读出；公共 11 位计数由真实 10 位存储计数补零。复位在两个时钟域同步释放，读侧 busy 同步回 UI 域。新增的精确 CDC 约束必须与实际综合网表端点核对，不能用整组异步时钟切断替代。

## 已完成的独立回归

| 入口和回执 | 本轮结果 | 实际范围 |
|---|---|---|
| `sim/check_control.py`；`sim/control/verification.json` | PASS | 四模式、1216 ROM 字读回、1384 次合法参数事务；错序/半载入提交/忙中重载拒绝；拒绝超 24 位符号扩展的 `0x00800000`、`0xff7fffff` 偏置；非法风格及 ROM 窗口越界。没有在该测试中执行 CPU 或 CNN。 |
| `sim/check_keys.py`；`sim/keys/verification.json` | PASS | 四单键、抖动、持键去重、启动/复位时持键不误触发、KEY1+KEY2 原图组合。测试缩短消抖和长按常数，不是实物按键测量。 |
| `sim/check_fps_jobs.py`；`sim/fps_jobs/verification.json` | PASS | 6262 周期、50096 检查；252 次完成、19 次计算错误、251 次显示 ACK、10 次完成与 ACK 同拍、145 次队尾入队和 9 次复位。用独立三槽模型核对所有权；计算完成和最终 B 是模型令牌。 |
| `sim/fps_reader/check_reader.py`；`sim/fps_reader/verification.json` | PASS | 实际 reader、厂商 FIFO 和标准 720p60 raster。正常用例逐像素检查 3686400 像素、3 次提交、0 欠载；故意跨消隐长期阻塞旧 R 的用例排空 16 拍旧数据，记录 2 次预期欠载，随后完整 921600 像素恢复。没有把故障注入的欠载写成正常链路无欠载。 |
| `sim/check_fps_write_pressure2.py --unit`；`sim/fps_write_pressure2/unit.json` | PASS | 80000 周期、2328 笔写事务、743 次注入 SLVERR/DECERR、1689 拍 B 背压；AW 先到 546 次、W 先到 595 次；最大在途 2，覆盖部分发送/两笔在途时复位。DDR 从机是可控流水模型。 |
| `sim/check_sapphire.py`；`sim/sapphire/verification.json` | PASS | 实际 Sapphire 3.4.0 RTL 执行本轮 3264 字节 C 固件；真实 APB 参数 ROM，0→3 风格切换、692 次参数事务、变延迟邮箱 ACK、摄像头 I²C/ID/曝光配置、两次 START 与 PLIC IRQ/W1C。摄像头寄存器和 DMA 完成为模型，不是整机实板。 |
| `sim/check_top_safety.py`；`sim/top_safety/verification.json` | PASS | 实际新顶层、reset、boot，覆盖开漏四状态/从机 ACK、三 PLL 分别失锁、DDR 校准失效、时钟停振、按键复位。功能 IP 明确黑盒，不能据此保证物理供电、Flash 启动内容、排线和信号完整性。 |
| `sim/scheduling/check_scheduler.py`；`sim/scheduling/verification.json` | PASS | 实际三原图池、三输出调度、reader、厂商 FIFO、720p60 raster 联合；12 个不同源帧以 3333333/3333333/3333334 UI 周期发布，12 次完成和 12 次显示提交，0 跳帧，完成间隔 3333333–3333334 周期，约 30.000fps。完整检查 23 个显示帧、21196800 像素，0 欠载；7 次计算与待显示帧重叠、348 周期 reader 提前 front 而尚未 ACK。生产 I 计数 always 块原样提取并编译，首帧原画不计 I、其余 11 帧计 I；这不是完整 `video_system_720` 实例。 |

参数 ROM、真实 CPU 初始化四通道及源码指纹由各回执和 `build/720p/firmware_manifest.json` 记录。后续若修改这些源、重编固件或改变模型，应重新执行相关回归；不能只沿用旧 PASS。

联合调度测试中，加速器是本轮完整 CNN/DMA 仿真所得 **2818615 UI 周期**的固定耗时完成模型。源帧发布代表“完整源图验证和最终 B 已完成”的生产者契约；显示 DDR 数据是带帧编号的可控模型，未实例化真实摄像头写入、CNN、DDR 控制器或总线仲裁。该项测试证明真实缓冲/显示调度不会把模型中的 30Hz 新帧供给锁成 20Hz，不能据此宣称实板整机已经稳定 30fps。CPU 启动由极小开销轮询模型提供，真实 Sapphire 执行另见独立回归。

## 30fps 的证据边界

本控制改动消除计算后等待唯一输出 bank 垂直消隐的串行瓶颈，并为摄像头/CNN 写入各保留一笔在途。它不单独证明 30fps。实际 CNN 计算吞吐、完整 720p 四风格整数结果、同时运行摄像头写入与 HDMI 读出的 DDR 仲裁压力、综合布局布线和精确 CDC/STA 另行签核；最终仍需上板区分 C、I 与 H60。
