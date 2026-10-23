# 彩条停留：摄像头启动诊断

> CAM1实板记录已确认DDR报校准、CPU开流及大量RAW好行，所有完整帧仍被拒绝。下一步使用[CAM2细分追踪版](packet_trace.md)；本页保留原12字段启动诊断。

2026-10-23。用户实测摄像头720p60版持续一分钟显示彩条，左上角C00、I00、H60。此现象尚未定位到唯一根因。HDMI扫描不等待DDR校准，OSD复位默认开启，因此彩条和H60不能证明DDR校准、CPU启动或摄像头开流。

地址、I²C位序、复位极性、163项V7模式表已核对，未发现可确定的错误。固件任一步失败都会停止采集、复位模组并永久等待；原版没有UART日志，也没有显示APB中的boot_status，继续等待无法区分故障。独立诊断版保留原控制行为，通过已有板载UART TX只读报告状态。它用于定位，不能预先宣称解决了摄像头无图。

## 当前构建

独立目录为 `build/camera_debug60/`，工程 `ti60_camera.xml`、候选输出 `outflow/ti60_camera.bit`。**仅最终signoff.json为PASS且与当前文件指纹一致时才可使用。** 原 `camera_ppi60` bit和原全部工程保留。

状态：**已完成独立CAD、79脚/12Bank电气与原生CDC签核，signoff.json为PASS。**

- [诊断bit](../build/camera_debug60/outflow/ti60_camera.bit) · [工程](../build/camera_debug60/ti60_camera.xml) · [签核](../build/camera_debug60/signoff.json) · [最终复核](../build/camera_debug60/final_review.json)
- RAM248/256、DSP148/160、XLR41268/60800；最小setup **+0.322ns**、hold **+0.026ns**。相比原60Hz版新增1034 XLR，RAM/DSP不增。
- 最终8条D-PHY首级均唯一连接第二级、0级组合逻辑，级间最小setup **+13.339ns**；原136条Gray、14条FPS束和17个标量首级约束保持。
- SHA256：`d34780d0e3616a2b33e5399f97731d45cdd7053091209c6ee241cc12f7f376b2`。
- 最终独立重新审计与签核一致、12个复位同步FF原生属性通过、SDC异地重建逐字节一致，旧十套发布的源码/配置/报告/权重/bit指纹保持。

此结果确认本地数字构建与电气配置，未代为下载、访问串口或写Flash。摄像头持续彩条的底层原因仍须用这份诊断版的实板记录定位。

## 如何取得诊断信息

1. 使用本目录签核后的诊断 `.bit` 做Programmer/JTAG临时下载。摄像头仍自动采集，不需要上传图片，不另外烧写CPU固件或Flash。
2. 关闭占用该板串口的上传GUI或串口助手。使用板载USB串口，不接J8。
3. 在已安装pyserial的Python环境运行：

```powershell
python F:/fpga_qiansai/elinx/projects/camera_art_styles/pc/camera_diagnostics.py --list
python F:/fpga_qiansai/elinx/projects/camera_art_styles/pc/camera_diagnostics.py --port COM31 --log F:/fpga_qiansai/elinx/projects/camera_art_styles/build/camera_diag.jsonl
```

`COM31`仅为示例，以列表中实际板载串口为准。诊断波特率为 **115200、8N1**，不同于上传图片时的2Mbps。脚本只读、不发送指令，Ctrl+C停止。若缺依赖，执行 `python -m pip install pyserial`。也可用串口助手115200直接查看每秒一行的 `@CAM1,...`。

4. 保留连续几条记录，按下表确定先查哪一级。未收到合法记录时先核对下载的是否是诊断bit、端口和波特率；原 `camera_ppi60` 的TX恒高，没有日志。

沿用用户已确认的J4和J2/J3均2–3，不改变跳线、I/O标准或供电。不要带电插拔模组。原未知Flash启动问题仍保留，JTAG临时下载不会改变下次上电程序。

## 状态如何解释

| 记录 | 含义和下一步 |
| --- | --- |
| CAL=0、UI_RST=1、B=0 | DDR未报校准，CPU尚不能运行；先查DDR、复位与时钟，不能归因于摄像头或CNN。HDMI彩条此时仍可显示。 |
| CAL=1、UI_RST/SOC_RST持续1 | 校准已报完成但系统仍复位，先查复位条件和是否反复重启。 |
| B=0，复位均0 | CPU尚未报告执行；核对CPU启动、实际RAM初始化和APB，不盲改sensor参数。 |
| B=1持续 | 已进入固件，正在等待复位/读ID；若持续则查CPU、I²C和计时。 |
| B=2持续 | ID已通过，正在配置、读回或加载权重。 |
| B=3、Q=L=E=0 | 已发开流命令，但解析端未看到PPI FIFO事件。检查实际MIPI输出/时钟/lane/接收使能；不能直接断定模组损坏。 |
| B=3、Q增长、E增长 | 接收端有事件但包被拒绝；检查速率、lane、ECC/CRC、RAW10/WC2400/尺寸和一包每次HS的兼容性。 |
| L/RAW/VS增长但C=0 | 检查帧完整性、CAP、预处理、捕获FIFO和DDR最终写响应，不能只看好行数认定完整帧已发布。 |
| C增长但I=0 | 已有DDR完整原画，继续查WEIGHT、SRC、START/BUSY和CNN/DDR响应。 |
| I增长而FRONT=0 | 处理已完成但未提交显示前台，查安全消隐和commit ACK。 |
| B最高位1 | 固件已进入安全失败循环，具体原因见下表；不会靠等待自动重试。 |

| B值 | 失败阶段 |
| --- | --- |
| 80000001 | APB标识不符 |
| 80000002 / 80000003 | ID读取I²C失败 / ID不是CD6B |
| 80000004 / 80000005 | 配置写NACK / 尺寸读回失败或不是1920×1080 |
| 80000006 | 开流写NACK |
| 80000007 / 80000008 / 80000009 | VTS或曝光读取失败 / VTS不足1080 / 限制曝光写失败 |
| 80000020 | 权重写入数量不符1217 |
| 80000040 | CPU非预期陷阱 |

串口的C/I/L/E/Q等是32位**累计计数**，脚本的Δ为相邻记录的模差；复位后差值无效，USB/主机读取间隔也不是精确硬件秒。屏幕C/I依旧是原FPS采样，H60为标称刷新率。不能把这些未验证记录预先写成赛题FPS已达标。

## 新增逻辑与接口

```text
原CPU/APB ──只观察完成交易── boot_status / capture_enable / 末次I²C输入读回
原PPI FIFO(UI读侧) ──────── 接收事件数 / 末次32位CSI包头
原CSI/DDR/CNN ──────────── 好行、包错、完整帧、RAW组、VS、处理周期
                         ↓ 同一100MHz域锁存原子快照
             camera_diag_uart → 已有R14 TX → 板载USB串口 → PC只读解析
```

没有新增CPU命令、总线master、ready/enable/复位驱动或跨域总线。观察器仅在APB选择、使能、ready同时有效且无PSLVERROR时记录指定交易；不修改APB响应。诊断UART复位取DDR域复位，独立于calibrated与CPU复位，可报告DDR校准未完成。所有快照输入均在UI域，传输期间保持一致。PPI观察在已有原子FIFO的UI读侧进行，不直接采样byte侧总线。

字段顺序：`boot,flags,good_lines,error_packets,ppi_ui_events,last_header,capture_frames,inference_frames,capture_errors,raw_groups,vs_edges,engine_cycles`。每字段8位十六进制，ASCII协议 `@CAM1,` 加12字段、逗号分隔及CRLF，共115字节，每秒尝试一报，首报复位释放后立即启动。若当前报文尚未发完则跳过节拍，不覆盖快照。100MHz整数868分频，实际约115207.37bps。

flags bit0=CAL，1=UI_RESET，2=SOC_RESET，3=模组复位释放，4/5=SDA/SCL开漏释放，6/7=最后一次APB读取的SDA/SCL输入，8=SRC，9=BUSY，10=WEIGHT，11=FRONT，12=CAP，13=当前包故障，14=传输溢出保持；高位保留。SDA/SCL末次输入读回不是实时电压测量。Q表示UI端PPI FIFO取出的记录，不等于CSI有效数据包数。HEADER只保存最后一次解析包头，未必有效；按CSI ECC及DT/VC/WC解释。

## 验证边界与构建

- 实际100MHz/115200逐位UART解码：115字节完整格式、输入变化中快照一致、周期重报、半字节/半报复位后重新同步、空闲/起停位通过。
- 实际新顶层APB观察器44项检查通过，包含合法/等待/错误交易、全部15个flag、RAW/VS计数、UI/CPU复位清零；真实UART证明CAL=0仍能报告。其他IP明确使用黑盒/强制状态，不冒充整机验证。
- 实际新顶层开漏四状态、从机ACK、三PLL失锁、DDR校准失效、停钟和按键保护通过。PC解析与假串口8项测试通过，未打开真实端口。
- 源码由已签核60Hz版严格派生，只新增观察输出。CPU固件、四条Boot RAM、四组模型、传感器表、DDR/HDMI参数、全部79脚和peri保持，原厂IP与demo不改。
- CAD保留原17个单比特首级、136 Gray最大延迟、14 FPS束约束。D-PHY仍先完全计时路由，原生证明8条首级唯一对应第二级后精确例外，再最终路由/原生证明与电气签核，禁止整组切异步时钟。

本地入口 `scripts/diagnostics/build.py prepare`，仿真通过后 `compile`，已签核文件只读复核用 `audit`；同一工程单任务四线程。该诊断不会提升推理速度，也不能替代实物电源/温升/MIPI波形、真实采集及并发验收。底层无图原因仍须从板上记录定位。
