# 新四风格按键版验证

本文件只记录 `uart_style_keys` 新版本，不能沿用旧 `uart_style_hdmi` bitstream 的签核或用户上板反馈。

四种新教师和定点学生训练均已完成，实际四模型检查通过。720p与VGA完整实现均已签核；本版本尚未上板。

已经运行：

- `sim/check_keys.py`：四键映射、去抖、长按不重复、复位时按住、同时按键优先级；完整源图有效性、处理中锁定权重、最新键排队、故障保留前台、上传 ACK 与本地作业隔离。
- `sim/check_link.py`：最终四种不同的本轮真实权重、64×8 RGB565，一次上传之后三次按键，源图区仅写64个128bit字；真实CNN/DDR/显示数据逐像素一致；新BEGIN忙应答不破坏源图，半帧/ABORT禁止推理，失败保留前台及按键重试，下一张完整图片恢复，安全换帧与重复END不重复推理。
- `sim/check_protocol.py`：旧协议边界回归，新增串口 STYLE 被禁用，METRICS、提交失败及偏移/CRC/超时/重复包恢复。
- `sim/check_cobs.py`：零字节、254 字节块、16KB 包、CRC/截断/溢出/超时恢复。
- `sim/check_control.py`：原仲裁器及原控制器回归；新按键控制器由 `check_keys.py` 和 `check_link.py` 验证。
- `sim/check_pc.py`：原图上传，不发 UART STYLE；部分写、拆包 ACK、NACK 重试、丢 END ACK 不重复推理、错误/取消关闭串口、GUI 设置在线程启动时锁定。
- `sim/check_video.py`：720p 与 VGA 居中模式，标准 720p60 同步、准确 FIFO 像素计数/顺序、黑边及下溢帧恢复。

所有测试在项目 `sim/`，工具工作目录为项目 `build/` 或 `sim/`；没有打开实际串口或 JTAG。

## 最终模型和整帧检查

- `check_cnn.py`：四种真实模型各19×17、各1×1，边界、停顿及逐像素对照PASS；记录在 `sim/distinct_final/` 和 `sim/distinct_tiny/`。
- `evaluate_distinct.py`：四种模型各6张256×256，CPU QAT对独立NumPy int64参考，共4,718,592个通道值，最大误差0。另48张开发回归记录色彩/内容/风格统计，不称盲测。
- `preview_distinct_image.py`：用户实际 `uart_hdmi/images/0001.png` 原生1280×720，四模型逐层核对，共11,059,200个通道值，最大误差0。输出在 `pycode/results/distinct_real_720p`，是定点软件参考，尚不是HDMI读回。
- 教师与学生各生成四风格72张输出、每风格6页12组对比；检查点SHA256与导出模型绑定，记录见 `pycode/results/distinct_evaluation/evaluation.json`。

整帧使用本轮真实星空权重，xsim包含显示DDR仲裁、AXI背压、错误响应与恢复，整帧CRC对照独立整数参考。为了测同一模型，整帧测试四槽复制星空；其他三模型由上述真实四模型小图RTL与原生720p软件检查覆盖。不能说“四种模型均完成全尺寸RTL仿真”。

| 处理尺寸 | 正常完成周期 | 100MHz等效时间 | 等效FPS | 显示仲裁拍数 |
|---|---:|---:|---:|---:|
| 640×480 | 5,135,297 | 51.35297ms | 19.47 | 834,128 |
| 1280×720 | 15,153,216 | 151.53216ms | 6.60 | 2,449,392 |

结果在 `sim/distinct_vga/frame_verification.json`、`sim/distinct_720/frame_verification.json`。这是推理模型周期，未包含真实USB上传、消隐等待或摄像头取帧。640×480是>15fps的验证路线；默认720p保留原生分辨率，不宣称720p推理达到15fps。HDMI标准720p60持续刷新，重复显示不计新处理帧。

## 完整构建与电气审查

Vivado2023.2、xc7k325tffg676-2、MIG4.2、Clock Wizard6.0。新工程88端口，以 `Kintex7_BaseC_FMC原理图.pdf` 第4、11页及DDR电源/接口页核对。KEY1/D26复位；KEY2/J26、KEY3/E26、KEY4/G26、KEY5/H26独立LVCMOS33输入，Bank14为3.3V，板上4.7k上拉，按下接地。四键各自两级同步、100MHz下10ms去抖。

两套新bitstream均完成综合、布局布线、时序与88端口电气审查。

| 配置 | WNS ns | WHS ns | WPWS ns | LUT | 寄存器 | BRAM | DSP | 端口审查 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 720p | +0.689 | +0.049 | +0.143 | 18945 | 12129 | 97.5 | 213 | 88 / PASS |
| vga | +0.731 | +0.053 | +0.143 | 18872 | 12085 | 50.5 | 213 | 88 / PASS |

- 720p bit SHA256：`691092fbbc8a5bd620aadba3add08dbc3fc94598bceb8f35be6ce79df5649fbd`；入口 `vivado/uart_style.runs/impl_1/uart_style_top.bit`，签核 `build/signoff.json`。
- vga bit SHA256：`3f241fa9969b1c5fb49eddf35154fadc47b71884cd7abccafb40db9887e36b57`；入口 `vivado_vga/uart_style.runs/impl_1/uart_style_top.bit`，签核 `build/vga/signoff.json`。

DDR端口SSTL15/DIFF_SSTL15与Bank32/33 1.5V，VCCAUX_IO NORMAL/1.8V，外部VREF；DDR3-800。实际时钟200MHz参考、400MHz DDR、100MHz UI、HDMI74.25/371.25MHz。新键不改变其他84端口或板级电压配置。`check_board.py`逐项检查路由设计导出的 `pin_audit.tsv`、时钟和MIG参数，不能仅用DRC代替原理图核对。

## 工具警告与待测事项

720p内部未约束端点、无时钟端点、组合环均为0，DRC Error为0；仍有522个Warning。主要为351个DSP输入流水建议、144个DSP MREG建议，4个MIG DQS缓冲提示、1个MIG PLL缓冲提示，20个RAMB36及1个RAMB18复位控制提示，另有规则汇总限制提示。未删除警告或放宽电气规则；DSP流水建议不等于实际100MHz时序失败。

VGA内部未约束端点、无时钟端点、组合环同样为0，DRC Error为0，Warning为523；与720p相比多1个CHECK-3规则汇总提示，其他类别及CDC/方法学汇总相同。不能将报告的规则显示限制误称为硬件错误已消失。

RAM历史不作清零复位，复位期间不依赖其内容；每帧由零填充扫描覆盖会被使用的历史，同步释放后恢复运算。异步复位断言仍可能影响RAM控制端，模块仿真不能代替实板异步复位验证。上板需检查复位、PLL失锁/重新锁定、DDR重新校准和再次完整上传。

CDC有12项单比特同步器Info、4项复位同步Info和2项MIG内部复位链缺ASYNC_REG属性Warning。按键各自同步，外部只到第一级D设置例外，第二级及去抖仍计时；不直接跨域采样多位风格编码。方法学另有4项LUTAR复位逻辑Warning、1项XDC对象查找Warning、32项SERDES复位Advisory。保留厂商IP与原复位拓扑，不宣称“全部警告为0”。

另只读打开720p路由检查点，检查四键两级寄存器均带ASYNC_REG，级间确有时序路径，建立裕量分别9.535、9.539、9.535、9.392ns；记录 `build/keys_sync_timing.tsv`。此检查确认没有把完整同步链误设为false path，仍不代替真实机械按键与复位试验。

异步串口/按键、复位，以及DDR复位/TMDS外部端口没有通常同步总线的全部I/O延时定义；UART/键经同步器，DDR PHY由MIG约束，HDMI为转发时钟串化输出。WNS不能代替USB稳定性、接收端信号完整性或实板按键测试。

新版本没有下载FPGA或Flash，没有打开实际串口；完整帧ACK总时间是否<10秒、新模型实屏、按键响应和实板推理FPS均未测。Ti60新四权重仅核心map PASS：144 DSP、161 RAM10、6938 LUT4、5962 FF、4649 ADD；未整机布线或摄像头/RISC-V/DDR/HDMI集成，不能宣称易灵思整题完成。

## 原版保护

2026-10-13新增主机摄像头自动上传工具与mock验证，见 [host_camera.md](host_camera.md)。本功能没有改Xilinx RTL、权重或已签核bitstream；再次检查两配置源码/权重指纹与88端口签核通过。相机预览为最新采集图，与串口延迟后显示的上一张完整照片可能不同，不能用两者作同帧逐像素比较。本机编号0/DSHOW未能打开，没有真实相机上传/实屏结果。

旧模型、参考和工程保持原路径；另备份186文件在 `../uart_style_hdmi/build/phase_baseline_20261012/`，包含模型、真实权重、源码、报告和两套旧bit。旧版版画保留，仅新四槽替换为油画。备份、权重、sim、约束/IP和bit按既定规则仅留本地；未提交或推送。
