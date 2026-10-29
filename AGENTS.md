# 工作区约束

适用范围：`F:\fpga_qiansai` 及其子目录。用户在当前会话中的明确要求优先于本文。默认使用中文沟通，代码标识符使用英文。

## 目标与平台分工

- 本工作区完成《易灵思.pdf》中的赛题一：AI 赋能的「实时绘画」——风格化视频渲染系统。不要混同于赛题四的边缘检测。
- `elinx/` 是易灵思 Efinix 平台资料和最终参赛实现所在目录。保留现有目录拼写，不擅自重命名。
- `xilinx/` 是 Xilinx 平台资料和辅助验证所在目录。用户当前没有可用于此平台的摄像头，采用 PC 串口传图、FPGA 缓存和 HDMI 显示验证。
- Xilinx 静态图验证通过不代表易灵思赛题完成；最终必须在 Ti60F225I3 平台完成摄像头实时采集、神经网络硬件加速、DDR 帧缓存、RISC-V 控制与 HDMI 显示。
- 串口路线默认指原始图像像素传输，不擅自扩展为 JPEG/PNG 硬件解码、USB 视频采集或实时串口视频。
- 用户已明确授权主机摄像头持续采集、自动逐张串口上传并可停止。PC只保留最新采集帧、每次仅一张完整图片在途，END ACK后再发下一张；支持完整帧后暂停和立即停止，分别说明半帧源图失效和已提交帧不回滚。该功能仍是原始RGB565停等传图，不宣称UART实时视频。

## 赛题基础验收边界

来源为根目录《易灵思.pdf》第 3–6 页，实施步骤见 `docs/赛题一实施计划.md`。

- 摄像头：MIPI CSI-2，参考 SC431HAI；RAW 转 RGB，并缩放至至少 640×480，采集/预处理达到 30fps。
- 存储：预处理后的帧写入外部 DDR，落实双缓冲和完整帧发布，验证缓冲所有权、溢出和丢帧情况。
- 推理：轻量化风格迁移神经网络，FPGA 至少实现 3×3 或 5×5 卷积、激活函数、BN 或 IN 的硬件近似；通过系统总线读写 DDR。
- 显示：至少标准 720p60 或 1080p30，支持原画/风格画对比或按键切换，并叠加实际处理 FPS。
- 控制：RISC-V 的 C 驱动负责摄像头配置、权重加载、加速器启动/完成/中断与显示配置。
- 性能：640×480 风格化处理稳定超过 15fps。分别报告采集 FPS、推理 FPS 与 HDMI 刷新率，不能将重复显示计为新处理帧。
- 传统灰度、Sobel、颜色量化等滤镜可用于链路调试，不可据此宣称满足神经网络风格迁移要求。
- 优先完成基础要求，再做多风格切换、720p 处理和其他高阶功能。

## 资料保护与工程组织

- 新工程必须自包含：仿真放在对应项目的 `sim/`，Vivado 工程/IP 放在项目的 `vivado/`，日志、临时文件和诊断放在项目的 `build/`。不得在工作区根目录新建 `sim/` 或输出构建文件；调用工具时工作目录使用项目自己的构建目录。已有其他项目资料不因整理而批量移动。
- `xilinx/projects/uart_style_hdmi/` 是新增的实际训练 CNN 验证工程，与原 `uart_hdmi/` 分开。它使用 COBS 请求及原 SLIP ACK，不能配合旧工程发送工具或 bitstream。通用卷积在 `common/rtl/`；四风格教师、学生、QAT 和整数参考在 `pycode/`，模型与训练结果继续留本地。
- 用户认可的旧风格参数保留，完整备份在 `uart_style_hdmi/build/phase_baseline_20261012/`。新四键版独立放 `xilinx/projects/uart_style_keys/`，图片仍从串口上传，风格选择由板上 KEY2–KEY5 完成，槽顺序为星空、浮世绘、水墨、彩色油画；旧版版画不删除、不覆写。新参考与实验位于 `pycode/styles/distinct_v1/`、`runs/distinct_teacher_v1/v2` 和 `runs/distinct_student_v1`。
- 四键版复用完整 DDR 原图，处理中锁存 engine_style，按键忙时只保留最新请求。新 BEGIN 使完整源图失效，半帧/ABORT/超时不得恢复源图有效性；转换忙时 BEGIN 返回忙且不破坏旧源图。按键作业不得制造 UART END ACK，输出仍等最终 AXI 写响应和安全消隐换帧。
- 风格工程默认`720p`配置为1280×720输入/CNN，另有显式`vga`配置为640×480输入/CNN、720p60居中显示；两者完整工程分别放`vivado/`与`vivado_vga/`，不能静默降低默认输入分辨率。PC选择须匹配bitstream，收到尺寸不匹配的ACK立即报错。两配置共用生成权重，另一构建运行时禁止改权重；模型切换后两套均重新构建签核。
- 当前最终定点学生为五层六通道、膨胀率1/1/2/4/8，带X/Y模4特征；特征在FPGA生成，不增加UART数据。`PHASE_INPUT`的移位加法仅用于0/85/170/255特征，不得用于任意uint8通道。冻结BN折叠不等同于原IN。四种ROM编译选择不等同于赛题RISC-V运行时权重加载已完成。
- 核心OOC、整机布局布线、仿真周期和UART线速预算分别标明范围，均不能替代真实板上FPS、十秒完整上传及连续视频验收；最终模型、RTL、权重和bitstream指纹须对应同次构建。新风格工程记录见其`docs/validation.md`，旧工程与旧bitstream继续保留。
- Xilinx 参考资料当前路径为 `xilinx/xc7k325tffg_base/`。工程脚本使用实际存在的路径，不继续硬编码旧的 `xc7k325tffg资料/`。新建可执行工程路径和临时路径优先使用英文。

- 现有两个平台目录以厂商资料和示例为主。默认保留 PDF、原理图、原版 RTL、IP、工程配置、安装包和既有构建产物。
- 实现新功能时，优先建立独立工程：`xilinx/projects/uart_hdmi/` 与 `elinx/projects/style_video/`。纯算法公共模块可放 `common/rtl/`，软件参考放 `models/`，公共 PC 工具放 `tools/`；项目专用工具、验证和说明放在对应项目的 `pc/`、`sim/`、`docs/`。按需要创建。
- 从示例复用时记录来源、版本、必需的 IP 和初始化文件，保留版权说明。检查相对路径及 include 路径，确保新工程不意外依赖原示例的缓存或绝对路径。
- 不批量修改 `*.runs/`、`*.cache/`、`*.gen/`、`ip_user_files/`、`outflow/`、`work_*/` 中的生成文件。通过可编辑源文件、IP 参数和工程配置重建。
- 加密 IP 按对应工具和授权使用，不尝试解密或将其当作可移植 RTL。
- 更换工具/IP 版本前先记录基线。不能仅因 IDE 建议升级就升级全部 IP；摄像头示例的说明已记录升级 CSI RX 后 VS 解析异常的情况。
- 工作区现在已有用户创建的 Git 仓库。保留当前分支及用户未提交改动；不得重新初始化、删除或重构大批资料，不自动提交、推送或烧写板卡。

## Git 上传范围

- 用户决定新建仓库，并要求基本只上传 RTL、Python、PDF、Markdown。根目录 `.gitignore` 使用默认忽略加白名单：`.v/.sv/.vh/.svh/.vhd/.vhdl/.py/.pdf/.md`，并保留根目录 Git 规则文件。
- 用户授权整理上传规则后，额外允许项目 `requirements.txt`，用于记录 Python 依赖；继续保留 `architecture.html` 例外。其他 TXT、JSON、YAML、图片和权重仍默认忽略，不因此放开 FPGA 配置或 C/C++。
- `pycode/convertpic/` 数据集仅保留 `README.md` 放置说明；`pycode/styles/`、`pycode/runs/`、`pycode/results/` 留本地。独立 Xilinx 工程的 `vivado*/`（包括 `vivado_fast/`）整体忽略，手写 RTL 放在外部 `rtl/`，构建/预览文件放 `build/`。
- 任意项目的 `sim/` 下所有内容仅留本地，包括 RTL/Python 仿真代码。现有 Testbench、modelsim 等仿真目录和典型 testbench 文件也忽略；后续仿真放入各自项目的 `sim/`，不在工作区根目录建立仿真目录。
- FPGA 项目文件、约束、IP 配置、初始化数据、生成网表、波形、报告、二进制、压缩包、安装包和环境缓存不上传。厂商示例中的生成 IP 目录亦忽略；工程目录内未被排除的手写 RTL 仍可收录。
- `.gitignore` 只控制 Git 收录，不删除或移动本地资料。此上传策略不等同于完整可重建工程归档；本地工程依赖需继续保留。
- 当前白名单未包含 C/C++ 驱动。后续编写 RISC-V C 驱动时遵循当时用户指定的上传范围；不要擅自扩展当前白名单。
- 修改忽略规则后使用 Git 实际匹配检查。不得用 `git add -f` 绕过规则批量加入工程产物；已跟踪文件不受 `.gitignore` 追溯影响，是否已跟踪须另行检查。

## 跨平台实现规则

- 通用卷积、定点运算、行缓存、图像处理及协议解析尽量使用可综合 Verilog/SystemVerilog，并参数化尺寸和数据位宽。
- Xilinx 的 PLL、OSERDESE2、OBUFDS、BRAM/FIFO、DDR IP 与易灵思的 PLL、Interface Designer、MIPI、LVDS、DDR、Sapphire IP 分别封装；不得直接互换厂商原语。
- 建立独立的约束与源文件清单。Xilinx 使用 `.xdc`；易灵思使用项目 `.xml`、`.peri.xml`/Interface Designer 配置与 `.sdc`，不能只移植 RTL。
- 不猜测引脚、I/O 电压、晶振、摄像头接口或 DDR 参数；以实际板卡版本对应的原理图和可复现示例为依据。
- 易灵思实板原理图以用户2026-10-19指定的 `elinx/elinxdemo/Ti60F225_DemoBoard_v4/TI60F225I3-V4_SCH-20261012（原理图）.pdf` 为唯一当前依据（SHA256 `8cf636e4253848cf2bb8a612031bd0fd7e4183a8c59ae7be71b1008aaf669b41`）；旧 `Ti60F225A_V4_SCH.pdf` 仅保留历史资料。KEY1应为P14/GPIOR_22、KEY2应为N14/GPIOR_21，旧P13/N13是LED0/1；各Ti60工程生成脚本/独立电气审查须使用正确映射。J8不作为UART：新图2=3.3V、4=CRESET_N、6=1.8V、8=VQPS、10=GND；使用板载USB串口R4 RX/R14 TX，不能照旧图接USB-TTL到J8。
- 用户已确认 Xilinx 器件 `xc7k325tffg676-2`、板卡「Kindex Base7 FMC版」和易灵思 `Ti60F225`。Xilinx 按本地 `Kintex7_BaseC_FMC原理图.pdf` 核对，G22输入时钟50MHz；易灵思实板已确认对应本地 `Ti60F225_DemoBoard_v4`，采用I3时序模型。
- 用户已进一步确认易灵思实板对应本地 `Ti60F225_DemoBoard_v4`，本轮先复现主机相机/串口链路，再接MIPI。独立移植工程放 `elinx/projects/uart_style_keys/`；DDR/PLL/串化使用V4原理图与现有例程，不套用Xilinx电气参数。用户2026-10-13进一步纠正：此前SC432HAI为笔误，实物是SC431HAI；新手册为`elinx/elinxdemo/Ti60F225_DemoBoard_v4/摄像头SC431HAI_数据手册_V1.1.pdf`。
- 用户2026-10-13指定易灵思本轮显示为720p30：输入/CNN仍显式640×480、无缩放居中显示，HDMI采用74.25MHz、3300×750总周期、H_FRONT=1760的CTA时序；USER_PLL仍为2.970GHz VCO与40/8分频。Xilinx保持原配置。采集/推理FPS与30Hz刷新分开报告；720p60旧构建保存于该工程`build/baseline_720p60_20261013/`。原赛题显示验收条款仍作为来源记录保留，本轮30Hz不能据此宣称原指标完成。
- 本地 BaseC FMC 原理图的 Bank14/15 为3.3V，Bank32/33为1.5V，VCCAUX_IO_G0为1.8V。不能照搬参考MIG的2.0V/HIGH和DDR3-1600；`uart_hdmi`采用1.8V/NORMAL、DDR3-800（400MHz DDR / 100MHz UI）、200MHz系统/IDELAY参考和74.25MHz HDMI像素时钟。构建结束逐项检查实际实现的84个端口映射、电平、方向和Bank；不得仅以DRC通过代替板级电源核对。记录见项目 `docs/electrical_logic_review.md`。
- 四键版按原理图第4/11页增加 KEY2/J26、KEY3/E26、KEY4/G26、KEY5/H26，均为 Bank14/3.3V/LVCMOS33 输入，板上4.7k上拉、低有效；KEY1/D26继续复位。本工程改为逐项审查全部88端口，保持DDR与HDMI电气参数。按键需两级同步、10ms消抖和长按去重，异步路径仅切到同步器首级。
- 摄像头实物型号现已由用户确认是 `SC431HAI`，此前 `SC432HAI` 为笔误。可按本地SC431HAI V1.1手册与V4例程核对；先读回0x3107/0x3108确认ID，再验证供电、复位、I2C地址、lane数、RAW位宽/Bayer、输出尺寸和真实采集FPS，不能仅因型号一致就宣称例程已上板成功。
- 用户反馈彩条实验已有成功基础，调整分辨率和 PLL 可实现 720p，原配置只能实现其所称的“1k”。记录为用户实测反馈；具体平台、修改后的工程/参数和“1k”的精确宽高尚未核对，不据此宣称当前磁盘工程已达到标准 720p60。
- HDMI 时序、像素时钟、同步极性、数据使能及像素读取延迟必须一起验证。720p60 目标采用74.25MHz像素时钟；原厂Xilinx示例为75/375MHz，不能直接标记为标准720p60。独立`uart_hdmi`工程已改为74.25/371.25MHz并通过模型仿真，实屏显示仍未上板验证。

## 数据流、存储和串口约束

- 在接口说明中明确像素布局（RGB/BGR、RGB565/RGB888）、字节序、行序、stride、每拍像素数、RAW 位宽/Bayer 排列及 padding。
- 模块接口明确时钟、复位极性、握手与延迟。跨时钟域使用同步器、异步 FIFO 或完整握手，禁止直接采样多位数据和跨域单周期脉冲。
- 复位在各时钟域同步释放；在 PLL 锁定、DDR 校准和外设初始化完成后启动数据流。
- 串口按实际时钟和实测稳定波特率配置。PC 端负责图片解码/缩放，FPGA 接收定义好的原始像素帧。
- `uart_hdmi`提供标准115200 / 1KB与独立`vivado_fast`的2Mbps / 16KB配置。提速版保持720p RGB565，不改变引脚电平或DDR参数；PC波特率必须匹配FPGA，每包大小不可超过其缓存上限。线速估算不能当作USB/DDR/软件开销均计入的实测总用时；10秒目标需通过真实完整帧ACK与总用时验证。旧标准bitstream保留，其历史指纹仅对应当时源码，当前提速签核在项目`build/fast/`。
- 帧协议必须定义同步标记、版本、尺寸、格式、帧编号、长度、校验、超时以及 ACK/NACK/重传规则，支持从错误或半帧恢复。起步可采用停等传输。
- 串口半帧和校验失败帧不可切到显示前台；接收完成后通过握手在显示帧边界换帧。
- HDMI 持续刷新已完成图像，更新速度与串口传输速度分开计算。不得假定 UART 能传送 640×480 的实时视频。
- DDR 读写考虑地址对齐、突发边界、背压、FIFO 水位和仲裁。采集、推理、显示分别管理帧所有权，禁止写入仍被读取的帧。
- 无背压能力的摄像头输入必须持续服务；若推理速度低于输入速度，显式记录推理取帧策略和计数。不能把主动跳过推理帧隐藏为“全链路不丢帧”。
- 帧发布等待 DDR 写响应完成；显示在垂直消隐边界切换。原画和风格画对比必须关联同一个源帧编号。
- 帧起点的跨域请求可能因AXI背压延迟到有效显示区，不能仅凭待处理请求交换前台。Xilinx验证工程使用寄存、同步且在有效区前一行关闭的安全换帧窗口；错过窗口则等待下一次消隐。DDR读数据写FIFO前同时检查RRESP和RLAST，异常拍不得先写入再报错。
- 所有定点算子记录有符号性、量化比例、累加位宽、舍入与饱和行为，并与软件参考一致。

## 验证与结果表述

- 每个新项目或功能阶段完成时，在对应项目目录创建或更新 `architecture.html` 架构说明图。采用简单、可离线打开的 HTML，标明数据流、模块分工、时钟域、关键接口、缓冲区与当前验证状态；相关实现发生变化时同步更新，避免图与代码脱节。项目 README 链接此图，交付时提供入口。
- 架构图属于用户要求保留的项目说明文件；Git 白名单额外允许名称为 `architecture.html` 的文件，其他 HTML 和工程产物继续遵守原有忽略规则。

- 每次实现先完成与改动相关的模块仿真，再做对应平台综合、布局布线、时序检查及必要上板验证。
- 优先覆盖 UART 错帧恢复、完整帧换帧、FIFO/CDC、图像边界、卷积多通道累加/溢出、AXI 背压和输出像素对齐等关键行为。
- 公共算子对照确定的 Python 定点参考，保存输入、权重、逐层输出和误差；随机权重只用于运算验证。
- 上板记录板卡版本、工具/IP 版本、工程入口、输入参数、资源与时序报告、采集/推理/显示计数、FIFO 溢出、撕裂和实际显示结果。
- 现有 `.bin`/`.bit` 或项目 `last_run_state="pass"` 只说明目录保存了旧产物/旧状态，不能当作当前环境重新构建或上板成功的证据。
- Icarus Verilog 可验证通用 RTL；厂商原语与加密 IP 需要对应仿真库或分层替代模型。未运行综合或上板时，明确写“未验证”。
- 资料审阅与规划任务仅更新约束和说明。后续实现任务可在用户授权范围内修改独立工程；板卡烧写需属于当次明确的实施范围。

## 真正720p分条阶段（2026-10-13）

- 新工程`elinx/projects/uart_style_tiles/`独立保留：默认720p输入/输出1280×720，四条各352×720，中央320列+左右16列重叠；显式vga为两条352×480，640×480处理。显示均按用户要求720p30。旧VGA/Xilinx工程与四模型不改。
- 全局边界外必须在每一层清零；相位特征按全局坐标。每条不得独立发布，必须等全部条输出及最后DDR B，再安全消隐提交完整帧。
- 两配置的`style_profile.vh`和ROM路径在各自`build/<profile>/`，共享RTL字节一致，构建另一个配置不使既有配置指纹失效。`vendor/`及仿真/构建继续仅留本地。
- 当前整机171/256 RAM10、144/160 DSP，CNN行缓存99块。完整尺寸软件四模型整数一致不等于完整尺寸RTL吞吐/实板FPS；当前100MHz算力不能据此保证720p>15fps。先验证640×480基础指标，再做独立CNN时钟与MAC流水，不能冒险提高DDR UI时钟。
- 最终摄像头缓冲建议三个原画bank（采集、最新完整、推理锁住）+两个风格bank，以免推理完成后等待唯一未锁bank的半帧。所有权/主动丢帧显式记录。MIPI、RISC-V、动态权重和FPS叠加尚未集成，不宣称整题完成。

- 分条项目2026-10-13电气/逻辑复查修正：原ASYNC_REG转换须匹配空格，UART与复位使用Efinity原生async_reg并核对实际12个FF；任何DDR/CORE/HDMI PLL失锁须同时复位DDR/UI/像素域，不依赖旧CAL_DONE清零。失锁后有效源图失效，需重传。复查前产物在本项目`build/pre_electrical_review_20261013/`，按最新签核指纹交付；原厂DDR保护内容不解密。

## 摄像头与 RISC-V 独立阶段（2026-10-15）

- 用户确认 SC431HAI 是 demo10 配套模组、排线直连 V4；模组控制口兼容性不适用于裸传感器或其他转接板。SCL/SDA/RESET按V7模组3.3V，RESET高有效；MIPI专用RX Bank2A/2B配置1.2V，实物跳线和电压仍须核实。
- 新整机放`elinx/projects/style_video/build/camera_vga/`，不覆盖旧串口工程或四组学习参数。参考demo10 V7 CSI5.15完整文件及原厂DDR；新建Sapphire3.4.0，不升级参考IP。
- 显式摄像头配置为V7的1920×1080 RAW10四lane，经2×2 Bayer合成至960×540，再裁剪640×480；HDMI维持用户要求720p30。BGGR、摄像头FPS、亮度及真实运行仍未验证，不声称新工程全720p推理。
- RISC-V C在32KB片内RAM运行，通过APB执行开漏I²C、CD6B ID/尺寸读回、按实际VTS限制曝光、1436项真实权重加载、START与PLIC IRQ16。图像DMA经AXI128访问DDR，CPU自身DDR主口关闭。C/ASM/LD继续按现有Git范围只留本地，vendor/build/sim亦忽略。
- 三原画bank为4/6/8MB、双风格bank为0/2MB；claim锁原画，完整EOF与最终B后发布，安全消隐后提交。忙中按键保留最新请求，加载目标单独锁存，不能混淆已加载模型身份。
- CSI datatype属于字节域，不能直接在UI域比较；当前仅同步字节域锁存的格式故障，格式故障整机复位恢复。pixel_per_clk属于像素域，debug属于AXI域；CSI AXI时钟/复位必须实际接入，帧尾校验后再W1C清错误状态。
- 综合资源约RAM212/256、DSP148/160，不能据此宣称时序或实板通过。新工程仍有厂商CSI内部元数据跨域时序待核对；不得用整组异步时钟切断或无依据多周期约束掩盖word_count等路径。只有最终signoff.json明确通过才允许把候选当可交付bit，未签核不下载。
- 两风格bank等待消隐会限制端到端吞吐；单独CNN模型、缩小几何仿真与720p30刷新都不能充当>15fps实板证据。架构、寄存器及当前未完成项以该项目architecture.html和docs为入口。

## 2026-10-16复查补充

- 易灵思串口四键VGA及分条VGA/720p的现有源码、模型、bit与时序/电气指纹已复核通过；这是复核旧构建，不是本轮重建或实板成功。资料复查入口为`style_video/docs/review_20261016.md`。
- 摄像头候选现用独立生成的同版CSI5.15、仅RAW10打包、启用像素侧带；原V7完整文件未改，上一轮候选快照在`style_video/build/baseline_camera_20261015/`。不是升级CSI版本。当前读取像素域关联的datatype/wordcount，不直接跨域采样byte侧总线。
- 真实CSI模型联合预处理发现上一版VS极性错误，现已修复为GENERIC VS上升沿开始、下降沿结束，W1C在结束之后执行。小尺寸连续32帧及完整1920×1080输入到640×480/360的各两完整帧通过。不能再沿用此前由示例计数器推断的反向极性。
- Questa10.7c中真实Sapphire3.4.0 RTL执行当前C固件，I²C/ID/配置、两组2872项学习参数、按键、启动及两次完成中断通过。仿真必须使用与综合一致的四条RAM初始化通道，IP Manager的Testbench目录可能仍带默认示例固件。摄像头/加速器完成为模型，不是整机实板验证。
- 640×360可作16:9调试，帧数据/像素相关运算少25%，但低于原赛题至少640×480；行缓存宽度未改，RAM不同比减少。仅参数化预处理验证了360高度，完整工程默认仍640×480，不能宣称已有360高度bit或720p两倍放大。
- 最新候选RAM212、DSP148，79脚配置审查通过；时序仍未签核，CSI byte→UI/反向setup为−0.561/−0.528ns。当前不得生成交付bit或下载，不能以功能仿真通过替代CDC采样关系与时序签核。

## CSI CDC调查补充（2026-10-16）

- 独立最小CSI复现位于`style_video/build/csi_cdc_515/`，同版5.15、I3、11 RAM/0 DSP已实际综合布局布线；生产工程RTL/IP/SDC保持不变。原生STA确认四lane共8条HS settle/StopState首级只有对应第二级寄存器后继，整机级间最小setup+13.085ns。精确首级例外仅在诊断STA验证，不代表整机签核。
- 仍待确认的是原始word_count到pixel_bits_cnt[18:3]的16个端点和稳定采样窗口。官方指南v3.3第21页DOC-2988声明内部异步CDC并要求配套约束，但修订对应IP5.16，不能自动追溯放行当前5.15。调查与厂商核对问题见`style_video/docs/csi_cdc_investigation.md`，未发送消息或升级IP。
- 新增公共端口压力仿真才显式模拟接收字节时钟在LP期间停振；此前Discontinuous参数本身不代表已经覆盖时钟停振。七组相位/停启/复位用例325个小尺寸好帧、0坏帧，不包含模拟亚稳态或内部元数据稳定窗口证明。自包含复现资料只留本地build，不作为可下载工程。

## 公共PPI替代实现与索引范围（2026-10-16）

- 旧`style_video/build/camera_vga/`的CSI5.15元数据稳定窗口仍未获厂商确认，保持未签核。新`build/camera_ppi/`独立使用已安装D-PHY RX5.8公开PPI、512×44原子异步FIFO及`csi_ppi_bridge.sv`，CSI包头/WC/CRC/RAW10只在100MHz UI解析；不实例化原争议byte2pixel，未升级/解密/修改保护IP，不宣称5.15已经厂商放行。
- 当前支持VC0 RAW10、宽度为16倍数、一个CSI包/一次HS传输；实物SC431HAI包模式尚未验证，同一HS内多包须扩展解析器后重建。FIFO溢出故障保持至复位，包错误使本帧作废。默认1080p RAW→640×480，HDMI720p30，四组原学习参数不变。
- 新整机已实际综合/接口/布局布线及原生STA：RAM204/256、DSP148/160、XLR48995/60800，最小setup+0.289ns、hold+0.026ns。8条D-PHY首级均唯一对应第二级，无组合逻辑，最终级间最小setup+13.555ns；只对首级D精确例外，136条Gray路径保留最大延迟。79脚配置及固件/模型/源码指纹通过，`camera_ppi/signoff.json`=PASS，已生成bit，未下载或固化。
- 合法D-PHY/PPI真实模型六组相位/停振/复位及完整1080p到VGA三好帧通过，另有ECC/CRC/尺寸/中断/超时/溢出恢复测试。数字仿真与CAD不能替代实物包模式、供电/Bayer/FPS和整机并发验收。新入口`style_video/docs/ppi_camera.md`，架构图已更新。
- DIDE语言服务曾观测约3.3GB内存。工作区`.dideignore`排除厂商示例、build/vendor/IP/仿真/缓存，`.vscode/settings.json`减少监控，保留手写RTL导航；这些本地IDE设置不改变综合源清单或当前Git上传白名单。重载后内存降幅尚未测量。本轮CAD单任务、4线程。

## 同一PPI bit的安全复查补充（2026-10-16）

- 用户已在本轮明确确认：摄像头接V4的J4，J2/J3均2–3短接（MIPI Bank2A/2B选择1.2V），不要重复询问同一接法。此确认不等于实际电压、电流或温升已测量。原理图PDF第3页为跳线，J4位于第11页；“J2跳线”与25MHz的“J2封装球位”须区分。
- 同一PPI bit（SHA256 `c82a9b2c0b2b14d03b0c5055d747b7de98e651a579b0f0b9c3ea53fd0b0c577c`）额外复核通过：79实际脚、12 Bank配置、24组DDR数据/OE绑定、SDC按精确白名单重新生成后逐字节一致。生产RTL/配置/固件/模型/bit未改，未重新综合或烧写。
- 新增实际顶层/reset/boot保护测试`sim/check_top_safety.py`，其余IP黑盒并强制状态；开漏四状态、从机ACK、三PLL各自失锁、校准失效、时钟停振与按键复位均PASS，不能称作完整SoC或模拟电气仿真。复查入口`style_video/docs/preflight_review_20261016.md`，本地结果`build/electrical_review_20261016/review.json`。
- SC431HAI手册第14页图1-7/1-8示意单个包经ST/ET/LP，支持当前单包/HS范围，但当前配置实物波形仍未测量。实际出图/Bayer/FPS与DDR/CPU/HDMI并发未验收，仍保留HDMI邻近耦合警告，不宣称零损坏风险或整题完成。

## 摄像头故障退出与未知Flash（2026-10-16）

- 用户明确回答易灵思板现有Flash内容“不清楚或从未烧写过”。不得把未下载的新bit签核当作上电会执行的新程序，也不得据此保证未知Flash的电平配置安全；须先明确启动内容/模式与实际供电，再进入易失性上板验证。本轮仍未下载或写Flash。
- 新增`style_video/sim/check_camera_fault_shutdown.py`，执行已签核新目录的实际RV32机器码，8项错误ID/无模组/SDA常低/SCL常低/配置NACK/尺寸错误/VTS不足/开流NACK均进入安全失败状态：采集关闭、模组复位、I²C释放、CNN不启动，后续1000指令无重试。仅为加速ISA/MMIO/I²C模型，不是Sapphire RTL或实板故障注入。生产RTL/固件/bit未改。
- 配套模组的板级供电、电平适配不能由裸传感器手册推定。SC431HAI手册第9页禁止DOVDD下电时控制口保持高电平，断电插拔/避免板卡带电单独断开模组供电；开漏释放或RESET不能当作电源隔离保证。现有J4和J2/J3接法已确认，不重复询问。

## 两套Ti60工程的首次使用准备（2026-10-17）

- 用户确认UART+HDMI与摄像头两套都在同一Ti60 V4上依次测试。本轮要求检查尤其电平、并说明工程使用；没有代为下载或固化。当前指南`docs/Ti60_programming_guide.md`，两项目README与architecture.html已链接。
- 本次UART选择`uart_style_tiles/build/720p/ti60_style.xml`及其`outflow/ti60_style.bit`（SHA256 `6d1f54b73989ab51ba641c7c8c52ce801806ee552eca34961e4195ee2a8cacf3`），输入/CNN1280×720、2Mbps、GUI选720p；摄像头选择`style_video/build/camera_ppi/ti60_camera.xml`及已记录的PPI bit，处理640×480、720p30居中。不要误选旧UART VGA或未签核camera_vga。
- 现有bit/源码/模型/配置/报告复核通过，非本轮重建或上板。UART66脚、setup/hold+0.387/+0.026ns；camera79脚、+0.289/+0.026ns；两套12 Bank配置完全一致。只读入口`style_video/scripts/check_download_pair.py`，独立结果`style_video/build/programming_review_20261017/pair_720p.json`，不覆盖原signoff、不访问硬件。
- 首次验证使用Programmer JTAG模式+.bit；一块FPGA一次只运行一套。Flash固化使用同目录SPI.hex与工具自动Ti60 JTAG Bridge，默认地址后写覆盖前写，当前没有实现双镜像切换。原理图配置Flash为U14/GD25LQ64/1.8V，非实读Flash ID。HEX启动前缀未独立解码或实板验证，已记录同次头、主体对应与指纹，不把它说成已验证固化成功。
- 两套的四键顺序KEY0星空/KEY1浮世绘/KEY2水墨/KEY3油画，KEY0+KEY3长按逻辑复位不同于板上CRESET_N配置复位。摄像头bit包含CPU固件/权重，不需另烧firmware.bin；摄像头版没有实现UART启动日志。现有Flash仍未知，JTAG易失性下载不会改变下一次上电的Flash内容，带模组上电前须明确启动配置与实际供电。

## demo10参考版本约束（2026-10-17）

- 用户明确要求不参考demo10 V6，只参考V7和V9，且不得修改demo。V7继续作为现有签核工程的采集、电气/DDR来源；V9用于图像问题对照，不能把源码审阅写成已整套移植或实板验证。
- V9实际修改Bayer窗口行相位、一个绿色位置的R/B来源、RAW增益路由和数据/DE/坐标延迟，并调整字节/颜色顺序、加入裁剪；不是新增通用抗锯齿滤波器。V7/V9的peri、SDC、原CSI和DDR RTL逐字节一致。
- V9有效ROM146项，删除显式0x3200..0x3221尺寸/裁剪/镜像写入并配合FPGA裁剪；当前PPI严格检查1920 RAW10/WC2400，不能孤立替换该寄存器表。当前bit保留V7的163项待机命令与末尾受控开流，模型/生产RTL/约束/bit不变。
- 复查记录见`style_video/docs/demo_v7_v9_review.md`；独立仿真`sim/check_bayer_alignment.py`检查四种Bayer相位、彩色边界、逐坐标首尾像素及完整1080p裁剪。真实模组Bayer和光学锯齿仍须实板色卡/画面验收。

## 六风格 Xilinx 独立实验（2026-10-18）

- 用户选定梵高厚涂、莫奈印象派、浮世绘、彩色剪纸、复古漫画、水墨，去掉水彩绘本；先改Xilinx。新项目`xilinx/projects/uart_style_six/`独立于旧四键版，KEY2/J26下一种、KEY3/E26上一种循环六种，KEY1/D26复位默认梵高，KEY4/G26及KEY5/H26保留输入。顺序槽0–5同上述顺序；编号扩为3位，6/7回退默认模型。
- 新参考在`pycode/styles/art6_v1/`：梵高/浮世绘/水墨保留原已记录来源，莫奈/剪纸/漫画是已审阅AI概念图画幅，不能标成名画原作或模型输出。训练仍分开固定训练集与留出集，实际预测与AI概念图分开。
- 第一轮8通道量化学生发生内容塌缩，完整保留于`runs/art6_v1/`，不用于交付；修正实验`runs/art6_v2/`使用12通道五层、膨胀1/2/4/8/16、63×63感受野、无固定XY特征，保留浮点与量化检查点，降低量化阶段学习率。旧四组参数与所有易灵思工程不改。此12通道资源预算针对Kintex7，Ti60后续须另行映射与签核。
- 新项目独立复制卷积RTL、扩六组ROM和12通道分级求和流水，不改变原`common/rtl`。默认720p输入/CNN1280×720，另有显式VGA；两套最终模型/权重需一致、顺序构建并分别验证88脚与时序。生产参数不以正在训练的检查点构建。当前训练/验证状态见新项目`docs/validation.md`及`architecture.html`，本轮不自动烧写。

- 六风格本轮最终选用全部`art6_v2`基础学生，六教师各10轮、学生各20轮；额外剪纸/漫画候选因画面发糊未选。六模型每组完整720p软件整数误差0，实际输出仍有纹理偏重、细节不足，不能把概念图称为板上效果。
- 新工程真实学习参数小尺寸六模型及保留编号、按键/控制、联合UART/DDR/CNN/显示通过；完整1280×720 CNN核心仅冻结梵高模型实跑921600像素、17000005周期，不是六模型完整SoC或实板FPS证明。最终记录在`uart_style_six/docs/validation.md`。
- 两套新bit已实际综合布局布线签核、88脚电气/方向/Bank与时钟审查通过：720p setup/hold +0.337/+0.049ns，RAM367/445、DSP750/840，bit SHA256 `dd940f28a83f12f600077ccb3a7776c65df07c06a23b8a43657e2679b0090726`；VGA +0.389/+0.051ns、RAM184/445、DSP750/840，SHA256 `610ecee8c3ce382f6b2c408a5ef33e83641a111a7458a5e3323ff0f827bd4991`。两套相同权重；继承XDC的按键循环已改显式首级D例外并重建，后级未切。保留已审阅MIG/BRAM/DSP警告，不称零警告。
- 37个旧基线文件与旧四风格两bit指纹保持一致。本轮未下载或固化、未访问串口/JTAG；Ti60继续原四风格，12通道新配置须独立做资源与时序映射。新架构图含使用与bit入口，按项目GUI配置匹配720p或vga。

## 六风格镜像边界修复（2026-10-19）

- 用户要求消除四周彩色框；实测原因是逐层zero padding经膨胀卷积形成外圈31像素伪影。仅Xilinx uart_style_six改逐层reflect-101，小轴length<=dilation时edge回退；原图尺寸、视野、六组学习参数/编译权重保持不变，旧模型默认zero行为保留。旧补零版97文件及两bit快照在build/baseline_zero_border_20261019。易灵思与公共/旧四风格不改。
- 独立软件边界实现pycode/art6_border.py，预览render_border_art6.py输出results/art6_border_v1；不要将旧checkpoint直接forward的zero输出当新版。正常完整图在所有层使用mirror，后续移植分条时仅在全图真实边缘使用该策略。
- 首轮32位通用读地址setup −0.564ns拒绝交付；最终九tap译码、限宽行龄/环形下标，MAC与握手延迟不变，约束不放宽。六模型全720p软件整数误差0、内部31像素以外RGB565保持原值，24组纯色输入无色框；小尺寸/极小轴/联合链路及优化版梵高完整921600像素核心RTL通过，周期17000005。不是六模型完整SoC或实板FPS验收。
- 镜像720p新bit重新CAD/88脚签核：setup/hold +0.206/+0.053ns，RAM367/445、DSP750/840，SHA256 `5d28c2c9e856df0d43e614aaff16a434f59f6ad30c23b9a8299d77ea96a6831c`。
- 镜像vga新bit重新CAD/88脚签核：setup/hold +0.461/+0.050ns，RAM184/445、DSP750/840，SHA256 `17ecf121c1cd401d178f1628568cd28f078ab570f750902345f02518dde62295`。
- 两配置同一组参数，旧四风格37基线文件/两bit及原训练启动指纹复核保持一致；本轮未打开串口/JTAG、未下载或固化。使用入口仍为项目architecture.html、README及docs/validation.md；新验证编排finish_border.py，原finish_art6.py为兼容入口。

## Ti60 新选四风格移植（2026-10-19）

- 用户选原六风格 ID 0/3/4/5，并确认先做 UART＋按键＋HDMI。新建独立 `elinx/projects/uart_art_styles/`，不修改旧工程、demo V7/V9 或训练参数。KEY0梵高厚涂、KEY1彩色剪纸、KEY2复古漫画、KEY3水墨；默认梵高，KEY0+KEY3持续一秒逻辑复位。图片仍从串口上传。
- 同一96×720核心实际map比较：四/六风格RAM173、DSP153相同，六风格多205 LUT4、133 ADD、58 FF，因此按用户条件选四种。风格数不成倍增加MAC，但不能声称零资源影响。对比只代表核心综合，完整资源以各配置签核为准。
- 保留art6_v2十二通道五层/dilation1/2/4/8/16和真实边界逐层reflect101；MAC三个输出通道复用以适配160 DSP，行缓存不存扫描padding列。条带96宽、中央32列、左右各32 halo，720p40条、VGA20条；人工条带边界不反射，全图外每层输出清零，不能套回旧6通道/XY/16 halo参数。
- 默认1280×720输入/CNN、720p30；显式VGA640×480居中。两配置已分别实际CAD/66脚签核：720p RAM245/256、DSP153/160、XLR26095/60800，setup/hold +0.324/+0.026ns，bit SHA256 `51be5fa44c58a43a3084fa445d8e0d335f2305afc4d7d482887e4222e4f70d29`；VGA同RAM/DSP、XLR26069，+0.483/+0.028ns，SHA256 `86992a925fc2257c580ad53016f3e1a5be784b190e90e61b96868897b63806be`。两套15个ROM文件相同，旧129基线文件未变。
- 四模型小尺寸逐像素/联合UART+DDR+显示和720行左右边缘两条通过；四模型全720p/VGA软件整数分条一致。完整高度RTL只跑梵高两个条带，不能称完整SoC吞吐；复用/halo增加周期，未证明10秒完整上传或>15fps。PC END等待至少15秒，DATA短超时不改；主机相机仍是停等照片上传。
- 继承V7的DDR/PLL/引脚配置，UART/按键3.3V、时钟/TMDS Bank1.8V、DDR1.5V，MIPI未启用；原HDMI邻近耦合警告保留。12个单比特首级精确例外，116条Gray路径有最大延迟，未放宽时钟。CAD不能代替实物电源/温升/并发/FPS验收，本轮未打开串口/JTAG、未下载或固化。
- 架构与使用入口为本项目README、architecture.html和docs/validation.md。新vendor整体仅留本地，sim/build亦忽略；本地配置、ROM、报告和bit不上传。资源余量仅11 RAM10/7 DSP，后续摄像头/RISC-V不能直接复用本版并宣称容量/性能通过。


## 正确Ti60原理图复核完成（2026-10-19）

- 统一入口 `docs/Ti60_correct_schematic_review.md`，只按TI60F225I3-V4_SCH-20261012正确PDF及设计说明第34页确认KEY1=P14/GPIOR_22、KEY2=N14/GPIOR_21；所有四项目均加入独立board_spec.py，签核绑定正确PDF与脚本指纹。J8不能接USB-TTL，正常使用板载USB串口；A1/VQPS是专用电源，不分配GPIO，不进行安全熔丝操作。
- 已实际顺序重建uart_art_styles 720p/VGA、uart_style_tiles 720p/VGA、uart_style_keys VGA、style_video camera_ppi，共六套。生产RTL/IP、学习参数和固件未改；仅两个按键输入绑定改变，所有66/79实际脚、12Bank、电平/方向与最终STA复核通过。原HDMI邻近耦合警告保留；并非零物理风险或已上板。旧bit/配置/报告各自保存在build/baseline_wrong_schematic_20261019。
- PPI重新做精确同步首级拓扑与最终native STA，未用旧证明替代新布局检查；camera_vga仍为未签核CSI候选，不放行。demo V7/V9未修改，未参考V6。当前默认bit指纹与报告：
  - uart_art_styles/720p：setup/hold +0.382/+0.027ns，SHA256 `927f0869f6593d32c579c16a5b446ba3c8a4d2fc058260be8b7e0bd80d5f6e62`。
  - uart_art_styles/vga：setup/hold +0.394/+0.027ns，SHA256 `2efafde3444f6ec473fa7f1c2bbbdf3ecd8210ad6c3e4f452ff403f762d8f73f`。
  - uart_style_tiles/720p：setup/hold +0.416/+0.029ns，SHA256 `dfae2093b2b13cc33b1a901b1d431c3946cfc774309dab86255112f48a45aef8`。
  - uart_style_tiles/vga：setup/hold +0.535/+0.026ns，SHA256 `d80ea36150647f6d96120302dd13be82322be1c8dd95b428ab25416052c03ae7`。
  - uart_style_keys/vga：setup/hold +0.301/+0.028ns，SHA256 `15f2f8f32ae6f9990bdc8efdcba04ffcab00c52b2abc6a73170ad6bd13f58d3c`。
  - style_video/camera_ppi：setup/hold +0.302/+0.026ns，SHA256 `7fc292efc91c6a28c1121dfb57224d63828ceb0d35fcd5dfffebae660d82bc23`。
- 本轮未访问真实串口/JTAG、未下载或固化，实物供电/温升/信号质量/现场功能未测量。后续不可再将历史P13/N13引脚或旧签核指纹当作当前板卡依据。

## Ti60四风格资源优化与再次电气复查（2026-10-19）

- 只修改uart_art_styles/rtl/art_conv3x3.sv：五个浅偏置表映射逻辑ROM释放24 RAM10，首层九个全精度乘法用逻辑释放9 DSP；时钟使能、同步读取/流水、定点参数、四模型、尺寸、条带/镜像边界和验证周期保持。其余Ti60/Xilinx/demo/训练参数未改。
- 优化版720p已实际Efinity2026.1.132/I3全CAD、66脚/12Bank/电平/方向及最终STA签核：RAM10 221/256，DSP 144/160，XLR 26161/60800，setup/hold +0.376 / +0.028 ns，bit SHA256 `66a05fbff2f22d6a7029fb1905193a9904444da8534cfdc0213eddfbbd90e571`。本轮旧正确引脚版本203文件保存build/baseline_resource_20261019，不作为当前下载入口。
- 优化版vga已实际Efinity2026.1.132/I3全CAD、66脚/12Bank/电平/方向及最终STA签核：RAM10 221/256，DSP 144/160，XLR 26212/60800，setup/hold +0.395 / +0.026 ns，bit SHA256 `89a63644807d73fbb3f36a50070dabb0934cb6747ad4056a5505c7278e582cff`。本轮旧正确引脚版本203文件保存build/baseline_resource_20261019，不作为当前下载入口。
- 两套peri.xml与正确引脚基线逐字节相同；12条单比特首级/116条Gray最大延迟保留，不放宽时钟。四模型五层/联合链路及720行梵高左右条带通过，同像素/周期；后者并非整帧SoC或实板FPS。全部六套当前发布及其他119冻结文件复核入口为本项目build/review_resource.py和build/resource_review_20261019/review.json。
- 架构/README/验证说明已更新，最新以docs/resource_optimization.md为准。XLR增加是用充足逻辑换紧缺RAM/DSP，不宣称所有资源都减少或相机/RISC-V可直接塞入。未打开串口/JTAG、未下载/固化；物理供电、电流、温升、信号质量和未知Flash行为仍未实测，HDMI邻近耦合警告保留。

## 摄像头新四风格独立版（2026-10-22）

- 用户选择直接移植梵高、剪纸、漫画、水墨。新工程elinx/projects/camera_art_styles，旧四个Ti60项目与六套发布复核通过且未修改；不改demo V7/V9。
- SC431HAI1920×1080 RAW10经原公共PPI、2×2 Bayer和裁剪640×480；DDR三原画/双输出、Sapphire3.4.0运行时1217项32位权重写入/START/PLIC、按键及C/I/H叠加。art6_v2十二通道五层、逐层reflect101，核心32+32halo+32=96宽。原新UART参数不改。
- 固件25032字节，真实Sapphire两模型2434项、四模型小尺寸CNN/DDR、当前固件8故障安全退出及顶层保护新跑通过；PPI/Bayer/采集等复用证据以逐字节一致性和原路径指纹绑定。完整640×480单梵高全部20条输出通过，46822062周期、模型等效2.136fps；不是完整RAW/SoC/实板FPS，不能写成>15fps。
- 最深行缓存拆双银行节省8 RAM、单周期不变。实际全CAD/79脚电气及精确CDC签核：RAM246/256、DSP148/160、XLR39156/60800，setup/hold +0.444/+0.026ns，最终D-PHY级间+13.781ns，bit SHA256 `f885bcd91325ed9308594ca2e65b13ecafa086d75e3e532ea14a3c367cb4cc53`。
- 当前候选/发布入口build/camera_ppi/ti60_camera.xml、outflow/ti60_camera.bit与signoff.json；架构和验证见本项目architecture.html、docs/validation.md。电气peri与修正旧摄像头版逐字节相同、无放宽时钟。本轮未JTAG/串口/下载/Flash，原HDMI耦合警告及实测供电/模组包模式/Bayer/FPS待验收边界保留。
- 本结构100MHz理想上限约3.014fps，>15fps及原赛题显示刷新尚未完成；720p30继续用户调试要求。下一阶段需独立轻量学生/流水存储重构，不能把当前bit或30Hz当整题完成。新vendor整体忽略，C/ASM、build/sim继续仅留本地。

## Ti60 UART 720p30 实屏故障诊断（2026-10-22）

- 用户反馈 uart_art_styles 实屏「输入不支持」，坚持720p30，不要求提供屏幕型号。不能由此宣称屏幕兼容或唯一根因已确认；完整END ACK、实物TMDS波形及EDID仍未取得。停止的build/720p60只保留本地尝试记录，不可下载。
- 原版确为74.25MHz／3300×750／30Hz；仅DVI式TMDS视频、没有AVI；像素及串化复位还依赖DDR校准。独立build/720p30_diag保持原1280×720输入/CNN、2Mbps、四模型与所有引脚电平，增加未提交原图时八色彩条，像素复位不再等待calibrated，UART/CNN/DMA仍等待校准，三PLL失锁和停钟保护保留。
- 新显示复用V7公开端口的原厂受保护HDMI TX与依赖，指定RGB/VIC62，逐字节复制vendor/hdmi_v7并绑定原文件指纹；没有解密、修改demo或升级IP。Questa实际运行该TX公开符号流，两完整帧／33个AVI校验和及BCH／RGB解码通过；V7公开HS边沿6次±1像素间隔差异和保护区位宽／未驱动线警告如实记录，不宣称HDMI合规认证。
- 新诊断版实际全CAD／66脚／12Bank／精确CDC签核PASS：RAM223/256、DSP144/160、XLR27241/60800，setup/hold +0.449/+0.029ns，bit SHA256 bc4ddc979570d54dc6ecededd9962f8747359d542b8186687cced22686f8d62e。当前入口本项目build/720p30_diag/outflow/ti60_style.bit和signoff.json；12原生UART/复位FF及116Gray约束、实际顶层复位黑盒测试通过。旧七套源码/配置/报告/bit复核保持一致。
- 先JTAG下载诊断版看无需上传的彩条，再用原GUI选720p／2Mbps上传；若彩条仍不支持，继续核对真实时钟／串化／信号完整性或屏幕模式能力，不能靠降低CNN帧率或改电平解决。本轮未访问串口/JTAG、下载或Flash，实屏故障仍待验证。架构和使用入口见uart_art_styles/architecture.html与docs/hdmi_720p30_diagnosis.md。

## 用户改为恢复UART 720p60（2026-10-22）

- 用户反馈两版720p30均「输入不支持」，现明确恢复720p60，覆盖本工程此前30Hz偏好。本轮仅uart_art_styles的新build/720p60_hdmi，不改摄像头旧版和其他工程；停止的build/720p60仍是不可下载历史尝试。
- 相对720p30_diag仅水平前沿1760→110（1650×750）和AVI VIC62→4；74.25/371.25MHz PLL、12Bank、66脚、电平、LVDS10位DDR/P-N反相、2Mbps UART和1280×720输入/CNN四模型不变。保留启动彩条与像素不等待DDR校准，DDR客户端仍等待校准，三PLL失锁／停钟保护保留。V7/V9原demo实际1080p60，通用video_720p默认才是720p60，勿混称。
- 新60Hz版已实际CAD／电气／精确CDC签核：RAM223/256、DSP144/160、XLR27237/60800，setup/hold +0.437/+0.030ns，bit SHA256 433462533aa33f2046f7c62982352ed46d4020123821078ab7d0f4985dd667dd。原八套发布的源／配置／报告／bit保持一致，12原生UART/复位FF属性复核通过。
- 真实V7 TX公开输出两完整60Hz帧、16个AVI的VIC4／RGB／校验和／BCH、RGB解码、新顶层复位保护通过；原±1像素行同步差异和警告保留。平均显示读110.592MB/s、活动峰值148.5MB/s，消隐关闭仍留约22.22µs整行裕量，预算不是实测DDR/CNN并发或推理60fps。
- 当前入口uart_art_styles/build/720p60_hdmi/outflow/ti60_style.bit，说明docs/hdmi_720p60.md和architecture.html。用户自行JTAG测试，下载后先看彩条、再原GUI选720p/2Mbps上传；本轮未代为下载／Flash，60Hz实屏是否解决仍待验证。
- 补充实际reader+pixel_fifo_efx+原厂FIFO完整RTL+60Hz扫描联合模型：两连续完整帧1843200像素、14400突发／230400拍逐值通过，零欠载／读错误；有效区排队bank切换在下一帧h3/v0才提交。AXI为有界合成从机（地址0..7、首拍13、间拍5/24周期），FIFO有效区最低1字，不能作为真实DDR/CNN并发带宽保证。回执sim/hdmi60_reader/verification.json绑定本次生产源，附到build/720p60_hdmi/final_review.json。

## 摄像头版恢复720p60（2026-10-22）

- 用户已确认UART720p60可以显示，并要求摄像头版也修改。新建camera_art_styles/build/camera_ppi60独立发布，旧九套源／配置／报告／bit保持。输入SC431HAI1920×1080 RAW、处理640×480、四模型、25032字节固件、CPU HDL/四条Boot RAM不变；HDMI为1280×720p60居中，H60叠加，先启动彩条。原赛题推理>15fps仍未完成，不能把60Hz显示当60fps推理。
- 实际新显示TX与已实屏UART60版逐字节相同，V7受保护模块未改／未解密；79实际脚、12Bank与整份peri.xml和旧摄像头完全一致，MIPI1.2V输入、SCL/SDA3.3V开漏和模组复位保护保持。像素不等calibrated；UI/CPU/MIPI/模组仍等待校准，PLL失锁和停钟保护保留。
- 新raster/system/overlay变体、640×480居中、三完整帧彩条/同步/坐标/欠载恢复/H60字形和新实际顶层开漏/从机ACK/PLL/校准/停钟/按键保护仿真通过。显示回执最初status PASS字段补result别名，保留原仿真日志及其他源指纹，无RTL变化或伪造重跑。复用旧采集/CPU/CNN/固件故障证据时保留原路径与明确同字节绑定。
- 实际Efinity2026.1.132/I3全CAD两次路由与两轮原生DPHY证明后签核：RAM248/256、DSP148/160、XLR40234/60800，setup/hold +0.319/+0.026ns，最终8条首级只接第二级、级间最小setup+13.508ns，17scalar/136Gray/14FPS束/8DPHY首级精确约束，未整组切跨域。bit SHA256 d00b8debc5c0e0146e897a6bc205eda1557e29b74760e4cbdc6235ee964403b3。
- 当前下载入口camera_art_styles/build/camera_ppi60/outflow/ti60_camera.bit，使用见docs/hdmi60.md和architecture.html。固件/权重已包含，不另烧firmware、不需串口传图；沿用已确认J4和J2/J3 2–3，不重复询问。本轮未下载或写Flash，新摄像头实屏、真实C/I FPS、Bayer/包模式/DDR并发仍待验证；未知Flash启动边界和原HDMI警告保留。

## 摄像头持续彩条的独立诊断版（2026-10-23）

- 用户自行运行camera_ppi60后，持续一分钟仍彩条、C00/I00/H60。此版像素不等DDR校准，OSD默认开启；不能由此认定DDR校准、CPU执行、摄像头已开流。静态核对APB地址、I²C位序/地址、模组复位和V7的163项表未发现确定错误，底层根因仍待实板日志，不能把诊断功能称为无图已修复。
- 独立camera_art_styles/build/camera_debug60新增只读APB观察、PPI FIFO的UI侧事件/包头、原DDR/CNN计数及camera_diag_uart。板载R14 TX由恒高改为115200/8N1，每秒115字节@CAM1记录12个32位字段；UART复位取ddr_reset，不等待calibrated，可报告CPU保持复位。无新总线命令/ready/enable/reset驱动，无新增跨域payload；SDA/SCL读样本仅最后一次APB读回，不冒充实时电压。
- CPU25032字节、四条RAM、四模型、sensor配置、640×480处理、720p60显示、全部79脚/12Bank与peri均保持。只在rtl/diagnostics和scripts/diagnostics新增变体，不修改原camera_ppi60、其他十套发布或demo V7/V9。
- 新真实串行逐位解码、实际top观察44项及顶层开漏/ACK/PLL/校准/停钟/按键保护通过，PC解析/假串口8项通过；IP/system黑盒范围明确，不写成完整SoC或摄像头实物通过。
- 实际单任务四线程全CAD、两次路由/两轮原生D-PHY证明及79脚电气签核PASS：RAM248/256、DSP148/160、XLR41268/60800，setup/hold +0.322/+0.026ns，8条唯一二级链最小setup+13.339ns；17标量/136Gray/14FPS束/8DPHY首级精确约束。最终SDC异地重建一致、12复位FF原生属性及十旧发布指纹复核通过。
- 当前排障入口build/camera_debug60/outflow/ti60_camera.bit，SHA256 d34780d0e3616a2b33e5399f97731d45cdd7053091209c6ee241cc12f7f376b2；signoff.json/final_review.json绑定同次构建。PC只读工具pc/camera_diagnostics.py可--list或--port COMx，默认115200，DTR/RTS打开前设False，不发送串口数据；Ctrl+C停止。日志与sim/build继续留本地。
- 彩条故障流程及错误码见docs/camera_diagnostics.md，architecture/README已同步。等待真实CAL、B阶段/失败原因、PPI Q/L/E及DDR/CNN累计C/I定位；本轮未访问串口/JTAG、未代为下载或写Flash，不能据CAD保证物理零风险，原未知Flash和HDMI耦合边界保留。

## CAM1实板记录与CAM2细分追踪（2026-10-23）

- 用户提供两条真实CAM1记录（第二条50+65字节拼接合法）：B3/flags34B9；相邻周期L+32400、RAW+15552063、VS+30、捕获错误+30、C/I均0、E+2552、最后包头1D09602B（RAW10/VC0/WC2400/ECC1D）。DDR已报校准、CPU已配置并发送开流、采集和权重有效；仍不能声称DDR完整读写或端到端采集通过。原始用户记录/解析在camera_art_styles/build/board_log_20261023。
- E是错误状态周期/事件计数，control_error高的每拍都会增加，不能称2552个独立坏包。当前证据集中于CSI错误标志/帧完整性/写帧发布，未唯一确定根因，不擅自改电平/跳线或屏蔽CRC、SoT、完整帧检查。
- 发现旧D-PHY联合测试把错误输出悬空/桥输入接0。独立sim/dphy_error_repro新接真实Control/Escape/SoT并和接0实例逐RAW对照：小尺寸50/50/29好帧，完整1080p输入3个640×480好帧，未复现实板持续错误。使用与生产同次生成/同公开参数的厂商ModelSim版本，不称整份保护实现同字节或实物模拟行为等效；旧回执不改。
- 新独立build/camera_packet_trace60保留所有原判据，仅追加UI域12项观察和每帧首次bad上下文，桥18用例/68断言/30807周期逐拍等价，剥观察块恢复原RTL完全一致。CAM2协议24×32位、223字节、115200/8N1；前12字段同CAM1，追加control周期/上升沿、SoT、lane、header、format、CRC、包中断、FE、超时、FS重叠、first_error_context。无新增跨域payload或控制驱动。
- 实际单任务四线程全CAD/79脚/12Bank/两轮D-PHY证明签核PASS：RAM248/256、DSP148/160、XLR42437/60800，setup/hold +0.403/+0.026ns，8唯一二级链最小setup+13.248ns。17标量/136Gray/14FPS束/8DPHY精确首级约束保留；12复位FF属性、SDC异地重建及十一套旧发布指纹复核通过。固件、BootRAM、四模型、sensor/DDR/HDMI参数与peri均保持。
- 当前细分排障bit为camera_art_styles/build/camera_packet_trace60/outflow/ti60_camera.bit，SHA256 63e250e5d74dc78610ad521c623ccc4b0820ff3381cf316debebdab5dd547b81；签核和final_review绑定同次构建。本轮未下载/Flash/打开串口。新PC工具pc/camera_trace.py只读，CAM1工具不解析CAM2；串口助手拆包可重组，不因此判断串口损坏。架构/README/docs/packet_trace.md与使用指南已同步，等待用户CAM2实板记录，不能称无图已解决。

## CAM2已定位SoT及空闲包边界恢复（2026-10-23）

- 用户真实CAM2：E=sot_records=49628，control/header/format/CRC/FE/timeout等分项0；C/I0、捕获错误594、VS595，first_error_context=22000400，即SoT/WAIT/VS1/HS0/第4行/raw_bytes0/sync_seen0。原始记录在camera_art_styles/build/board_log_20261023/camera_cam2_user.txt；这是SoT分支导致丢帧的证据，未证明物理SoT是假报，记录不含队列和模拟波形。
- 官方D-PHY指南说明真正SoT错误也不带valid/sync，禁止简单AND valid/sync筛掉。独立新rtl/sot_recovery/csi_ppi_bridge_recover.sv仅允许state WAIT、sync_seen0、四队列空、本记录valid/sync0的孤立错误记软告警；包内/排队/部分同步SoT保持硬错。所有CRC/ECC/VC/WC/尺寸/FE/超时/溢出与下游精确像素、EOF、最终DDR B发布检查保持。
- 总SoT仍计数，新增soft_sot_records；CAM2协议与24字段不变，flags低15位保持，bit15为软计数非零，高16为软计数16位饱和值。底层32位计数回卷后重新计数，不是永久sticky；该计数可与其他硬错误同拍，不等于已恢复完整帧，不影响帧发布。
- 新26场景109检查/31470逐拍单位验证与9场景75检查的真实FIFO/Bayer/packer/writer/pool背压链路通过：旧3完整CRC好帧捕获0/context22000400，新实际恢复RTL捕获3、RGB565逐值一致且最终B后才发布；缺RAW/FS/FE、部分同步、HEADER/PAYLOAD/CRC/非空队列SoT均保留拒绝。简单valid/sync过滤反例会错误发布，明确不交付。不是实物DDR/CNN/CPU联合验收。
- 新独立build/camera_sot_recover60实际单任务四线程全CAD/79脚/12Bank/两轮原生DPHY证明签核PASS：RAM248/256、DSP148/160、XLR42423/60800，setup/hold +0.445/+0.026ns，8唯一二级同步链最小setup+13.478ns。17标量/136Gray/14FPS束/8DPHY精确首级、12原生复位FF、SDC异地重建和十二套旧发布指纹复核通过。固件/BootRAM/模型/sensor/DDR/HDMI/peri保持，不调PHY采样或电平。
- 当前建议JTAG临时测试camera_art_styles/build/camera_sot_recover60/outflow/ti60_camera.bit，SHA256 177031364a8352fb59670fe8ba7b817d2535132f561b2a6a29dc39a5ae63f65a。仍用115200/CAM2及pc/camera_trace.py，观察C/I与画面，若不出图保留新记录。architecture/README/docs/sot_recovery.md与使用指南已同步；本轮未打开串口/JTAG、未代为下载或写Flash，实板命中恢复边界及出图尚未确认。
- 当前未实现行号/FS-FE帧号关联，CRC/行数不能理论排除丢行加重复行或特定多重故障拼接，不声称任意故障下可证明原帧。恢复不会补丢失行或提升CNN速度，>15fps仍未验收；保持未知Flash及HDMI耦合等实物边界。

## 摄像头画质对照与3:2放大（2026-10-23）

- 用户自行运行SoT恢复版后报告C30/I02/H60并有图像；暗处纯色，梵高/水墨近黑，亮处仅少量轮廓。此为实板功能进展，不代表画质/Bayer/曝光/DDR并发合格。对同一测试照片做5档软件压暗，冻结梵高/水墨模型未变整幅黑，因此不能把现场异常唯一归因为光线暗或立即重训。实际firmware.bin中的4×1217数据字及1217地址已逐项对上冻结模型导出；不等于板上权重RAM读回。
- 新独立camera_art_styles/build/camera_view60，新增rtl/view变体，不改13套旧发布、demo V7/V9、固件/Boot RAM/模型、sensor寄存器、PHY、PLL或peri。处理保持640×480，HDMI仍标准720p60；同步640×16行缓存做3:2最近邻放大为960×720，左右各160列，新增2 RAM10，不称960×720真实推理或新增细节。
- 启动原画；单按KEY0梵高、KEY1剪纸、KEY2漫画、KEY3水墨；KEY1+KEY2按住0.5秒回原画，KEY0+KEY3一秒复位保持。组合键按下初期可能产生一次单键风格请求，随后原画为准。模式在整帧引擎启动锁存，原画复制复用source claim/lock、相同DMA、最后DDR B及安全消隐commit，不允许直接显示未锁原画bank。I只累计CNN完成，原画复制和重复刷新均不计入I。
- 原粉色欠载标记改为红黄棋盘，可明确区分显示错误与风格色块。每秒CAM3/33字段/304字节/115200，前24同CAM2，追加源/输出像素数、RGB和、模式；pc/camera_view.py只读。源统计为最近完整预处理帧，输出为最近成功作业，未按帧号配对，不当像素误差；本版尚无板上权重读回/图像导出。未新增跨域多位payload。
- 新真实CNN/DMA四模型128×24逐像素整数误差0、原画逐值/整帧模式锁存/最终B/背压/三类AXI错误恢复、输出RGB统计通过。4完整扫描帧4950000周期、缓存空时不误报、真实欠载棋盘及下帧恢复通过；实际reader+真实厂商FIFO两完整帧1382400显示像素/614400源读/4800突发、有效区排队bank消隐换帧和有界AXI下零欠载通过。不是实物DDR/CNN并发证明。按键/源统计/系统I计数/CAM3逐位串行与305分片解析/新top安全黑盒测试通过。
- 实际Efinity2026.1.132/I3完整CAD、79脚/12Bank及两轮原生D-PHY证明PASS：RAM250/256、DSP148/160、XLR43795/60800，setup/hold +0.326/+0.026ns，8唯一二级链级间最小setup +13.539ns。17标量首级/136Gray最大延迟/14FPS束/8D-PHY精确首级保持；12原生复位FF、SDC异地重建、13旧发布指纹及新签核fresh audit通过。
- 当前bit为camera_art_styles/build/camera_view60/outflow/ti60_camera.bit，SHA256 153e8e6dd931168d75a6e65a016f4d6f72ee934b00a75e9ddeefe59cc91852f5；signoff/final_review绑定同次构建。README、architecture.html、docs/camera_view.md及首次使用指南已更新。未打开串口/JTAG、未代为下载或Flash，原画/Bayer/亮度和四风格实板对照仍待用户测试，不能宣称黑屏/画质根因修复或>15fps达标。电平保持，原HDMI耦合及未知Flash/实际供电边界保留。

## CAM3定位偏置映射错误与独立修复（2026-10-23）

- 用户提供真实CAM3，boot3/capture2634/inference148/capture_errors0，CSI硬错误各分项0、SoT214111保留，mode14表示剪纸1且非原画；源RGB均值约16/16/16，输出恰8/125/74。用户进一步反馈原画可辨识但略绿，960×720放大已实板确认。原始记录/解析在camera_art_styles/build/board_log_20261023/camera_cam3_user.*；源/输出未配对同帧，均值不能证明每像素恒定。
- 独立build/cnn_map_probe真实Efinity2026.1.132原CNN综合网表+原生RAM/DSP/FF/LUT模型，96×64/RGB16/剪纸，复现mapped4d7e0b vs RTL555f8e，RGB565展开正好实板8/125/74。旧长仿真在已获得错误后手动停止，回执sim/cnn_mapped/reproduction.json明确REPRODUCED_MISMATCH，不能记完整帧PASS。短逐拍探针显示输入和权重一致，首层首组偏置mapped0000116c00000fc1fffff223 vs RTL000015f600001281fffff223；动态数组索引+动态子位段写入经当前综合映射后通道错位。
- 新rtl/bias_fix/video_conv3x3_fixed.sv对每输出通道采用独立常量位置译码写32位偏置；除模块名与这一写入块外，可静态还原为原卷积逐字相同。集成变体只改模块名。运行时1217事务/计数不能代替实际参数映射正确性，后续类似运行时参数存储改动必须增加实际映射后数值回归，不能只跑RTL和时序。
- 独立修复工程build/camera_bias_fix60保留14套旧发布、demo V7/V9、所有训练模型、25032字节固件/BootRAM、sensor寄存器、PPI/DDR、PLL、整份peri、电平、CAM3、启动原画/四键/KEY1+KEY2预览和960×720放大。旧camera_art_styles各运行时偏置版保留为失败/诊断历史，不能继续把它们视为画质验收通过或最新交付。
- 修复后真实CNN/DMA四模型128×24逐像素整数误差0，原画/模式整帧锁存/统计/背压/最终B/三类AXI错误恢复通过。独立实际修复综合网表24×40四模型每种960像素完整帧，总3840像素与RTL全相同，固定RGB16输出也独立对上Python整数参考：6a5243/555f8e/587572/bababa。原生模型11287条未连接端口告警保留，无Error；是模块级无延迟网表验证，非完整摄像头SoC、时序后仿真或实板画质。
- 新版实际全CAD/79脚/12Bank/两轮原生D-PHY签核PASS：RAM250/256、DSP148/160、XLR44268/60800，setup/hold +0.228/+0.026ns，8唯一二级链级间最小setup+13.602ns；17标量首级/136Gray最大延迟/14FPS束/8D-PHY精确首级、12原生复位FF属性、SDC异地重建及14旧发布指纹复核通过。
- 当前bit为camera_art_styles/build/camera_bias_fix60/outflow/ti60_camera.bit，SHA256 500e118bb3108d6e819877eeda2c9ce045e700be823c6300f11cb1a999cfb29e。signoff/final_review绑定同次构建；README、architecture、docs/bias_mapping_fix.md及首次使用指南为当前入口。未代为下载/Flash/打开串口，旧错误已在网表复现并修复，新实板画质仍待确认；原画偏绿/Bayer/白平衡和完整ISP尚未解决，CNN吞吐仍约2fps，不能宣称>15fps达标。


## 摄像头真正720p与独立CNN时钟（2026-10-23）

- 用户现已认可camera_bias_fix60四风格实板效果，认为暗场有各自色倾向；保留该VGA基线/全部模型。本轮不盲目更改曝光、白平衡或训练参数。用户授权清理无用中间prj，实际仅清理21个可再生work_syn/work_pnr/SDC副本目录，251241127字节约239.6MiB；项目XML、必要IP、bit、报告、签核链和demo均保留。记录camera_art_styles/build/cleanup_20261023.json。
- 新独立camera_art_styles/build/camera_720_fast与rtl/p720，SC431HAI/V7传感器表、PPI/SoT恢复、固件25032字节和四组1217项模型保持。新Bayer双线性插值按floor(3*x/2)、floor(3*y/2)将1920×1080全视野变为真正1280×720，不使用旧960×540裁640×480；HDMI直接1280×720p60全幅，取消旧960×720放大。
- 采集记录178→179位、word索引16→17位，覆盖115200个128位数据字；完整EOF/最终DDR B、三原画4/6/8MB与双输出0/2MB所有权保持。条带中心32→48、左右halo32，宽112共27条，末条保留32列；每层reflect101与整数运算保持。
- CNN计算/输出流水重叠、舍入相加与移位饱和拆级，固定通道偏置写入修复保留。仅CORE_PLL新增cnn_clk输出，VCO/反馈/UI100MHz/DDR PHY400MHz/HDMI不改；200MHz两轮实际布线负setup，不交付，尝试报告留attempt_200mhz。最终CNN166.667MHz，跨域像素两组24×128异步FIFO，cfg48位/起点稳定请求ACK、完成toggle，APB等待最后真实参数写入后才允许提交/START。
- 新预处理四Bayer相位/完整1080→720共921600像素逐值、短行/包错/溢出/复位恢复通过。720p采集921600像素/115200字跨65536索引及EOF/最终B屏障通过；真实reader/FIFO两完整720p60帧1843200像素、合成有界AXI下零欠载。实际Sapphire执行原固件、可变配置等待、2434项权重/两次启动中断通过；四模型小尺寸整数、原画/背压/AXI故障恢复和停CNN时钟后全局复位重载通过。
- 实际Efinity映射CNN24×40四模型3840像素等于RTL，独立整数固定RGB16颜色核对通过；11163个原生模型未连接端口告警保留、0 Error。完整720p仅梵高一个模型RTL/CNN/DMA实际逐值通过921600像素、全部27条和末32列，53156739 UI周期，100MHz UI/6.002ns CNN（166.611MHz）下等效1.881229fps；与最终166.667MHz差约0.033%。旧VGA2.136fps，因此像素吞吐约2.64倍，但跨分辨率总FPS略降，不能宣称>15fps或实板FPS。
- 新整机实际Efinity2026.1.132/I3全CAD、79脚/12Bank/电平和最终原生STA签核PASS：RAM254/256、DSP148/160、XLR45613/60800，最小setup/hold +0.428/+0.026ns，CNN自身setup +0.572ns，8条DPHY唯一二级链最小setup +13.489ns。23标量首级、166 Gray最大延迟、75位稳定束(FPS14/cfg48/起点13)、8精确DPHY首级，无整组切断；15个reset_sync来源FF及另3个与FIFO复位合并的真实三级链属性/连接核对通过，不按源注释盲数18个独立FF。
- 当前bit为camera_art_styles/build/camera_720_fast/outflow/ti60_camera.bit，SHA256 fbaecb588dbe01c85db920e8fdeae6a1525f5abd2f459ad913afbf163d10aa19；signoff/final_review绑定同次源/模型/固件/配置/报告，15套历史发布指纹保持。架构图、README、docs/full720.md和首次使用指南同步；当前尚未JTAG/Flash/串口访问，新720p真实画质、采集/推理/DDR并发与温升/供电待用户实板验证。原未知Flash与HDMI耦合边界保留，不承诺物理零风险。


## 全工程缓存清理、详细解读与分支上传（2026-10-23）

- 用户本轮明确授权“所有项目中间文件删除、关键改动上传到我的分支”，本次允许在imezpy提交/推送；此授权不更改以后默认不自动推送的规则，不允许触及main或改demo。
- 按477个JSON引用检查、绝对路径/reparse保护，删除9个独立工程和明确pycode缓存共305项/1329文件/898115146字节（856.51MiB）。仅可再生work_syn/work_pnr、.Xil/*.cache、仿真编译work/.vvp及Python缓存；保留项目、IP、bit、映射/时序/电气报告、原始日志、mem和验证回执。特别保留uart_style_keys/build/baseline_720p60_20261013全部内容，归档清单明确依赖其中工作目录和pyc。
- 清理回执camera_art_styles/build/cleanup_all_result.json；删除后最新版p720 audit/final_review及15套Ti60历史指纹PASS。8个Xilinx bit里6个匹配，uart_hdmi/fast与uart_style_six默认720p现有bit相对旧签核指纹已不一致、mtime早于清理；本轮未改写/重建/重新放行，记录cleanup_postcheck.json及docs/cleanup_inventory.md。
- 新详细文件camera_art_styles/docs/project_guide.md按最新camera_720_fast解读顶层/系统/采集/DDR/显示/CNN/CDC/RISC-V/APB/CAM3，附33个手写模块与3个厂商公开边界的完整参数/端口声明，未解密IP。rtl/p720/ti60_camera_720_top.sv为当前build顶层逐字节阅读镜像，源XML仍使用build内原顶层，禁止重复加入两份同名模块。未修改活动生产RTL/模型/电平/bit。
- Git选择性上传独立项目/common/pycode/说明及授权规则，不上传用户新增demo V9、build/sim/vendor/权重/工程配置/C固件。仓库依然不是独立可重建的完整工程归档，文档须明确本地依赖边界。

## 帧率候选与按键/手势设计（2026-10-23）

- 用户本轮优先研究提高帧率，已允许独立轻量学生训练、先比较画质再决定；手势仅1–4，依次梵高/剪纸/漫画/水墨。原12通道模型、已签核bit、demo V7/V9不覆盖；本轮不自动提交/推送或访问硬件。
- 独立六通道RF33/RF63各四模型已真实训练100轮浮点+24轮QAT、每组5952步，可用候选统一在pycode/runs/fps_student_v1/refined；首轮塌缩单独保留为失败。每组小/极小尺寸五层软件整数0误差，两梵高各完整720p0误差；真实留出照片比较位于pycode/results/fps_student_v1/refined，说明pycode/fps_student.md。C6更平滑、RF63较接近原版，未替用户选择画质。
- camera_art_styles/rtl/fps为独立C6实验，不在正式XML中。五层并行6/6/6/6/3、浅权重寄存器、1024深多银行历史RAM、18位坐标；运行时配置365项而非旧1217，旧固件不能直接复用。8组真实学习参数RTL各112×40共35840像素与独立整数逐值一致，含输入停顿/输出背压；五种RAM深度覆盖全部地址、边界、读保持和同址旧数据，最大11424。
- RF33梵高完整720p实际CNN/DMA、两672×720条带/核心640/halo16、真实异步FIFO/有界AXI/最后B逐值通过921600像素，6007407个100MHz UI周期，CNN6.002ns，等效16.646fps。没有真实摄像头/DDR控制器/CPU/显示提交并发，不代表实板或整题>15fps。RF33 core实际map122RAM/126DSP，整机230RAM/130DSP只是相加预算，未整机布局布线/STA；RF63不能沿用该资源或帧率。
- 旧video_job_control等COMMIT ACK才启动下一作业，60.074ms计算在60Hz下可能量化至4帧=15fps或5帧=12fps。建议三输出bank解耦计算/显示，保留front/pending/engine所有权、旧读事务排空和最终B；720p30采集+15fps推理的共享单拍写每19.29UI拍需完成一次AW/W/B，真实联合压力及必要突发合并尚未完成。不得把16.646内核模型称新整机达标。
- rtl/fps12独立保原12通道数值/1217升序配置，顺序浅权重实际推断4968个SRL8；224宽core153RAM预算整机261超限，208宽core143RAM预算251有潜力，约3fps仍为估算。此存储不是任意地址RAM，只支持完整顺序加载，现控制器expected_address逐项核对与冻结固件满足；映射后常量及非均匀/背压梵高960像素与RTL/整数一致，不等于整机签核。
- 后续按键用于原图/风格/左原右风格，手势只在已生效的原图/对比界面采样。同手势需4个完整一秒窗口，1Hz下t0/1/2/3/4五次新检测才证明4秒，失效/超时/换界面清资格，确认无手后才重新武装。rtl/interaction/gesture_hold_gate.sv独立5参数63758周期通过，仅门控而非图像分类器，未接生产或生成新交互bit。对半显示必须同源frame_id，增加源bank引用/容量，不能只延后原三槽release导致采集无空槽。
- 阶段入口camera_art_styles/docs/fps_experiments.md、fps_architecture_analysis.md、display_gesture_design.md；README与architecture.html同步。新增候选的图像/权重/build/sim继续只留本地，模型选型、映射数值、三bank调度、365项固件及精确CDC/电气/STA完成前不交付新bit；签核bit可用于后续JTAG实测，未实测不称FPS或整题验收完成。用户新增style_model/与demo V9不触碰。

## RF33三缓冲SRL整机签核（2026-10-24）

- 用户看过真实四风格比较后，已明确选“优先六通道RF33，继续争取帧率”。新独立build/camera_fps_rf33_srl_720采用该四模型，旧12通道/可用bit保留；不重复询问选型。本轮没有JTAG/串口/Flash或Git提交/推送。
- 普通FF浅权重整机camera_fps_rf33_720实际map230RAM/130DSP，但pack69716XLR超过60800，失败报告保留且签核显式拒绝。新SRL变体只改权重存储/类名，真实1152权重SRL8，小核少9216FF/5766LUT；完整升序365项加载是必要契约，APB逐项地址校验+原固件克隆两处1217→365满足，不能支持任意单字更新。
- 最终新固件9692B、四处16份boot lane副本一致；真实Sapphire3.4.0/新APB两模型730写入、可变cfg_ready、START/PLIC IRQ和8故障安全退出通过。新SRL四模型RTL17920像素、原生映射网表3840非均匀像素与整数一致；完整SRL梵高720p第三bank921600像素误差0、6007407UI周期，6.002ns CNN，模型16.646fps，不能代替实板FPS。
- 三输出槽0/2/10MiB、三原图4/6/8MiB；output_bank与commit_bank独立2bit，原图source在engine_done释放，输出前台仅reader晚ACK释放。reader先排旧读/FIFO复位/两域busy退出且仍在guard窗才ACK，真实rd_busy经2FF；pixel_fifo_fps显式10bit词数补0至11bit。新jobs/reader/真实FIFO/720p60联合6作业间隔仅多5–11UI拍、19完整显示帧逐值通过；引擎为延迟模型，不冒充完整SoC。
- axi_write_pair_fps允许每主一笔/总两笔在途，AW/W成对保序，固定ID0有序B队列路由，只有真实B释放信用，保留最后B完整帧屏障。随机2328事务/743错误/同拍进出/背压/reset通过；合成压力额外B延迟边界13→23拍，24仍积压FAIL，不据此保证实际DDR吞吐。后续对半显示扩原图槽不能占用已分给第三输出的10MiB。
- 实际Efinity2026.1.132/I3整机CAD/79脚12Bank/最终原生STA签核PASS：RAM230/256、DSP130/160、XLR55759/60800；setup/hold +0.379/+0.027ns，CNN自身setup+0.501ns，8条DPHY唯一二级链最小+13.541ns。24标量首级、166Gray最大延迟、73实际稳定束(cfg48+起点11+FPS14)、8精确DPHY首级，无整组切断/无依据多周期。peri与旧720版逐字节相同，未改DDR/UI/外部电平。
- 当前bit路径camera_art_styles/build/camera_fps_rf33_srl_720/outflow/ti60_camera.bit，SHA256 2a288989e1fdf84264a3579f7bd823b5f903aac50f661db0636ffd072cda2398。scripts/fps/signoff.py audit(False)先于离线pgm文件生成，audit(True)及16历史发布指纹复核PASS；signoff/final_review绑定同次源/模型/固件/配置/报告。本轮未上板，新720p真实采集/DDR/CPU/CNN/HDMI并发、画质/FPS/供电温升待测，不宣称整题完成。
- 当前操作仍启动原画，KEY0–3选四风格，KEY1+KEY2约0.5秒回原图、KEY0+KEY3约1秒复位；原画复制不计I。按键三界面、实际图像手势识别未接本bit，仅独立4秒门控通过。入口docs/rf33_720.md、README、architecture.html及根Ti60_programming_guide同步；旧project_guide明确对应保留12通道版。

## 借鉴47风格的四风格30fps候选（2026-10-30）

- 用户明确要求审阅`style_model/`及其`elinx/`、借鉴47风格约20fps实现并争取四风格30fps。参考工程保持只读；独立实现为`elinx/projects/camera_art_30/`，原RF33/旧12通道模型与bit保留，本轮不自动Git提交/推送、JTAG/串口/Flash访问。
- 候选复用已训练C8的原槽0/3/4/5（梵高/剪纸/漫画/水墨），本地槽0/1/2/3，四组各1159B、1216B对齐ROM共4864B。没有本轮重训，画质不等同于已认可RF33；实际同源720p/RGB565与软件低光对照在`build/quality/`，说明`docs/model_quality.md`。参考原47组DW/head相同并固化，stem/PW由RISC-V配置；346次兼容事务并不等于全部层可任意动态更新。
- 摄像头/DDR/输出图像仍1280×720，CNN分支2×2池化后640×360，C8 stem3×3+四组DW/PW(d1/2/4/8)+有符号RGB残差+最近邻放大+原720p RGB旁路。196MAC/原图像素不含halo；不可称每层全720p CNN，也不能直接加载RF33权重。10条核心128/halo32/总宽192，全球偶数池化相位、reflect101及最终B屏障保持。
- 优化包括PW双context稳态II8、两128bit打包槽与AW/W/B重叠、三输出0/2/10MiB及三源4/6/8MiB、reader晚ACK与两写请求在途。UI100MHz/CNN166.667MHz/DDR PHY400MHz/HDMI720p60不升频、不改引脚电平。参考40.65ms计算再串行等60Hz消隐可能量化为50ms≈20fps，这是代码推断而非独立实测。
- 发现Efinity2026.1.132对二维数组动态局部写入的实际映射差异：PW结果首像素错，DMA部分W lane被常量0；RTL四完整720p通过仍不足放行。已用固定context/channel及slot/lane唯一写者修复，失败正式源/映射/时序/诊断归档`build/baseline_dynamic/`，没有错误交付bit。根因说明`docs/synthesis_issue.md`。后续同类存储必须验证真实原语数值，不能仅看RTL/DRC/STA。
- 修复后的四种完整720p RTL/CNN/DMA均各921600像素与独立整数参考误差0，UI周期2818615/2818616/2818619/2818615，100MHz UI与6.002ns CNN模型下最慢35.478367fps；未含真实DDR控制器/摄像头/HDMI并发。实际pool/jobs/reader/FIFO/raster加固定engine耗时模型12个不同30Hz源帧，12完成/12ACK/0跳帧、23完整HDMI帧逐值、0欠载，原画不计I；该测试不是完整CNN SoC或实板30fps。
- 完整四风格、实际原语核与DMA、按键/APB/Sapphire/三bank/错误排空/保护、79脚12Bank、精确CDC和原生STA须共同通过`build/720p/signoff.json`才允许交付bit。参考/旧bit保持、同字节候选与生产别名须明确验证绑定，不通过只改收据冒充重跑。最新状态与入口见本项目README、architecture.html和docs/performance.md；手势/对半显示仍未集成。
- 本轮最终Efinity2026.1.132/I3全CAD签核PASS：RAM174/256、DSP100/160、XLR53603/60800，setup/hold +0.309/+0.026ns，8条D-PHY唯一二级链最小+13.778ns。离线生成`camera_art_30/build/720p/outflow/ti60_camera.bit`，SHA256 `18f3fb3ffdd3d55951dfd2d38260dca726f2ba4fb38a61d2a2858b252c817c3f`；输入、14类仿真、参数/固件/ROM、原生STA、原理图及精确SDC重生共同绑定。尚未上板，35.478367为模型吞吐，不能当实板30fps。
- DMA原语网表使用`build/experiments/*_fixed.sv`编译，和最终生产文件完整字节相等；严格别名审计保留原PASS/当前收据、compiled inputs/map/logs，并限制只能增加规定的alias字段。后续清理须保留这些源、`build/probe_dma/`必要映射证据及`sim/dma_mapped/candidate_verification.json`，否则正确地使fresh audit失效。core256仅独立模型37.5694fps/未采用，16beat突发写仅后续方案/未实现，不擅自升PLL。

## 全720p六通道新网络（2026-10-30）

- 用户明确要求更换轻量网络、减少参数并保持真正720p争取30fps。新独立工程`elinx/projects/camera_full720_30/`，训练在`pycode/full720_style/`；原C8半尺寸分支、RF33、style_model及demo V7/V9不改，本轮不下载/Flash/串口访问或Git提交推送。
- 实际训练c6_v1共6000步、batch12、96×96训练裁剪、冻结BN和末段QAT；复用固定512张训练划分，用户照片留出，教师只读C8原槽0/3/4/5。学生stem1×1(3→6)、四组DW3×3/PW1×1(d1/2/4/8)、有符号head及逐像素原RGB残差，无池化/下采样/2×2共享；逻辑每层均1280×720、RF31。单风格卷积权重784→396（−49.49%），四风格联合可训练参数747；参数少不代表恢复全尺寸后硬件资源同比下降。
- 四条各352×720，中央320列+左右16 halo，四条恰输出完整1280×720。全局reflect101、逐层边界、最终B屏障保持。PW双出通道/四上下文，DW三列bank并行三tap；初版地址长链setup−2.251ns保留`build/baseline_pre_pipeline`，用前瞻地址/列bank及行基址寄存流水修复，未提高时钟或用新例外掩盖该路径。
- 四风格完整720p实际RTL/CNN/DMA均各921600像素与独立整数参考误差0，UI周期2558528/2558528/2558526/2558527，100MHz UI/6.002ns CNN模型下最低39.084974fps（25.58528ms）。此为有界AXI/真实异步FIFO模型，未含真实DDR控制器及摄像头/HDMI完整并发，不称实板30fps。两张留出照片八个完整720p软件整数案例、16极小案例和九隐藏层720×1280形状核对通过；实际画质与C8/RF33不同，对照位于新项目`build/quality/`。
- 四模型真实EFX原语核24×40各960像素、DMA128×24各3072像素均逐值通过，含背压/三bank/最终B/故障恢复/原图；探针DMA只改模块名和几何，完整文本派生及当前生产源哈希核对。原语日志保留14705/18006个未连接端口告警、0 Error。216配置事务/736B对齐单模型/2944B四组ROM；3272B固件与四boot lane一致，真实Sapphire执行两模型432写入及START/PLIC IRQ通过。检查点重新量化与全部导出逐值一致，不能与346/365/1217事务旧固件混用。
- Efinity2026.1.132/I3最终CAD/79脚12Bank签核PASS：RAM220/256、DSP142/160、XLR52326/60800；最小setup/hold +0.043/+0.026ns，CNN setup+0.043ns余量较小。UI100MHz、CNN166.667MHz、DDR PHY400MHz、HDMI720p60及整份peri与保留C8一致。24标量首级/166Gray最大延迟/74位稳定束/8精确D-PHY首级，8条唯一二级链最小setup+13.450ns；SDC异地重建一致，不整组切断或无依据多周期。
- 新bit为`camera_full720_30/build/720p/outflow/ti60_camera.bit`，SHA256 `fe53fe766aa0e6b7c97c63c06aa1d0777b74d68d105e8817cb487f3a9938925b`。17类当前回执、模型/固件/源码/原生STA/电气和当前bit共同绑定，signoff/final_review均PASS，旧C8/RF33及参考源/bit指纹保持。README、architecture、docs/model/implementation/performance/validation与根使用指南同步。启动原图，KEY0–3梵高/剪纸/漫画/水墨，组合键同C8，CAM4/115200；真实整机FPS/画质/实际供电温升仍待上板。
- Git规则补齐camera_art_30及camera_full720_30的vendor排除，生成学习常量`camera_full720_30/rtl/full_shared_params.sv`也仅留本地；手写RTL/Python/MD/architecture按既有白名单。保留`build/probe*`、全部仿真回执/原始日志/必要网表和初始化文件，清理时不得破坏签核证据。新工程仍不是完整可重建Git归档；实际手势/按键三界面未集成。

## 独立风格重训、主机手势和三界面（2026-10-30）

- 用户要求先减少无用中间文件、重训改善梵高/水墨并处理亮屏观感，加入PC摄像头手势，硬件本轮只加原图/风格/左原右风格。已明确采用KEY0循环界面、KEY1下一风格、KEY2上一风格、KEY3独立长按约1秒复位；不要沿用旧直接四风格键或组合键复位。新工程`elinx/projects/camera_art_interactive`，旧full720/C8/RF33、style_model、demo V7/V9保留。没有授权本轮自动提交/推送、串口/JTAG/Flash访问。
- 清理先扫描659份JSON签核/来源引用，拒绝广泛动态删除后只处理6个展示并验证不被引用的Questa work编译库，删除2904882486B；源码、旧模型/bit、报告、网表、RAM初始化和回执日志保留，旧full720 fresh audit在清理后PASS。记录新项目`build/cleanup_result.json`，其他候选缓存未批量删除。
- `pycode/painterly_style`四教师各1600步、学生14000步＋3000步真实折叠整数QAT已完成。每风格C6/RF31/396卷积权重，但DW/head不再共享常量，全部216事务运行时加载，四模型2944B ROM、3272B真实CPU固件；没有2×2池化。使用固定512训练划分，留出用户照片；曝光/gamma/亮屏矩形与水墨纸白约束。最终两张四风格720p软件/QAT/独立int64误差0，实际画质仍有局部纹理和边缘偏重限制，不把教师图当学生或实板效果。
- 新运行时层首候选61270XLR超限。依据`abs(bias)+255*sum(abs(weight))<2^21`将累加/偏置缩为22位、舍入23位、局部树按数学界限缩窄，不更改图像尺寸或外部时钟/电平。中间trimmed候选58593XLR、CNN setup+0.008ns，余量很小；归档`build/attempt_runtime_trimmed`并解除仅该候选冻结后，最终模型已导出，最终CAD/原语/完整帧回归正在进行。最终仍以同次signoff/final_review均PASS为交付门槛，当前不可用中间结果替代新bit签核。
- 对半在CNN内部已对齐的原RGB FIFO处按全局x<640合成，RAW与风格来自同源帧同坐标；不新增DDR原图引用或显示读口，因此保留三源/三输出槽。原图模式复制整帧，所有模式等最后DDR B及安全消隐ACK；模式/风格在engine_start锁存、按输出bank关联、commit ACK后才更新前台。小尺寸四风格对半、忙中改变、最终B/故障恢复、12种模式/风格元数据和新按键/KEY3保护已通过，完整最终回归继续。
- CAM5仍115200/33字段，mode新增请求显示15–16、前台显示17–18、作业显示19–20、前台风格21–22，其余延续CAM4。`pc/camera_view.py`只读。高位style[5]仅在内部现有启动邮箱复用为split标志，低2位模型ID；无新的无握手多位CDC。79脚/12Bank与正确20261012原理图及保留full720的整份peri保持。
- `pycode/gesture_demo`已从EMEET SmartCam C960 2K采集，用户确认1–4可保持4秒切换PC风格；针对“三只认中间三指”又兼容自然弯拇指的拇指＋食指＋中指，75合成变换/8门控通过，调整后的实际姿势待复测。只在原图/对比采样，t0/1/2/3/4五次新采样证明4完整秒，帧隙>0.4秒/数字不明确/模式暂停清资格；确认后无手0.5秒才再武装。原图确认后仍保持原图，需切视图查看；不要误报无响应。
- 主机GUI用独立`.venv`和官方MediaPipe Hand Landmarker21点，通过`launch.py`的桌面兼容启动器解决打包进程摄像头COM/DLL查找失败，不改驱动/隐私。停止或关闭窗口释放摄像头；图像不保存或上传，JSON只有诊断计数。GUI已验证旧→最终模型加载与四风格整数输出。它不连接板卡、不发UART命令，不等于FPGA手势实现，PC FPS不能冒充板上FPS。README、architecture及详细模块/工作流说明在新项目，上传范围不放开C/XML/SDC/权重/vendor。

- 交互版最终签核补充：RAM220/256、DSP142/160、XLR58593/60800；setup/hold +0.084/+0.026ns；最低CNN/DMA模型吞吐39.084974fps；四模型完整720p各逐值通过、完整对半帧通过，实际EFX核四模型/实际EFX对半DMA四模型逐值通过，21类最终回执。79脚12Bank、23标量/166Gray/75稳定束/8 D-PHY精确首级及原生STA、同次模型/ROM/3272B固件/源码/bit共同绑定，未提高DDR/UI/外部电平。新bit `camera_art_interactive/build/720p/outflow/ti60_camera.bit` SHA256 `9c6d490b2354fa84202c07772671aea949b5cde4768cc04f959418ec1e26858c`，signoff/fresh final_review均PASS后才交付。README、architecture、模块/模型/验证/性能及根使用指南已更新；未上板，实际持续30fps、画质、供电温升仍待验收。

## 本轮清理与imezpy上传授权（2026-10-30）

- 用户当前明确要求“把不重要的删掉，然后上传到仓库”，本轮允许在既有imezpy提交和推送关键改动；不改main、不扩展固件/模型/工程产物白名单，不代表以后自动推送授权。
- 本次重新扫描715份JSON/3568绝对引用，仅删除新交互项目20个无引用Questa编译work库，共383文件/1105059808B约1.03GiB。具体目标、路径/reparse/保护扩展名检查及回执在其build/cleanup_repository_20261030_*，模型/bit/配置/IP/实际网表/原始日志/回执保留。tools/cache_inventory.py仅只读盘点，不自动删除。
- 上传此前未提交的RF33/三bank性能改动、C8/全720/新交互独立工程手写源、Python训练/定点/手势与说明；用户新增demo V9及style_model参考不加入本次提交。补排除三个独立工程继承的生成tiny_shared_params.sv，不将学习常量借RTL扩展名上传。详情docs/repository_sync_20261030.md；清理后对最新交互版重新fresh审核，不重新宣称实板验收。
