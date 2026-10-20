# 视频平台与队友接口契约

## DDR与显示公共接口、RISC-V接入位置

顶层三模块为camera_capture、framebuffer、hdmi_display。`style_ddr_framebuffer`内部保留原平台核心的帧池、DMA、APB和CNN接口；`style_hdmi_display`统一封装显示FIFO、时序、诊断跨域和HDMI编码。**RISC-V接在顶层framebuffer实例的paddr/psel/penable/pwrite/pwdata/prdata/pready/pslverr与irq，当前仍未实例化Sapphire。**详细接线、全部显示接口和Efinity操作见 [DDR/显示模块文档](ddr_display_modules.md)。

当前RESERVE_CNN=1：左侧640×480预处理原图，右侧图像区黑色，上下状态信息保留。内部COPY和双图读取仍用于完整帧流转验证。CNN上线需连接framebuffer的accel_*、FORCE_BYPASS=0、软件清bypass，并准备工程时加`--show-result`解除右黑预留；未接CNN时解除只显示COPY。采集/COPY历史30FPS不等于此版已上板或神经推理性能。

## 独立采集模块

板级顶层现实例化 `style_camera_capture`，接口和实例化示例见 [采集模块说明](camera_capture.md)。输入为摄像头域已解包RAW10×4与高有效VS/HS/DE；输出为核心域RGB888 ready/valid、SOF/EOL/EOF/frame_id、取消事件/编号、累计计数和FIFO水位。可选raw_mean是摄像头域单拍，不得当成核心域信号。模块封装旧RAW预处理、Gamma、图像/取消CDC和统计；MIPI物理IP、I²C初始化和DDR DMA仍各有独立所有者。此次封装不是采集提速，实板验证待拿到板子。

## 分工和当前实现

本平台负责摄像头预处理、CDC、DDR搬运、帧所有权、显示及Ti60物理工程连接。当前 `FORCE_BYPASS=1`，使用 `style_accel_bypass` 原样复制，控制默认 enable/auto/bypass 均为1。没有实例化 Sapphire，没有CNN、权重加载或神经风格迁移实现。队友后续接入不能仅改一个软件开关；必须完成硬件模块连接和联调。

## 统一 RGB 流

处理尺寸为640×480，行优先，每拍一个像素 `{R[7:0],G[7:0],B[7:0]}`。数据和 `sof/eol/eof/frame_id` 同拍，只有 `valid && ready` 的上升沿有效；valid=1、ready=0期间必须保持整个payload。SOF只标记第一像素，EOL标记每行第640像素，EOF只标记整帧第307200像素，最后像素也包含EOL。所有像素的frame_id相同。

当前WB版本链路为RAW10按物理A/B/C/D扣黑 → camera_preprocess Bayer/G均值/固定WB/缩小 → style_rgb_gamma → camera_cdc → DDR。BLACK_LEVEL_A/B/C/D通用默认0，物理measured配置为65/66/66/67，每个RAW10先减对应常数并钳位0，再选色/两G向下取整均值/RAW10固定WB/截取高8位；没有白点拉伸。WB_GAIN_R/G/B_Q8通用为256，物理measured为493/256/504；按21bit无符号(raw*gain+128)>>8半向上舍入并饱和1023。正常默认tone-profile=gamma18，可显式选择gamma22或linear；DDR输入图、COPY图和未来CNN读入的像素均为当前黑位与固定白平衡处理后、再按tone编码的RGB888；位宽、RRGGBB顺序、RGBX字节布局和valid/ready/帧标志不变，但亮度数值语义改变。ORIGINAL是完成RAW转RGB和当前tone预处理后的图像，不是原始线性RAW。需要线性输入的队友构建时用--tone-profile linear关闭，匹配训练/部署输入假设；它是构建选项，不是当前APB在线开关。这不是精确sRGB、白平衡或校准ISP。

CONTRAST PROBE01保留上述gamma18摄像头和DDR数据，仅在显示端对右图进行五档对比度映射，左图为基线。KEY1循环1.00/1.25/1.50/1.75/2.00倍，通用模块默认1.50倍，当前WB版本物理启动1.00，已实测不发绿及30fps，室外天空微红待诊断；消抖20ms后在帧边界生效；结果不回写DDR，不改变未来CNN的输入值。它是临时显示对照，不是CNN推理、锐化或自动黑电平校正。RAW四位置均值始终取自BLC/WB前原始输入的完整合法帧中心128×128区，经40bit异步FIFO整组跨域、像素域整组锁存；它们不是与当前显示前台逐帧绑定的传感器寄存器读回；即使BLC工作，遮镜显示仍可能为041/042/042/043，不应要求统计变成0。已测BLC位流启动1.50，用户调到RIGHT1.00最自然；当前WB版本物理启动0（1.00），通用默认2（1.50）保留，新候选已实测不发绿及30fps，室外天空微红待诊断。CONTRAST PROBE01是复用UI标记，不能唯一识别BLC或WB新位流；WB后白纸显示原始A/B/C/D也不应要求相等。

摄像头真实输入无背压。预处理本地队列和跨域FIFO只吸收短时停顿，长期堵塞必须丢新帧并报告，不能声称无限缓存。前端保存真实VS帧结束前的最后输出像素，防止短帧获得有效EOF。

原生Efinix CSI-2接收器的VS/HS均为高有效，VS上升沿开始帧、下降沿结束帧，HS高表示有效行。采集封装内部显式VS_ACTIVE=1。底层预处理另有VS_ACTIVE参数；封装接口只接受高有效VS/HS，其他极性在边界适配。不能从旧frame_info_det的neg_vs注释推断原始CSI极性。

物理接入将采集模块s_valid连接到CSI的DE，模块内部按 `s_valid & s_hs` 门控后交给预处理和统计，只在原生CSI行有效范围内接受RAW拍，与此前平铺顶层和官方frame_buffer的门控相同。通用预处理本体仍检测违反HS/VS范围的有效数据。

## 被动性能监测

启用方式：`python scripts/prepare_efinity.py --contrast-probe --wb-calibration --performance-monitor`。PERF_ENABLE通用默认0，物理启用后0x100..0x17C为新增APB性能银行，旧寄存器不变，完整定义见本文末表。

CAP从核心端为该帧分配采集槽开始到成功DDR写入，QUEUE从采集完成到领取任务，JOB从领取任务到完整结果DDR写入成功，TOTAL从分配采集槽到完整pair发布。LAST字段全部对应PERF_FRAME_ID同一帧；MAX分别统计清零以来成功阶段。实板TICK_HZ=1000000即微秒，AXI等待和窗口的CORE_HZ=100000000即核心周期。TOTAL不含曝光、RAW预处理/摄像头CDC等待、发布后的扫描及显示器延迟；JOB含DMA，不是纯CNN执行时间。成功采集、处理、发布分别计数，重复刷新不算新发布；失败或标签错误不制造成功耗时。

每秒自动快照；软件写PERF_CONTROL=2可关闭自动并冻结一个新快照，然后读取低/高32位；写1恢复自动；写4清统计并关闭自动。清统计保留在途帧和AXI状态；同拍清统计优先于统计累加，建议先清、再执行任务、最后手动快照。自动读取时核对读前后的PERF_SEQUENCE一致。0xFFFFFFFF表示32位延迟或等待计数的饱和值，延迟饱和另置FLAGS.bit1；字节和窗口保持64位。

平台AXI口按真实R/W握手统计字节，W按WSTRB逐字节计数；它只覆盖平台四个DMA，不自动包含未来额外CPU主机的DDR流量。读等待是已发出读事务、RREADY有效而RVALID无效；读背压是RVALID有效但RREADY无效，两者分开。B等待从写地址和最后W拍都已接受后开始。统计反映该AXI边界的等待，不能仅凭它认定DDR内部瓶颈。实际平均MB/s可按bytes×CORE_HZ/window_cycles/1000000计算。

屏幕y104..117有PERF 01诊断行，每120个HDMI帧换页，60Hz下约2秒。LAT页F为快照时最后发布帧的十六进制frame_id，可与画面上实时FRAME不同；四项CAP/JOB/QUE/TOT以十进制微秒显示并相互属于同一帧；DDR/BUS/MAX页S为十六进制快照序号，其余值为十进制，分别显示窗口周期与字节、等待、FIFO高水位和最长连续停顿。没有发布记录时LAT显示横线。源快照经608bit请求/应答信箱整组跨域，显示帧起点锁存并在104行前完成四数BCD转换。拥塞可合并中间诊断快照，视频数据不经过诊断FIFO。

## 卷积队友接入口

`style_platform_core` 的 `accel_input_*` 是送给加速器的输入流，`accel_output_*` 是加速器返回的结果流。双方均在core时钟域。加速器接收 `accel_start` 一拍任务起点，处理恰好一帧；输出尺寸、色序和frame_id必须与输入契约一致。start后平台经过一拍J_ARM再进入J_STREAM，使队友能够在时钟边沿清空旧valid再启动。平台已提供输入DDR读DMA、结果DDR写DMA，所以当前接法要求队友交付RGB流式整网模块。

`accel_abort` 在J_ABORT状态持续为1。收到abort的算法模块必须取消本次任务，清空内部流水和待输出valid，随后保持空闲到下一个accel_start。这个显式取消契约允许丢弃被取消任务的待输出像素；正常任务没有abort时仍必须遵守valid等待ready保持不变。平台只在DDR读写事务安全结束后回收失败帧槽。

网络内部的权重、中间特征、量化尺度、残差/上采样等由计算队友负责定义。如果其交付是AXI主机而非RGB流，需要调整共享DDR仲裁和任务寄存器，不能直接套入现有流口。当前平台未为CNN实现权重加载寄存器或权重DMA。

接入真正算法需：实例化模块，连接全部ready/valid及frame标志，把 `FORCE_BYPASS` 设为0，在空闲时清CONTROL的bypass位，并逐帧验证输入输出和B响应。OSD当前标签COPY FPS须跟随真实算法上线更新。

## RISC-V 队友接入口

APB3从接口：`paddr[11:0], psel, penable, pwrite, pwdata[31:0], prdata[31:0], pready, pslverr, irq`。paddr是字节offset，不是Sapphire系统绝对地址。未来CPU外设基址在实际SoC地址表/BSP中分配，不得把DDR帧池地址0x01000000误当寄存器地址。

PREADY固定1，访问阶段psel&&penable有效。非法offset或写只读地址返回PSLVERR；只读内容默认0。IRQ_STATUS是sticky，IRQ_ENABLE控制对CPU的IRQ电平。IRQ_CLEAR写1清除，若同拍有新事件，新事件优先。软件读取原因、完成必要处理、写IRQ_CLEAR，再按PLIC/BSP完成中断应答。

初始化摄像头的I²C控制权必须明确：独立物理工程保留官方硬件初始化方式；以后RISC-V接管应禁用同一总线上的原配置主机。CPU不应覆盖DMA正在读写或显示保留的帧区域。

## 启动条件与摄像头版本

顶层全局复位等待核心、DDR、HDMI和摄像头PLL锁定，在各工作时钟域同步释放。新 `style_camera_initializer` 按官方ROM完成164个I²C事务后置config_done，核心域经两级同步，与DDR cal_done及abort队列健康条件共同允许采集DMA接收新帧。这不意味着摄像头已经通过身份和寄存器读回检查：当前wrapper只统计wr_done/rd_done，不检查NACK或传感器ID。

VS极性的原始依据为Efinix《MIPI CSI-2 RX Core User Guide》v2.1，第7页端口表及第15页输出时序图：本地文件 `E:/Desktop/DEMO/_work/docs/mipi-csi2-rx-core-ug-v2.1.pdf`。2026-10-14用户报告首次上板有OSD但FRAME/FPS0；20:53仅是GUI所示旧bit文件修改时间，实际下载时间及运行bit哈希未独立核实。原RTL低极性适配错误已确认，历次修复和实物观察见 [硬件问题记录](camera_hardware_fix.md)。

初始化过渡帧可能产生累计错误使D2保持亮，不能把D2必须灭作为通过条件。历史13fps显示基线为build/style_video_display_burst128.bit及build/display_fix_receipt.json；第一轮camera_vs_high.bit曾有下半紫色抖动。当前30fps文件为build/style_video_camera_short_exposure.bit及build/camera_short_exposure_receipt.json，active marker为build/active_hardware_image.json；颜色仍待修复。不要误选GUI旧efinity/outflow/style_video.bit。

历史13fps、短曝光30fps和GBRG2颜色失败均保留。最新用户确认COLOR PROBE01标记和RGB白灰条正确，右侧BGGR3颜色正确但偏暗，CAP/COPY30、UF/ERR/DROP0。依据build/color_probe_receipt.json及active marker，有效BGGR3针对当前传感器/ROI/方向已获观察支持，但没有RAW四位置数值或精确时长。正式BGGR+gamma颜色已获用户确认，但图像模糊、低对比仍待优化；当前无CNN，不能把COPY帧率当推理性能，也不是DDR吞吐/电气签核。

短曝光三个寄存器与164项其余数据不再改变。旧正式基线build/style_video_bggr_gamma.bit显式BGGR3、gamma22，去掉probe/右图交换/黄框/标准条，状态见build/bggr_gamma_receipt.json；gamma18文件为build/style_video_bggr_gamma18.bit，用户已反馈仍发灰且完全遮镜也灰，CAP/COPY30、UF/ERR/DROP0，见build/bggr_gamma18_receipt.json；此前build/style_video_contrast_probe.bit已获标记/KEY1正常与暗场65/66/66/67反馈；build/style_video_black_level.bit已获遮镜纯黑、RIGHT1.00最自然及CAP/COPY30/零错误反馈，仍有轻微绿偏待测；诊断成功记录见build/color_probe_receipt.json。正常默认Bayer3/tone gamma18（旧gamma22基线需显式选择），旧COLOR PROBE要求显式Bayer0、默认tone linear，通用预处理仍默认0。未新增寄存器读回，原controller的dout未驱动，done不能当作真实读回。

实际参与综合的 `efinity/vendor/rtl/csi_rx_controller.sv` 是官方已验证5.15版本，HS_BYTECLK_MHZ参数70；同参考包中 `ip/csi_rx_controller/settings.json`记录5.16/50。该元数据差异来自原资料，本工程没有迁移或重新生成CSI IP。在Efinity IP Manager里不能直接接受自动升级/重生成，否则会替换当前已保留的源版本，需重新验证VS、RAW打包和物理接口。

未使用的fabric USER1调试JTAG接口已从独立工程去掉，实际下载器的硬件JTAG保持原样。顶层不实例化CPU调试核或Sapphire。

## DDR 地址和像素布局

帧池基址0x01000000，每槽0x00200000（2MiB），四输入槽加两结果槽。每帧640×480×4=1,228,800字节，stride=2560字节。RGBX8888的32位字为0x00RRGGBB，按LE字节存放 `[B,G,R,0]`；第一个像素在AXI128 bits31:0。

|槽|用途|地址|
|---|---|---|
|0|输入|0x01000000|
|1|输入|0x01200000|
|2|输入|0x01400000|
|3|输入|0x01600000|
|4|结果|0x01800000|
|5|结果|0x01A00000|

当前共享DDR接口AXI4、数据128位、地址32位、ID4；四个DMAID分别为0采集写、1结果写、2任务读、3显示读。通用读DMA默认16拍，平台READ_BURST_BEATS默认128（最多2048字节）；两写DMA仍16拍。所有突发不跨4KiB，各方向最多一个outstanding，读写独立并行。

四输入槽保留采集/READY/计算/显示原图的所有权，两个结果槽保护写入和显示结果。输入在复制或推理完成后不会立即释放；原图必须与其结果共同保留，直至安全显示切换且旧读取结束。这个多槽实现满足输入/结果分别双缓冲的最低要求，并补足原画对比保留需求。

## 完成与错误

采集完成=像素/标志完整且全部DDR写响应成功。任务完成=输入恰好读一帧、结果标志正确且最后写响应成功。结果完成先成为pending pair，只有显示安全窗口drain旧AXI、flush FIFO和切换握手后才成为front。DISPLAYED_COUNT统计新pair发布，不统计重复扫描。

DMA错误码1命令/对齐、2abort、3LAST、4RESP、5ID、6timeout。abort不能撤销已经发出的AXI VALID；必须drain已接受事务。timeout置sticky_fault，禁止新事务并要求系统复位；无响应总线不能通过丢掉busy冒充恢复。错误/半帧不能进入front。

显示刷新窗口默认y600..749或y0..99，y100..119留guard，图像y120..599。欠载第一次即标粉并停止本帧后续读取，下一次刷新清空后恢复。计数跨域采用Gray或完整握手，禁止直接采样变化的二进制多位字。

像素端欠载后停止消费FIFO，核心同步看到underflow_count变化必须立即进入D_DRAIN，取消显示读DMA并清除本地解包输出，按AXI协议排空已接受读事务。不能等到下一次refresh_request才取消：默认图像区剩余时间可达10.67ms，会超过默认100MHz下DMA的10ms无进展看门狗。这个立即排空不改变帧所有权；FIFO共同flush、旧pair释放及新pair发布仍在安全窗口进行。

DROP_COUNT和ERROR_COUNT按阶段事件求和，不对frame_id去重。同一坏帧可能先被摄像头前端丢弃，再被采集帧槽/协议/DMA报告。因此它们适合诊断，不能直接当作唯一丢帧数或唯一坏帧数；成功采集、处理和前台发布计数分别属于各自完成阶段。

OSD诊断行RAW/DROP/ERR/UF是十六进制累计计数，不是FPS。RAW/DROP/ERR在核心域采快照，经同一个刷新bundle握手锁存；UF在像素域accept_refresh时锁存。初始化过渡帧的历史错误不会因后续好帧而清零，D2亮不等于当前必然失败。

已在独立压力模型复现旧16拍读突发故障：640×48双pane、首读等待48核心周期，首欠载x1088/y40（图像起y20），后34752像素为FF00FF，UF1、无fatal/丢帧；回执pipeline passed=false而expected_failure_observed=true。该模型支持下半紫色为FIFO欠载保护的解释，但实际DDR首延迟未测，不能等同实物根因签核。128拍读突发的完整720p60/640×480、30fps输入、96周期首读压力已完成3次采集/复制/配对和5次完整显示，3072000像素全匹配，UF/drop/error0，编译/运行退出0；当前源码绑定状态见build/performance/receipt.json，其native log指向build/performance_latency/full_96_128_3cam。持续无限读请求的密集COPY模型在96/128下平均56.728M像素/秒，低于57.6M需求，是单独的带宽边界失败，不能将有限帧调度通过推广到任意满负载。

## APB 寄存器表

|Offset|名称|权限|行为|
|---|---|---|---|
|0x000|IDENT|RO|0x53565931（SVY1）|
|0x004|CONTROL|RW|bit0 enable，bit1 auto_run，bit2 bypass；复位均为1|
|0x008|START|WO|写bit0=1触发；手动请求保存一项待执行任务，重复写合并|
|0x00C|STATUS|RO|bit0平台启动条件就绪（DDR/摄像头配置/abort队列），1采集忙，2任务忙，3前台有效，4待发布，5fatal，10当前前台bypass，11手动任务待执行|
|0x010|IRQ_STATUS|RO|bit0采集完成，1处理完成，2前台发布，3帧/DMA/fatal错误；sticky|
|0x014|IRQ_ENABLE|RW|低4位中断使能；复位0|
|0x018|IRQ_CLEAR|WO/W1C|低4位写1清除；同拍新事件优先保留|
|0x020|DISPLAY_MODE|RW|0左右，1左原图/右黑，2左黑/右结果；复位0|
|0x030|WIDTH|RO|当前处理宽，默认640|
|0x034|HEIGHT|RO|当前处理高，默认480|
|0x038|STRIDE|RO|WIDTH*4，默认2560字节|
|0x03C|FORMAT|RO|1 = RGBX8888，LE word=0x00RRGGBB|
|0x040|FRAME_BASE|RO|0x01000000，DDR帧池地址；不是APB系统基址|
|0x044|SLOT_BYTES|RO|0x00200000，每槽2MiB|
|0x048|SLOT_COUNTS|RO|0x00000204：低8位4输入槽，bits15:8为2结果槽|
|0x050|READY_MASK|RO|低4位分别对应四个输入 READY 槽|
|0x054|FRONT_ID|RO|当前显示原图/结果共同frame_id|
|0x060|CAMERA_FRAMES|RO|摄像头看到的输入SOF总数|
|0x064|CAPTURED_COUNT|RO|完整采集且DDR写响应成功的帧数|
|0x068|PROCESSED_COUNT|RO|完整结果写响应成功的任务数；当前是复制完成|
|0x06C|DISPLAYED_COUNT|RO|发布新前台pair的次数，不是60Hz扫描次数|
|0x070|DROP_COUNT|RO|前端和采集阶段丢弃事件之和；同一坏帧可多阶段计数，非去重帧数|
|0x074|ERROR_COUNT|RO|前端、帧池、协议和显示错误事件之和；非去重坏帧数|
|0x078|UNDERFLOW_COUNT|RO|显示图像欠载次数，已从像素域跨域|
|0x080|FPS|RO|低16位采集完成FPS，高16位处理完成FPS，按CORE_HZ的一秒窗口统计|
|0x100|PERF_CONTROL|RW|bit0自动每秒快照（复位1）；bit1手动快照脉冲；bit2清统计脉冲。写2冻结并拍照，写1恢复自动，写4清统计并关闭自动；清统计保留在途帧/AXI跟踪|
|0x104|PERF_SEQUENCE|RO|每个快照递增；其余RO字段属于同一快照。自动模式读前后核对序号，或写2冻结|
|0x108|PERF_TICK_HZ|RO|延迟计时刻度/秒，实板1000000，故延迟单位微秒|
|0x10C|PERF_FLAGS|RO|bit0存在配对发布记录；bit1延迟曾饱和32位；bit2标签异常累计非零|
|0x110|PERF_FRAME_ID|RO|最后完整发布帧的ID；CAP/JOB/QUEUE/TOTAL LAST均与此ID对应|
|0x114|PERF_CAP_LAST|RO|该发布帧从核心端分配采集帧槽到成功写入DDR的刻度数|
|0x118|PERF_CAP_MAX|RO|清统计以来所有成功采集帧的最大耗时，不限于最后发布帧|
|0x11C|PERF_JOB_LAST|RO|该发布帧从领取处理任务到完整结果DDR写入成功的刻度数，包含DMA|
|0x120|PERF_JOB_MAX|RO|清统计以来所有成功处理任务的最大耗时|
|0x124|PERF_QUEUE_LAST|RO|该发布帧从采集写入成功到领取处理任务的排队刻度数|
|0x128|PERF_TOTAL_LAST|RO|该发布帧从核心采集帧槽分配到前台pair发布的刻度数；不含曝光、前端CDC、实际扫描及显示器延迟|
|0x12C|PERF_TOTAL_MAX|RO|清统计以来已发布帧的最大总耗时|
|0x130|PERF_CAPTURED|RO|监测到有有效标签的成功采集次数，32位饱和|
|0x134|PERF_PROCESSED|RO|监测到有有效标签的成功任务次数，32位饱和|
|0x138|PERF_PUBLISHED|RO|监测到有有效标签的新前台发布次数，重复扫描不计|
|0x13C|PERF_TAG_MISSES|RO|标签缺失/不匹配事件数，32位饱和，应为0；不等同原ERR或去重丢帧|
|0x140|PERF_WINDOW_CYCLES_LO|RO|自上次快照或清统计以来的核心周期数低32位|
|0x144|PERF_WINDOW_CYCLES_HI|RO|同一64位窗口长度的高32位|
|0x148|PERF_READ_BYTES_LO|RO|窗口内平台AXI读通道实际握手字节数低32位，每R拍16字节，包含错误响应的已接收数据|
|0x14C|PERF_READ_BYTES_HI|RO|同一64位读字节数的高32位|
|0x150|PERF_WRITE_BYTES_LO|RO|窗口内W握手且WSTRB置1的字节数低32位，包含RGBX填充字节|
|0x154|PERF_WRITE_BYTES_HI|RO|同一64位写字节数的高32位|
|0x158|PERF_AR_STALL|RO|窗口内ARVALID且非ARREADY的核心周期数，32位饱和|
|0x15C|PERF_R_WAIT|RO|窗口内已有读事务、RREADY且无RVALID的周期数，32位饱和|
|0x160|PERF_R_BACKPRESSURE|RO|窗口内RVALID且非RREADY的周期数，32位饱和|
|0x164|PERF_AW_STALL|RO|窗口内AWVALID且非AWREADY的周期数，32位饱和|
|0x168|PERF_W_STALL|RO|窗口内WVALID且非WREADY的周期数，32位饱和|
|0x16C|PERF_B_WAIT|RO|地址和最后W拍均已接受后，BREADY且无BVALID的周期数，32位饱和|
|0x170|PERF_R_MAX_GAP|RO|窗口内连续R_WAIT的最大周期数，边界处重新计段|
|0x174|PERF_W_MAX_STALL|RO|窗口内连续W_STALL的最大周期数，边界处重新计段|
|0x178|PERF_FIFO_HIGH|RO|窗口高水位：低16位摄像头FIFO读域占用（含预取，采样有跨域延迟）；高16位显示FIFO写域占用|
|0x17C|PERF_CORE_HZ|RO|AXI等待/窗口周期的时钟频率，实板100000000；与延迟TICK_HZ区分|
