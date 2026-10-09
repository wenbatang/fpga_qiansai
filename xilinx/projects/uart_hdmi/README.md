# UART → DDR3 → 720p HDMI

独立工程目录：`xilinx/projects/uart_hdmi/`。目标器件 `xc7k325tffg676-2`，使用本地 BaseC 原理图的引脚。PC 通过串口发送 1280×720 原始 RGB565 图片，FPGA 写入外部 DDR3 后在显示帧边界换图，HDMI 持续以 720p60 时序刷新。

完整说明见 [离线 HTML 架构图与工作原理](architecture.html)：包含 UART 8N1、RGB565 字节与地址布局、DDR3/MIG/AXI 基础、12 步传图流程、双缓冲发布与 FIFO 刷新、720p/TMDS、时钟/复位/CDC、主要模块职责、异常恢复以及当前验证边界。页面带双缓冲交互演示和线速下限计算器，可直接离线打开。引脚逐项核对与修复依据见 [电气及逻辑复核](docs/electrical_logic_review.md)。两份说明与项目实现一起维护。

## 当前状态

**最新提速版：2Mbps / 16KB / 720p RGB565，独立工程与bitstream已生成，未烧写实板。** [提速说明及时间预算](docs/transfer_speed.md)。GUI重启后可点“提速2Mbps / 16KB”；必须使用对应FPGA配置，不能只改PC参数。

- 提速工程：[vivado_fast/uart_hdmi.xpr](vivado_fast/uart_hdmi.xpr)。
- 提速bitstream：[vivado_fast/uart_hdmi.runs/impl_1/uart_hdmi_top.bit](vivado_fast/uart_hdmi.runs/impl_1/uart_hdmi_top.bit)。
- 提速实现：WNS +0.893ns、WHS +0.054ns、WPWS +0.143ns；0时序失败、0 DRC错误，保留5条MIG警告。全部84引脚及目标时钟复核通过；LUT 13158、FF 9197、RAMB36 4。
- 34张图的转义/包头/成功ACK线速预算9.2475–9.7876秒，**不是实板总用时**。USB、DDR及软件等待还需额外时间，10秒目标尚待实测。
- 新增16KB边界和实际2Mbps UART→收包→AXI写入联合仿真通过；GUI完整113个DATA传输、丢ACK与尾包回归通过。源码与提速bitstream指纹保存在`build/fast/build_receipt.json`和`final_signoff.json`。
- PC使用已有NumPy加速RGB565转换；34张图片与原方法逐字节一致，转换平均0.1360s→0.0065s。NumPy可选，缺少时使用原方法；这不是串口实测时间。

以下保留标准115200 / 1KB版本的历史验证基线及使用说明。原bitstream文件未覆盖；本次共享源码和构建脚本已更新，历史标准凭据仅匹配当时源码。默认参数仍保持标准行为并通过回归。

已编写 RTL、工程生成 Python/Tcl、独立 MIG 配置、板级 XDC 和 PC 传图脚本，并通过 Icarus Verilog 通用行为仿真、PC协议测试、真实厂商模型及两帧完整720p联合仿真。用户确认板卡为「Kindex Base7 FMC版」。

**2026-10-09 已完成 Vivado 2023.2 工程创建、综合、布局布线和 bitstream 生成，进程退出码0。未上板。**

- 工程入口：[vivado/uart_hdmi.xpr](vivado/uart_hdmi.xpr)。
- bitstream：[vivado/uart_hdmi.runs/impl_1/uart_hdmi_top.bit](vivado/uart_hdmi.runs/impl_1/uart_hdmi_top.bit)，11,443,722字节。
- 内部时序：WNS **+0.893ns**、WHS **+0.026ns**、WPWS **+0.143ns**，setup/hold/脉宽失败端点均为0。
- DRC：0错误、5警告（4条MIG DQS输入缓冲无负载BUFC-1、1条MIG时钟缓冲REQP-1709）；CDC：0严重项、2条MIG内部复位属性警告。方法学无严重项，保留4条复位组合逻辑警告、1条IP约束查询效率警告和32条SERDES复位advisory。
- FIFO Gray 指针 bus skew 检查全部通过；无缺失时钟、无未约束内部端点、无组合环。
- 外部接口仍提示异步复位/UART RX和DDR reset、TMDS、UART TX端口缺少部分input/output delay（详见`vivado/check_timing.rpt`）。未凭空填写板级时延；这里是内部时序通过，实板DDR校准与HDMI显示仍需验证。

启动失败、旧路径、800MHz BUFG 违例和 CDC 修复详见 [构建问题与验证记录](docs/build_validation.md)。未修改 Vivado 安装、注册表和厂商参考工程。
最终84个引脚及200/400/100/74.25/371.25MHz时钟自动核对通过。第二轮复核修复长DDR背压越过消隐期换帧、错误RLAST拍进入FIFO的问题；异常回归和长停顿联合仿真通过。构建输入与bitstream的SHA256已记录，最终值见[构建记录](docs/build_validation.md)。旧版本已被替代。


## 文件与入口

```text
uart_hdmi/
  architecture.html       离线架构说明图
  create_project.py       提取校验过的参考配置，生成独立 Tcl/XDC/MIG 参数
  rtl/                    手写模块；复用的 TMDS 编码器/串化器
  pc/send_image.py        选图、RGB565 编码、分包、进度、重试和应答检查
  pc/send_image_gui.py    中文GUI；选图预览、串口/波特率、进度、停止、日志
  pc/estimate_transfer.py 按图片内容统计转义、协议、ACK的线速预算
  images/                 预留图片目录；请复制自己的 1280×720 图片
  ip/mig.prj              MIG 独立参数，不依赖原示例缓存
  ip/reference_manifest.json  参考文件路径及 SHA256
  constraints/            板级约束；cdc.xdc 仅用于实现阶段
  scripts/create_project.tcl  Vivado 工程创建入口
  scripts/desktop_process.py  Windows 应用包环境下的工具启动兼容
  sim/                    模块/厂商仿真、测试向量与仿真产物
  build/logs/             启动诊断、批处理日志与验证记录
  vivado/                 .xpr、独立 IP、综合实现产物与 bitstream
  vivado_fast/            独立2Mbps / 16KB提速版；报告不覆盖标准版
  build/fast/             提速日志、指纹、时序签核与线速预算
```

仿真和构建产物全部在本工程内部，按照 Git 约束只保留本地；工作区根目录不再有本项目的 `sim/`。

本机已在项目 `.venv/` 准备好 pyserial 3.5，Pillow 复用现有环境，没有修改原 Conda 环境。可用以下解释器直接运行 PC 脚本：

```powershell
$uartPython = 'F:/fpga_qiansai/xilinx/projects/uart_hdmi/.venv/Scripts/python.exe'
& $uartPython xilinx/projects/uart_hdmi/pc/send_image.py --list-ports
```

本次端口枚举发现 `COM29: USB-SERIAL CH340`。这只是 PC 检测到的串口设备，不代表 FPGA 工程已烧写或链路已验证；COM5/COM12 是 com0com 模拟串口。重新插拔后端口号可能变化，传图前重新枚举。

队友的 PC 环境依赖版本见 [pc/requirements.txt](pc/requirements.txt)，其中 NumPy 在代码中可选，清单包含它以启用加速转换。Git 保留本 README、架构图和源文件；`sim/`、`build/`、`vivado/`、`vivado_fast/` 及其产物仅留本地。架构页里指向这些文件或 IP/约束配置的链接，在仅克隆源码仓库时可能不存在。

## 生成 / 打开工程

在工作区根目录执行，Python 生成工程入口不需要第三方包：

```powershell
python xilinx/projects/uart_hdmi/create_project.py
python xilinx/projects/uart_hdmi/create_project.py --run
```

如果 Vivado 安装位置不同，使用 `--vivado "实际路径/vivado.bat"`。也可在能够正常启动的 Vivado 2023.2 Tcl Console 运行：

```tcl
source F:/fpga_qiansai/xilinx/projects/uart_hdmi/scripts/create_project.tcl
```

预期生成 `xilinx/projects/uart_hdmi/vivado/uart_hdmi.xpr`。完成相关仿真后，全流程构建命令是：

```powershell
python xilinx/projects/uart_hdmi/create_project.py --build
```

脚本不会覆盖已有工程。已有工程可用 `create_project.py --build --resume` 继续；修改 RTL 或本项目 IP 参数后用 `--build --resume --reset-synth` 从综合重建。更改 `UART_BAUD` 时，在 Vivado 的 sources_1 generic 设置修改参数并重新构建，或在创建新工程前用 `create_project.py --baud 921600` 生成相应 Tcl。`--resume` 保留已存在工程中的波特率设置。

Vivado 构建应检查 `ip_status.rpt`、`timing_summary.rpt`、`utilization.rpt`、`drc.rpt`、`cdc.rpt`，确认 IP 未锁定、实现完成、约束和时序达标后再考虑上板。创建工程不代表实现或时序通过。

## 串口发送图片

把图片放入 `images/`。默认要求 1280×720；FPGA 不解码压缩图片，PC 使用 Pillow 解码。

推荐使用GUI。在PowerShell中执行以下命令，工作目录不限：

```powershell
& 'F:/fpga_qiansai/xilinx/projects/uart_hdmi/.venv/Scripts/python.exe' 'F:/fpga_qiansai/xilinx/projects/uart_hdmi/pc/send_image_gui.py'
```

GUI自动载入本项目`images/`，可选择其他目录或单个文件。左侧点击图片即可预览；刷新串口后选择板卡的CH340端口，再选择匹配FPGA的波特率/数据包大小。默认115200 / 1KB匹配标准版；提速按钮选择2000000 / 16KB，匹配`vivado_fast`版本，修改GUI不会自动修改FPGA。点击“仅检查图片”可在不打开串口的情况下验证尺寸与编码；“开始发送”才打开串口。

发送在后台线程运行，进度按已收到成功ACK的像素字节计算。进度达到100%后仍等待END应答，收到完整帧发布确认后才显示成功；HDMI实屏结果需要自行查看。日志显示重试与失败原因，停止后关闭串口，下一次发送重新建立会话。已经发布的图片不会因停止而回滚。传输中锁定图片与串口设置，避免切换参数影响当前帧。非720p图片可勾选等比例缩放补黑边；当前用户放入的34张PNG已检查均为1280×720。

GUI使用Python自带Tkinter、Pillow与pyserial，复用下方命令行的同一协议；不需要新增GUI框架。窗口/模拟串口回归入口为`sim/test_sender_gui.py`，日志为`build/logs/sender_gui_tests.log`。已覆盖两种配置的完整720p、分段写入、丢ACK重传、取消、串口占用错误、预览布局与状态恢复；真实串口传图尚未验证。GUI显示的成功总用时包含解码、串口打开和所有命令确认。使用提速配置需要烧写新的提速bitstream。

命令行也可继续使用：

```powershell
python -m pip install pyserial Pillow
python xilinx/projects/uart_hdmi/pc/send_image.py --list-ports
python xilinx/projects/uart_hdmi/pc/send_image.py --list
python xilinx/projects/uart_hdmi/pc/send_image.py --port COM5 --baud 115200
```

只有一张图时直接发送；多张时可输入编号或文件名，例如`1`或`0001.png`。无效输入会提示正确格式，不再直接将文件名转成整数。指定单图、依次发送整个目录或在无硬件时检查编码：

```powershell
python xilinx/projects/uart_hdmi/pc/send_image.py --port COM5 --image xilinx/projects/uart_hdmi/images/my_picture.png
python xilinx/projects/uart_hdmi/pc/send_image.py --port COM5 --all --interval 5
python xilinx/projects/uart_hdmi/pc/send_image.py --image xilinx/projects/uart_hdmi/images/my_picture.png --dry-run
```

非 720p 图片默认报错。需要等比例缩放并补黑边时添加 `--resize`。传输显示字节进度；默认应答超时 2 秒、额外重试 3 次。串口为 8N1，无 RTS/CTS，不自动切换波特率。FPGA 校准完成前不能正常应答；错误串口、占用或波特率不一致会超时。

默认波特率 **115200**，1,843,200 字节原始像素至少 160 秒；921600 至少 20 秒，另有转义、包头、ACK、软件等待开销。HDMI 60Hz 是显示刷新率，不是串口更新率；静态图停等传输不是实时视频。提高波特率必须同时修改 FPGA 参数和 Python 参数，稳定波特率需实测。

## 数据、协议和所有权

- 帧尺寸 1280×720，RGB565，低字节先发，逐行、行内从左到右，无 padding，stride=2560 字节。
- 每包 20 字节小端头，格式 `<BBHIIHHHBB`：版本、命令、包序号、帧号、字节偏移、payload 长度、宽、高、格式、保留字段；版本=1、格式=1、保留=0。
- 包线格式：`7E + escaped(header + payload + crc32_le) + 7E`；7E/7D 转义为 `7D` 加原字节 XOR 20。
- CRC32/ISO-HDLC（与 Python `zlib.crc32` 一致），包 CRC 覆盖未转义的头和 payload。BEGIN payload 是整帧 CRC32。
- 命令：BEGIN=1，DATA=2，END=3，ABORT=4，QUERY=5。DATA 最多 1024 字节，偏移和长度按 16 字节对齐；全帧 1800 包 DATA。
- 应答命令为原命令 OR 80hex，单字节 payload 为状态，offset 为已确认像素字节数。状态：0成功、1头/尺寸错误、2包校验/帧错误、3顺序错误、4忙、5AXI写错误、6整帧CRC错误、7会话超时、8未校准。通用错误应答用命令80hex、序号FFFFhex。
- 每包停等，成功 DATA ACK 必须等最后一笔 AXI B 响应；BEGIN/END/DATA 最近成功包缓存命令、帧号、序号和 CRC，丢 ACK 后重发不会重复写入/发布。
- 提速版仍使用上述协议，但DATA上限扩为16384字节，完整帧113包；包内解码存储16408字节、15bit地址/长度。标准版上限1024字节保持不变；PC `--chunk-bytes` 不可超过已加载FPGA的上限。
- 包间字节空闲 1 秒后丢弃半包；已开始帧在空闲 5 秒后放弃会话。Python 每次新图先 ABORT 再 BEGIN，因此异常退出后可以重新传图。
- Bank 0 基址 0，Bank 1 基址 0x00200000；每帧占 0x001C2000 字节。写后台、读前台；END 验证全部字节与整帧 CRC 后申请发布。
- `frame_reader`等待帧边界请求，先排空旧AXI读事务，并检查像素域同步来的`refresh_window`后才换前台。窗口在有效显示前一整行关闭；长背压错过窗口时等待下一窗口，不在有效显示区交换。重新清理FIFO，busy结束后预取；END ACK只在前台所有权交换后发送。RRESP或RLAST异常的数据拍不进入FIFO。
- 无图时输出黑画面；有效帧显示发生欠载时，本帧后续填洋红并计数，下一帧从起点恢复，避免欠载造成后续永久像素错位。
- AXI 写采用 128bit 单 beat，全 WSTRB、AW/W 独立握手。显示读采用 16 beat / 256 字节对齐突发，单笔 outstanding，FIFO 水位限制预取，不跨 4KB 边界。
- AXI 无响应时不能安全取消已经发出的事务，应复位并检查 MIG；PC 应答超时不能视为 DDR 错误帧已被发布。

## 时钟 / 来源 / 引脚

复用来源：

1. `xilinx/xc7k325tffg_base/17ddr3_axi_read_write/.../ip/mig_7series_0/mig_a.prj`：MIG 4.2，MT41K256M16XX-107，32bit DDR3、4:1 PHY，30bit AXI 地址 / 128bit 数据 / 4bit ID。原配置800MHz DDR、2.0V/HIGH不符合本板1.8V辅助供电条件。复制后改为200MHz MIG输入、2500ps内存周期（400MHz DDR）、1.8V/NORMAL、CL6/CWL5，保留引脚及AXI参数；通过IP生成器重新计算PLL，不编辑生成RTL，不升级IP。变更和源SHA256记入manifest。
2. `xilinx/xc7k325tffg_base/hdmi/rtl/hdmi_encoder.sv`、`hdmi_serializer10to1.sv`：按原始字节复制，保留原文件注释及版权信息，SHA256 记在 manifest。未复用原 HDMI 顶层/时序驱动；新顶层修正原例程同步端口方向与控制位通道。
3. `xilinx/xc7k325tffg_base/资料/Kintex7_BaseC_FMC原理图.pdf` 第4–7页：逐项核对串口、HDMI、DDR 映射。原 DDR 示例的 sys_clk=AG21、rst_n=AJ25 与本原理图不一致；这些顶层引脚不沿用。

新工程：50MHz 输入 G22，低有效复位 D26；UART RX B20、TX C22。HDMI1 时钟 F17/E17，数据0 J15/J16、数据1 E15/E16、数据2 G17/F18，输出使能 E22。DDR 引脚由 MIG 的独立配置提供，不抄入新顶层 XDC。引脚匹配这份本地原理图，仍需核对实物板卡版本。

DDR Clock Wizard 从50MHz生成单路200MHz，供MIG系统输入和IDELAY参考输入；MIG内部PLL生成400MHz DDR时钟、100MHz UI时钟，速率为DDR3-800。辅助电压按原理图为1.8V/NORMAL，DDR Bank32/33为1.5V。UART分频与1秒/5秒超时均按100MHz UI配置。视频MMCM从100MHz UI级联，VCO=`100×37.125/5=742.5MHz`，分别除以10、2产生 **74.25MHz / 371.25MHz**。720p时序有效1280×720、总1650×750、H前/同步/后=110/40/220，V前/同步/后=5/5/20，正同步极性。

UI 和像素域各自同步释放复位；像素域每个独立复位来源先同步释放，再组合。UART、发布控制、FIFO 等待 DDR 校准及必要时钟锁定。帧请求、应答和前台有效位用双触发器同步；像素使用 XPM 异步 FIFO。XPM 写域 busy 已汇总完整读写复位握手，顶层不再次跨域同步读 busy；像素域直接使用自己的读 busy。

厂商接口依据：[AMD XPM_FIFO_ASYNC 文档](https://docs.amd.com/r/2021.2-English/ug953-vivado-7series-libraries/XPM_FIFO_ASYNC)、[MIG UG586](https://docs.amd.com/r/en-US/ug586_7Series_MIS/Documentation)。本地约束采用具体配置，不能只靠文档通用参数替代原理图。

## 已完成验证与实际边界

本机 Icarus Verilog 仿真：

```powershell
& 'F:/fpga_qiansai/xilinx/projects/uart_hdmi/.venv/Scripts/python.exe' xilinx/projects/uart_hdmi/sim/run_checks.py
& 'F:/fpga_qiansai/xilinx/projects/uart_hdmi/.venv/Scripts/python.exe' xilinx/projects/uart_hdmi/sim/run_vendor.py
```

通过 UART 收发/break、包与整帧CRC、重复包、错误偏移、半包/会话超时、AW/W不同背压、B错误阻止发布、END等待显示边界、AR/R背压、旧读事务排空、FIFO复位/busy、突发对齐、完整3帧720p时序与欠载恢复。PC 使用分片应答、丢ACK场景验证重传；实际 RTL 生成的转义应答由 Python 解码并核对CRC。DDR 写侧缩小为64×2测试帧，读侧128×16测试帧；显示时序使用完整1280×720。未宣称缩小模型仿真等于整帧物理 DDR 验证。

实际 Xilinx 模型已通过：XPM 128→16位 FWFT 像素顺序、清空旧帧和完整读写复位握手；MMCM 74.25/371.25MHz；OSERDESE2 十位串化、蓝通道 HS/VS 控制映射和差分极性。使用 unisims_ver 与 secureip 仿真库。顶层连接及 IP 接口也已通过 Vivado 综合和实现。

尚需核对实物板卡版本，并上板验证 DDR 校准、已知图案读写、串口稳定波特率、完整720p图像、屏幕显示和无撕裂。HDMI 外部电气与时延未实测，不标记“已上板成功”。

## Git 范围

Python、手写/复用 RTL、Markdown 与用户要求的 `architecture.html` 可以收录。图片、MIG参数、XDC/Tcl、IP生成文件、Vivado工程、bitstream和 `sim/` 保留本地；不自动提交或推送。队友克隆后需要本地参考 MIG 参数文件才能重新生成此板卡工程，当前上传策略不是完整可重建工程归档。
