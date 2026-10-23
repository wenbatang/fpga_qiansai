# Ti60 摄像头 + RISC-V + 四风格 CNN

> **2026-10-19 已更换正确原理图并重建签核。KEY1=P14、KEY2=N14；J8不是UART。** 当前六套bit指纹、时序及电气核对以[本次复核](../../../docs/Ti60_correct_schematic_review.md)为准。camera_ppi：setup +0.302 ns / hold +0.026 ns。原错误引脚bit已保存快照；下文早期构建数值如有不同属于历史记录。


2026-10-17补充：[demo10 V7/V9 锯齿、像素对齐与电平复查](docs/demo_v7_v9_review.md)。按用户要求只参考V7、V9，不使用V6、不修改demo。当前bit保留V7采集模式与独立Bayer/PPI链路，未整套替换V9；具体差异、对齐回归及原bit复核范围见记录。

历史CSI5.15候选 `build/camera_vga/ti60_camera.xml`，用于 **Ti60F225I3 / DemoBoard V4 / demo10 配套 SC431HAI 模组、排线直连**。参考 demo10 的 `Ti60f225_sc431hai2hdmi_v7`，保留原厂CSI与DDR资料；当前独立生成同版CSI5.15的RAW10专用、像素侧带配置，并创建Sapphire3.4.0实例，不升级或覆盖参考IP。上一轮候选快照在`build/baseline_camera_20261015/`。

入口：[离线架构图](architecture.html)、[本轮串口/电气/尺寸复查](docs/review_20261016.md)、[验证记录](docs/validation.md)、[电气与逻辑复查](docs/electrical_logic_review.md)、[控制寄存器](docs/control_registers.md)。

历史：[PPI版本电气、时序与链路复查](docs/preflight_review_20261016.md)。同一bit的79脚、精确约束、DDR数据/OE、开漏及失锁/停钟保护复核通过；用户已确认摄像头J4与J2/J3均2–3短接。未测实际电压/电流/温升，未下载板卡，不能把软件复核当作实板出图保证。

后续补充：8项摄像头初始化故障的机器码模型测试均安全退出。用户不清楚当前Flash内容，新bit尚未下载；正常上电可能执行旧Flash配置，这份未知配置不在新bit签核范围内。应先明确上电配置与实际供电，再进行易失性上板验证。

首次操作入口：[两套Ti60工程下载与使用](../../../docs/Ti60_programming_guide.md)。2026-10-17按用户要求复核串口720p与本项目PPI摄像头版的签核指纹、实际电平及最终时序，通过文件/CAD检查；未重建或访问板卡。摄像头bit内已含Sapphire固件与四组权重，使用时不需PC传图或另烧CPU固件。

新增：[CSI 5.15 跨域调查与复现](docs/csi_cdc_investigation.md)。仅CSI的11 RAM / 0 DSP工程复现同类问题；已核实四lane共8条控制同步链，并在独立STA验证精确首级例外。七组相位/字节时钟停启/复位仿真共325个小尺寸好帧、0坏帧。仍缺5.15内部16个word_count采样端点的稳定窗口依据；旧候选约束未放宽。新PPI替代工程见下文。

数据流：V7 的 1920×1080 RAW10 → 四 lane CSI → 2×2 Bayer 块合成 RGB，得到 960×540 → 中央裁剪 640×480 → RGB565 写 DDR 三原画缓存 → 五层六通道定点 CNN → DDR 两风格缓存 → 安全消隐换帧 → 720p30 HDMI 居中显示，并叠加 C/I/H 计数。

这是显式 VGA 处理配置。已有 `uart_style_tiles` 的真正 720p 工程与签核产物继续保留。四种学习权重仍为星空、浮世绘、水墨、彩色油画，本轮不重训练、不改参数。

RISC-V C 固件从 32KB 片内 RAM 启动，通过 APB 控制开漏 I²C、读 CD6B ID、写入并读回模式、按实际 VTS 限制曝光、加载每种风格 1436 项配置、启动 CNN，并处理中断。按键忙时保留最新请求，加载目标独立锁存。CPU 不执行逐像素卷积；采集/CNN DMA 经 128bit AXI 仲裁访问 DDR。Sapphire 自身 DDR 主口关闭。

## 当前可供上板试验的 PPI 版本

独立入口 `build/camera_ppi/ti60_camera.xml`，顶层 `rtl/ti60_camera_ppi_top.sv`，配置文件 `build/camera_ppi/outflow/ti60_camera.bit`（2,952,954字节）。`build/camera_ppi/signoff.json` 为 **PASS**：RAM204/256、DSP148/160、XLR48995/60800，I3全时序最小setup **+0.289ns**、hold **+0.026ns**，79脚配置对照通过。SHA256：`7fc292efc91c6a28c1121dfb57224d63828ceb0d35fcd5dfffebae660d82bc23`。

使用本机D-PHY RX5.8公开PPI、44bit原子异步FIFO及自编UI域CSI RAW10解析，结构上移除原5.15内部word_count跨域争议路径。8条单比特同步链逐项检查唯一后继及正级间时序，未用全时钟组切断。完整1080p RAW到640×480的3帧及故障/停启测试通过。Sapphire、四组实际学习权重、DDR与HDMI720p30保持原设计。详见[新PPI架构、测试与复现](docs/ppi_camera.md)。

这是CAD/数字仿真签核，**没有下载或固化，没有实测摄像头/FPS**。当前支持VC0 RAW10、一个CSI包/一次HS传输；厂家模型满足此模式，实物SC431HAI是否相同仍需验证。若实物在同一HS突发连续发多个包，需要扩展解析器重建，不保证此bit即插即用。旧CSI5.15候选依旧未签核，以下历史说明不再代表新PPI目录的状态。

## 旧CSI5.15候选的本地构建


```powershell
python scripts/refresh_candidate.py
python sim/check_modules.py
python sim/check_firmware.py
python sim/check_runtime.py
python sim/check_csi_vendor.py
python sim/check_csi_vendor.py --full
python sim/check_sapphire.py
python scripts/build_camera.py --flow map
python scripts/build_camera.py --flow interface
python scripts/build_camera.py --flow route
# 当前源码、时序、电气检查全部通过后才能生成配置文件
python scripts/build_camera.py --flow config
python scripts/camera_signoff.py
```

脚本适配本机 Efinity 2026.1.132、RV32 GCC 15.2、已安装的 Java 17。`config` 只生成文件，不下载开发板。CPU RAM 四条初始化字节通道会逐字节对照固件；源码、初始化数据、模型与报告均绑定指纹。构建运行期间不要再执行准备脚本或修改权重。

## 旧CSI5.15候选的验证边界

模块、实际Efinix FIFO、四模型以及真实Sapphire RTL运行C固件的Questa仿真已验证。CSI官方模型与Bayer联合仿真修复了VS极性，完整1080p RAW输入到640×480及640×360裁剪均通过。物理模组/DDR/HDMI/Sapphire与FPS仍待实板验收，没有下载或固化。BGGR需色卡确认，当前无自动曝光、白平衡、完整ISP或原画分屏。

最新综合与布局布线完成，资源RAM212/256、DSP148/160，79脚配置对照通过。**时序未签核**：CSI内部byte→UI / UI→byte分别有−0.561 / −0.528ns待核对路径，详见验证记录与本地`candidate_status.json`。当前签核脚本拒绝生成配置文件，没有新bit，不应将其直接下载板卡。

640×360预处理已作为参数化模块试验验证，可减少25%帧数据/像素相关运算，保持16:9，但不满足赛题至少640×480的基础要求，行缓存也不会随高度同比减少。本工程默认保留640×480，没有静默降低尺寸；尚未建立完整360高度bit或720p两倍放大显示配置。

C=DDR 发布的完整采集帧/秒，I=CNN 成功完成帧/秒，H30=配置的 HDMI 刷新率；重复显示不增加 C/I。CSI 格式故障保持至整机复位；CRC/ECC2 等状态保留至帧尾校验之后再清除。实际摄像头 30fps、推理 >15fps 尚未测量，两输出缓存等待消隐也可能限制端到端吞吐。用户指定的 720p30 不等同于原赛题显示指标。

V7 参考目录位于 `elinx/elinxdemo/Ti60F225_DemoBoard_v4/10_Ti60f225_sc431hai2hdmi_demo/Ti60f225_sc431hai2hdmi_v7/Ti60f225_sc431hai2hdmi_v7/`。传感器依据为 SC431HAI V1.1 手册，时钟域依据 [Efinix CSI 用户指南](https://www.efinixinc.com/docs/mipi-csi2-rx-core-ug-v3.2.pdf) 表 6–8。保护 IP 未解密，版权保留。

`vendor/`、`build/`、`sim/`、FPGA 配置和模型继续留本地。现有 Git 白名单不含 `firmware/*.c/*.S/*.ld`，固件保留本地，未扩大上传范围；仓库不是完整可重建归档。旧 `measure_core.py` 与历史 map-only 结果继续保留，与新整机分开记录。
