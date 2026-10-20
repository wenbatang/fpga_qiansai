# 摄像头预处理模块

模块：`rtl/style_camera_preprocess.sv`。这是新工程的独立、可综合 SystemVerilog（`sv_09`）模块，不修改官方例程。没有 Xilinx 原语，也没有在本模块内实例化 MIPI 接收 IP；MIPI D-PHY/CSI-2 仍由易灵思官方封装接收。

## 接收边界

在 MIPI 的 `i_mipi_rx_pclk` 域连接官方 IP 的 `vsync_vc0`、`hsync_vc0`、`pixel_data_valid` 和 `pixel_data[39:0]`。一拍包含从左到右连续四个 RAW10：`x0=s_raw[9:0]`、`x1=[19:10]`、`x2=[29:20]`、`x3=[39:30]`。

物理顶层传给本模块的有效拍为 `w_mipi_rx_de & w_mipi_rx_hs`，与已验证 v6/V4/J5 基线 `frame_buffer.i_de(...)` 相同。官方 Figure 2 的合法图像像素有效拍均在 HS 高区，因此这个 gate 保留合法 RAW 图像并排除 HS 外有效性。通用模块仍严格检查 `s_valid && !s_hs`，仿真继续验证协议异常；输入丢了任何图像拍仍会因行长或整帧尺寸检查失败，gate 不会绕过完整帧保护。

默认 `VS_ACTIVE=1`，VS 上升沿开始一帧，下降沿结束；HS 高表示有效行范围，行内 `s_valid=1` 才接受四个像素。Ti60 顶层也显式传入 `.VS_ACTIVE(1)`，与原生易灵思 CSI 接收输出匹配。允许行内 valid 间歇，不把间歇当成行尾。VS 开始与第一拍像素之间至少隔一个时钟；HS 可以与第一拍 valid 同时拉高。帧末 VS 可与最后一行 HS 下降沿同时到达。其他来源若有效帧内 VS 为低，可显式选择 `VS_ACTIVE=0`；不能把显示器的 VS 同步脉冲极性直接套到摄像头 CSI 帧电平上。

来源核对：官方 **MIPI CSI-2 RX Controller Core User Guide v2.1** 第 7 页 Table 6 说明 HS/VS 是 `clk_pixel` 域的有效高电平信号，第 15 页 Figure 2/3 显示 HACT 中 HS 为高、VACT 中 VS 为高；第 17 页 Generic 模式说明的是不依赖 Line Start/Line End 获得准确同步时序，并未改变有效高电平约定。第 11 页 Table 12 给出 RAW10（datatype 0x2B）为 4 像素×10bit=40bit/拍。参考文件：`E:/Desktop/DEMO/_work/docs/mipi-csi2-rx-core-ug-v2.1.pdf`。

官方 v6 `rtl/frame_buffer_V3/frame_info_det.v` 第 38–59 行会根据 `i_de` 有效时的 `i_vs` 自动选择上升沿或下降沿作为帧开始。其 `neg_vs` 附近的“video start”注释不表示实际 CSI 输出默认有效低。旧版重构据该注释选用了 VS_ACTIVE=0，这是接口极性错误：在有效高的 RAW 帧中无法接受像素或生成合法 EOF，最终会表现为黑底、帧编号/FPS 为 0、错误计数增加。现已改为原生有效高，并保留低极性显式参数回归。

默认尺寸 `1920×1080`，依据 v6 `rtl/cam_i2c_ctrl/i2c/i2c_master_reg_rom.v` 第 236–239 行：3208/3209=0780、320A/320B=0438。其寄存器 3221=66 涉及传感器方向；应在实际板卡、镜头方向与当前寄存器表下确认 Bayer 相位，不以注释图代替物理验证。

## 参数

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `CAM_WIDTH` | 1920 | 输入像素列数，必须是 4 的倍数 |
| `CAM_HEIGHT` | 1080 | 输入行数，必须为偶数 |
| `OUT_WIDTH` | 640 | 输出列数，1 到 CAM_WIDTH/2 |
| `OUT_HEIGHT` | 480 | 输出行数，1 到 CAM_HEIGHT/2 |
| `BAYER_PATTERN` | 0 | 0 RGGB、1 GRBG、2 GBRG、3 BGGR |
| `BLACK_LEVEL_A/B/C/D` | 各0 | 物理2×2左上/右上/左下/右下RAW10固定黑位；物理measured为65/66/66/67 |
| `WB_GAIN_R/G/B_Q8` | 各256 | 无符号Q8，0..1024；256恒等，物理measured为493/256/504 |
| `VS_ACTIVE` | 1 | 输入有效帧内 VS 电平；易灵思原生 CSI 为高 |
| `QUEUE_DEPTH` | 256 | 同步包 FIFO 深度，每包 1 或 2 个输出像素 |

## 接口

| 端口 | 方向与位宽 | 含义 |
|---|---|---|
| `clk`、`rst_n` | 输入，1 位 | 摄像头像素时钟；低有效同步复位 |
| `s_vs`、`s_hs`、`s_valid` | 输入，1 位 | 帧电平、行电平、RAW 拍有效，没有输入 ready |
| `s_raw` | 输入，40 位 | 四个 RAW10，低位像素先 |
| `m_valid`、`m_ready` | 输出/输入，1 位 | 输出握手；两者为 1 时接受一个 RGB 像素 |
| `m_rgb` | 输出，24 位 | `[23:16]R`、`[15:8]G`、`[7:0]B` |
| `m_sof`、`m_eol`、`m_eof` | 输出，1 位 | 与像素同拍：整帧首像素、每行末像素、整帧末像素 |
| `m_frame_id` | 输出，32 位 | 对应输入帧号，从 1 开始，包括丢弃帧，按 32 位回绕 |
| `m_abort` | 输出，1 位脉冲 | 当前输入帧已失效，不能发布；需事件 FIFO/握手跨域 |
| `m_abort_frame_id` | 输出，32 位 | abort 所针对的帧号 |
| `input_frames` | 输出，32 位 | 收到的 VS 帧开始次数 |
| `drop_frames` | 输出，32 位 | 失效或因队列阻塞无法接收的帧数，每帧一次 |
| `error_frames` | 输出，32 位 | 同上，当前所有丢弃都属于协议/缓冲错误 |

在 `m_valid=1 && m_ready=0` 时，RGB、标志、frame_id 和 valid 全部保持不变；新 VS、输入错误、FIFO 溢出均不得更改已经提供给下游的像素。

## 处理逻辑

1. **行缓存。** 偶数输入行写入 `CAM_WIDTH/4 × 40bit` 同步 RAM。奇数行读取对应四像素，得到两个完整 2×2 Bayer 单元。默认行 RAM 19,200 bit，不存储整个图像。
2. **2×2 单元转 RGB。** 每单元先按物理A/B/C/D分别做RAW10饱和减黑位，再取一个R、一个B，两个G求无符号均值。例如 RGGB 的 `R=左上`、`B=右下`、`G=floor((右上+左下)/2)`。保持RAW10，先对两G向下取整求均值，再按Q8增益乘加128、右移8并饱和1023，最后各通道>>2转RGB888。通用增益256恒等，物理候选493/256/504。
3. **最近邻缩小。** 先形成 960×540 个 Bayer 单元，再输出 640×480。输出 `(x,y)` 选择单元 `(floor(x*960/640), floor(y*540/480))`。实现使用常量商/余数与 DDA 累加，运行时只有加法、比较和减法，不实例化动态除法器。
4. **并行转串行。** 一拍可选中 0、1、2 个单元，最多两个 RGB 装入一包，同步包 RAM 排队，再串行为一拍一个 RGB。默认包 RAM 256×87 bit，另有输出保持寄存器；实际 BRAM 映射与资源以 Efinity 综合报告为准。
5. **完整帧验证。** 检查每行是否恰好 CAM_WIDTH/4 个有效 RAW 拍、总行数是否恰好 CAM_HEIGHT。最后一个输出像素单独暂存，直到真正 VS 帧结束且所有输入尺寸合法，才加入队列并携带 EOF。因缩小而提前选中最后输出像素时，也必须继续检查剩余输入行。

**图像质量边界：这是半分辨率2×2 Debayer和最近邻缩小，不是官方全尺寸双线性Debayer。** 预处理本体含固定RAW黑位/白平衡，不做gamma或自动曝光/AWB；正式物理候选在其RGB输出后另接style_rgb_gamma。当前诊断已获用户CAP/COPY30、UF/ERR/DROP0及右图BGGR3颜色正确反馈，右图仍偏暗；gamma版本颜色已获确认，亮度和锐度仍未验收，模型输入质量也需队友确认。

官方 `raw_to_rgb.v` 的说明图画 RGGB，但有效代码还依赖上游行缓存偏移，并存在方向寄存器影响。因此默认 BAYER_PATTERN=0 是明确的软件/RTL约定，不能声称已在实物上核对相位。可通过四种模式和红蓝色块实拍确认。

## 异常恢复与下游要求

输入不能背压。FIFO 满、短行、长行、短帧、额外行、VS/HS 范围外 valid 均使当前帧失效：发送一次 abort，计数一次，停止接收该帧剩余内容，等待下一 VS 开始。

已经送出的像素不能撤销；队列中同 frame_id 的旧像素可能在 abort 后继续排出，但没有合法 EOF。下游采集 DMA 必须记住被 abort 的帧号，并丢弃该 ID 的后续像素（包括延迟的 SOF），直到下一新 ID 的 SOF。abort 事件跨域比像素更早到达也必须安全。不能仅依据像素数量发布帧；需要正确尺寸、EOF、全部 DDR 写响应以及未收到 abort。

若上一完整帧的暂存 EOF 因 FIFO 仍满而不能排队，则新输入帧被明确丢弃，不覆盖已经验证的旧帧尾。这样 FIFO 的压力表现为可观测的丢帧，而不是假 EOF 或错误 frame_id。

输出跨入 DDR/core 域时须使用完整像素包异步 FIFO。abort 使用独立事件异步 FIFO或可靠握手。禁止只用两个触发器同步 RGB、帧号或 abort 的多位伴随值。

## 本地仿真

入口：`D:\python3.11\python.exe sim/camera/run_camera.py`（项目目录作为工作目录）。编译选项 `-g2009`，所有测试要求编译和执行退出码均为 0，并包含 PASS 标记。可用 `--iverilog`、`--vvp` 指定其他电脑的工具位置。

覆盖：四种 Bayer、绿色两样本均值和 RAW10 末位、输出像素与 floor 坐标参考逐一比对；24×18→8×8 覆盖默认 2/3 横向与 8/9 纵向比例；32×24→8×6 覆盖整数比例；完整 1920×1080→640×480、默认 256 包队列；SOF/EOL/EOF/frame_id；间歇下游背压及 held 输出稳定；短帧、额外行、短行、持续背压 FIFO 溢出；错误后恢复。

另有 `protocol_edges`：长行、HS 外 valid、HS 内 valid 间歇、VS/HS 同拍结束，12 输入帧、6 完整、6 失效。`pending_eof` 使用 1×1 输出和 2 包 FIFO，连续输入直至已验证 EOF 暂存不能入队；下个新帧被明确丢弃，原来 held 的像素在多次 VS 变更和 abort 时仍稳定，之后四个完整帧按序排出并恢复下一帧。

当前回归共 **11 组**：原八组显式选择低极性 VSA=0，验证通用低电平输入仍受支持；`native_high_fractional` 选择 VSA=1，24×18→8×8，覆盖全部尺寸/valid/溢出错误与恢复；`native_high_geometry` 选择原生 VSA=1，输入完整 1920×1080 RAW10，逐像素验证 640×480 输出与全部标志。正反极性由同一个驱动参数产生，有效区和空白区同步转换，不只是翻转某一个测试信号。

`native_polarity_reproduction` 将同一组四个合法原生高 VS 帧同时送给两个实例。旧低极性实例得到 0 个合法 EOF、4 个错误；修正高极性实例得到 4 个完整帧、0 错误，逐像素验证 RGB、缩放坐标、全部标志与帧号。这是对黑底/FPS 为 0 根因的直接回归，不以翻转显示输出代替摄像头采集。

仿真排空等待采用 `2*QUEUE_DEPTH+64` 个 ready 有效时钟：FIFO 每包最多两个像素，加一个两像素输出保持寄存器、一个暂存 EOF 像素及流水延迟，即有明确的队列排空上界。带背压的帧结束后还会恢复 ready 再等待这个上界。没有缩短摄像头完整 RAW 帧，也没有删减逐像素和错误断言；只去掉原来每帧结束后空等三幅输出帧的无效周期。

本文的像素测试属于 RTL 仿真；完整工程的 Efinity RAM 映射和布局布线结果见 `build/efinity_receipt.json`。摄像头物理 Bayer 相位、实际 CSI 解包和上板画面仍须实板验证。

启动阶段预处理复位早于传感器全部 I²C 配置完成；ROM 先在 0x90 写 stream-on，再在 0x99–0xA3 设置输出尺寸/裁剪/方向。过渡帧可能被严格尺寸检查拒绝，累计错误使 D2 保持亮并不自动表示后续视频仍失败。应同时检查 CAP/PROC FPS 与 FRAME 是否持续推进；本模块不将初始化完成计数等同于传感器身份/ACK/readback 验证。

历史记录：2026-10-14 的原八组低极性仿真全部编译/执行退出 0，完整尺寸测试有 1,843,541 次输出像素握手、4 完整帧和 4 失效帧。但这些测试当时没有覆盖原生 CSI 高极性，不能证明板级同步接口正确。最新十一组结果、VS_ACTIVE、输入/丢弃计数及当前 RTL SHA256 保存在 `build/camera/*.log` 与 `build/camera/receipt.json`。像素数包含失效帧已经送出的部分，不代表完整图像帧数；不以旧回执代替当前实现验证。

仅新增独立用例而未改 DUT/原有 bench 时，可使用 `run_camera.py --collect` 避免重复完整尺寸仿真。它只复用工具、参数、顶层、RTL/bench SHA256 和日志均与已完成严格 PASS 一致的用例；编译或执行非零、源变化、日志被改或缺失均拒绝收集。DUT 源哈希与 runner 自身哈希分别记录，复用用例保留原完成时间，新增用例实际执行，并备份收集前回执。完整正常运行仍会从头执行十一组。

## 当前实物状态与13fps历史基线

最新COLOR PROBE01实物反馈：标记和RGB白灰条正确，右侧BGGR3颜色正确但暗，CAP/COPY均30、UF/ERR/DROP均0。对当前摄像头/ROI/方向，有效Bayer3已获观察支持，见[color_probe_receipt.json](../build/color_probe_receipt.json)及[active marker](../build/active_hardware_image.json)。没有RAW四位置数值或精确时长，运行bit身份未独立读回；正式BGGR+gamma版本颜色已获确认，图像质量待优化，COPY也不是神经推理。此前短曝光30fps但偏色及GBRG2失败记录继续保留。

此前 `build/style_video_display_burst128.bit` 稳定基线为CAP/COPY均13、UF/DROP0。随后RAW累计从0x38E到0x429增加155帧、间隔约10秒、ERR0；RAW是十六进制CSI SOF累计数，计时不精确，不把粗略15.5当精确帧率。该段是短曝光之前的历史观察，13fps文件与回执保留作对照。

## 短曝光提速依据

官方SC431HAI《数据手册V1.1》第23页规定：线性曝光值为

`E = ((3E00 & 0xF) << 12) | (3E01 << 4) | (3E02 >> 4)`，单位是半行，范围为 `4 ≤ E ≤ 2×VTS−11`；第N帧写入的新曝光值在第N+2帧生效。默认VTS为1500时，上限为2989半行。

| 配置来源 | 3E00 | 3E01 | 3E02 | 编码曝光（半行） |
|---|---|---|---|---:|
| 官方v6当前基线 | 01 | BB | F0 | 7103 |
| 官方v1同模式候选 | 00 | BA | D0 | 2989 |

v6的7103高于默认VTS1500所允许的2989。长曝光有降低输出帧率的依据，恢复同模式v1三个值后已获用户30fps反馈；当前仍没有实际寄存器读回，不能把ROM值当作运行中VTS/曝光读数。短曝光可能使画面更暗，本次用户表示亮度可接受，但颜色偏差仍待处理。

准确来源：

- 官方手册：`D:/QQ/摄像头SC431HAI_数据手册_V1.1.pdf`，实际PDF第23页与印刷页23一致。
- 官方v1 ROM：`E:/Desktop/qiansai1/fpga_qiansai/elinx/elinxdemo/Ti60F225_DemoBoard_v4/10_Ti60f225_sc431hai2hdmi_demo/Ti60f225_sc431hai2hdmi_v1/rtl/cam_i2c_ctrl/i2c/i2c_master_reg_rom.v`，第198–200行。
- 当前保留的官方v6 ROM：`efinity/vendor/rtl/cam_i2c_ctrl/i2c/i2c_master_reg_rom.v`，第198–200行。
- 两表ROI设置第228–243行相同，输出尺寸第236–239行均为 `0780/0438`。v1为161项；v6前161项仅索引0x73–0x75曝光数据不同，追加0xA1增益3E08=80、0xA2增益3E09=2A、0xA3方向3221=66；PLL、4lane及ROI模式相同。

## 项目自己的配置ROM与序列模块

`rtl/style_camera_reg_rom.v` 与 `rtl/style_camera_reg_set.v` 使用项目自己的名字，厂商ROM原件不编辑。`prepare_efinity.py` 的camera_profile支持 `verified` 与 `short_exposure`，默认 `short_exposure` 明确为实验profile。verified保留v6原值；short_exposure只将3E00/3E01/3E02恢复为00/BA/D0，保留v6共164项的其他数据、顺序、增益与方向。DDR、CSI物理设置、1920×1080输入与640×480缩小逻辑没有因此改变。当前生效profile和三个差异的来源/SHA记录在 `build/camera_profile_receipt.json`。

| 模块 | 端口 | 含义 |
|---|---|---|
| `style_camera_reg_rom` | `clock` | 5MHz配置时钟；同步查询ROM |
| 同上 | `addr_ptr` | 配置序号，不是传感器寄存器地址 |
| 同上 | `rdata_out` | 25位配置字：bits24:9为地址、bits8:1为数据、bit0为读写标志 |
| `style_camera_reg_set` | `clk/rst_n` | 5MHz配置时钟和低有效序列复位 |
| 同上 | `init_done` | 等待底层I²C控制器初始化完成后开始命令序列 |
| 同上 | `wr_done/rd_done` | 底层事务流程结束事件，不证明传感器ACK或真实读数据 |
| 同上 | `wr_en/rd_en` | 读/写命令一拍使能，发出后等待done才推进索引 |
| 同上 | `addr/dout/dev_addr` | 当前配置项的16位寄存器地址、8位写值、8位设备地址编码 |

序列等待初始化、读取ROM、发命令、撤回使能、等待done，直到164项结束；外层 `style_camera_initializer` 累计done后锁存config_done。配置主机仍只有一个，未增加RISC-V或动态自动曝光控制。本次不增加RAW FPS、芯片ID、HTS/VTS或曝光读回；继承控制器的读数据 `dout` 实际未驱动，不能沿用它冒充真实读回。

实际通用模块缺省值分别为ROM的TOTAL_ROM_DEPTH=256、reg_set的DATA_LENGTH=61；物理initializer明确传入DATA_LENGTH=164，reg_set进一步将ROM深度覆盖为164。实际参数声明与全部端口由离线网页从源码解析显示，通用缺省值不能当作本平台执行项数。

显式准备命令为 `python scripts/prepare_efinity.py --camera-profile short_exposure` 或 `--camera-profile verified --black-level-profile none`，随后重新回归及 `python scripts/build_efinity.py --build`。准备脚本默认short_exposure，当前源profile见审计回执；历史稳定bit不随源码重新准备改变。配置切换必须重新构建并复位执行初始化，不能用旧bit冒充新profile。

短曝光30fps历史文件和回执保留；当前有用户证据的诊断图像见build/color_probe_receipt.json及active_hardware_image.json，右图BGGR3颜色正确但偏暗。正式BGGR+gamma候选见build/bggr_gamma_receipt.json，颜色已获确认，亮度和锐度仍未验收；13fps、GBRG2失败及早期半幅紫色记录均保留。

## Efinity工程入口与源列表缓存

该短曝光文件来自 `build/efinity/20261014_225018/efinity/style_video.xml`，入口同时记录于回执project。56项源码绑定测试通过，map/interface/pnr/pgm退出0，WNS +0.547ns、WHS +0.026ns；这些构建事实与实物颜色问题分别记录。

稳定bit可以直接用Programmer下载。需要IDE再次综合时，推荐打开回执project指定的完整构建快照；225018快照补入两个新项目模块，综合源共78项，脚本已检查路径存在且无重复。此前224612首编使用IDE保存的旧76项源清单，报新模块unknown，并不代表新增RTL未实现。

若回到主 `efinity/style_video.xml` 开发，先关闭旧工程，再prepare选择profile，然后重新打开生成XML并检查两个style_camera_reg模块。关闭旧工程时也可能保存旧清单，因此顺序不能反过来；不要在仍打开的缓存工程里直接Compile并假定新源已加载。prepare本身按全部项目RTL生成完整清单，CLI构建另会检查并补齐独立快照，不修改厂商输入。

## 颜色问题：先核对Bayer相位

诊断前的链路审查发现cell_rgb、packer、unpacker、COPY和HDMI保持RRGGBB色序，RAW10取高8位与官方top的vin一致，绿色取两G均值。正式候选在CDC前新增gamma会改变亮度数值，但不交换R/G/B；这与此前通道顺序检查分别记录。

绿/紫偏色优先核对绿色位置的Bayer相位。若真实GRBG/GBRG被按RGGB解释，红色区域可能被当作绿色、绿色区域可能变紫；这是代码映射的推断，仍须实拍红/蓝/白色块确认。官方debayer包含行缓冲偏移、WB以及后续R/B交换，不能只照其注释或移植末端通道交换。当前没有白平衡；先确定物理Bayer相位，再判断是否需要颜色增益。

当时独立颜色候选为 `build/style_video_camera_gbrg.bit`，打包/实现/实物状态见 [camera_color_phase_receipt.json](../build/camera_color_phase_receipt.json)。相对已确认30fps基线，仅物理顶层显式`.BAYER_PATTERN(2)`选择GBRG；通用默认RGGB=0及四模式支持保留，曝光、增益、DDR/COPY/HDMI和白平衡均不改。当时尚无颜色修复通过的实物反馈，30fps短曝光文件继续作为有用户证据的基线。

相位推导与源码审计在 [camera_color_phase/profile_receipt.json](../build/camera_color_phase/profile_receipt.json)：手册第30页图2-7给原生BGGR，第31页公开输出x偏移0x0144为偶数、y偏移5为奇数，结合3221=66双向flip与1920×1080偶数尺寸可推导GBRG。但上游3200..3207窗口定义没有在该手册公开，官方旧流水还存在像素对/中心行偏移，推导不能替代真实红/蓝/白色块确认。该候选不是白平衡修正，不能提前宣称颜色已修好。


## GBRG实物失败与COLOR PROBE 01诊断

2026-10-15用户针对GBRG文件报告红色物体显示绿色、蓝色显示黑色、绿色显示粉紫；CAP/COPY30，UF/ERR/DROP保持0。此候选颜色测试失败。094400映射网表实际使用top偶列+bottom奇列求G，R来自bottom偶列、B来自top奇列，命名bit与构建bit的SHA一致，证实本地BAYER2配置进入产物；运行FPGA身份仍未独立读回。上节待测状态被本次反馈更新，不能继续把公开ROI/flip推导视为物理相位已确定。

COLOR PROBE01左RGGB0/右R/B交换等效BGGR3，另显示中心四RAW均值、黄框和标准色条。用户已确认版本/色条正确、右图颜色正确但暗，CAP/COPY30、UF/ERR/DROP0；没有提供四位置读数。当时active marker引用诊断文件，当前已按正式BGGR+gamma的用户反馈更新，GBRG2失败记录保留。对当前摄像头/ROI/方向，有效BGGR3已获观察支持；正式双图颜色后续已获确认，但亮度和锐度仍未验收，详见[color_probe.md](color_probe.md)。

## 正式BGGR3与gamma亮度候选

候选文件为 [style_video_bggr_gamma.bit](../build/style_video_bggr_gamma.bit)，状态见 [bggr_gamma_receipt.json](../build/bggr_gamma_receipt.json)。物理顶层显式BAYER_PATTERN=3，通用预处理仍默认0并支持四种排列；去掉probe、左右交换、黄框、参考条和诊断统计。曝光寄存器、DDR和原valid/ready/帧标志不改。

style_rgb_gamma位于camera_preprocess的RGB输出到camera_cdc入包之前，接口s_rgb[23:0]→m_rgb[23:0]为纯组合，ENABLE=1查表、0透传，无时钟或新增流水拍。256×8 LUT离线按 `floor(255*(x/255)^(1/2.2)+0.5)` 生成，R/G/B使用同一曲线；硬件没有浮点/幂运算或外部mem依赖。官方2P2.mem为x^2.2压暗，方向相反，不能直接复用。维护scripts/generate_gamma.py后须重新生成并验证LUT。

该gamma22基线使用--tone-profile gamma22；当前新候选默认gamma18，color-probe在未给tone时默认linear、要求显式Bayer0，color-probe+gamma18或gamma22被拒绝。需要线性输入的队友用--tone-profile linear关闭。该gamma22基线的camera→gamma→CDC让DDR、COPY及未来CNN输入均为近似gamma2.2编码RGB888；当前gamma18候选为近似gamma1.8编码；位宽/字节序/握手不变，但亮度数值语义改变，应匹配训练输入。它不是精确sRGB、白平衡或完整校准ISP。当前右图正确但偏暗是诊断版实物结论，正式gamma版本颜色已获确认，但图像模糊、低对比仍待优化。

源清单数量不要固定沿用历史78/80项。当前IDE入口和已检查源数量以当次实现回执为准，构建快照会补齐项目RTL并检查路径与重复项；生成文件后也要关闭旧缓存工程再prepare/reopen，不能用旧list直接重编。


## 最新照片反馈：颜色正确，图像质量待优化

用户确认正常BGGR+gamma版本颜色正确，但图像模糊。显示器照片中OSD相对清楚、摄像头画面边缘软且低对比，CAP/COPY为30、UF/ERR/DROP为0；这些数值来自单张照片，不构成新增持续稳定性证明。位流身份按会话关联，未独立读回；亮度和锐度尚未验收，状态见[bggr_gamma_receipt.json](../build/bggr_gamma_receipt.json)。

镜头离魔方约10cm，用户已确认镜头可手动对焦，尚无调焦后清晰度或50–100cm远距对比，先通过远距目标检查焦点。当前2×2半分辨率Debayer从1920×1080得到960×540，再最近邻缩至640×480；16:9到4:3属于非等比缩放，横向相对压缩25%。该旧gamma22链路没有黑电平校准或锐化，但不能据此断言传感器内部没有BLC。Gamma只逐像素映射、不混合邻域；失焦、采样细节损失、黑电平和Gamma各自贡献尚未测量，不凭两张拍摄条件不同的照片确定单一原因。


## gamma18实物反馈：仍明显发灰，遮镜也灰

针对原gamma22画面偏灰、低对比，本轮仅把Gamma从2.2减为1.8；BGGR3、曝光、DDR和HDMI保持。新候选名为[style_video_bggr_gamma18.bit](../build/style_video_bggr_gamma18.bit)，当次构建和实物状态以[bggr_gamma18_receipt.json](../build/bggr_gamma18_receipt.json)为准。原style_video_bggr_gamma.bit及其颜色正确但灰/糊的反馈保留，不能把旧版反馈当成新候选通过。

style_rgb_gamma新增GAMMA_TENTHS=18（支持18/22），ENABLE=0仍透传，LUT按`floor(255*(x/255)^(10/GAMMA_TENTHS)+0.5)`离线生成。prepare支持`--tone-profile linear/gamma18/gamma22`，普通默认gamma18，color-probe仍须Bayer0和linear。RGB位宽、顺序与握手不变，DDR/COPY及未来CNN的数值语义随tone变化，队友需匹配训练输入；这是构建选项，不是在线寄存器开关。

gamma18比gamma22少提升中暗部，仍是逐像素组合映射，无新增流水拍；没有实现独立对比度、FPGA黑电平校准或锐化，用户已反馈仍明显发灰，CAP/COPY30、UF/ERR/DROP0，完全遮镜后仍明显灰；尚无数值黑位测量。用户已确认手动对焦镜头，尚未给出调焦后的清晰度结论；不将Gamma调节当作失焦修复。


## CONTRAST PROBE01实物：暗场读数与1.50倍偏好

gamma18实物反馈仍灰，完全遮镜也明显灰；这说明需要测量暗场，但尚未确定灰位来自传感器、黑电平、显示映射或其他环节。新诊断保持gamma18摄像头与DDR内容，左图是基线，仅右图x640..1279、y120..599在显示端调节对比度。KEY1依次循环1.00/1.25/1.50/1.75/2.00倍，默认1.50倍；20ms消抖、帧边界生效。映射不回写DDR，也不改变未来CNN输入。

底部出现CONTRAST PROBE01、RAW A/B/C/D均值、档位/KEY1提示和参考色条。复用中心128×128区的四奇偶位置统计，只有完整合法帧发布40bit整组结果，经异步FIFO和像素域整组锁存；并非与显示前台逐帧绑定。请完全遮镜、等待读数稳定后记录A/B/C/D，再打开镜头比较各档和左图。本次遮镜测得65/66/66/67，成为后续固定黑位候选的依据；旧诊断本身没有自动BLC、锐化或CNN处理。

使用`python scripts/prepare_efinity.py --camera-profile short_exposure --bayer-pattern 3 --tone-profile gamma18 --black-level-profile none --contrast-probe`复现旧未扣黑诊断；它与`--color-probe`互斥并要求Bayer3/gamma18，普通版本仍默认gamma18，旧color-probe要求Bayer0/linear。候选名为[style_video_contrast_probe.bit](../build/style_video_contrast_probe.bit)，完成状态见[contrast_probe_receipt.json](../build/contrast_probe_receipt.json)。原gamma18/22位流和实物历史保留；该诊断已获用户标记/KEY1正常，CAP/COPY30、UF/ERR/DROP0；遮镜A041/B042/C042/D043，右侧1.50倍较自然。正式画质仍没有通过验收。


## 当前BLC实物反馈：黑灰底解决，轻微绿偏待测

用户确认CONTRAST PROBE01标记和KEY1正常、CAP/COPY30且UF/ERR/DROP0；完全遮镜后A041/B042/C042/D043，即65/66/66/67，右侧1.50倍较自然。新[style_video_black_level.bit](../build/style_video_black_level.bit)及[black_level_receipt.json](../build/black_level_receipt.json)独立保存，旧位流和实物记录保留。BLC位流已获用户遮镜“纯黑”、RIGHT1.00最自然、CAP/COPY30及UF/ERR/DROP0反馈；标记仍为同一CONTRAST PROBE01，不能唯一识别BLC版本，务必选择新文件，运行身份仍按会话关联。

预处理新增BLACK_LEVEL_A/B/C/D，通用默认0；物理measured为65/66/66/67。A/B/C/D固定指2×2左上/右上/左下/右下，每个RAW10先`max(raw-offset,0)`，再按Bayer选色、两G均值、最后截取8bit，后接gamma18。BGGR3对应蓝A65、红D67、两G各66。没有白点拉伸、曝光或白平衡更改。旧黑样本截到8bit约16，gamma18后55，可解释灰底；理想等于偏置的样本扣后0→0，用户遮镜观感已为纯黑，按本次反馈黑灰底问题已解决；未测量每个数字像素是否恒为0，剩余噪声与画质不能据此全面验收。

`--black-level-profile none/measured`中普通默认measured，仅支持short_exposure/Bayer3；color-probe强制none。复现该已测BLC为`python scripts/prepare_efinity.py --camera-profile short_exposure --bayer-pattern 3 --tone-profile gamma18 --black-level-profile measured --white-balance-profile none --contrast-probe --contrast-initial-level 2`。复现旧gamma18/22或旧contrast需显式none。DDR/COPY/未来CNN接收扣黑后gamma18像素，位宽、字节序、握手不变但数值语义更新。

右侧KEY1对比度界面保持，已测BLC位流启动1.50，但用户校正后选择RIGHT1.00最自然；原始RAW统计仍取自BLC前，因此遮镜A/B/C/D仍可能041..043，不应要求变为0。这是此次配置下的固定偏置，不是自动黑位跟踪，不代表全幅、全温度或其他曝光已校准。


最新颜色反馈：用户认为魔方颜色大致正确，但画面仍轻微偏绿。后续白纸RAW A09C/B0F5/C0F5/D0A0已收到；该BLC历史位流未加入白平衡增益，当前固定WB已实测不发绿与30fps/零错误，但室外天空微红；白平衡与清晰度未验收。当前WB版本物理顶层已显式设置对比度启动档0（1.00），通用style_contrast_probe的INITIAL_LEVEL默认2（1.50）保持；用户已确认WB版不发绿，CAP/COPY均30、UF/ERR/DROP均0；直接拍室外天空微红，隔玻璃更红，整体颜色适应性和清晰度仍待验证；启动档位未单独读回。


## 当前固定白平衡实测：室外天空微红待诊断

白纸原始A09C/B0F5/C0F5/D0A0=156/245/245/160，扣黑后按BGGR3得到R93/G179/B91。以G为基准，固定Q8增益R493/G256/B504约为1.926/1/1.969；原始证据在[white_balance_measurement.json](../build/white_balance_measurement.json)。新文件[style_video_white_balance.bit](../build/style_video_white_balance.bit)及[white_balance_receipt.json](../build/white_balance_receipt.json)单独记录，旧BLC黑底已通过的实物结论保留，用户已确认WB版不发绿，CAP/COPY均30、UF/ERR/DROP均0；直接拍室外天空微红，隔玻璃更红，整体颜色适应性和清晰度仍待验证。

处理顺序为物理RAW10各点钳位扣黑→Bayer选R/B和floor两G均值→`min(1023,(raw10*gain_q8+128)>>8)`→RGB8截高8位→gamma18。乘加为21bit无符号，Q8半向上舍入，10bit饱和；通用WB_GAIN_R/G/B_Q8均256，物理measured为493/256/504。代入此次均值预测RGB10各179、gamma前RGB8各44，不保证每个像素一致。没有修改曝光、传感器增益或白点拉伸。

`--white-balance-profile none/measured`默认随BLC选择：measured BLC默认measured WB，其他默认none；measured WB只适用于BGGR3/short_exposure/measured BLC。当前准备：`python scripts/prepare_efinity.py --camera-profile short_exposure --bayer-pattern 3 --tone-profile gamma18 --black-level-profile measured --white-balance-profile measured --contrast-probe --contrast-initial-level 0`。复现旧BLC必须显式WB none及contrast初档2；旧无BLC对比度默认WB none/初档2。

本候选物理对比度启动0即1.00，通用INITIAL_LEVEL默认2仍保留，KEY1五档不变。左图是BLC+固定WB+gamma18基线，右图启动1.00时透传。RAW统计仍在BLC/WB前，因此白纸A/B/C/D不必相等；UI仍CONTRAST PROBE01，需选择新位流文件，不能靠复用标题认定版本。DDR/CNN输入数值语义变为扣黑、固定WB、近似gamma1.8，队友应匹配训练预处理。

这是当前光照一次测量的固定校准，不是AWB或完整ISP；R/B增益可能放大噪声、造成高光饱和及改变整体亮度。用户已确认WB版不发绿，CAP/COPY均30、UF/ERR/DROP均0；直接拍室外天空微红，隔玻璃更红，整体颜色适应性和清晰度仍待验证。

### 室外中性色复测

较暗白纸059/071/071/05C已确认不隔玻璃测量。新增较亮白纸0A9/110/110/0AD扣黑后RGB106/206/104，按现有Q8增益493/256/504及Gamma1.8计算约为RGB104/104/104；天空0BE/0FB/0FB/0BE扣黑后RGB123/185/125，计算约为RGB113/98/115。用户确认天空肉眼呈白色或灰白云层。以上是对中心ROI均值套用处理公式的预测，不是逐像素输出实测；两次采样照明光谱及最新两组是否均无玻璃未独立确认。两组通道比例不同，仅换一组全局增益不能同时使这两个均值中性；偏色物理原因仍未确定。当前RTL、白平衡增益和位流保持不变。见[配对测量记录](../build/neutral_scene_pair.json)。
