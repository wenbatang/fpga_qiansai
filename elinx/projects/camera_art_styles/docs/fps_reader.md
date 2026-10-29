# 三输出缓冲的显示reader（独立FPS候选）

本说明只覆盖 `rtl/fps/frame_reader_fps.sv` 和 `rtl/fps/pixel_fifo_fps.sv`。它们是供新RF33整机集成的独立变体，不改已签核的 `rtl/frame_reader.sv`、`rtl/p720/pixel_fifo_720.sv` 或原工程XML。手势与原图/对比分屏没有在这两个模块中接入。

## 地址与接口

`frame_reader_fps` 保留原reader的端口名称，仅把 `commit_bank` 和 `front_bank` 扩为2位；新增可覆写参数 `THIRD_BANK_BASE`。

| 编号 | 基址 | 说明 |
| --- | --- | --- |
| 0 | `0x00000000` | 原输出0 |
| 1 | `0x00200000` | `BANK_STRIDE`，原输出1 |
| 2 | `0x00A00000` | `THIRD_BANK_BASE`，新输出2 |
| 3 | 不合法 | 不ACK，不更新前台，继续重复显示旧前台 |

三个原画槽保持4/6/8MiB，不把第三输出放在这些源图地址上。720p RGB565每帧 `0x001C2000` 字节，仍小于每槽2MiB。

`WIDTH/HEIGHT` 默认1280/720，`FIFO_WORDS` 默认512；`BANK_STRIDE` 默认2MiB，新增 `THIRD_BANK_BASE` 默认10MiB。AXI仍16拍×128位固定读突发，256字节对齐。`araddr` 根据已锁存的前台基址加帧偏移生成，不随在途 `commit_bank` 改变。

提交方必须让 `commit_valid/commit_bank/commit_frame` 保持到 `commit_ack`。编号3没有错误完成端口，只通过不ACK拒绝；正常作业分配器必须保证永不产生3。

## 提交与旧前台释放

1. 消隐请求到来时，reader停止发新的帧读请求；已有ADDRESS必须等待AR握手，已有DATA必须继续收至实际RLAST。
2. 存在未处理消隐请求时，旧R数据继续接收排空，但不写像素FIFO。原RRESP/RLAST校验仍保留。
3. 只有进入RUN（没有在途AR/R）且同步后的受保护消隐窗口仍有效，才锁存新 `front_bank/front_frame`。
4. 对像素FIFO断言公共异步复位至少16个UI周期，复位释放后等待 `fifo_wr_busy` 和同步后的 `fifo_rd_busy` 均清零。
5. 若等待busy退出期间错过消隐窗口，继续等待下一次受保护窗口。
6. 最后同时更新 `refresh_ack` 并发出一次 `commit_ack`。这时才允许作业控制器释放旧输出前台。

`front_bank` **可能早于ACK改变**，用于锁存下一前台，但不是释放旧bank的许可。新 `video_job_control_fps` 应独立记住自己拥有的旧前台，等ACK才转移所有权。仅根据 `reader.front_bank` 的提前变化选择写目标会重新引入覆盖正在读取帧的风险。

`fifo_rd_busy` 在新整机中应接实际像素域的忙信号，而不是旧系统中的常量0；reader内部已有两级同步。`fifo_wr_busy` 使用FIFO包装器的UI域输出。像素域仍按原请求/ACK与FWFT消费，不增加新多位跨域载荷。

## FIFO计数宽度的独立修正

原厂FIFO在DEPTH512时 `wr_datacount_o` 是10位，公共包装器接口为11位。旧 `pixel_fifo_720` 将两者直接连接；Icarus通常自动补0，而本次Questa10.7c严格输出连接留下一个Z高位，导致reader水位比较成为未知值、无法预取。

新 `pixel_fifo_fps` 只增加10位内部 `storage_word_count`，再显式：

```verilog
assign wr_data_count = {1'b0, storage_word_count};
```

除模块名和该连接外，与p720包装器相同。128→16位FWFT、512写字深度、SYNC_STAGE2、8:1编码、字节/像素顺序、`wr_reset/rd_reset[7:0]`、`rd_busy_sync[1:0]`、`storage`实例及全部原厂参数不变。

这修正了新候选的仿真/接口歧义，不能据此断言旧已实现bit在实物上必定有浮空计数。原p720文件与签核继续保留，不被悄悄改写。

## 已运行的联合回归

入口 `sim/fps_reader/check_reader.py`，Questa10.7c；使用实际新reader、实际新FIFO包装器、未改原厂FIFO RTL、未改720p60扫描器。像素时钟名义74.25MHz，UI100MHz，AXI从机为有界合成服务，不是DDR控制器模型。

| 用例 | 结果 |
| --- | --- |
| 0→1→2三个DDR输出 | 三次提交依次使用0/2/10MiB；请求在有效区排队，下次受保护消隐才生效 |
| 四个完整扫描帧 | 3,686,400个RGB565/FWFT/RGB逐值一致，28,800个读突发、460,800拍，零欠载/读错 |
| 非法编号3 | 保持请求跨下一次刷新，拒绝ACK，前台保持bank2，第四帧继续逐值一致 |
| 旧R长时间阻塞 | 在旧帧有效区阻塞一条读突发，跨越下一次完整消隐，在v30才恢复，已错过v24关闭的窗口 |
| 旧R排空 | 16个旧数据拍全部收至RLAST且不写新FIFO；未提前换bank/ACK |
| 延迟提交与恢复 | 再下一帧受保护消隐才ACK bank2，排空及两域busy退出后释放；921,600个恢复帧像素逐值一致 |
| 长阻塞导致的欠载 | 两个坏显示帧被明确计为欠载，不把这种超出服务预算的情况报成零欠载 |

所有完整帧还检查1650×750总周期、40像素HS、5行VS、1280×720 DE、空白为黑、RGB565展开与坐标对齐。所有commit ACK检查无在途读、FIFO reset已至少16周期、两busy都为0、FIFO空且仍在受保护窗口。AR与合成R从机背压时稳定。

回执 `sim/fps_reader/verification.json` 绑定源和日志SHA256。两次测试0 Error；原厂FIFO模型6条缺省未连接端口告警保留，不写成零告警。没有真实CPU、摄像头、DDR仲裁/校准、CNN并发、HDMI编码/串化或实屏验证。

## 真实60Hz显示下的三槽调度联合模型

新增入口 `sim/fps_scheduler/check_scheduler.py`，联合实际 `video_job_control_fps`、本reader、FIFO包装器、原厂FIFO RTL和标准720p60扫描器。此处没有把显示ACK手工定时伪造：ACK实际经过消隐请求、AXI读排空、FIFO复位与busy等待。

CPU被明确建模为“busy低就START”，源claim ACK延迟2–8拍；引擎被明确建模为每次6,007,407个UI周期后完成，这是此前完整RF33 CNN/DMA单帧测试的测量值，**此联合模型本身没有执行CNN或真实CPU**。DDR从机按有界服务返回该bank最近完整作业的frame_id常量标签，不是实际风格像素。

| 测量 | 结果 |
| --- | --- |
| 启动/完成/真实显示ACK | 各6次，bank依次0/1/2/0/1/2，没有重复/乱序 |
| 相邻完成间隔 | 6,007,412–6,007,418 UI周期；5段全部断言小于6,100,000周期 |
| 单次额外调度成本 | 相对引擎模型多5–11拍，不再锁到四个60Hz帧的约66.67ms |
| 首末完成之间模型吞吐 | 16.646094fps，排除首次启动和最后等待显示的收尾 |
| 完整显示逐值比较 | 19帧，17,510,400个像素，按该显示帧对应的bank/frame_id全部一致 |
| DDR模型读突发 | 136,800次 |
| 计算与待显示重叠 | 5次新计算在前结果尚待显示ACK时开始 |
| 提前改变reader前台 | 174拍；旧front仍由作业调度器保留，没有当作空槽写入 |
| 欠载/错误/重复ACK | 均0；原厂FIFO模型6条缺省连接告警保留 |

每个UI周期用独立三槽引用/有序队列参考检查引擎目标不覆盖FRONT/READY、提交payload稳定、完成后才能显示及最终全部引用排空。每个有效扫描像素都检查FIFO值和RGB565展开。

正常60.07407ms引擎比60Hz刷新慢，因此本用例没有把第二个READY尾槽填满（queued_tail=0）；尾队列与同拍done/ACK冲突仍以 `sim/fps_jobs/` 的独立单位测试覆盖，不能把本用例写成尾队列已受压。回执为 `sim/fps_scheduler/verification.json`。

16.646094fps只证明新调度没有把**该固定延迟模型**额外量化到四帧，不代表实际摄像头、CNN、DDR控制器与仲裁、RISC-V、HDMI串化并发的整机或实板FPS。后者仍需真实联合压力、CAD与上板计数验证。

## CDC与整机签核注意

FIFO内部Gray指针的参数和层级未变，因此相对p720的166条Gray最大延迟路径预计保持。这个预期不能替代新综合后的真实计数与连线核对。

新reader实际连接 `fifo_rd_busy` 后，`system/reader/rd_busy_sync[0]` 成为像素→UI首级；旧p720约束没有将其列入标量首级白名单，因为旧系统把该输入接0。若新map保留该链，需独立核对唯一第二级后继并加入精确首级约束，标量数可能从23增加到24。若工具与其它busy同步器合并，应按实际网表证明，不能简单改固定数字或切断整组异步时钟。

本子任务没有运行综合、布局布线或原生STA，也没有生成/下载bit。新整机必须完成三bank所有权联合、轻模型数值映射、365项固件、实时并发、精确CDC、电气及最终时序签核后才能交付。
