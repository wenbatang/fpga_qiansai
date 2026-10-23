# CAM1实板记录与细分错误追踪

> 后续CAM2已确认SoT为唯一增长原因、首错22000400；当前优先测试[有边界SoT恢复版](sot_recovery.md)，本页保留原诊断与日志分析。

2026-10-23。用户给出两条CAM1记录，第二条被串口助手分成50+65字节。拼接后两条均为合法115字节记录；显示分段不等于数据损坏。原始记录与解析结果留在 `build/board_log_20261023/`。

## 已确认与尚未确认

| 字段 | 相邻记录变化 | 结论 |
| --- | --- | --- |
| B / flags | 3 / 0x34B9 | DDR已报校准，CPU完成模式配置并发出开流；模组复位已释放、CAP与权重有效。没有UI/CPU复位或PPI FIFO溢出保持。 |
| 好行L | +32400 | 恰好1080×30；大量RAW10行通过了CRC与打包长度检查。 |
| RAW组 | +15552063 | 接近1920×1080÷4×30，多63反映快照位于不同行内位置。不是没有MIPI图像数据。 |
| VS起点 | +30 | 解析器持续识别帧起点。 |
| DDR捕获错误 | +30 | 各帧被写帧器中止或拒绝。 |
| DDR完整帧C / 推理I | 始终0 / 0 | 首张完整原画未发布，CNN还没有可完成的输入帧。 |
| E | +2552 | 接收错误计数持续增长；**不是已经确定2552个独立坏包**，原逻辑对持续control_error每拍计数。 |
| 最后包头 | 0x1D09602B | VC0、RAW10、WC2400，符合1920像素行；只代表最后一项，不证明所有短包/附加包都正确。 |

硬件按100MHz的100M周期尝试每秒一报。以上是两个诊断周期的增量，不能替代完整DDR采集FPS或端到端风格化FPS验收。两个采样的packet_error均为1，但现有E没有来源细分，尚不能唯一判断是LP控制状态、SoT、格式、CRC或帧尾出错，也不能完全排除捕获FIFO/AXI/EOF计数的问题。

发现旧真实D-PHY联合仿真的覆盖缺口：虽使用真实TX/RX和FIFO，但把桥的 `control_error`、`ppi_sot_error`接为0。现已新建独立测试，把真实RxErrControl、RxErrEsc、RxErrSotSyncHS全部接回，与旧接0实例逐帧、逐RAW组对照。合法流测试用于补齐覆盖，不能据其通过就否认实板错误。

本轮真实接线测试三组小尺寸得到50、50、29好帧，与接0实例的帧数和逐组RAW一致；连续时钟用例保留一张启动半帧。完整1920×1080输入，两实例均3张完整640×480好帧、0坏帧，另有第四张部分数据。Control/Escape均未触发，仅LP停振启动时见一次SoT错误，不影响后续帧。没有复现实板持续丢帧。测试外壳继承36条位宽/空端口提示，无Fatal，不称零警告。

模型可追溯到生产D-PHY的同一次生成：生产vendor与 `style_video/build/dphy_bridge/ip/camera_dphy/camera_dphy.sv` 同字节，本次ModelSim文件与其Testbench/modelsim文件同字节，四份文件的第一个完整公开模块及参数相同。IP5.8/2026.1.132、70MHz byte/100MHz control、四lane/Discontinuous、LPX50/CLK_TERM38/D_TERM35/HS_SETTLE85/HS_PREPARE_ZERO145保持。模型与生产整份受保护实现并非同字节，不据此保证硅片模拟行为。

官方指南说明RxErrControl/RxErrEsc属于LP控制/逃逸事务错误，并可保持至下一次事务；它们不能直接解释为每拍一个RAW坏包。[Efinix D-PHY RX指南v2.0，第8页](https://www.efinixinc.com/docs/mipi-dphy-rx-core-ug-v2.0.pdf)。实际错误归属仍需分项与发生位置；本次**不放宽原坏帧、CRC/ECC、尺寸或完整帧检查**。

## 新的细分诊断版本

独立候选 `build/camera_packet_trace60/`，保留原CAM1诊断版及全部工程。24个32位字段在同一UI时钟一次锁存，通过既有板载UART输出：`@CAM2,`、24个8位十六进制字段、逗号分隔、CRLF，共223字节，115200/8N1。传输中不替换快照，无新增跨域数据。

状态：**独立全CAD、电气与原生CDC签核通过，signoff.json为PASS。**

- [CAM2细分诊断bit](../build/camera_packet_trace60/outflow/ti60_camera.bit) · [工程](../build/camera_packet_trace60/ti60_camera.xml) · [签核](../build/camera_packet_trace60/signoff.json) · [最终复核](../build/camera_packet_trace60/final_review.json)
- RAM248/256、DSP148/160、XLR42437/60800；最小setup **+0.403ns**、hold **+0.026ns**。
- 8条D-PHY首级均唯一接二级、无组合逻辑，最终级间最小setup **+13.248ns**。17标量首级、136 Gray最大延迟、14 FPS束和8个D-PHY精确首级例外保持，不整组切异步时钟。
- 实际79脚/12Bank、整份peri与原诊断版一致；CPU固件/BootRAM/模型/摄像头配置/DDR/HDMI保持。12个复位同步FF原生属性、SDC异地重建及十一套旧发布指纹复核通过。
- bit SHA256：`63e250e5d74dc78610ad521c623ccc4b0820ff3381cf316debebdab5dd547b81`。

新增桥18用例、68断言、30807个UI周期逐拍等价，移除观察块后原解析RTL完全一致；真实115200串行223字节/原子快照/复位重同步和PC假串口9项通过。实际顶层开漏、ACK、三PLL失锁、校准失效、停钟与按键保护通过。上述数字模型/CAD结果不能替代实板错误来源；本轮未打开串口、未JTAG下载或写Flash。

前12字段与CAM1完全相同：`boot,flags,good_lines,error_packets,ppi_ui_events,last_header,capture_frames,inference_frames,capture_errors,raw_groups,vs_edges,engine_cycles`。

追加12字段依次为：

| 字段 | 含义 |
| --- | --- |
| control_cycles | LP控制/逃逸合并错误为高的UI周期数，可能跨多个周期 |
| control_rises | 上述合并信号0→1次数；不是每个lane独立事务数 |
| sot_records | 原子FIFO里带SoT同步错误的记录数 |
| lane_overflows | 分lane暂存空间溢出的周期数 |
| header_errors | 原解析分支实际处理的header ECC/VC错误 |
| format_errors | 原解析分支拒绝的RAW尺寸/帧状态或不支持的数据类型 |
| crc_errors | 原CRC或RAW打包长度失败次数 |
| packet_interrupts | header/payload/CRC未结束即遇新SoT |
| fe_errors | 帧尾到来时VS/行数不符 |
| timeout_errors | 等不到完整帧尾的超时 |
| fs_overlaps | 旧帧仍有效时又出现新FS |
| first_error_context | 每次bad从0变1时锁存该帧首次故障位置，保留到下次首次故障或UI复位 |

前三类来源计数按各自输入状态记录，其余按原解析优先级计数，不把被高优先级遮住的分支算作实际执行。计数可能同拍同时增长，不能把分项之和强当E。首故障上下文：[31:28]原因、[27:26]状态、[25]VS、[24]HS、[23:8]行数、[7:4]RAW暂存字节、[3:0]sync_seen。原因1控制、2SoT、3lane、4传输溢出、5包头、6格式、7CRC、8包中断、9帧尾、10超时、11重复部分SoT、12帧起点重叠。

## 如何测试

Programmer用JTAG临时下载上方CAM2 bit。板载USB串口设置115200/8N1，关闭其他占用该端口的GUI；每秒输出一条CAM2记录。记录连续2–3条，尤其追加12字段与首故障上下文；串口助手拆成多段也可重新拼接。CAM1工具不解析CAM2，新工具只读、不发命令，Ctrl+C停止：

```powershell
python F:/fpga_qiansai/elinx/projects/camera_art_styles/pc/camera_trace.py --list
python F:/fpga_qiansai/elinx/projects/camera_art_styles/pc/camera_trace.py --port COM31 --log F:/fpga_qiansai/elinx/projects/camera_art_styles/build/camera_trace.jsonl
```

COM31仅为示例，以板载实际串口为准。现有CAM1 bit仍可下载，但只有旧12字段，不能定位细分原因。本地复核入口 `scripts/packet_trace/build.py audit`；重新构建需新目录并按prepare→相关仿真→compile执行，不能覆盖当前发布或运行中改源。

摄像头配置、CPU固件、四模型、DDR、720p60、79脚和全部Bank电压保持。沿用已确认的J4和J2/J3 2–3，不改变电平或供电，不带电插拔。此版本用来取得错误来源，不宣称无图故障已经修复，也不改变现有推理性能边界。
