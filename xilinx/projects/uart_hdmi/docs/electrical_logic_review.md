# 引脚、电平与逻辑复核

后续新增2Mbps / 16KB RGB565提速配置，独立输出到`vivado_fast`；本文件早先标准版记录保留为历史基线。提速版再次核对84个引脚、方向、电平与时钟通过，1.8V/NORMAL辅助电压和DDR3-800配置不变，未烧写实板。提速版当前指纹及测试见[提速记录](transfer_speed.md)，旧标准构建指纹不再用于断言当前已参数化的源码相同。

2026-10-09，用户确认板卡为「Kindex Base7 FMC版」，器件 `xc7k325tffg676-2`。依据本地 `xilinx/xc7k325tffg_base/资料/Kintex7_BaseC_FMC原理图.pdf` 第2、4、5、6、7页，逐项对照 Vivado 布线后的84个顶层端口。本次没有下载到板卡，也没有写入配置 Flash。

## 已修正的电气问题

参考 MIG 的 `VccAuxIO=2.0V` / `VCCAUX_IO=HIGH` 与原理图不符：第2页的 P8、R9、T8（VCCAUX_IO_G0）接在 `VCC_1V8`。这不是由 RTL 给板卡设定供电电压，而是接口配置和时序模型应当匹配实际电源。独立项目已经改为 **1.8V / NORMAL**，通过 IP 参数重新生成，没有修改原厂生成 RTL。

[AMD DS182 v2.19](https://docs.amd.com/v/u/en-US/ds182_Kintex_7_Data_Sheet) 第15页表18规定：FF封装、−2速度等级、HP Bank、1.8V VCCAUX_IO 的4:1 DDR3接口上限为1333Mb/s。原来的1600Mb/s也不符合这个供电条件。当前使用 **DDR3-800（DDR时钟400MHz、UI时钟100MHz）**，CL6、CWL5，外部VREF保持启用；保留 MT41K256M16、32bit总位宽、AXI128bit数据接口和原理图对应的内存引脚。

MIG 系统输入与 IDELAY 参考仍为200MHz。生成的PLL参数为输入周期5000ps、倍频4、DDR输出除2、UI输出除8、内存周期2500ps。视频 MMCM 改为100MHz输入，`100 × 37.125 ÷ 5 = 742.5MHz`，输出74.25MHz和371.25MHz。UART显式采用100MHz分频，半包超时100,000,000周期、会话超时500,000,000周期，仍分别为1秒和5秒。

**此前使用2.0V/HIGH或DDR3-1600的bitstream不再作为本板的有效版本。应使用最终重建产物及其构建记录中的SHA256。**

## 引脚与电压

| 功能 | 封装引脚 | Bank / 电源 | 配置与方向 |
|---|---|---|---|
| 50MHz时钟 | G22 | 14 / 3.3V | LVCMOS33，输入 |
| KEY1低有效复位 | D26 | 14 / 3.3V | LVCMOS33，输入 |
| UART RX | B20 | 14 / 3.3V | LVCMOS33，CH340E TXD → FPGA |
| UART TX | C22 | 14 / 3.3V | LVCMOS33，FPGA → CH340E RXD |
| HDMI1电源使能 | E22 | 14 / 3.3V | LVCMOS33，输出；驱动板上Q1/U12电源开关 |
| HDMI1时钟 P/N | F17 / E17 | 15 / 3.3V | TMDS_33差分输出 |
| HDMI1数据0 P/N | J15 / J16 | 15 / 3.3V | TMDS_33差分输出 |
| HDMI1数据1 P/N | E15 / E16 | 15 / 3.3V | TMDS_33差分输出 |
| HDMI1数据2 P/N | G17 / F18 | 15 / 3.3V | TMDS_33差分输出 |
| DDR DQ、DQS、DM | 44个引脚，详见导出表 | 32 / 1.5V | DQ/DQS双向，DCI；DM输出 |
| DDR地址、BA、控制、时钟 | 27个引脚，详见导出表 | 33 / 1.5V | SSTL15、DIFF_SSTL15；reset为LVCMOS15 |
| DDR辅助电源 | P8 / R9 / T8 | VCCAUX_IO_G0 / 1.8V | 全部DDR端口VCCAUX_IO=NORMAL |
| 配置Bank | CFGBVS P7、Bank0 | 3.3V | CFGBVS=VCCO，CONFIG_VOLTAGE=3.3 |

第6页的CH340E VCC和V3均接3.3V，经39Ω电阻接串口信号，收发方向已经核实。传图使用 **P2 UART Type-C**；P1为FT232HQ JTAG，不是此协议的串口。

第7页HDMI1对应J5；TMDS线连接在3.3V域，51Ω电阻接3.3V。E22只输出3.3V控制信号，由Q1/U12切换HDMI连接器的5V供电，不能将E22当作5V GPIO。当前未使用HPD或DDC/EDID，固定输出720p60，屏幕需支持该模式。

DDR VCCO=1.5V与VCCAUX_IO=1.8V是两个不同的供电。VREF由板上DDR3_VREF供给，MIG `InternalVref=0`。FMC可调VCC_ADJ属于Bank12/13，本工程没有在这些Bank放置输出。

完整实现引脚表为 `vivado/pin_audit.tsv`，包含端口、封装引脚、Bank、方向、电平标准和辅助电压属性。`scripts/check_board.py`保存从已阅览原理图核对得到的84个端口映射；构建结束自动检查端口全集、无引脚冲突、DDR参数与配置Bank电压。这里核对的是设计配置与原理图，不是测量实板电源或信号波形。

## 已修正的逻辑边界

`packet_rx`原来只在已经解码至少一个字节时计时。如果仅收到`7E 7D`然后断流，转义标志会一直保留。现在转义等待也计入1秒半包超时；若转义后直接遇到分隔符，则报告坏包并恢复分包状态。新增测试验证这两种恢复方式，以及空分隔符不会反复超时。错误包仍不能写入DDR或发布。

工程脚本还修正了继续构建逻辑：已完成的run不重复launch；源文件变化导致NEEDS_REFRESH时重置对应run。避免在已有工程上继续构建时出现“run needs to be reset”。

### 第二轮复核：异常DDR响应与长背压

新增异常测试在上一版RTL上复现了两处问题，修复后同一测试通过，基线证据保存在`build/logs/recheck_baseline.log`。

- **延迟换帧越过消隐期**：原来只依赖帧开始的toggle请求。如果AR/R背压持续到有效显示区，请求仍待处理，排空旧读事务后就会交换前台。现在`video_720p`输出寄存的`refresh_window`，在有效显示前一整行关闭；在UI域以两级同步器接收。`frame_reader`只有在请求待处理且窗口开放时才切换前台、清FIFO。错过窗口就等待下一次窗口，不发起新的旧帧读取，也不撤销已握手或正在等待握手的AXI事务。该余量覆盖当前100MHz UI的同步延迟，避免窗口关闭传播延迟造成有效区换帧。
- **错误RLAST的数据拍进入FIFO**：原来先依据RRESP写FIFO，再在时钟沿检查RLAST是否与第16拍匹配，提前结束的一拍可能已经进入FIFO。现在FIFO写使能同时检查RRESP和RLAST；错误拍与随后处于故障状态的拍全部丢弃，仍排空已发出的事务，下一帧重新清理、恢复。

不改变板级引脚、I/O标准、DDR电压或时钟。增加的是内部单比特跨域窗口和读响应检查；其首级同步器单独约束，仍保留FIFO Gray指针时序及bus skew检查。

## 逻辑检查与仿真证据

- UART：8N1、起始位/停止位、输入同步、break与帧错误恢复；实际波特率仍需上板确认。
- 收帧：包CRC、整帧CRC、尺寸/格式/偏移、重复包、丢ACK重传、半包及会话超时、转义异常恢复。
- 写DDR：AW/W分别等待握手，背压时地址和数据保持；只有全部B响应OK才增加已确认偏移，错误响应不会发布；END必须等换帧ACK。
- 所有权：BEGIN选择非前台缓冲；半帧与错误帧不切前台；END重复包不重复发布。显示读事务排空后才释放旧前台供下一次写入。
- 读DDR：16拍、256字节突发，地址对齐且不跨4KB；FIFO预留突发空间；换帧先排空旧响应，在有提前关闭余量的窗口内切换，再清FIFO。
- 显示：1650×750总时序、1280×720有效区、正HS/VS、RGB565扩展与寄存延迟；欠载后本帧填洋红，下一帧恢复。
- 厂商模型：真实XPM FIFO的128→16bit小端FWFT顺序、复位丢弃旧像素、busy握手；真实MMCM输出74.25/371.25MHz；OSERDESE2十位串化、TMDS控制符及差分极性。
- 新增联合仿真：真实XPM和MMCM连接`frame_reader`与`video_720p`，DDR用可背压的AXI行为模型。连续两帧各921,600个像素逐一对照，第一帧显示中提交下一帧、仅在下一消隐期交换；零读错误、零显示欠载。该测试验证读出/跨域/显示集成，DDR物理接口与UART→写入链路另由模块仿真及后续上板验证覆盖。
- 异常回归：ARVALID保持及地址稳定、读事务越过窗口关闭、推迟到下一窗口发布；提前RLAST、缺失RLAST、SLVERR、错误拍禁止进入FIFO及下一帧恢复。
- 长停顿联合仿真：真实74.25MHz视频时序、XPM FIFO和窗口同步，第一帧末尾暂停DDR响应，直到第二帧有效区才解除。确认有效区不交换前台，明确计数两帧欠载、错误区域填洋红，第三帧在下一个窗口换图后输出全部921,600个正确像素。故障帧主动丢弃，不能将其表述为“故障注入时全程零欠载”。

入口：`sim/run_checks.py`、`sim/run_fault_checks.py`、`sim/run_vendor.py`、`sim/run_integration.py`（`--late`注入长停顿）。日志分别为`build/logs/module_tests.log`、`fault_tests.log`、`vendor_tests.log`、`integration_tests.log`、`integration_late_tests.log`。仿真与构建产物均位于项目内，并按既有规则忽略上传。

## 结果边界

### 最终复核（2026-10-09）

本轮没有发现新的实质缺陷，未修改可综合RTL、约束或IP参数，继续使用16:03生成的bitstream。新增`sim/run_final_checks.py`复跑原模块测试，并补充校准未完成时拒收、错误版本/宽高/格式/保留字节/长度、未知命令、错误帧号、提前END、零长度或非对齐DATA、超过剩余帧大小、1500字节超长包后的恢复、QUERY不改变会话、ABORT保留当前显示帧、两块缓冲的内容核对、复位后清除重复包历史及半包、AW/W背压稳定性。以上全部通过；单独验证复位异步置位、第三个时钟沿同步释放及短复位脉冲恢复。测试中的接收器、写入器与AXI行为模型一起复位；不据此宣称已经验证真实MIG的复位重校准。

再次运行长背压和RLAST/RRESP异常回归，全部通过。证据保存为`build/logs/final_checks.log`与`build/logs/final_fault_checks.log`，入口均在项目`sim/`中，Git实际匹配确认其保持本地忽略。

自动检查19份构建输入的SHA256均与构建凭据相同，实际器件/115200波特率设置一致，当前bitstream大小为11,443,722字节，SHA256为`F49F6537055ED83CFEDDDF5FB6E838071BD6918DAC87CC13F80EF33AAD1836F1`。84个布线端口、MIG电压/速率/时钟审计再次通过。实现报告WNS=+0.893ns、WHS=+0.026ns、WPWS=+0.143ns；建立/保持/脉宽失败端点均为0，无缺失时钟或未约束内部端点。DRC仍保留5项已记录的MIG警告；外部接口的2项输入和6项输出delay提示也保留，未用虚构板级延迟消除提示。此结论仅覆盖当前本地工程，仍未烧写实板。

最终bitstream、SHA256、时序与资源以[构建记录](build_validation.md)为准。MIG保留的BUFC-1、REQP-1709、CDC-8和SERDES复位提示逐项记录，没有删除原厂约束或降低严重级别。

最终实现还导出`vivado/clocks.tsv`，自动核对200MHz参考、400MHz DDR、100MHz UI、74.25/371.25MHz视频时钟；`vivado/build_settings.tsv`记录实际器件、工具和UART generic。`build/build_receipt.json`记录构建输入及bitstream的SHA256，并检查构建期间输入未变化，用于后续确认产物是否仍与本地源文件一致。

内部时序、引脚映射、I/O标准和仿真通过，不能替代实板DDR校准、HDMI信号质量、复位重锁和完整串口传图验证。AXI从设备若永久不返回响应，不能随意撤销已握手事务，需要系统复位；当前没有承诺从物理DDR故障自动恢复。确认本地原理图对应实板后，仍需要实际上板测试；此次未烧写。
