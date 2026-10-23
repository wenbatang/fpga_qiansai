# Ti60 正确原理图复核

2026-10-22补充：现有四个易灵思项目/六套发布再次复核通过，均未改动。新建的[摄像头新四风格工程](../elinx/projects/camera_art_styles/README.md)另完成79脚电气、全CAD和CDC签核；加上该工程共五项目/七配置。新bit与资源、功能范围及仍未达到的FPS指标见其[验证记录](../elinx/projects/camera_art_styles/docs/validation.md)，下表保留原六套入口。

用户于 2026-10-19 指定 **TI60F225I3-V4_SCH-20261012（原理图）.pdf** 为实板正确原理图，取代此前 `Ti60F225A_V4_SCH.pdf`。后者保留作历史资料，不再作为本板电气签核依据。正确 PDF SHA256：`8cf636e4253848cf2bb8a612031bd0fd7e4183a8c59ae7be71b1008aaf669b41`。

## 已发现并修正的差异

| 项目 | 原错误依据 | 正确原理图及处理 |
| --- | --- | --- |
| KEY1 | P13 / GPIOR_27 | **P14 / GPIOR_22**，BR、3.3V、输入 |
| KEY2 | N13 / GPIOR_24 | **N14 / GPIOR_21**，BR、3.3V、输入 |
| P13 / N13 | 误作两个按键输入 | 新图为 LED0 / LED1；旧工程也是输入，未发现因这处差异导致输出对打，但按键功能接错 |
| J8 | 旧图 4/6 脚标成 UART 信号 | **J8 不是串口排针**；新图 2=3.3V，4=CRESET_N，6=1.8V，8=VQPS，10=GND；不要接 USB-TTL 适配器 |
| 原理图审查 | 使用旧 PDF 与错误按键表 | 所有当前签核检查加入正确 PDF 指纹和独立 66/79 脚转录表，旧映射必须拒绝 |

KEY0=C4/GPIOL_07、KEY3=A3/GPIOL_03 保持；四键为 3.3V、外部 10k 上拉、按下接地。模块的两个同步级、消抖和风格位顺序均不变。原理图 PDF 第 8 页（图纸 sheet7）是 GPIO 映射，第 6 页是按键电路。

本地《TI60F225I3-V4 DEMO板软硬件设计说明-260924.pdf》第34页也独立列出 C4/P14/N14/A3 及对应 GPIO，与新原理图一致。不是仅把旧检查脚本的期望值改成当前实现。

板载 USB FT4232 的串口仍对应 **FPGA RX=R4，FPGA TX=R14，3.3V**。图中的 UART_TX_3V3 / UART_RX_3V3 是主机侧命名，不能与 FPGA 方向互换。新图第 4 页与第 8 页已标注/核对。

## 其余电气核对

| 接口 | 正确图纸依据（PDF 页） | 当前实现核对结果 |
| --- | --- | --- |
| 电源 Bank | 第3页 | TL/TR/BL/BR=3.3V；1A/1B/3A=1.8V；3B/4A/4B=1.5V；2A/2B按MIPI跳线=1.2V；配置无动态电压切换 |
| DDR3 | 第7页，MT41J128M16JT-125 | 所有地址、BA、控制、DQ、DQS、DM、时钟、VREF 的封装脚和方向不变；1.5V SSTL；保留 V7 PHY、数据/OE 和 PLL 参数 |
| 时钟 | 第9/14页 | 25MHz=J2、27MHz=H2，两者1.8V；未用的3.3V时钟不混用 |
| HDMI 输出 | 第10/13页 | Bank3A=1.8V。板上 FPGA P/N 与连接器网络反接，已有 `tmds_efx` 将数据和时钟整体取反补偿；未改成 GPIO 直接驱动或5V电平 |
| 摄像头控制 | 第11页 J4 | SCL=D12、SDA=B14，3.3V开漏，输出数据恒0、OE控制拉低/释放；RESET=C12、3.3V高有效。J4为配套模组5V电源，不可据此给裸传感器接5V |
| MIPI RX | 第11页 J4 | CK=E8/D8；逻辑D0=B8/A8、D1=C8/C9、D2=B7/A7、D3=B9/A9，均仅接收、Bank2A/2B为1.2V。J4图中D20/D21后缀不是逻辑lane编号，需按模组MD0/MD1/MD2/MD3标注核对 |
| MIPI 跳线 | 第3页 | J2/J3的2–3接1.2V；用户此前已确认J4及两处2–3。此处引用已有确认，不等于万用表测量 |
| 配置 Flash | 第9页 | U14=GD25LQ64，接VCCIO1A=1.8V；仍是图纸型号，未实读Flash ID、未烧写 |
| J7 扩展接口 | 第11页 | 新图更正右侧若干LVDS连接序号；当前四个工程未驱动J7对应信号，不涉及这次功能输出 |
| 电源启动/VQPS | 第2/3/4页 | 新图增加/更正RC启动、A1/VQPS及J8供电定义。属于板上硬件和专用电源网络，当前用户逻辑不分配或驱动；不能用bit证明实际供电时序/电流已合格 |

补充 VQPS：本机 Ti60F225 的工具 pin 表仍将 A1 标为 GND，新原理图将该专用脚标为 VQPS 并通过 R250/10k 下拉。厂商 [Ti60 数据手册 v3.2](https://www.efinixinc.com/docs/titanium60-ds-v3.2.pdf) 第53–55页说明部分 F225 批次新增 VQPS，常规运行应保持低，只有安全熔丝操作才供电。这是专用电源/批次说明差异，不应通过更改 GPIO 电平去“修复”。本次不接 J8、不供 VQPS、不执行安全熔丝操作；软件检查不证明实物下拉或上电时序已经测量。

## 当前重建状态

全部六个配置均已按正确图纸重新综合、接口生成、布局布线、原生时序和独立电气审查，并生成新的本地 bit。所有使用端口逐项核对、12个Bank电压一致；旧按键映射被新审查脚本拒绝。摄像头PPI另外重新提取D-PHY两级同步器拓扑及最终时序报告，未沿用旧STA证明或扩大例外。

| 项目 / 配置 | 实际使用脚 | 最小 setup / hold | 新 bit SHA256（链接下载本地文件） |
| --- | --- | --- | --- |
| uart_art_styles / 720p | 66 | +0.376 / +0.028 ns | [66a05fbff2f22d6a7029fb1905193a9904444da8534cfdc0213eddfbbd90e571](../elinx/projects/uart_art_styles/build/720p/outflow/ti60_style.bit) |
| uart_art_styles / vga | 66 | +0.395 / +0.026 ns | [89a63644807d73fbb3f36a50070dabb0934cb6747ad4056a5505c7278e582cff](../elinx/projects/uart_art_styles/build/vga/outflow/ti60_style.bit) |
| uart_style_tiles / 720p | 66 | +0.416 / +0.029 ns | [dfae2093b2b13cc33b1a901b1d431c3946cfc774309dab86255112f48a45aef8](../elinx/projects/uart_style_tiles/build/720p/outflow/ti60_style.bit) |
| uart_style_tiles / vga | 66 | +0.535 / +0.026 ns | [d80ea36150647f6d96120302dd13be82322be1c8dd95b428ab25416052c03ae7](../elinx/projects/uart_style_tiles/build/vga/outflow/ti60_style.bit) |
| uart_style_keys / vga | 66 | +0.301 / +0.028 ns | [15f2f8f32ae6f9990bdc8efdcba04ffcab00c52b2abc6a73170ad6bd13f58d3c](../elinx/projects/uart_style_keys/build/vga/outflow/ti60_style.bit) |
| style_video / camera_ppi | 79 | +0.302 / +0.026 ns | [7fc292efc91c6a28c1121dfb57224d63828ceb0d35fcd5dfffebae660d82bc23](../elinx/projects/style_video/build/camera_ppi/outflow/ti60_camera.bit) |

**随后本轮资源优化：** `uart_art_styles`两配置已进一步减少RAM/DSP；上表已更新为优化版，其他四套不变。[最新资源与电气复查](../elinx/projects/uart_art_styles/docs/resource_optimization.md)。下述“生产RTL未改/仅两按键变化”描述的是此前原理图修正阶段，不能套到后续卷积资源优化。

默认新四风格工程仍是 `uart_art_styles/build/720p/`；按键风格和PC工具用法不变。重建前后的生产RTL/IP、ROM、模型与CPU固件指纹完全相同，Interface Designer配置除KEY1/KEY2的GPIO绑定外逐字节规范化比对一致，未改供电、驱动、PLL和DDR。仅修改控制引脚位置不会改变卷积图像算法。现场按键、显示与实际电源仍未验收。

此前改按键阶段的历史复核入口：`elinx/projects/style_video/scripts/review_correct_schematic.py`；输出 `style_video/build/schematic_review_20261019/all_projects.json`。已保留原HDMI邻近耦合警告，不称零警告。

每个项目旧工程输入、报告、bit/hex和说明已复制到各自 `build/baseline_wrong_schematic_20261019/`，不删除旧资料。旧 `camera_vga` 的 CSI5.15候选继续未签核，不因这次按键修正放行；不参考或修改 demo V6，不修改 V7/V9。

快照只作追溯，不能作为当前下载或重建入口。原 XML 可能仍记录原工作目录；使用本页最终列出的当前工程及新 bit。

本轮额外重跑摄像头实际顶层的开漏四状态/从机ACK、三个PLL各自失锁、校准失效、停钟和按键复位保护，均通过；IP/系统为黑盒加状态强制，不能称完整SoC或模拟电气仿真。实际RV32机器码的八组无模组、错误ID、I²C卡低、配置NACK、尺寸/VTS异常及开流NACK均安全退出：停止采集、复位模组、释放I²C、不启动CNN；此处为ISA/MMIO/I²C数字模型，无实板故障注入。

此次没有算法、ROM、CPU固件、PLL频率或DDR工作参数改动。数字配置检查不能代替实际电源、电流、温升、信号质量和整机运行验收；没有打开真实串口/JTAG、没有下载或固化。未知 Flash 的上电程序仍需按首次使用流程确认。

后续资源优化后的六套当前发布统一复核入口为 `uart_art_styles/build/review_resource.py`，结果 `uart_art_styles/build/resource_review_20261019/review.json`。原理图阶段记录及快照继续保留。
