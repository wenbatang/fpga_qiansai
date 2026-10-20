"""Build the offline RTL explainer from current sources and verification receipts.

No browser/network dependency. Port/parameter tables and embedded source are
regenerated from the actual RTL, while reviewed explanations remain explicit.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

DESCRIPTIONS = {
    "style_ddr_framebuffer": {
        "title":"DDR帧缓存公共接口", "domain":"100MHz core；显示请求/安全窗口由内部同步", "group":"存储与控制",
        "purpose":"封装采集、CNN、显示共享的帧存储边界：四DMA、AXI仲裁、帧池、完整帧发布、APB与IRQ。",
        "logic":"内部复用未修改的style_platform_core core；四输入槽加两结果槽，每槽2MiB，按RGBX8888存储。采集和结果的最后DDR写响应成功后才确认完整帧，原图和结果按frame_id配对保留。物理DDR控制器/PHY仍由板级顶层经AXI128连接。",
        "handshake":"cam_*接独立采集模块；accel_*接队友完整CNN；display_*接显示模块，逐行原图640像素后结果640像素。APB的paddr/psel/penable/pwrite/pwdata/prdata/pready/pslverr及irq是Sapphire接入口，系统基址由BSP分配。",
        "recovery":"仍保留原有背压、坏帧取消、超时/AXI错误处理和安全换帧。当前顶层FORCE_BYPASS=1、APB空闲，内部COPY用于通路验证；新显示模块右图默认黑色，不代表已接CNN。",
        "states":"公共接口本身无新增状态，全部帧/任务/显示状态机位于core子实例。由generate_ddr_wrapper.py按核心真实端口生成，不能只复制此文件而遗漏内部RTL。"},
    "style_hdmi_display": {
        "title":"独立HDMI显示与CNN预留区", "domain":"100MHz core / 74.25MHz pixel / 可选50MHz camera诊断", "group":"显示",
        "purpose":"把DDR配对RGB流变为720p60视频和TMDS编码字；默认左侧原图、右侧图像区域固定黑色留给CNN。",
        "logic":"内部显示FIFO/时序/OSD后接可选颜色、对比度、白平衡和性能诊断；RAW/WB统计各通过整组异步FIFO跨域，UF通过Gray计数同步回core。RESERVE_CNN=1时最终遮罩在全部叠加与紫色欠载保护之后固定右图黑色；仍消费全部双图token以保持行序。",
        "handshake":"s_rgb/s_valid/s_ready属于core域，一行先原图后结果。refresh_request/safe_window来自pixel域，refresh_ack/core_flush来自core域，内部保持原同步及快照握手。video_rgb/de/hs/vs、x/y属于pixel域；tmds四组10bit字接既有板级串化器。raw_mean/WB状态属于camera域。",
        "recovery":"长时供数不足沿用原整帧欠载保护及UF报告，右侧预留图像仍黑。拿到完整CNN后同时连接accel、清硬件/软件bypass并用--show-result解除RESERVE_CNN；单独解除时现有结果仍是COPY。新版未上板。",
        "states":"复用sink的flush/快照/欠载状态和原诊断模块状态；公共层新增常量右图遮罩，没有另造帧缓存。ENCODE_TMDS默认1，通用仿真显式0，Efinity构建使用保留的licensed encoder。"},
    "style_camera_capture": {
        "title":"独立摄像头采集接口", "domain":"50MHz camera → 100MHz core；raw_mean仍在camera域", "group":"采集",
        "purpose":"把RAW10预处理、Gamma、图像/取消FIFO、计数CDC和可选RAW统计封装成可复用采集模块。",
        "logic":"输入高有效VS/HS、DE和40bit RAW10×4，内部DE与HS门控；逐物理位置扣黑→Bayer/G均值/白平衡→半分辨率网格缩小→Gamma→59bit图像FIFO。32bit取消FIFO独立跨域；帧/丢弃/错误计数Gray同步；可选原始A/B/C/D均值输出给现有白纸校准和诊断。",
        "handshake":"m_rgb[23:0],m_valid,m_ready,m_sof,m_eol,m_eof,m_frame_id均为core域，valid&&ready传一像素，背压期间整组保持。m_abort与编号无ready，接收方每个有效拍都处理；raw_mean是camera域脉冲，不能直接给其他时钟域或CPU采样。",
        "recovery":"输入CSI无反压，长期堵塞会取消坏帧；取消和像素独立跨域，可先可后到达，平台须按编号丢弃整帧。取消队列溢出锁存abort_queue_fault，共同复位恢复。模块不含D-PHY/CSI IP、I²C主机或DDR DMA；本次封装保留全部图像参数，新位流实板待测。",
        "states":"复用已验证子模块状态机；本层只有取消队列故障锁存和两级同步。源/目的复位须协调，FIFO使用同一async_rst_n。"},
    "style_rgb_gamma": {
        "title": "RGB亮度编码近似", "domain": "摄像头像素域内纯组合逻辑", "group": "采集",
        "purpose": "在实测有效BGGR3的RGB输出上提供gamma1.8/2.2显示编码近似；gamma18已实测仍明显发灰，当前通过独立显示端对比度诊断继续定位。",
        "logic": "256×8表离线按floor(255*(x/255)^(10/GAMMA_TENTHS)+0.5)生成，GAMMA_TENTHS支持18和22、默认18；R/G/B分别使用相同函数。ENABLE=1使用所选表，ENABLE=0全部24位透传；不含运行时浮点、幂运算、时钟、寄存器或外部mem依赖。官方2P2.mem是x^2.2的压暗方向，不能直接复用。",
        "handshake": "s_rgb到m_rgb组合映射；物理顶层在camera_preprocess与camera_cdc入包之间插入，原valid/ready及全部帧标志保持。DDR、COPY及未来CNN输入都收到当前tone编码后的RGB888，等待ready时payload继续稳定。",
        "recovery": "这是近似gamma编码，不是精确sRGB、白平衡或完整ISP。原gamma22位流颜色获确认但图像模糊、低对比；gamma18用户反馈仍明显发灰，完全遮镜也灰，CAP/COPY30且UF/ERR/DROP0；灰位来源尚未测定。需线性输入的队友用--tone-profile linear关闭，避免训练/部署亮度语义不一致。",
        "states": "无状态；确定性组合查表，零新增流水拍。维护scripts/generate_gamma.py后重新生成RTL并核对LUT审计。",
    },
    "style_camera_reg_rom": {
        "title": "摄像头寄存器配置ROM", "domain": "5 MHz I²C控制时钟域", "group": "采集",
        "purpose": "在项目自身RTL中选择已验证v6配置或同模式v1短曝光实验值，保留厂商ROM原件。",
        "logic": "164项配置保持v6顺序和其余数据；short_exposure只把3E00/3E01/3E02由01/BB/F0恢复为v1的00/BA/D0。RAW10、4lane、PLL、1920×1080 ROI、增益和方向寄存器不随该实验替换。25位ROM字包含16位地址、8位数据和1位读写标志。",
        "handshake": "clock同步读取addr_ptr所选项，rdata_out供配置序列状态机使用；不是DDR数据流，也没有像素ready/valid。",
        "recovery": "短曝光已获用户CAP/COPY30、UF/ERR/DROP0；后续COLOR PROBE01右图确认有效BGGR3颜色正确但偏暗。正式BGGR+gamma不再改传感器寄存器，颜色已获确认，图像质量待优化。ACK/寄存器没有读回，原13fps历史与GBRG失败保留。",
        "states": "索引到寄存器字的同步ROM查询；无采集或显示状态机。",
    },
    "style_camera_reg_set": {
        "title": "摄像头寄存器命令序列", "domain": "5 MHz I²C控制时钟域", "group": "采集",
        "purpose": "以项目自己的序列模块驱动同一个官方I²C控制器，保留单一总线主机并选择配置ROM。",
        "logic": "等待I²C控制器init_done，按索引读取ROM，发一拍wr_en或rd_en，等待对应done再推进，完成DATA_LENGTH项后停止。通用缺省61，物理initializer明确传164，ROM通用深度256也被实例覆盖为164；short_exposure仍只有三项数据差异。",
        "handshake": "addr/dout/dev_addr伴随命令给控制器；wr_done/rd_done只表示事务流程结束。当前controller读数据dout未驱动，未新增芯片ID、HTS/VTS或曝光读回能力。",
        "recovery": "没有传感器NACK验证，不能以rd_done当作读回成功。未来RISC-V接管时必须停用本配置主机；profile切换需重新准备/构建并复位执行初始化，不能在运行中无握手替换ROM。",
        "states": "S0等待/选择 → S1 ROM等待 → S2发命令 → S3撤回使能 → S4等done后加索引。",
    },
    "style_camera_initializer": {
        "title": "摄像头 I²C 初始化", "domain": "5 MHz I²C控制时钟域", "group": "采集",
        "purpose": "复用V4/J5官方寄存器ROM与I²C控制器，给独立平台一个明确的命令序列完成条件。",
        "logic": "通过项目自己的style_camera_reg_set/ROM执行164个配置事务，以wr_done或rd_done累计完成数，最后置config_done并保持到复位。prepare支持verified基线和默认short_exposure实验profile，后者只恢复同模式v1的三个曝光寄存器值。顶层先等待PLL锁定、复位同步释放和启动延时，再开始配置；config_done经两级同步到核心域，与DDR cal_done一起允许采集DMA接新帧。",
        "handshake": "SCL/SDA是开漏控制，scl_padoen_o/sda_padoen_o低有效，在顶层翻转成Interface Designer的高有效OE。没有RGB流握手；未来RISC-V接管同一I²C总线前必须禁用本配置主机。",
        "recovery": "config_done只表示ROM事务结束，不证明ACK、型号或寄存器读回正确，继承controller读数据dout未驱动。未新增RAW FPS/ID/HTS/VTS读回。短曝光30fps已确认，诊断右图BGGR3颜色已确认但偏暗；正式gamma版本颜色已获确认，图像质量待优化。",
        "states": "项目style_camera_reg_set选择ROM并发命令，继承官方i2c_16addr_8data控制事务；本层completed_transactions及config_done锁存。",
    },
    "style_camera_preprocess": {
        "title": "摄像头预处理", "domain": "摄像头像素时钟域", "group": "采集",
        "purpose": "把官方 CSI 输出的每拍四个 RAW10 像素转换成 640×480 RGB888，给后续帧存储一个统一流接口。",
        "logic": "保留一条偶数源行，在下一条奇数行组成2×2单元：A左上/B右上/C左下/D右下各RAW10先做max(raw-BL,0)，再按Bayer取R/B、平均两G；BLACK_LEVEL_A/B/C/D通用默认0，物理measured为65/66/66/67。得到半分辨率 RGB，再按 floor 坐标最近邻缩放。默认从 1920×1080 RAW 得到 960×540 Bayer 单元网格，再缩放至 640×480。这是半分辨率 Debayer，不是完整分辨率双线性插值。扣黑后先取R/B与floor两G均值，再按WB_GAIN_R/G/B_Q8做min(1023,(raw10*gain+128)>>8)，21bit无符号中间量，最后截取高8位。通用增益均256，物理measured493/256/504。没有白点拉伸或曝光改动；固定白平衡不是AWB。",
        "handshake": "原生Efinix CSI输出的VS/HS高有效：VS上升沿开始帧、下降沿结束帧，默认VS_ACTIVE=1，物理顶层显式设置1，并传入s_valid=w_mipi_rx_de&w_mipi_rx_hs，与官方已验证frame_buffer一致。低极性通用输入仍可显式设置0。输入没有ready，输出背压由packet FIFO吸收，等待时数据/标志保持。尾像素等真实VS结束验证后才带EOF发布。",
        "recovery": "短行、长行、短帧、多余行或溢出都报告abort，半帧不能发布。原低极性默认是确定的RTL适配错误，首次用户观察为OSD正常但FRAME/FPS0；当时运行bit指纹未知，不能断言唯一实物原因。高极性+DE与HS门控修复的软硬件状态见回执。初始化过渡帧可留下累计错误使D2持续亮，重测看CAP/COPY FPS和FRAME增长，不要求D2灭。",
        "states": "frame_open/frame_bad 管输入帧；groups_seen/rows_seen 核对行列；next_x/next_y 与余数累加器做常数比例缩放；tail_pending/tail_good 执行最后像素验证。",
    },
    "style_cfa_stats": {
        "title": "RAW四采样位置统计", "domain": "摄像头像素时钟域", "group": "采集",
        "purpose": "颜色/对比度诊断共用旁路，直接测BLC/WB前中心128×128原始RAW的四奇偶位置。当前遮镜实测A/B/C/D=65/66/66/67；读数不自动反馈校正。",
        "logic": "A=偶行偶列、B=偶行奇列、C=奇行偶列、D=奇行奇列；每类4096个10bit样本分别求和后右移12位取平均。四结果打包为D/C/B/A，从低位到高位每项10bit。默认ROI源坐标x896..1023、y476..603。",
        "handshake": "共享原CSI输入，完全不对主采集产生背压。只在完整合法帧的VS下降后发一拍mean_valid；顶层经40bit异步FIFO转到像素域，在显示y640边界锁存整组读数。",
        "recovery": "短行、长行、短帧、超范围有效信号或样本数不足均不发布；复位清空当前统计。诊断FIFO满则锁存溢出并将显示读数置无效，不将旧均值冒充新值。",
        "states": "VS帧边界、HS行计数、group计数和四路sum/count；均值只在帧尾更新。",
    },
    "style_color_probe_overlay": {
        "title": "临时颜色诊断显示", "domain": "74.25 MHz像素时钟域", "group": "显示",
        "purpose": "在COLOR PROBE 01版本中同时比较RGGB0和BGGR3，并提供独立标准RGB色条和四CFA均值。",
        "logic": "采集以RGGB0解释；左图保持原像素，右图仅在图像区交换R/B，等效于同一RAW按BGGR3重建。底部固定文字标出版本和0/3两种解释，显示A/B/C/D十六进制均值，再绘制红/绿/蓝/白/灰参考条。黄色框标记对应中心RAW统计区。",
        "handshake": "组合覆盖video_rgb，视频HS/VS/DE和像素时序保持原连接；参考条在右图交换之后覆盖，因此不受摄像头Bayer和右图通道交换影响。",
        "recovery": "sample_valid=0时显示---。这是显式--color-probe启用的临时诊断，右图通道交换不是CNN结果，不能作为正式风格处理或颜色验收完成。",
        "states": "无时序状态；按x/y选择原图、右图交换、边框、字体和参考色条。",
    },
    "style_contrast_probe": {
        "title": "显示端对比度与RAW诊断", "domain": "74.25 MHz像素时钟域", "group": "显示",
        "purpose": "CONTRAST PROBE01左图保留当前摄像头处理后的基线，右图用KEY1切换五档对比度，同时给出BLC前原始RAW四位置均值；新BLC候选复用同一UI。",
        "logic": "右图x640..1279/y120..599对RGB各通道使用clip[0,255](floor(((code-128)*(4+level)+514)/4))。level0..4对应1.00/1.25/1.50/1.75/2.00倍；level0严格透传。13bit有符号中间量，以128为中心、加2后算术右移两位作舍入并饱和；并非减去实测传感器黑位。页脚显示版本、LEFT BASE、RAW十六进制读数、RIGHT档位/KEY1及独立RGB白灰条。",
        "handshake": "KEY1低有效，模块内2FF同步后连续1485000像素周期稳定才接受，74.25MHz时20ms。稳定按下使requested_level循环，长按不重复，释放也需消抖；当前level只在x=y=0锁存，同拍按下可到下一帧生效。rgb组合输出、零像素流水延迟，HS/VS/DE时序保持。",
        "recovery": "通用复位INITIAL_LEVEL默认2即1.50倍；当前WB版本物理顶层显式设0即1.00，已实测不发绿及30fps，室外天空微红待诊断。sample_valid=0时四均值显示---。仅显示右图与诊断页脚被映射，DDR及未来CNN输入不变。没有自动BLC、白平衡、锐化或CNN推理；仅为定位与可调对照，不保证根治灰感。",
        "states": "按键同步/消抖计数 → requested_level → 帧起点锁存level；像素覆盖为组合选择。",
    },
    "style_async_fifo": {
        "title": "异步 FIFO", "domain": "写时钟域 ↔ 读时钟域", "group": "跨域",
        "purpose": "隔离摄像头、DDR 核心和显示时钟，保持数据及帧标志一同跨域。",
        "logic": "双口 RAM 使用本域二进制指针寻址，Gray 指针经两级同步传到另一域以判断空/满。读端先把 RAM 字注册到 read-ahead 寄存器，再用 m_valid 交付。容量是 2^ADDR_BITS 个 RAM 字加一个预取字。",
        "handshake": "写端 s_valid&s_ready 接受一字；读端 m_valid&m_ready 消费一字。读端预取输出在 ready=0 时保持。wr_level 是 RAM 所有权占用量，rd_level 包含已预取的字。",
        "recovery": "必须共同复位两端，不能只清一个指针。异步断言复位，各域通过 style_reset_sync 同步释放；复位未释放时 ready/valid 为 0。",
        "states": "full、out_valid 和 wbin/rbin 指针构成状态，不依赖厂商 FIFO IP。",
    },
    "style_reset_sync": {
        "title": "复位同步释放", "domain": "每个使用它的本地时钟域", "group": "跨域",
        "purpose": "允许共同复位立即断言，避免异步撤销复位破坏本域状态。",
        "logic": "异步低有效输入清零同步移位链，复位撤回后经过本域若干上升沿才输出有效 rst_n。",
        "handshake": "复位没有 ready/valid。每个异步 FIFO 的写域、读域各有独立实例。",
        "recovery": "PLL 失锁、DDR 未就绪或顶层复位时重新断言；恢复启动条件由平台顶层控制。",
        "states": "同步移位链。",
    },
    "style_cdc_counter": {
        "title": "计数诊断跨域", "domain": "源计数域 → 核心寄存器域", "group": "跨域",
        "purpose": "把摄像头和显示统计安全送到核心寄存器，避免直接采样变化的 32 位二进制数。",
        "logic": "源域注册 Gray 编码，经两级目的域同步，再组合解码为二进制。显示诊断会有数拍延迟。",
        "handshake": "只适用于每个源时钟最多增加 1 的单调计数；不适合任意变化的配置字、帧地址或一拍跳多个计数。",
        "recovery": "两域计数与同步链应按同一个系统复位重新起点；诊断数不是事务完成握手。",
        "states": "源 Gray 寄存器、目的同步级；无任务状态机。",
    },
    "style_pixel_packer": {
        "title": "RGB888 → AXI 打包", "domain": "核心 DDR 时钟域", "group": "存储",
        "purpose": "把四个 RGB888 像素整理成一拍 128 位 DDR 写数据。",
        "logic": "每像素形成字 0x00RRGGBB；第一个像素在 bits31:0，第四个在 bits127:96。lane 按 0..3 累积，四像素后给出 m_data。当前整帧尺寸是 4 的倍数，因此没有有效帧尾 padding。",
        "handshake": "输出等待时保持 m_valid/m_data/m_last；s_ready 管输入。s_last 是整帧最后像素，不是每行结束。clear 用于新任务或丢弃半帧。",
        "recovery": "clear 丢弃未完成打包和待输出字，只能用于上层已决定取消的帧，不能在有效 AXI 事务中直接撤回数据。",
        "states": "lane、pack_data、输出 valid。",
    },
    "style_pixel_unpacker": {
        "title": "AXI → RGB888 解包", "domain": "核心 DDR 时钟域", "group": "存储",
        "purpose": "把 128 位读数据还原成四个顺序像素，供计算或显示使用。",
        "logic": "按 lane=0..3 取各 32 位字的低 24 位，忽略高 8 位 RGBX padding；末拍 m_last 只在第四个像素上有效。",
        "handshake": "m_valid&m_ready 才推进 lane；上一个字最后像素被接收时可以同时接下一个 128 位字。",
        "recovery": "clear 取消本地待输出字；读 DMA 的 AXI 事务仍须先按协议 drain。",
        "states": "有效字寄存器及 lane 计数。",
    },
    "style_axi_write_dma": {
        "title": "突发写 DMA", "domain": "核心 DDR 时钟域", "group": "存储",
        "purpose": "把连续 128 位数据写到一段 DDR，采集和结果各用一个实例。",
        "logic": "命令给地址和总拍数；先收满一次 burst 的数据，再独立完成 AW 和 W 握手，最后检查 B。每 burst 不超过 BURST_BEATS，不跨 4 KiB，所有 byte strobe 有效。只有最后一拍 B 返回 OKAY，整帧才 done 且 error=0。",
        "handshake": "cmd_valid/cmd_ready 接命令；s_valid/s_ready 收数据；AWVALID/WVALID 一旦提供就不能因 abort 或超时撤回；BREADY 接收写响应。",
        "recovery": "错误码 1 命令、2 abort、3 LAST、4 RESP、5 ID、6 timeout。已发出的写事务必须完成 B；没有响应的 timeout 置 sticky_fault，禁止新命令，要求复位而不是直接重用 AXI。失败帧绝不发布。",
        "states": "IDLE → FILL → ISSUE → RESPONSE；每 burst 回 FILL，整任务回 IDLE。",
    },
    "style_axi_read_dma": {
        "title": "突发读 DMA", "domain": "核心 DDR 时钟域", "group": "存储",
        "purpose": "为计算和显示读出 DDR 数据，每个实例只保留一个未完成 burst。",
        "logic": "发AR后先在burst buffer收完整段，检查每拍RID/RRESP/RLAST，再提供m_valid，坏响应不先进入图像FIFO。通用模块默认BURST_BEATS=16；平台读实例用READ_BURST_BEATS，现默认128，写实例仍16。较大读burst分摊每次首读等待，地址对齐与4KiB边界仍受检查。",
        "handshake": "cmd_valid/cmd_ready 接命令；ARVALID 保持到 ARREADY；RREADY drain 已接事务；m_valid/m_ready 输出已验证数据。m_last 是该命令的最后一拍。",
        "recovery": "错误码同写 DMA。错误或 abort 仍 drain 到真实 RLAST；timeout 为 sticky_fault，不能凭计时器假设总线事务消失。已经提供且被背压的输出拍仍保持稳定。",
        "states": "IDLE → ADDRESS → RECEIVE → OUTPUT；每段验证后 OUTPUT，剩余段再 ADDRESS。",
    },
    "style_axi_arbiter": {
        "title": "共享 DDR 仲裁", "domain": "核心 DDR 时钟域", "group": "存储",
        "purpose": "把两个写客户端和两个读客户端合到板载 DDR 的一个 AXI 接口。",
        "logic": "写方向轮转公平分配，读方向偏向 client1 显示，但以 READ_CLIENT1_LIMIT 限制连续显示授权，避免计算永久饥饿。读写方向可各有一个 outstanding，独立运行。最小 slice 是 client0。",
        "handshake": "先注册事务 owner 再提供 AW/AR；等待期间不能换 owner。B 只送写 owner，R 只送读 owner；B 或 RLAST 握手后释放。",
        "recovery": "错误响应仍交给 owner DMA 判断；仲裁器不会替代 DDR 响应或自行取消无响应事务。",
        "states": "wr_active/wr_owner/aw_seen/w_seen 与 rd_active/rd_owner/ar_seen 两组状态。",
    },
    "style_frame_pool": {
        "title": "输入/结果帧池", "domain": "核心 DDR 时钟域", "group": "帧管理",
        "purpose": "维护输入与结果独立所有权，让原画和风格结果使用同一个 frame_id。",
        "logic": "四个输入槽、两个结果槽。优先给采集一个空输入槽；计算选择最早 READY 输入与空结果。完成后保留原图和结果为 pending pair，显示安全换帧后才释放上一对。地址由 BASE_ADDR+slot*SLOT_BYTES 计算。",
        "handshake": "cap_take/cap_done、job_take/job_done、display_switch 是本域事件，必须与对应 slot 和成功标志同时提供。cap_done/job_done 只在全帧 DDR 响应确认后送入。",
        "recovery": "失败采集和失败任务回收未发布槽；有待显示 pair 时不再取下一个 job，避免覆盖 pending。无空槽时上层显式丢新输入帧并计数。",
        "states": "输入 FREE → CAPTURE → READY → PROCESS → RETAIN → FREE；结果 OUT_FREE → OUT_WRITE → OUT_RETAIN → OUT_FREE。",
    },
    "style_accel_bypass": {
        "title": "复制占位计算模块", "domain": "核心 DDR 时钟域", "group": "队友接口",
        "purpose": "队友 CNN 未完成时先验证完整任务链路，输入像素和标志原样返回。",
        "logic": "一个弹性寄存器保存 RGB、SOF/EOL/EOF 和 frame_id。它没有卷积、网络权重或风格迁移能力。",
        "handshake": "标准 ready/valid，空输出或下游愿意接收时可接新数据；输出等待时 payload 保持。",
        "recovery": "clear 取消本地占位输出，任务取消仍由平台处理 DMA 和帧槽。",
        "states": "valid 一位状态，数据打包为 59 位。",
    },
    "style_platform_core": {
        "title": "平台控制与集成核心", "domain": "核心 DDR 时钟域", "group": "集成",
        "purpose": "连接采集、帧池、复制/外部加速器、显示、四个 DMA、AXI 仲裁和 APB 寄存器。",
        "logic": "采集FSM逐像素核对帧编号及SOF/EOL/EOF；任务FSM读READY输入并写结果；显示FSM排空旧读、清FIFO、在安全窗口切换，再逐行原图640像素/结果640像素。READ_BURST_BEATS默认128用于任务/显示读，写DMA仍16拍。FORCE_BYPASS=1只复制，未实例化Sapphire。",
        "handshake": "AXI128、ID_WIDTH=4；采集写 ID0，结果写 ID1，计算读 ID2，显示读 ID3。外部加速器是 RGB888 双向流及 accel_start/accel_abort，帧标志只在握手拍有效。start之后有J_ARM空拍，允许队友按时钟启动并清除旧valid；abort期间队友必须清空未交付输出并回到空闲。APB3 是 offsets 接口，不包含 CPU 系统基地址。",
        "recovery": "坏 frame marker、摄像头 abort、DMA 错误都禁止发布半帧；sticky fault 形成 fatal_fault 并停止新任务，需系统复位。显示欠载计数变化时立即进入D_DRAIN、取消旧读并丢弃本地解包数据，避免像素端标粉后停止消费造成超过10ms的无进展误超时。旧AXI仍按协议排空；FIFO清空和pair释放继续等safe_window。错误/丢帧合计是各阶段事件之和，同一坏帧可被多阶段记录，不是去重后的坏帧数。",
        "states": "采集 C_IDLE/C_COMMAND/C_STREAM/C_WAIT/C_ABORT；任务 J_IDLE/J_COMMAND/J_ARM/J_STREAM/J_WAIT/J_ABORT；显示 D_WAIT/D_DRAIN/D_FLUSH/D_SETTLE/D_COMMAND/D_STREAM。",
    },
    "style_control_regs": {
        "title": "APB 控制与统计寄存器", "domain": "核心 DDR 时钟域", "group": "控制",
        "purpose": "为未来Sapphire软件提供平台启停、模式、事件、中断和FPS接口，独立模式使用复位默认配置。",
        "logic": "APB3访问阶段psel&&penable读写。CONTROL管理enable/auto/bypass；START产生单拍触发，平台保存一个待执行手动任务，重复触发合并。IRQ_STATUS按event_set置sticky，W1C清除，事件同拍发生时置位优先。每个fps_tick计算完整采集和完整处理计数差，饱和到65535。",
        "handshake": "PREADY固定1；未定义地址或写只读寄存器PSLVERR。paddr是byte offset，真实SoC寄存器基址尚未分配。IRQ为irq_status&irq_enable非零的电平。",
        "recovery": "复位默认enable/auto/bypass=1，IRQ使能=0；软件应读IRQ原因、完成处理、写IRQ_CLEAR再进行PLIC应答。配置不能替代DMA/frame安全完成。",
        "states": "寄存器状态、irq_status/irq_enable、前一秒计数；没有隐含软件CPU。",
    },
    "style_display_sink": {
        "title": "布局与像素显示端", "domain": "核心域 → 74.25 MHz 像素域", "group": "显示",
        "purpose": "把每行原图再结果的 1280×480 token 流放到 720p 显示的 y120..599。",
        "logic": "4096 像素 RAM FIFO 加预取；模式 0 两侧、1 仅左、2 仅右。隐藏的半边仍消耗其全部 tokens。配置在核心域注册快照，再通过内部 ACK 两级同步，在安全窗口锁存。",
        "handshake": "refresh_request 从启动及每次图像区结束保持到安全 ACK；core_flush 扩展为至少 16 个核心周期共同复位 FIFO；ACK 只表示刷新配置接纳，不等同于 DDR 吞吐保证。",
        "recovery": "空前台黑屏不报错。有效前台第一次没有 FIFO head 即标粉 FF00FF，余下本帧全粉并停止消费，underflow_count 只增一次。核心同步看到欠载计数变化立即取消并排空旧显示读任务；FIFOflush、槽释放和新配置ACK仍等安全窗口，不能在图像中途重置FIFO。",
        "states": "refresh_request、front 配置快照、frame_poisoned；safe_window 默认 y600..749 和 0..99，y100..119 留 guard。",
    },
    "style_video_timing": {
        "title": "标准 720p60 时序", "domain": "74.25 MHz 像素时钟域", "group": "显示",
        "purpose": "生成显示坐标、DE、正极性 HS/VS、帧起点、安全窗口。",
        "logic": "默认 H=1280+110+40+220=1650，V=720+5+5+20=750；74.25 MHz 总计对应 60 Hz。有效区原点 x0/y0；HS1390..1429，VS725..729。",
        "handshake": "持续扫描，不能给显示器施加 ready 背压。RGB 与时序必须保持同拍；新增寄存级须一起延迟。",
        "recovery": "pixel_rst_n 清计数并屏蔽 DE/HS/VS；恢复后从左上角重新扫描。",
        "states": "h_count/v_count 两级扫描计数。",
    },
    "style_osd": {
        "title": "文字和诊断叠加", "domain": "像素时钟域的组合逻辑", "group": "显示",
        "purpose": "显示ORIGINAL/RESULT、CAP FPS、COPY FPS、frame_id、RAW/DROP/ERR/UF累计诊断及BYPASS COPY。",
        "logic": "5×7字模放大两倍，组合生成命中和颜色；FPS十进制四位，frame_id八位十六进制。y88行RAW/DROP/ERR/UF均为八位十六进制累计数，RAW不是FPS。核心统计通过display_sink的同一次bundle握手锁存，UF在像素域accept_refresh锁存。文字不消耗DDR像素。",
        "handshake": "无流式握手且不额外增加整拍延迟；配置使用 display_sink 锁存的同一组前台值。",
        "recovery": "未接入真正 CNN 前保留 COPY FPS 标签，不能把重复显示或复制吞吐标成推理 FPS。",
        "states": "字形选择是组合逻辑，无任务状态机。",
    },
    "style_tmds_encoder": {
        "title": "TMDS 通道编码", "domain": "74.25 MHz 像素域", "group": "物理封装",
        "purpose": "将 RGB8 和 DE/控制转换为 10 位 TMDS 码，供易灵思高速输出串化。",
        "logic": "按 TMDS 编码减少跳变并维护 running disparity；有效像素与消隐控制码分别处理。实际 ports、参数和源码见下表，PLL/串化仍由 Efinity Interface Designer 负责。",
        "handshake": "像素持续刷新，无 ready；若编码器注册输出，控制与数据延迟须一起补偿。",
        "recovery": "复位或消隐重建 disparity；不包含音频或 HDMI InfoFrame。",
        "states": "running disparity 及编码输出寄存器。",
    },
    "style_ti60_top": {
        "title": "Ti60F225 物理平台顶层", "domain": "摄像头 / DDR 核心 / 像素 / 串化多域", "group": "物理封装",
        "purpose": "用 Ti60F225 V4 官方平台的 MIPI、DDR、PLL 和高速输出封装接入手写平台核心。",
        "logic": "复制并保留官方 V4/J5 平台必需 IP 和引脚配置，接入重构的预处理、RGB 流 FIFO、平台核心及显示。厂商加密 IP 不解密、不冒充通用 RTL。当前摄像头物理模式保持官方 RAW10 配置；未使用的fabric USER1调试JTAG接口移除，板卡下载JTAG不变。",
        "handshake": "复位包含核心、DDR、HDMI及摄像头PLL lock。config_done经核心两级同步，与DDR cal_done及abort队列健康共同允许采集DMA。原生CSI VS/HS高有效，显式VS_ACTIVE=1；RAW有效输入为CSI DE&HS。图像/abort经FIFO、计数经Gray跨域。",
        "recovery": "历史经历VS错误无图、半幅紫色、128拍读13fps和短曝光30fps；GBRG2实物失败。COLOR PROBE01版本/参考条正确，右侧BGGR3颜色正确但偏暗，CAP/COPY30、UF/ERR/DROP0。旧正式gamma22显式BGGR3，颜色已获确认但亮度/锐度未验收；gamma18在CDC前，不改曝光/DDR，用户仍反馈灰感；CONTRAST PROBE的标记/KEY1已确认正常，遮镜测得65/66/66/67；BLC版用户确认遮镜纯黑、RIGHT1.00最自然，CAP/COPY30且UF/ERR/DROP0；仍轻微偏绿，白平衡和清晰度未验收；COPY不是CNN，传感器ID没有读回。",
        "states": "平台初始化、复位释放和各子模块 FSM，实际顶层连接以嵌入源码为准。",
    },
}

REGISTERS = [
    ("000", "IDENT", "RO", "0x53565931（SVY1）"),
    ("004", "CONTROL", "RW", "bit0 enable，bit1 auto_run，bit2 bypass；复位均为1"),
    ("008", "START", "WO", "写bit0=1触发；手动请求保存一项待执行任务，重复写合并"),
    ("00C", "STATUS", "RO", "bit0平台启动条件就绪（DDR/摄像头配置/abort队列），1采集忙，2任务忙，3前台有效，4待发布，5fatal，10当前前台bypass，11手动任务待执行"),
    ("010", "IRQ_STATUS", "RO", "bit0采集完成，1处理完成，2前台发布，3帧/DMA/fatal错误；sticky"),
    ("014", "IRQ_ENABLE", "RW", "低4位中断使能；复位0"),
    ("018", "IRQ_CLEAR", "WO/W1C", "低4位写1清除；同拍新事件优先保留"),
    ("020", "DISPLAY_MODE", "RW", "0左右，1左原图/右黑，2左黑/右结果；复位0"),
    ("030", "WIDTH", "RO", "当前处理宽，默认640"),
    ("034", "HEIGHT", "RO", "当前处理高，默认480"),
    ("038", "STRIDE", "RO", "WIDTH*4，默认2560字节"),
    ("03C", "FORMAT", "RO", "1 = RGBX8888，LE word=0x00RRGGBB"),
    ("040", "FRAME_BASE", "RO", "0x01000000，DDR帧池地址；不是APB系统基址"),
    ("044", "SLOT_BYTES", "RO", "0x00200000，每槽2MiB"),
    ("048", "SLOT_COUNTS", "RO", "0x00000204：低8位4输入槽，bits15:8为2结果槽"),
    ("050", "READY_MASK", "RO", "低4位分别对应四个输入 READY 槽"),
    ("054", "FRONT_ID", "RO", "当前显示原图/结果共同frame_id"),
    ("060", "CAMERA_FRAMES", "RO", "摄像头看到的输入SOF总数"),
    ("064", "CAPTURED_COUNT", "RO", "完整采集且DDR写响应成功的帧数"),
    ("068", "PROCESSED_COUNT", "RO", "完整结果写响应成功的任务数；当前是复制完成"),
    ("06C", "DISPLAYED_COUNT", "RO", "发布新前台pair的次数，不是60Hz扫描次数"),
    ("070", "DROP_COUNT", "RO", "前端和采集阶段丢弃事件之和；同一坏帧可多阶段计数，非去重帧数"),
    ("074", "ERROR_COUNT", "RO", "前端、帧池、协议和显示错误事件之和；非去重坏帧数"),
    ("078", "UNDERFLOW_COUNT", "RO", "显示图像欠载次数，已从像素域跨域"),
    ("080", "FPS", "RO", "低16位采集完成FPS，高16位处理完成FPS，按CORE_HZ的一秒窗口统计"),
]

PERF_REGISTERS = [
    ("100","PERF_CONTROL","RW","bit0自动每秒快照（复位1）；bit1手动快照脉冲；bit2清统计脉冲。写2冻结并拍照，写1恢复自动，写4清统计并关闭自动；清统计保留在途帧/AXI跟踪"),
    ("104","PERF_SEQUENCE","RO","每个快照递增；其余RO字段属于同一快照。自动模式读前后核对序号，或写2冻结"),
    ("108","PERF_TICK_HZ","RO","延迟计时刻度/秒，实板1000000，故延迟单位微秒"),
    ("10C","PERF_FLAGS","RO","bit0存在配对发布记录；bit1延迟曾饱和32位；bit2标签异常累计非零"),
    ("110","PERF_FRAME_ID","RO","最后完整发布帧的ID；CAP/JOB/QUEUE/TOTAL LAST均与此ID对应"),
    ("114","PERF_CAP_LAST","RO","该发布帧从核心端分配采集帧槽到成功写入DDR的刻度数"),
    ("118","PERF_CAP_MAX","RO","清统计以来所有成功采集帧的最大耗时，不限于最后发布帧"),
    ("11C","PERF_JOB_LAST","RO","该发布帧从领取处理任务到完整结果DDR写入成功的刻度数，包含DMA"),
    ("120","PERF_JOB_MAX","RO","清统计以来所有成功处理任务的最大耗时"),
    ("124","PERF_QUEUE_LAST","RO","该发布帧从采集写入成功到领取处理任务的排队刻度数"),
    ("128","PERF_TOTAL_LAST","RO","该发布帧从核心采集帧槽分配到前台pair发布的刻度数；不含曝光、前端CDC、实际扫描及显示器延迟"),
    ("12C","PERF_TOTAL_MAX","RO","清统计以来已发布帧的最大总耗时"),
    ("130","PERF_CAPTURED","RO","监测到有有效标签的成功采集次数，32位饱和"),
    ("134","PERF_PROCESSED","RO","监测到有有效标签的成功任务次数，32位饱和"),
    ("138","PERF_PUBLISHED","RO","监测到有有效标签的新前台发布次数，重复扫描不计"),
    ("13C","PERF_TAG_MISSES","RO","标签缺失/不匹配事件数，32位饱和，应为0；不等同原ERR或去重丢帧"),
    ("140","PERF_WINDOW_CYCLES_LO","RO","自上次快照或清统计以来的核心周期数低32位"),
    ("144","PERF_WINDOW_CYCLES_HI","RO","同一64位窗口长度的高32位"),
    ("148","PERF_READ_BYTES_LO","RO","窗口内平台AXI读通道实际握手字节数低32位，每R拍16字节，包含错误响应的已接收数据"),
    ("14C","PERF_READ_BYTES_HI","RO","同一64位读字节数的高32位"),
    ("150","PERF_WRITE_BYTES_LO","RO","窗口内W握手且WSTRB置1的字节数低32位，包含RGBX填充字节"),
    ("154","PERF_WRITE_BYTES_HI","RO","同一64位写字节数的高32位"),
    ("158","PERF_AR_STALL","RO","窗口内ARVALID且非ARREADY的核心周期数，32位饱和"),
    ("15C","PERF_R_WAIT","RO","窗口内已有读事务、RREADY且无RVALID的周期数，32位饱和"),
    ("160","PERF_R_BACKPRESSURE","RO","窗口内RVALID且非RREADY的周期数，32位饱和"),
    ("164","PERF_AW_STALL","RO","窗口内AWVALID且非AWREADY的周期数，32位饱和"),
    ("168","PERF_W_STALL","RO","窗口内WVALID且非WREADY的周期数，32位饱和"),
    ("16C","PERF_B_WAIT","RO","地址和最后W拍均已接受后，BREADY且无BVALID的周期数，32位饱和"),
    ("170","PERF_R_MAX_GAP","RO","窗口内连续R_WAIT的最大周期数，边界处重新计段"),
    ("174","PERF_W_MAX_STALL","RO","窗口内连续W_STALL的最大周期数，边界处重新计段"),
    ("178","PERF_FIFO_HIGH","RO","窗口高水位：低16位摄像头FIFO读域占用（含预取，采样有跨域延迟）；高16位显示FIFO写域占用"),
    ("17C","PERF_CORE_HZ","RO","AXI等待/窗口周期的时钟频率，实板100000000；与延迟TICK_HZ区分")
]
REGISTERS.extend(PERF_REGISTERS)

DESCRIPTIONS.update({
    "style_perf_monitor": {
        "title":"按帧性能监测", "domain":"100MHz核心域", "group":"平台监测",
        "purpose":"被动统计同一发布帧的采集、排队、任务及总耗时，并观察平台AXI流量和FIFO高水位。",
        "logic":"四个输入槽保存完整32bit帧标签和64bit时间戳；跟随cap/job完成及新pair发布，在发布时整组选择同一帧记录。实板微秒刻度，溢出32位饱和并置标志。AXI按R/W握手计字节、按WSTRB统计写字节，区分地址等待、读数据等待、接收背压、写等待及B响应等待。",
        "handshake":"只观察事件/AXI，不输出任何数据流控制信号。自动每秒或APB手动拍摄1024bit快照；软件可冻结后读取，自动时核对前后SEQUENCE。PERF_ENABLE默认0，顶层performance-monitor选项显式开启。",
        "recovery":"失败帧不给出成功发布耗时；错标签单独累加TAG_MISSES。清统计保留在途时间戳和总线所有权；旧0x000..080寄存器不变。计时不含镜头曝光/前端CDC/显示器延迟，不是纯CNN计算时间。",
        "states":"每槽tag/capture/job有效位、一个在途任务和一个pending结果标签；读写方向各一个outstanding观察器。"},
    "style_perf_overlay": {
        "title":"性能快照与十进制显示", "domain":"核心域→74.25MHz像素域", "group":"显示",
        "purpose":"在y104..117空白区显示PERF 01及四页性能指标，原按键功能保留。",
        "logic":"从快照抽取608bit显示字段，经请求/应答整组信箱跨域，在显示帧起点锁存；单个逐位BCD转换器用128个像素时钟完成四个32bit值转十进制，在第104行前完成。每120个HDMI帧换页，正常60Hz约2秒。",
        "handshake":"发送端锁存整组payload并翻转请求，双触发器同步请求后目标域采样并返回应答；应答同步返回前源数据保持不变。拥塞合并尚未发送的快照；只影响诊断刷新，视频数据不经过信箱。两个域需共同复位。",
        "recovery":"没有完整发布记录时延迟值显示横线；其他页仍显示总线数据。页脚字节/窗口值超32位时显示4294967295，APB保留完整64位；诊断行外RGB透传。",
        "states":"最新快照/在途信箱、请求应答同步、像素域最新/当前帧副本、32步乘4字段BCD转换。"},
    "style_wb_calibrator": {
        "title":"按键白平衡校准", "domain":"50MHz摄像头域", "group":"采集",
        "purpose":"KEY2对白纸采样并锁定R/B增益，KEY3恢复固定白平衡。",
        "logic":"按键2FF同步及20ms消抖；等新SOF后采四个完整帧的RAW均值，扣物理黑位并平均。以G为目标，19拍逐位除法依次算R/B的Q8比值，增益范围0.25至4倍。算完后整组请求，由摄像头预处理在SOF锁存。",
        "handshake":"mean_valid是本域完整帧统计单拍；按键期间旧帧不计。request_r/b为待SOF应用值，active_r/b为已应用值，绿色固定256。状态和已应用增益通过26bit异步FIFO送显示域。",
        "recovery":"暗分量低于32、任一RAW均值达到960、增益超限或2秒超时，均拒绝并保留原参数。KEY3可取消校准，下个SOF恢复493/504；长按不重复，忙时忽略额外KEY2。当前候选实板待测。",
        "states":"DEFAULT→ARM→SAMPLE(4帧)→CALC→DIV_R→DIV_B→APPLY→LOCKED；失败REJECT，KEY3回默认。"},
    "style_wb_overlay": {
        "title":"白平衡状态显示", "domain":"74.25MHz HDMI像素域", "group":"显示",
        "purpose":"显示WB CAL 01、校准状态和已应用R/B十六进制Q8增益。",
        "logic":"y628至641绘制状态页脚；采样时在左画面画中心RAW ROI边框。其他像素透传，不修改DDR数据。",
        "handshake":"顶层异步FIFO跨域传26bit整组状态，HDMI帧起点再锁存；输入应为本显示帧稳定的数据。",
        "recovery":"复位显示DEFAULT及默认增益，REJECT使用橙色文字。状态显示有跨域与帧锁存延迟，不与某个摄像头frame_id严格对应。",
        "states":"组合字体和区域选择，无状态机。"}
})
DESCRIPTIONS['style_camera_preprocess']['logic'] += ' DYNAMIC_WB=1时新增wb_r/g/b_q8输入，在输入SOF整组锁存，整帧保持；默认0保留旧静态参数行为。动态增益显式作为颜色函数实参，保证纯色输入也重新求值。'

def escaped(value: object) -> str:
    return html.escape(str(value), quote=True)

def balanced(text: str, offset: int) -> tuple[str, int]:
    depth = 1
    start = offset + 1
    index = start
    while index < len(text):
        if text[index] == "(": depth += 1
        elif text[index] == ")":
            depth -= 1
            if not depth: return text[start:index], index + 1
        index += 1
    raise ValueError("unclosed module header")

def split_commas(text: str) -> list[str]:
    parts, current, depth = [], [], 0
    for char in text:
        if char in "([{" : depth += 1
        elif char in ")]}": depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(current).strip()); current = []
        else: current.append(char)
    if current: parts.append("".join(current).strip())
    return parts

def parse_module(path: Path) -> dict:
    source = path.read_text(encoding="utf-8-sig")
    clean = re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.S)
    clean = re.sub(r"\(\*.*?\*\)", "", clean, flags=re.S)
    match = re.search(r"\bmodule\s+([A-Za-z_]\w*)", clean)
    if not match: raise ValueError(f"No readable module in {path}")
    name = match.group(1)
    cursor = match.end()
    while clean[cursor].isspace(): cursor += 1
    parameters = []
    if clean[cursor] == "#":
        cursor = clean.index("(", cursor)
        declaration, cursor = balanced(clean, cursor)
        for token in split_commas(declaration):
            if "=" in token:
                lhs, rhs = token.split("=", 1)
                ident = re.findall(r"\b[A-Za-z_]\w*\b", lhs)[-1]
                parameters.append((ident, rhs.strip()))
    cursor = clean.index("(", cursor)
    declaration, end = balanced(clean, cursor)
    ports = []
    direction, width = "", "1"
    for token in split_commas(declaration):
        token = token.strip()
        prefix = re.match(r"^(input|output|inout)\b", token)
        if prefix:
            direction = prefix.group(1); width = "1"
            token = token[prefix.end():].strip()
        ranges = re.findall(r"\[[^\]]+\]", token)
        if ranges: width = " ".join(ranges)
        names = re.findall(r"\b[A-Za-z_]\w*\b", re.sub(r"\[[^\]]+\]", "", token))
        names = [n for n in names if n not in {"wire", "reg", "logic", "signed", "unsigned"}]
        if not direction or len(names) != 1:
            raise ValueError(f"Unsupported ANSI port {name}: {token}")
        ports.append((names[0], direction, width))
    comments = " ".join(line.lstrip("/ ") for line in source.splitlines()[:8] if line.lstrip().startswith("//"))
    desc = DESCRIPTIONS.get(name, {
        "title": name, "domain": "以端口所示时钟为准", "group": "平台新增模块",
        "purpose": comments or "平台 RTL 模块。",
        "logic": "此模块是当前源码新增部分；端口/参数和源代码已自动收录。集成及资源/时序状态需结合当前构建报告核对。",
        "handshake": "核对下表的 valid/ready、配置与本域复位；厂商串化和外设接口按 Interface Designer 工程配置。",
        "recovery": "未做行为覆盖的新增模块不会因被文档收录而自动算验证通过。",
        "states": "见嵌入源代码中的 localparam、case 和计数器。",
    })
    return {"name": name, "path": path.relative_to(ROOT).as_posix(), "source": source,
            "parameters": parameters, "ports": ports, "desc": desc}

def table(headers: list[str], rows: list[tuple]) -> str:
    head = "".join(f"<th scope='col'>{escaped(x)}</th>" for x in headers)
    body = "".join("<tr>" + "".join(f"<td>{escaped(x)}</td>" for x in row) + "</tr>" for row in rows)
    return f"<div class='table-wrap'><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"

def port_meaning(module: str, name: str, direction: str) -> str:
    if module=="style_wb_calibrator":
        return {"clk":"50MHz摄像头时钟", "rst_n":"低有效复位，恢复固定增益493/504", "key_cal_n":"KEY2低有效，2FF同步和20ms消抖，空闲时触发一次校准", "key_restore_n":"KEY3低有效，优先取消校准并恢复默认", "s_vs":"高有效输入VS，上升沿为生效边界", "mean_valid":"本域完整合法帧RAW统计的单拍有效", "mean_data":"扣黑前A/B/C/D各10bit，A在低位", "request_r":"待下一个SOF锁存的红色Q8增益", "request_b":"待下一个SOF锁存的蓝色Q8增益", "active_r":"已在SOF生效的红色Q8增益", "active_b":"已在SOF生效的蓝色Q8增益", "state":"0默认/1等待新帧/2四帧采样/3红除法/4蓝除法/5待生效/6锁定/7拒绝/8算均值"}.get(name,"校准控制接口")
    if module=="style_wb_overlay":
        return {"x":"HDMI横坐标", "y":"HDMI纵坐标", "input_rgb":"对比度叠加后的RGB888", "state":"经FIFO跨域并在显示帧起点锁存的校准状态", "gain_r":"已经生效的红色Q8增益，页脚显示十六进制", "gain_b":"已经生效的蓝色Q8增益，页脚显示十六进制", "rgb":"新增WB CAL 01状态文字；采样时标出左图中心ROI；不回写DDR"}.get(name,"显示接口")
    if module=="style_camera_preprocess" and name in ("wb_r_q8","wb_g_q8","wb_b_q8"):
        return "摄像头域动态Q8增益请求，DYNAMIC_WB=1时仅在输入SOF整组锁存；默认0忽略此端口，保持静态参数行为"
    if module=="style_contrast_probe":
        return {"clk":"74.25MHz像素时钟", "rst_n":"低有效复位；恢复INITIAL_LEVEL并清除按键状态", "key1_n":"板上KEY1低有效输入；模块内2FF同步及20ms按下/释放消抖", "x":"当前完整HDMI扫描横坐标，含消隐", "y":"当前完整HDMI扫描纵坐标，含消隐；x=y=0应用请求档位", "input_rgb":"显示布局/原OSD输出RGB888，DDR数据不因本模块回写", "cfa_means":"像素域整组锁存RAW10均值：A9:0、B19:10、C29:20、D39:30", "sample_valid":"四均值有效；0时页脚显示---", "rgb":"组合输出：右图对比度映射与诊断页脚覆盖，其他位置保留input_rgb", "level":"当前已在帧起点生效的3bit档位0..4；通用默认2=1.50，当前WB版本物理设0=1.00，已实测不发绿及30fps，室外天空微红待诊断"}.get(name,"显示诊断接口，详见参数和实现")
    if module=="style_rgb_gamma":
        return {"s_rgb":"预处理输出RGB888：R23:16/G15:8/B7:0，查表前像素", "m_rgb":"ENABLE=1按GAMMA_TENTHS输出近似gamma1.8或2.2编码RGB888，ENABLE=0为24位透传；零新增流水拍"}.get(name,"RGB组合亮度编码接口")
    if module=="style_camera_reg_rom":
        return {"clock":"5MHz配置时钟，上升沿查询ROM", "addr_ptr":"配置序列索引，不是传感器寄存器地址", "rdata_out":"25位配置字：bits24:9地址、bits8:1数据、bit0读写标志"}.get(name,"配置ROM接口；实际位宽与声明见表")
    if module=="style_camera_reg_set":
        return {"clk":"5MHz I²C配置时钟", "rst_n":"低有效配置序列复位", "init_done":"底层I²C控制器初始化流程完成", "wr_done":"底层写事务流程结束事件，未验证NACK", "rd_done":"底层读事务流程结束事件，当前不提供真实读数据", "wr_en":"本域一拍写命令", "rd_en":"本域一拍读命令；本次未扩展读回功能", "addr":"当前ROM项的16位传感器寄存器地址", "dout":"当前ROM项的8位写配置数据", "dev_addr":"配置的8位I²C设备地址编码"}.get(name,"寄存器命令序列接口；实际位宽与声明见表")
    if module=="style_osd" and name=="underflow_count":
        return "像素域刷新时锁存的累计UF数，以十六进制显示，非FPS"
    if module=="style_display_sink" and name in {"core_camera_frames","core_drop_count","core_error_count"}:
        return {"core_camera_frames":"核心域RAW SOF累计数，经配置bundle锁存到像素域",
                "core_drop_count":"核心域阶段丢弃事件合计，经bundle锁存，非唯一丢帧数",
                "core_error_count":"核心域阶段错误事件合计，经bundle锁存，可能重复同一坏帧"}[name]
    if name=="underflow_count" and module=="style_platform_core":
        return "已同步到核心域的显示欠载计数，变化立即触发D_DRAIN取消旧读"
    if name=="underflow_count" and module=="style_control_regs":
        return "已同步到核心域的显示欠载计数，供APB只读诊断"
    exact = {
        "clk":"本模块核心/摄像头工作时钟，所属域见上文", "rst_n":"本域低有效复位",
        "core_clk":"DDR平台核心时钟", "core_rst_n":"核心域低有效复位",
        "pixel_clk":"显示像素时钟，默认74.25MHz", "pixel_rst_n":"像素域低有效复位",
        "wr_clk":"FIFO写入时钟", "rd_clk":"FIFO读出时钟", "async_rst_n":"FIFO两端共同低有效异步复位输入",
        "src_clk":"诊断计数的源时钟", "dst_clk":"诊断目的时钟", "src_rst_n":"源域低有效复位", "dst_rst_n":"目的域低有效复位",
        "src_count":"每源周期最多增1的原始计数", "dst_count":"Gray同步后恢复的目的域计数",
        "clear":"取消本地缓存内容，高有效；上层须先保证事务安全", "abort":"请求终止当前DMA，已提供AXI事务仍按协议排空",
        "cmd_valid":"命令有效，与cmd_ready握手后开始", "cmd_ready":"可接受新命令；sticky fault后为0",
        "cmd_addr":"命令起始DDR字节地址，按AXI拍对齐", "cmd_beats":"本次命令的AXI数据总拍数，非字节数",
        "busy":"任务进行中", "done":"本域单拍任务结束事件，须与error同看", "error":"任务结束失败事件",
        "error_code":"任务失败原因码，见恢复说明", "sticky_fault":"不可安全复用总线的故障锁存，需复位",
        "s_vs":"原生CSI高有效VS，默认1；上升沿SOF、下降沿EOF；显式参数0支持低极性输入", "s_hs":"原生CSI行有效输入，高有效",
        "s_raw":"一拍4个RAW10像素，首像素在bits9:0", "m_abort":"该帧不完整/溢出的单拍取消事件",
        "m_abort_frame_id":"取消事件对应frame_id", "input_frames":"看到的物理输入SOF计数",
        "drop_frames":"摄像头前端丢帧计数", "error_frames":"摄像头前端错误计数",
        "wr_level":"FIFO内RAM字占用量，跨域有同步延迟", "rd_level":"FIFO读域可用量，包含读端预取字",
        "refresh_request":"像素域持续刷新请求，需核心两级同步", "refresh_ack":"核心域持续ACK，内部注册快照后跨像素域",
        "safe_window":"像素域安全更新窗口，需核心两级同步", "frame_start":"扫描x0/y0的一拍指示",
        "core_flush":"共同清空显示FIFO，延长到至少16核心周期", "core_front_valid":"本次刷新是否有完整前台pair",
        "core_frame_id":"本次刷新原画/结果关联的源帧ID", "core_mode":"本次刷新显示模式，随ACK锁存",
        "video_rgb":"与video_de/hs/vs同拍的RGB888", "video_de":"有效显示区使能", "video_hs":"正极性水平同步", "video_vs":"正极性垂直同步",
        "video_x":"水平扫描坐标，含消隐", "video_y":"垂直扫描坐标，含消隐", "underflow_count":"有效图像FIFO欠载次数，像素域计数需跨域",
        "x":"当前水平扫描坐标", "y":"当前垂直扫描坐标", "de":"有效显示像素使能", "hs":"正极性水平同步", "vs":"正极性垂直同步",
        "capture_fps":"按完整采集计数得到的FPS", "process_fps":"按完整任务计数得到的FPS；当前为COPY", "bypass_active":"当前前台是否由COPY占位生成",
        "frame_id":"当前前台源帧编号", "hit":"当前位置是否命中文字笔画", "rgb":"命中文字的RGB888",
        "paddr":"APB3字节offset，12位", "psel":"APB选中从设备", "penable":"APB访问阶段使能", "pwrite":"APB写访问标志",
        "pwdata":"APB写32位数据", "prdata":"APB读32位数据", "pready":"APB响应就绪，当前固定1", "pslverr":"当前APB非法访问错误", "irq":"使能sticky事件的中断电平",
        "enable":"允许平台启动新采集和任务", "auto_run":"自动处理READY输入槽", "bypass":"请求后续任务使用COPY路径",
        "display_mode":"左右/仅左/仅右显示模式", "start_pulse":"手动启动一项任务的单拍事件", "fps_tick":"统计一秒窗口结束事件",
        "status":"平台状态位，详见APB表", "ready_mask":"四输入槽处于READY的位掩码", "front_id":"当前前台源帧ID",
        "event_set":"低4位采集/处理/发布/错误事件", "cal_ready":"平台启动就绪；物理顶层组合DDR校准、摄像头配置完成与abort队列健康",
        "fatal_fault":"任一DMA sticky fault的合计，停止新任务",
        "camera_frames":"摄像头输入SOF总计", "camera_drops":"摄像头前端丢帧计数", "camera_errors":"摄像头前端错误计数",
        "captured_count":"整帧DDR采集成功计数", "processed_count":"整帧结果DDR成功计数", "displayed_count":"新前台pair发布计数",
        "drop_count":"各阶段丢弃事件合计，可能重复记录同一坏帧", "error_count":"各阶段错误事件合计，非去重坏帧数", "front_valid":"存在已发布完整前台pair", "pending_valid":"存在待安全发布的完整pair",
        "accel_start":"本域单拍外部算法任务启动提示，下一拍J_ARM保护启动",
        "accel_abort":"J_ABORT期间保持，队友取消并清空待输出/内部流水，直到下次start保持空闲",
        "scl_pad_i":"I²C SCL总线采样输入", "scl_pad_o":"I²C SCL开漏输出值，官方控制器固定0",
        "scl_padoen_o":"SCL开漏输出使能，低有效；顶层翻转为高有效OE",
        "sda_pad_i":"I²C SDA总线采样输入", "sda_pad_o":"I²C SDA开漏输出值，官方控制器固定0",
        "sda_padoen_o":"SDA开漏输出使能，低有效；顶层翻转为高有效OE",
        "config_done":"DATA_LENGTH（默认164）个ROM事务done后保持；不证明传感器ACK/ID/读回正确",
    }
    if name in exact: return exact[name]
    axi = re.search(r"(?:s|m)_axi_(aw|ar|w|b|r)(\w+)", name)
    if axi:
        channel, field = axi.groups()
        channel_label={"aw":"写地址","ar":"读地址","w":"写数据","b":"写响应","r":"读数据"}[channel]
        field_label={"id":"事务ID","addr":"字节地址","len":"burst拍数减1","size":"每拍字节数log2","burst":"地址模式，INCR=01","valid":"有效，等待ready时保持","ready":"接收方就绪","data":"数据","strb":"字节写使能","last":"本burst最后数据拍","resp":"响应码，OKAY=00"}.get(field,field)
        return "AXI "+channel_label+" "+field_label+("；两个客户端打平，client0在低slice" if name.startswith("s_axi_") else "")
    if name.startswith("accel_input_") or name.startswith("accel_output_"):
        stream = "平台送给算法" if name.startswith("accel_input_") else "算法送给平台"
        name_part = name.split("_",2)[2]
        descriptions={"rgb":"RGB888像素","valid":"像素有效","ready":"接收就绪","sof":"第一像素标志","eol":"每行最后像素标志","eof":"整帧最后像素标志","frame_id":"全帧关联ID"}
        return stream+"："+descriptions.get(name_part,name_part)
    for prefix,label in [("s_","输入流"),("m_","输出流"),("cam_","摄像头统一流"),("display_","显示控制/读流")]:
        if name.startswith(prefix):
            key=name[len(prefix):]
            descriptions={"rgb":"RGB888像素","data":"打包数据","valid":"有效，握手才推进","ready":"接收就绪","sof":"第一像素标志","eol":"行尾像素标志","eof":"帧尾像素标志","last":"命令/帧最后数据","frame_id":"源帧ID","abort":"该帧取消事件","abort_id":"取消源帧ID","refresh_request":"像素域刷新请求","safe_window":"像素域安全窗口","refresh_ack":"核心域刷新ACK","flush":"核心域显示FIFO清空事件"}
            return label+"："+descriptions.get(key,key)
    if name.startswith("cap_"): return "采集帧槽握手/地址信息："+name
    if name.startswith("job_"): return "任务输入/结果槽握手与配对信息："+name
    if name.startswith("front_"): return "已发布前台pair信息："+name
    if module=="style_ti60_top": return "物理平台或Interface Designer生成端口；引脚/时钟约定见自包含peri配置"
    return "本模块配置/状态，见实现逻辑及当前源码"

def diagram(names: set[str]) -> str:
    def node(name: str, x: int, y: int, w: int, h: int, title: str, subtitle: str, kind="node") -> str:
        target = f"#{name}" if name in names else "#integration"
        return f"<a href='{target}' data-module='{name}'><g class='{kind}'><rect x='{x}' y='{y}' width='{w}' height='{h}' rx='10'/><text x='{x+w//2}' y='{y+28}' text-anchor='middle'>{title}</text><text class='sub' x='{x+w//2}' y='{y+51}' text-anchor='middle'>{subtitle}</text></g></a>"
    content = """
<svg id="framework" viewBox="0 0 1200 820" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="diagram-title diagram-description">
<title id="diagram-title">Ti60 视频平台代码架构</title><desc id="diagram-description">摄像头经过预处理、可选gamma编码和跨域FIFO，DMA写DDR；复制占位或队友加速器读输入写结果；配对显示经FIFO和TMDS输出。未来RISC-V通过APB控制。</desc>
<defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="#466176"/></marker></defs>
<style>.band{fill:#F5F8FA;stroke:#DAE3EC}.bandlabel{font:16px 'Microsoft YaHei',sans-serif;fill:#526C7D}.node rect{fill:#FFF;stroke:#B8CBD8;stroke-width:1.5}.node text{font:18px 'Microsoft YaHei',sans-serif;fill:#142C3E}.node .sub{font-size:13px;fill:#536D7D}.future rect{stroke-dasharray:6 5;fill:#FAFAFA}.platform rect{fill:#EDF4F9}.edge-label{font:13px 'Microsoft YaHei',sans-serif;fill:#536D7D}</style>
<rect x="20" y="26" width="1160" height="142" rx="15" class="band"/><text x="40" y="50" class="bandlabel">采集：摄像头时钟 → 核心域</text>
<rect x="20" y="304" width="1160" height="222" rx="15" class="band"/><text x="40" y="330" class="bandlabel">DDR 核心域：帧所有权、突发读写和任务</text>
<rect x="20" y="592" width="1160" height="192" rx="15" class="band"/><text x="40" y="619" class="bandlabel">显示：核心域 → 74.25 MHz 像素域 → 371.25 MHz 串化</text>
<g class="arrows" fill="none" stroke="#466176" stroke-width="2" marker-end="url(#arrow)">
<path d="M255 109 H305"/><path d="M555 109 H615"/><path d="M845 109 H905"/>
<path d="M1030 145 V178 H805 V294 H665 V350"/>
<path d="M755 390 H855"/><path d="M855 425 H755"/>
<path d="M560 460 V552 H210 V645"/>
<path d="M350 683 H435"/><path d="M740 683 H860"/>
</g>
<g class="control" fill="none" stroke="#7F8794" stroke-width="2" stroke-dasharray="6 5" marker-end="url(#arrow)">
<path d="M860 235 H760"/><path d="M615 271 V350"/>
<path d="M345 391 H445"/><path d="M615 271 V287 H1045 V350"/>
<path d="M615 271 V284 H390 V568 H590 V645"/>
</g>
<text x="776" y="375" class="edge-label">输入与权重*</text><text x="776" y="451" class="edge-label">结果写回</text>
<text x="47" y="563" class="edge-label">逐行读取：原图640像素 → 结果640像素</text>
"""
    content += node("style_camera_initializer", 45, 74, 210, 72, "SC431HAI / 官方 CSI IP", "RAW10 · 4像素/拍 · I²C配置", "node platform")
    content += node("style_camera_capture", 305, 74, 250, 72, "独立采集模块：预处理", "RAW接口 → 扣黑/BGGR/WB/tone")
    if "style_rgb_gamma" in names:
        content += "<a href='#style_rgb_gamma' data-module='style_rgb_gamma'><text x='585' y='161' text-anchor='middle' class='edge-label'>gamma18/22 / linear → CDC</text></a>"
    content += node("style_camera_capture", 615, 74, 230, 72, "采集模块内：CDC / 状态", "core域 RGB流 + abort + 计数")
    content += node("style_ddr_framebuffer", 905, 74, 245, 72, "DDR模块：采集写入", "4 RGBX像素 / AXI128拍")
    content += node("style_control_regs", 470, 198, 290, 72, "控制寄存器 / IRQ", "APB3 offsets · 无CPU实例")
    content += node("style_platform_core", 860, 198, 290, 72, "队友：Sapphire RISC-V", "后续接入 · 软件驱动与调度", "node future")
    content += node("style_ddr_framebuffer", 45, 350, 300, 110, "DDR模块：帧池 / 核心", "4输入 + 2结果 · 原图配对保留")
    content += node("style_ddr_framebuffer", 445, 350, 310, 110, "DDR模块：共享AXI接口", "连接保留的DDR控制器/PHY")
    content += node("style_accel_bypass", 855, 350, 295, 110, "计算接入口 / COPY 占位", "队友以 RGB 流接入完整 CNN")
    content += node("style_axi_read_dma", 55, 645, 295, 80, "显示 DMA / 解包", "读已完成原图与结果")
    content += node("style_hdmi_display", 435, 645, 305, 80, "显示模块：FIFO/布局/OSD", "左640×480原图 · 右黑预留CNN")
    if "style_contrast_probe" in names:
        content += "<a href='#style_contrast_probe' data-module='style_contrast_probe'><text x='797' y='633' text-anchor='middle' class='edge-label'>可选 CONTRAST PROBE → HDMI（仅显示，不回写DDR）</text></a>"
    target = "style_hdmi_display"
    content += node(target, 860, 645, 290, 80, "TMDS / 易灵思高速输出", "标准 720p60 · 正HS/VS", "node platform")
    content += '<text x="42" y="756" class="edge-label">实线：像素/内存数据　虚线：控制　*当前 COPY 无权重读取，CNN 权重接口需与队友集成。</text></svg>'
    return content

INTERFACE_MD = """# 视频平台与队友接口契约

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

"""

def read_receipt(name: str) -> tuple[str, str]:
    path = ROOT / "build" / name
    if not path.exists(): return "尚未生成验证记录", "尚未验证；没有找到 " + path.relative_to(ROOT).as_posix()
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    snapshot=value.get("sources")
    differences=[]
    if isinstance(snapshot,dict):
        for source_path,digest in snapshot.items():
            source_file=ROOT/source_path.replace("\\","/")
            if not source_file.is_file() or hashlib.sha256(source_file.read_bytes()).hexdigest()!=digest:
                differences.append(source_path)
        value["current_source_check"]={"matches_snapshot":not differences,"different_paths":differences}
    if name.startswith("validation"):
        if value.get("passed") is True or value.get("all_passed") is True:
            label = "RTL 行为验证通过" if not differences else "历史RTL快照通过，当前源码已变化"
        else: label = "验证记录已生成，查看详细状态"
    else:
        if value.get("full_build_passed") is True or value.get("implementation_passed") is True:
            label = "Efinity 实现构建通过" if not differences else "历史快照构建通过，当前源码已变化"
        elif value.get("status")=="building":label="Efinity 构建进行中，尚未完成签核"
        else: label = "Efinity 记录已生成，查看各阶段状态"
    return label, json.dumps(value, ensure_ascii=False, indent=2)

def implementation_detail() -> str:
    path=ROOT/"build"/"efinity_receipt.json"
    if not path.exists():return "<p>尚无当前Efinity实现记录。</p>"
    value=json.loads(path.read_text(encoding="utf-8-sig"))
    if not value.get("full_build_passed"):
        return "<p>Efinity流程尚未完成；各阶段状态见下方原始记录。</p>"
    rows=[("构建阶段",", ".join(name for name,passed in value.get("phases",{}).items() if passed)),
          ("命令退出码",value.get("exit_code","未记录")),
          ("WNS / WHS",f"{value.get('wns_ns','未记录')} ns / {value.get('whs_ns','未记录')} ns"),
          ("V4/J5引脚复核",f"{value.get('verified_pin_count','未记录')}个，匹配={value.get('pinout_matches_verified_V4_J5','未记录')}"),
          ("时钟配置复核",value.get("clock_profile_verified","未记录")),
          ("实际综合源条目数",value.get("verified_design_file_count","未记录")),
          ("快照补入项目RTL",", ".join(value.get("snapshot_sources_added",[])) or "无"),
          ("bitstream大小",str(value.get("bytes","未记录"))+" bytes"),
          ("SDC警告数量",value.get("sdc_warnings","未记录")),
          ("本次构建候选的下载记录",value.get("programmed",False))]
    detail=table(["验证项目","当次记录"],rows)
    issues=value.get("interface_issues",[])
    if issues:
        detail+="<h3>Interface Designer遗留告警</h3>"+table(["实例","级别","规则","内容"],[(i.get("instance_name",""),i.get("severity",""),i.get("rule_name",""),i.get("message","")) for i in issues])
    detail+=f"<p>本次综合、接口、布局布线和编程文件生成通过，报告WNS {escaped(value.get('wns_ns','未记录'))} ns、WHS {escaped(value.get('whs_ns','未记录'))} ns。仍有 {escaped(value.get('sdc_warnings','未记录'))} 条SDC告警，详细来源见当次日志。</p>"
    if value.get("sha256")=="51c1f8823dff84db21b207dedaff03511a6c9dc703a952388c43238abaf51feb":
        detail+="<p>这次记录的249条SDC告警主要来自继承的reference-pin模板与未使用时钟；另有3个已优化掉的统计Gray计数起点告警。当前6组实际FIFO跨域约束没有同类起点告警，但这不是全部CDC和DDR物理电气签核。</p>"
    elif value.get("sha256")=="6c58920a21d98d81d45c99f0696e77ed5ddcc7a7ae3b32ba7c784d886c79c8ab":
        detail+="<p>本次243条SDC告警包含继承的reference-pin模板与未使用时钟告警。仅stat_camera/stat_drops的Gray同步因未使用统计被优化而出现起点匹配告警（SDC315/316）；stat_underflow已保留并用于欠载后立即排空恢复（SDC318）。这不是全部CDC和DDR物理电气签核。</p>"
    detail+="<div class='callout'>正时序裕量只针对本次报告接受的约束，继承模板延迟项与LVDS间距告警仍需复核。第一轮VS修复bit下半紫色、128拍读后稳定13fps；短曝光文件现获用户CAP/COPY30、UF/ERR/DROP0且稳定的反馈，后续诊断确认右图BGGR3颜色正确但偏暗，正式gamma颜色已获确认，但图像质量待优化。本次观察不是长期稳定性、DDR实测吞吐或电气签核。</div>"
    return detail

def camera_fix_detail() -> str:
    path=ROOT/"build"/"display_fix_receipt.json"
    intro="<h3>已接受的13fps稳定显示基线</h3><p><a href='build/style_video_display_burst128.bit'>build/style_video_display_burst128.bit</a> · <a href='build/display_fix_receipt.json'>显示基线回执</a>。保留原生VS高有效及RAW DE&HS门控，平台读突发128拍、写16拍，显示RAW/DROP/ERR/UF诊断。用户确认画面稳定，CAP/COPY均13，UF/DROP一直0；随后RAW累计0x38E→0x429增加155帧、时间约10秒、ERR0。时间未精确计量，约15.5是粗略CSI SOF速率；本轮FRAME具体值未报告。COPY13fps不满足30fps采集目标，也没有接入CNN或验证神经推理>15fps；视觉确认不等于DDR实测带宽或电气签核。</p><p>历史第一轮<a href='build/style_video_camera_vs_high.bit'>camera_vs_high.bit</a>已获用户部分失败反馈：CAP/COPY均约13、FRAME增长，但下半图紫色抖动；<a href='build/camera_fix_receipt.json'>历史回执</a>。初始化过渡帧可留下累计D2错误灯，不要求D2灭。后续短曝光候选单独A/B比较，避免误选旧efinity/outflow/style_video.bit。</p>"
    if not path.exists():return intro+"<p>当前稳定显示候选回执尚未生成，不能据文件名判断打包或验证完成。</p>"
    value=json.loads(path.read_text(encoding="utf-8-sig"))
    rows=[("修复", "平台读burst128；RAW/DROP/ERR/UF累计诊断；保留VS高有效及DE&HS"),
          ("状态",value.get("status","未记录")),("源码绑定回归数",value.get("test_count","未记录")),
          ("WNS / WHS",f"{value.get('wns_ns','未记录')} ns / {value.get('whs_ns','未记录')} ns"),
          ("bit字节数",value.get("bytes","未记录")),("SHA256",value.get("sha256","未记录")),
          ("已进行实物重测",value.get("hardware_retested",False)),("最新实物记录",json.dumps(value.get("hardware_result","回执尚未记录最新用户反馈"),ensure_ascii=False)),("首次运行bit指纹","未独立核实")]
    return intro+table(["项目","当前修复回执"],rows)

def readme_implementation_summary() -> str:
    path=ROOT/"build"/"efinity_receipt.json"
    if not path.exists():return "尚未生成Efinity实现记录，不能据现有源码或旧bitstream判断实现通过。"
    value=json.loads(path.read_text(encoding="utf-8-sig"))
    if not value.get("full_build_passed"):return "Efinity当前记录状态为 "+str(value.get("status","未完成"))+"，详细结果以收据为准。"
    text=f"最新Efinity记录：map/interface/pnr/pgm退出{value.get('exit_code','未记录')}，bitstream已生成，WNS {value.get('wns_ns','未记录')}ns、WHS {value.get('whs_ns','未记录')}ns；{value.get('verified_pin_count','未记录')}个引脚复核，SDC警告{value.get('sdc_warnings','未记录')}条、接口告警{len(value.get('interface_issues',[]))}条。"
    if value.get("sha256")=="51c1f8823dff84db21b207dedaff03511a6c9dc703a952388c43238abaf51feb":
        text+="本次包括1个继承的LVDS距离告警、249条继承模板/未使用时钟SDC告警和3个优化掉统计Gray计数的起点告警。"
    elif value.get("sha256")=="6c58920a21d98d81d45c99f0696e77ed5ddcc7a7ae3b32ba7c784d886c79c8ab":
        text+="本次保留1个LVDS距离告警；统计Gray起点告警仅为优化掉的stat_camera/stat_drops两组，stat_underflow已实际保留用于欠载恢复。"
    return text+"不是零告警或板级物理签核。详细状态以收据和网页为准，修改源码后必须重新验证对应快照。"

def efinity_project_path() -> str:
    path=ROOT/"build"/"efinity_receipt.json"
    if path.exists():
        value=json.loads(path.read_text(encoding="utf-8-sig"))
        project=Path(value.get("project",""))
        if project.is_file():
            try:return project.resolve().relative_to(ROOT).as_posix()
            except ValueError:return project.as_posix()
    return "efinity/style_video.xml"

def efinity_project_summary() -> str:
    path=ROOT/"build"/"efinity_receipt.json"
    if not path.exists():return "尚无实现回执；关闭IDE旧工程后先prepare，再重新打开主XML核对完整源列表。"
    value=json.loads(path.read_text(encoding="utf-8-sig"))
    project=efinity_project_path()
    return f"当次IDE综合入口：[{project}]({project})，来自efinity_receipt.project；构建完成={value.get('full_build_passed',False)}，已核对源条目{value.get('verified_design_file_count','未记录')}项、快照补入{len(value.get('snapshot_sources_added',[]))}项。稳定bit可直接交给Programmer，无需重新综合。若改用主efinity/style_video.xml，先关闭旧工程，再prepare并重新打开，避免IDE保存的旧源列表覆盖新列表。"

def performance_detail() -> str:
    path=ROOT/"build"/"performance"/"receipt.json"
    caution="<p>持续无限读请求的密集COPY模型在首R等待96周期/128拍读时平均56.728M像素/秒，低于双图显示与30fpsCOPY所需57.6M，是独立的带宽边界失败。这里的有限帧调度测试不证明无限满负载或真实DDR性能；摄像头适配器模型有ready背压，物理CSI无ready。</p>"
    if not path.exists():return "<h3>完整尺寸延迟压力</h3><p>尚未生成当前性能回执。</p>"+caution
    value=json.loads(path.read_text(encoding="utf-8-sig"))
    hashes=value.get("rtl_sha256",{})
    matches=bool(hashes) and all((ROOT/"rtl"/name).is_file() and hashlib.sha256((ROOT/"rtl"/name).read_bytes()).hexdigest()==digest for name,digest in hashes.items())
    status="通过，当前RTL匹配" if value.get("passed") and matches else "历史记录或未通过，请核对源码及回执"
    rows=[("状态",status),("profile",f"{value.get('geometry')} / 首R {value.get('axi_initial_read_delay_cycles')} 周期 / 读 {value.get('read_burst_beats')} 拍"),("输入/完整HDMI扫描",f"{value.get('camera_frames_requested')} / {value.get('hdmi_frames_requested')}"),("实际统计",json.dumps(value.get("metrics",{}),ensure_ascii=False)),("真实日志",value.get("native_run_log","build/performance/run.log")),("实板带宽已验证",value.get("hardware_bandwidth_verified",False))]
    return "<h3>完整尺寸延迟压力</h3>"+table(["项目","当前性能回执"],rows)+caution

def short_exposure_detail() -> str:
    text="<h3>历史短曝光：30fps已确认，颜色见后续诊断</h3><p>2026-10-15用户确认<a href='build/style_video_camera_short_exposure.bit'>style_video_camera_short_exposure.bit</a>画面稳定，CAP/COPY均30fps，UF/ERR/DROP均0，亮度可接受；整体偏绿或偏紫仍未解决。来源为<a href='build/camera_short_exposure_receipt.json'>短曝光回执</a>及<a href='build/active_hardware_image.json'>当前硬件记录</a>。用户观察没有精确时长，运行bit身份未独立读回；COPY不是CNN，神经推理>15fps尚未验证。</p><p>历史<a href='build/style_video_display_burst128.bit'>13fps基线</a>及其RAW从0x38E到0x429、约10秒增加155帧的观察保留。短曝光仅恢复同模式v1的3E00/3E01/3E02=00/BA/D0，曝光编码从7103降为2989半行；164项其他数据、增益/方向、DDR/CSI/缩小配置保留。官方手册V1.1第23页给出E≤2VTS−11，默认VTS1500时上限2989；实际寄存器没有读回，不能把配置值当作运行中读数。准确来源见<a href='docs/camera.md'>摄像头文档</a>。</p><p>prepare支持verified和默认short_exposure，当前<a href='build/camera_profile_receipt.json'>profile审计</a>记录三个差异及来源SHA。未新增RAW FPS或寄存器读回，继承controller的dout未驱动。后续GBRG2已实物失败；COLOR PROBE01右图BGGR3颜色已确认但偏暗，正式BGGR+gamma版本颜色已获确认，图像质量待优化，不增加白平衡。</p>"
    profile_path=ROOT/"build"/"camera_profile_receipt.json"
    if profile_path.exists():
        profile=json.loads(profile_path.read_text(encoding="utf-8-sig"))
        text+=table(["当前源profile审计","记录"],[("选择",profile.get("profile","未记录")),("配置项数",profile.get("entry_count","未记录")),("三个差异",json.dumps(profile.get("changed_registers",[]),ensure_ascii=False)),("其余项未变",profile.get("all_other_entries_unchanged","未记录")),("厂商输入被修改",profile.get("vendor_inputs_modified","未记录"))])
    path=ROOT/"build"/"camera_short_exposure_receipt.json"
    if not path.exists():return text+"<p>短曝光候选回执尚未生成，不能判断编译、打包或实物测试状态。</p>"
    value=json.loads(path.read_text(encoding="utf-8-sig"))
    rows=[("状态",value.get("status","未记录")),("bit字节数",value.get("bytes","未记录")),("SHA256",value.get("sha256","未记录")),("源码绑定测试数",value.get("test_count","未记录")),("当次完整IDE项目",value.get("project","未记录")),("已实物重测",value.get("hardware_retested",False)),("30fps用户确认",value.get("achieved_30fps",False)),("实物记录",json.dumps(value.get("hardware_result",value.get("hardware_observation","未记录")),ensure_ascii=False))]
    return text+table(["短曝光候选项目","当次回执"],rows)

def color_phase_detail() -> str:
    text="<h3>GBRG颜色相位候选：尚待实物颜色确认</h3><p>基于已确认30fps的短曝光文件，仅物理顶层显式设置BAYER_PATTERN=2（GBRG）；通用模块缺省RGGB=0与四模式支持保留。曝光、增益、DDR/COPY/HDMI通道和白平衡均不改。候选<a href='build/style_video_camera_gbrg.bit'>style_video_camera_gbrg.bit</a> · <a href='build/camera_color_phase_receipt.json'>打包回执</a> · <a href='build/camera_color_phase/profile_receipt.json'>相位推导与源码审计</a>。</p><p>官方手册第30页原生BGGR，加第31页公开输出y偏移5和双向flip定义可推导GBRG；上游3200..3207窗口定义未公开，官方旧流水也含行/像素偏移，因此推导仍需红/蓝/白色块实拍。当前绿紫问题未解决，不把编译通过或拟议相位当作实物颜色通过。当前有用户证据的运行文件仍以<a href='build/active_hardware_image.json'>active marker</a>为准。</p>"
    path=ROOT/"build"/"camera_color_phase_receipt.json"
    if not path.exists():return text+"<p>GBRG打包回执尚未生成，编译、打包及实物状态尚不能判断。</p>"
    value=json.loads(path.read_text(encoding="utf-8-sig"))
    if value.get("hardware_retested") and not value.get("color_corrected"):
        text="<h3>历史GBRG候选：实物颜色测试失败</h3><p>用户报告红色物体显示绿色、蓝色显示黑色、绿色显示粉紫；CAP/COPY均30，UF/ERR/DROP0。综合日志和映射网表确认BAYER2确实进入<a href='build/style_video_camera_gbrg.bit'>GBRG位流</a>，但运行中版本没有独立读回。仅凭公开窗口和flip推导的相位没有得到实物支持；应通过标准RGB参考条和四个RAW采样位置均值诊断。<a href='docs/color_probe.md'>COLOR PROBE 01使用说明</a>。此文件保留为失败记录，不作为正确颜色基线。</p>"
    rows=[("状态",value.get("status","未记录")),("SHA256",value.get("sha256","未记录")),("bit字节数",value.get("bytes","未记录")),("IDE项目",value.get("project","未记录")),("已实物重测",value.get("hardware_retested",False)),("用户颜色反馈",json.dumps(value.get("hardware_result",value.get("hardware_observation","未记录")),ensure_ascii=False))]
    return text+table(["GBRG候选项目","当次回执"],rows)

def color_probe_detail() -> str:
    text="<h3>COLOR PROBE01实物确认：右图BGGR3颜色正确但偏暗</h3><p>用户确认版本标记及RGB/白/灰条正确，右图颜色正确但偏暗，CAP/COPY30、UF/ERR/DROP0。诊断左侧为RGGB0，右侧对同一RGB仅交换R/B，等效BGGR3；这为当前摄像头/ROI/方向的有效Bayer3提供实物证据，GBRG2失败历史保留。参考条由显示端生成，未经过摄像头/DDR或右图交换。用户没有提供四RAW数值或精确观察时长，运行bit身份未独立读回。</p><p><a href='build/style_video_color_probe.bit'>诊断bit</a> · <a href='build/color_probe_receipt.json'>诊断回执</a> · <a href='build/active_hardware_image.json'>active marker</a> · <a href='docs/color_probe.md'>诊断文档</a>。中心128×128的四RAW位置均值整组跨域，黄框和文字帮助测量；此版本右图是相位对照，不是CNN结果，左图也不是正式正确颜色输出。正式BGGR+gamma候选去掉这些诊断覆盖层，颜色已获确认，亮度和锐度仍未验收。</p>"
    path=ROOT/"build/color_probe_receipt.json"
    if not path.exists():return text+"<p>诊断构建/打包尚未完成，以回执为准。</p>"
    value=json.loads(path.read_text(encoding="utf-8-sig"))
    return text+table(["诊断项目","当次回执"],[("状态",value.get("status")),("SHA256",value.get("sha256")),("源码绑定测试数",value.get("test_count")),("WNS / WHS",str(value.get("wns_ns"))+" / "+str(value.get("whs_ns"))+" ns"),("IDE项目",value.get("project")),("实物已测试",value.get("hardware_retested",False)),("有效Bayer确认",value.get("confirmed_effective_bayer_pattern","未记录")),("用户观察",json.dumps(value.get("hardware_observation",{}),ensure_ascii=False))])

def bggr_gamma_detail() -> str:
    text="<h3>原BGGR3+gamma22基线：颜色已确认，图像质量待优化</h3><p><a href='build/style_video_bggr_gamma.bit'>style_video_bggr_gamma.bit</a> · <a href='build/bggr_gamma_receipt.json'>候选回执</a>。基于诊断右图BGGR3颜色正确但偏暗的反馈，正式物理顶层显式Bayer3，camera_preprocess RGB经style_rgb_gamma后进入camera_cdc。去掉probe/左右R/B交换/黄框/标准条，曝光和DDR不改；没有白平衡或完整ISP。</p><p>gamma22是离线256×8表，y=floor(255*(x/255)^(1/2.2)+0.5)，同一函数分别作用于R/G/B。硬件无浮点、幂运算或额外流水拍；ENABLE=0/--tone-profile linear透传。官方2P2.mem采用x^2.2压暗，方向相反，不能直接复用。当前正常默认Bayer3/gamma18，原gamma22需显式选择，color-probe要求显式Bayer0、默认linear；DDR及未来CNN输入因此是当前tone编码的RGB888，非精确sRGB或校准线性图像。用户已反馈颜色正确但模糊，所附单张照片显示CAP/COPY30、UF/ERR/DROP0；亮度、锐度与持续稳定性尚未由本次照片验收。</p>"
    text+="<p>最新照片对比：用户确认颜色正确但模糊，OSD相对清楚、摄像头画面低对比；单张照片的CAP/COPY30与UF/ERR/DROP0不代表持续稳定性。镜头距魔方约10cm；用户已确认镜头可手动对焦，尚未报告调焦后的清晰度或50–100cm远距对比。当前2×2半分辨率Debayer得到960×540，再最近邻缩至640×480，16:9到4:3为非等比缩放（横向相对压缩25%）。该旧gamma22链路没有黑电平校准或锐化；这不说明传感器内部没有BLC。Gamma逐像素映射、不混合邻域，其对发灰观感的贡献尚未测量。运行bit身份按会话关联，未独立读回；亮度与锐度未验收。</p>"
    source_path=ROOT/'build/source_receipt.json'
    if source_path.exists():
        current=json.loads(source_path.read_text(encoding='utf-8-sig'))
        text+=table(['当前准备源配置','记录'],[('tone_profile',current.get('tone_profile','尚未记录')),('Bayer',current.get('bayer_pattern','尚未记录')),('color_probe',current.get('color_probe_enabled','尚未记录')),('contrast_probe',current.get('contrast_probe_enabled','尚未记录')),('black_level_profile',current.get('black_level_profile','尚未记录')),('RAW A/B/C/D黑位',json.dumps(current.get('raw_black_levels',{}),ensure_ascii=False)),('white_balance_profile',current.get('white_balance_profile','尚未记录')),('RGB Q8增益',json.dumps(current.get('white_balance_gains_q8',{}),ensure_ascii=False)),('对比度启动档',current.get('display_contrast_initial_level','未启用'))])
    path=ROOT/'build/bggr_gamma_receipt.json'
    if not path.exists():return text+'<p>正式候选打包回执尚未生成，不能据文件名判断构建或实物状态。</p>'
    value=json.loads(path.read_text(encoding='utf-8-sig'))
    return text+table(['正式候选项目','当次回执'],[('状态',value.get('status')),('SHA256',value.get('sha256')),('IDE项目',value.get('project')),('源码绑定测试数',value.get('test_count')),('实物已测试',value.get('hardware_retested',False)),('用户观察',json.dumps(value.get('hardware_observation',value.get('hardware_result',{})),ensure_ascii=False))])

def gamma18_detail() -> str:
    text="<h3>gamma18实物反馈：仍明显发灰，遮镜也灰</h3><p>针对旧gamma22照片偏灰、低对比的问题，本候选只将Gamma从2.2改为1.8，保留BGGR3、曝光、DDR和HDMI配置。style_rgb_gamma新增GAMMA_TENTHS=18参数，支持18/22，ENABLE=0透传；仍为逐像素组合LUT，不混合邻域、不加流水拍。该gamma18版本未加入独立对比度、黑电平或锐化处理。用户实物反馈仍明显发灰，CAP/COPY30且UF/ERR/DROP0；完全遮住镜头时也明显灰。当时没有数值黑位读数；后续CONTRAST PROBE遮镜实测见下节。</p><p>prepare支持--tone-profile linear/gamma18/gamma22，普通默认gamma18；color-probe仍要求Bayer0与linear。新文件为<a href='build/style_video_bggr_gamma18.bit'>style_video_bggr_gamma18.bit</a>，原gamma22文件及回执保留，active marker仅按实物反馈更新。DDR/COPY及未来CNN接收当前tone编码的RGB888，队友须匹配训练输入；该选择是构建配置，不是APB在线开关。用户确认手动对焦镜头，但尚未报告调焦后的清晰度。</p>"
    path=ROOT/'build/bggr_gamma18_receipt.json'
    if not path.exists():return text+'<p>候选打包回执尚未生成；不能据拟定文件名判断构建完成。</p>'
    value=json.loads(path.read_text(encoding='utf-8-sig'))
    return text+table(['gamma18候选项目','当次回执'],[('状态',value.get('status')),('SHA256',value.get('sha256')),('IDE项目',value.get('project')),('源码绑定测试数',value.get('test_count')),('实物已测试',value.get('hardware_retested',False)),('用户观察',json.dumps(value.get('hardware_observation',{}),ensure_ascii=False))])

def contrast_probe_detail() -> str:
    text="<h3>CONTRAST PROBE01：右图可调对比度与RAW黑位观察</h3><p>用户确认本诊断标记和KEY1正常，CAP/COPY30、UF/ERR/DROP0；遮镜RAW A041/B042/C042/D043即65/66/66/67，右图1.50倍较自然。该旧诊断保留未扣黑的gamma18摄像头、DDR和左图基线，只对右图x640..1279、y120..599在显示端做五档对比度映射。KEY1循环1.00/1.25/1.50/1.75/2.00倍，默认1.50倍；20ms按下/释放消抖，长按只计一次，x=y=0帧起点应用。精确映射为clip[0,255](floor(((code-128)*(4+level)+514)/4))，level0严格透传；以128为中心，超过范围饱和，不能当作实测黑位扣除。它不会回写DDR或改变CNN输入，也不是CNN结果、锐化或自动BLC。</p><p>底部显示CONTRAST PROBE01、A/B/C/D的10bit RAW均值、档位/KEY1提示及参考色条。中心128×128区完整合法帧的四位置均值经40bit异步FIFO跨域，像素域整组锁存；用户完全遮镜后的该组读数已作为新候选的固定黑位估计；不是自动跟踪，也未证明全幅、全温度和所有曝光配置都相同。动态场景的统计并非与显示前台逐帧绑定。</p><p>用--contrast-probe启用，与--color-probe互斥、要求Bayer3/gamma18；普通版本仍默认gamma18，旧color-probe仍要求Bayer0/linear。候选<a href='build/style_video_contrast_probe.bit'>style_video_contrast_probe.bit</a>与<a href='build/contrast_probe_receipt.json'>回执</a>独立保存；gamma18/22历史与位流保留，正式画质仍未通过。这是定位与可调对照，不保证根治灰感。</p>"
    path=ROOT/'build/contrast_probe_receipt.json'
    if not path.exists():return text+'<p>诊断打包回执尚未生成，不能据拟定名称判断构建完成。</p>'
    value=json.loads(path.read_text(encoding='utf-8-sig'))
    return text+table(['CONTRAST PROBE候选','当次回执'],[('状态',value.get('status')),('SHA256',value.get('sha256')),('IDE项目',value.get('project')),('源码绑定测试数',value.get('test_count')),('实物已测试',value.get('hardware_retested',False)),('用户观察',json.dumps(value.get('hardware_observation',{}),ensure_ascii=False))])

def black_level_detail() -> str:
    text="<h3>实测RAW黑位修正：黑灰底已解决，轻微绿偏待测</h3><p>遮镜A041/B042/C042/D043对应65/66/66/67。style_camera_preprocess新增BLACK_LEVEL_A/B/C/D，通用默认0；物理measured将物理2×2四位置设为65/66/66/67，在RAW10上逐样本做max(raw-offset,0)，再Bayer选色、平均两G、截取8bit，随后仍接gamma18。BGGR3的蓝来自A65、红来自D67、两G为B/C66。不做白点拉伸，不改曝光或白平衡。</p><p>该实测黑位若未扣除，旧流程截到8bit约16，gamma18查表后为55，可解释灰底；理想等于偏置的样本扣后0→gamma0，用户实屏确认遮镜为纯黑，黑灰底问题按本次观察已解决；这不等于测得每个数字像素恒为0。用户仍反馈轻微偏绿，白平衡与清晰度尚未验收。偏置来自此次场景/配置的固定估计，不是自动跟踪全温度或所有曝光。</p><p>新<a href='build/style_video_black_level.bit'>style_video_black_level.bit</a>复用原CONTRAST PROBE01标题/KEY1五档，已测位流启动默认1.50，用户在扣黑后选择RIGHT1.00最自然。当前WB版本物理顶层已显式启动0即1.00，通用模块默认2即1.50保留；新候选实板待测。统计仍在BLC前，遮镜RAW均值可能仍为041..043而非0。必须选择新文件；该UI标记不唯一识别新版本，运行bit身份仍按会话关联、未独立读回。</p><p>prepare新增--black-level-profile none/measured，正常默认measured，仅适用于short_exposure/Bayer3；color-probe强制none。none可重现旧未扣黑输入。DDR及未来CNN收到BLC后gamma18像素，位宽/字节序/握手保持但数值语义更新。用户报告CAP/COPY30、UF/ERR/DROP0，魔方颜色大致正确但仍轻微偏绿。用户后续白纸RAW A09C/B0F5/C0F5/D0A0，扣黑后RGB93/179/91，见下一固定WB候选；该BLC历史位流未加入白平衡修正；整体画质和清晰度未完成验收。</p>"
    path=ROOT/'build/black_level_receipt.json'
    if not path.exists():return text+'<p>打包回执尚未生成，不能据拟定文件名判断构建完成。</p>'
    value=json.loads(path.read_text(encoding='utf-8-sig'))
    return text+table(['BLC候选','当次回执'],[('状态',value.get('status')),('SHA256',value.get('sha256')),('IDE项目',value.get('project')),('源码绑定测试数',value.get('test_count')),('实物已测试',value.get('hardware_retested',False)),('用户观察',json.dumps(value.get('hardware_observation',{}),ensure_ascii=False))])

def white_balance_detail() -> str:
    text="<h3>固定白平衡实测：绿偏消失，室外天空微红待诊断</h3><p>用户在BLC版上提供白纸A09C/B0F5/C0F5/D0A0，即156/245/245/160。扣除65/66/66/67并按BGGR3选色后R93/G179/B91，以G为参考得到Q8增益R493/G256/B504（约1.926/1/1.969）。<a href='build/white_balance_measurement.json'>测量记录</a>保存原始证据。</p><p>style_camera_preprocess先逐RAW10扣黑、选色并向下取整两G均值，再计算min(1023,(raw10*gain_q8+128)>>8)：21bit无符号乘加、半向上舍入和10bit饱和，最后截到RGB8再gamma18。通用增益均256，物理measured493/256/504。将本次均值代入得到RGB10约179/179/179、gamma前RGB8为44/44/44；这是均值计算预测，不保证每个像素都相等。</p><p>新<a href='build/style_video_white_balance.bit'>style_video_white_balance.bit</a>同时采用物理对比度启动0即1.00，KEY1五档保留；通用INITIAL_LEVEL默认2不变。左图为BLC+固定WB+gamma18基线，右图启动1.00时严格透传，仅显示端后续对比度不回写DDR。原RAW统计仍在BLC/WB之前，白纸A/B/C/D不会因为该修正自动变相等；复用CONTRAST PROBE01标题，须用新文件名核对候选。</p><p>prepare新增--white-balance-profile none/measured，普通measured BLC默认measured WB；测量增益仅用于BGGR3/short_exposure/measured BLC。旧BLC复现需WB none及--contrast-initial-level 2；旧无BLC对比度默认WB none/初档2。DDR与未来CNN输入改为扣黑、固定WB、近似gamma1.8的RGB888，需匹配训练预处理。</p><p>这是当前照明一次测量的固定WB，不是自动白平衡或完整ISP。增大R/B可能导致高光饱和、放大噪声及整体亮度变化；曝光和传感器增益未改。用户已确认WB版不发绿，CAP/COPY均30、UF/ERR/DROP均0；直接拍室外天空微红，隔玻璃更红，整体颜色适应性和清晰度仍待验证。</p>"
    path=ROOT/'build/white_balance_receipt.json'
    if not path.exists():return text+'<p>候选打包回执尚未生成，不据拟定名称判断构建完成。</p>'
    value=json.loads(path.read_text(encoding='utf-8-sig'))
    return text+table(['WB候选','当次回执'],[('状态',value.get('status')),('SHA256',value.get('sha256')),('IDE项目',value.get('project')),('源码绑定测试数',value.get('test_count')),('准备配置检查数',value.get('prepare_test_count')),('实物已测试',value.get('hardware_retested',False)),('用户观察',json.dumps(value.get('hardware_observation',{}),ensure_ascii=False))])

CSS = """
:root{color-scheme:light;--ink:#142C3E;--muted:#536D7D;--bg:#F3F6FA;--panel:#FFF;--line:#DAE3EC;--blue:#14638A;--soft:#EAF3F9;--warm:#FFF3D8}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.7 'Microsoft YaHei','Segoe UI',sans-serif}a{color:var(--blue)}a:focus-visible,button:focus-visible,input:focus-visible,summary:focus-visible{outline:3px solid #2289C2;outline-offset:3px}header{padding:42px 6vw 26px;background:linear-gradient(130deg,#142C3E,#20516C);color:#fff}header p{max-width:950px;color:#D8EAF6}h1{font-size:34px;margin:0 0 14px}h2{font-size:25px;margin:0 0 14px}h3{font-size:18px;margin:20px 0 8px}.eyebrow{font-size:13px;letter-spacing:2px;color:#BAE6FD}.badge{display:inline-block;border:1px solid #97B2C2;padding:3px 12px;border-radius:20px;margin:5px 7px 0 0;font-size:13px}.layout{display:grid;grid-template-columns:255px minmax(0,1fr);gap:24px;max-width:1510px;margin:auto;padding:28px 3vw}aside{align-self:start;position:sticky;top:15px;max-height:94vh;overflow:auto}aside a{display:block;padding:6px 9px;text-decoration:none;font-size:13px}aside a:hover{background:var(--soft)}.nav-group{font-size:13px;color:var(--muted);margin:13px 9px 2px}main{min-width:0}section,.module{background:var(--panel);border:1px solid var(--line);border-radius:13px;padding:24px;margin-bottom:20px}.callout{padding:14px 17px;border-left:4px solid #C29824;background:var(--warm)}.muted{color:var(--muted)}.toolbar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:16px 0}.toolbar input{flex:1;min-width:220px;padding:11px 13px;border:1px solid #A9BECD;border-radius:7px;font:inherit}button{padding:10px 14px;border:1px solid #A9BECD;border-radius:7px;background:var(--panel);color:var(--ink);font:inherit;cursor:pointer}button:hover{background:var(--soft)}.table-wrap{overflow:auto;margin:12px 0}table{border-collapse:collapse;width:100%;font-size:14px}th{text-align:left;background:var(--soft);font-weight:600}th,td{padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:top}td:first-child{font-family:Consolas,'Microsoft YaHei',monospace;overflow-wrap:anywhere}summary{cursor:pointer;font-weight:600;font-size:19px}.module>summary{list-style-position:outside;padding-left:4px}.module[open]>summary{padding-bottom:16px;border-bottom:1px solid var(--line)}.module-title{color:var(--muted);font-weight:400;font-size:14px}.pill{display:inline-block;padding:2px 9px;border-radius:14px;background:var(--soft);font-size:12px;margin-left:6px}pre{overflow:auto;white-space:pre;max-height:580px;padding:18px;background:#152C3D;color:#E1EDF4;border-radius:9px;font:13px/1.55 Consolas,monospace}code{font-family:Consolas,monospace}p code,li code{background:var(--soft);padding:2px 5px;border-radius:4px}.source-link{font-size:14px}.module section{padding:0;border:0;border-radius:0}.sequence{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.step{background:var(--soft);padding:14px}.step b{display:block}.frame-slots{display:grid;grid-template-columns:repeat(6,1fr);gap:8px}.slot{background:var(--soft);border-top:3px solid var(--blue);padding:10px;text-align:center;font-size:13px}.slot.result{background:#F0F5E7;border-color:#658249}svg{width:100%;height:auto;display:block}.band{fill:#F5F8FA;stroke:#DAE3EC}.bandlabel{font-size:16px;fill:#526C7D}.node rect{fill:#FFF;stroke:#B8CBD8;stroke-width:1.5}.node text{font:18px 'Microsoft YaHei',sans-serif;fill:#142C3E}.node .sub{font-size:13px;fill:#536D7D}.node:hover rect{fill:#EAF3F9;stroke:#14638A}.future rect{stroke-dasharray:6 5;fill:#FAFAFA}.platform rect{fill:#EDF4F9}.edge-label{font:13px 'Microsoft YaHei',sans-serif;fill:#536D7D}.receipt{font-size:13px}.empty{padding:25px;background:var(--warm);text-align:center}[hidden]{display:none!important}footer{padding:24px;text-align:center;color:var(--muted);font-size:13px}@media(max-width:1050px){.layout{grid-template-columns:1fr}aside{position:static;max-height:260px;columns:2}.sequence{grid-template-columns:1fr 1fr}.frame-slots{grid-template-columns:repeat(3,1fr)}}@media(max-width:600px){header{padding:28px 20px}h1{font-size:27px}.layout{padding:18px 12px}section,.module{padding:18px}.sequence{grid-template-columns:1fr}aside{columns:1}summary{font-size:16px}.toolbar input{min-width:100%}}
"""

JS = """
(() => {
  'use strict';
  const search = document.getElementById('module-search');
  const cards = Array.from(document.querySelectorAll('details.module'));
  const navLinks = Array.from(document.querySelectorAll('aside a[data-module]'));
  const count = document.getElementById('match-count');
  const empty = document.getElementById('no-matches');
  function filterCards() {
    const terms = search.value.trim().toLowerCase().split(/\\s+/).filter(Boolean);
    let visible = 0;
    cards.forEach(card => {
      const matches = terms.every(term => card.dataset.search.includes(term));
      card.hidden = !matches;
      if (matches) visible += 1;
    });
    navLinks.forEach(link => { link.hidden = document.getElementById(link.dataset.module).hidden; });
    count.textContent = visible + ' / ' + cards.length + ' 个模块';
    empty.hidden = visible !== 0;
  }
  search.addEventListener('input', filterCards);
  document.getElementById('expand-all').addEventListener('click', () => {
    cards.filter(card => !card.hidden).forEach(card => { card.open = true; });
  });
  document.getElementById('collapse-all').addEventListener('click', () => {
    cards.forEach(card => { card.open = false; });
  });
  document.getElementById('clear-search').addEventListener('click', () => {
    search.value = ''; filterCards(); search.focus();
  });
  document.querySelectorAll('a[data-module]').forEach(link => {
    link.addEventListener('click', event => {
      const card = document.getElementById(link.dataset.module);
      if (!card || !card.classList.contains('module')) return;
      event.preventDefault();
      if (card.hidden) { search.value = ''; filterCards(); }
      card.open = true;
      card.scrollIntoView({behavior:'smooth',block:'start'});
      window.history.replaceState(null, '', '#' + card.id);
    });
  });
  filterCards();
})();
"""

def perf_monitor_detail() -> str:
    path=ROOT/'build/performance_monitor_receipt.json'
    state="新版构建和实板验证状态以独立回执为准；当前尚无该版本实板验收。"
    if path.exists():
        record=json.loads(path.read_text(encoding='utf-8'))
        state=f"已打包候选，WNS {record.get('wns_ns')}ns、WHS {record.get('whs_ns')}ns；实板验证：{'已有记录' if record.get('hardware_tested') else '待用户确认'}。"
    return """<section id='performance-monitor'><h2>新增：按帧性能监测</h2><p>CAP/JOB/QUEUE/TOTAL全部对应同一发布frame_id，单位为微秒。CAP从核心分配采集帧槽到成功写入DDR；JOB包含任务读写DMA；TOTAL止于完整结果pair发布，不含镜头曝光、前端CDC和实际显示扫描延迟。统计只观察事件和总线，不参与视频流控制。</p><p>上方PERF 01每120个HDMI帧轮换LAT/DDR/BUS/MAX四页，延迟、字节、等待及高水位均为十进制；F帧号和S快照号为十六进制。原KEY1/2/3功能保留。软件通过0x100..0x17C性能寄存器读取相同快照，写CONTROL=2冻结、写1恢复自动、写4清统计；64位读数需在同一快照中读取高低字。</p><p>DDR统计位于平台AXI出口，只覆盖该平台的DMA；不等于DDR理论峰值或未来全SoC所有主机吞吐。FIFO高水位是所连接时钟域观测到的占用峰值；摄像头读域含预取并有跨域同步延迟。</p><p>"""+state+""" <a href='build/style_video_performance.bit'>性能监测位流</a> · <a href='build/performance_monitor_receipt.json'>构建/验证回执</a> · <a href='#registers'>完整寄存器表</a></p><p>维护入口：scripts/generate_core.py和scripts/perf_core.vh生成核心接线；prepare_efinity.py的--performance-monitor启用物理封装。新版重建命令：<code>python scripts/prepare_efinity.py --contrast-probe --wb-calibration --performance-monitor</code>。</p></section>"""

def camera_capture_detail() -> str:
    path=ROOT/'build/camera_capture_receipt.json'
    state='采集接口仿真和配置生成检查已完成；Efinity构建状态见验证记录。新封装版未上板。'
    if path.exists():
        record=json.loads(path.read_text(encoding='utf-8'))
        state=f"封装版已构建，WNS {record.get('wns_ns')}ns、WHS {record.get('whs_ns')}ns；新采集/配置检查10项通过，其余未改模块沿用源码匹配的90项记录。实板验证：{'已有记录' if record.get('hardware_tested') else '待拿到板子后验证'}。"
    return """<section id='camera-capture-interface'><h2>独立采集模块：style_camera_capture</h2><p>现在顶层通过一个模块实例接入采集：<b>摄像头域RAW10×4 / VS / HS / DE → 黑位/Bayer/白平衡/缩放/Gamma → 图像与取消CDC → 核心域RGB流、状态和水位</b>。MIPI物理接收IP、传感器I²C初始化、DDR DMA保留独立边界，便于Sapphire队友接管配置。</p><p>统一输出：m_rgb[23:0]、m_valid/m_ready、m_sof/m_eol/m_eof、m_frame_id[31:0]；另有m_abort及编号、input/drop/error计数、abort_queue_fault和FIFO水位。所有这些输出属于core_clk；可选raw_mean_valid/data单独属于camera_clk。动态白平衡请求也必须在camera_clk域稳定，SOF时锁存。</p><p>输入CSI不能反压；输出拥塞过久会取消整帧，接收方须按编号丢弃残余像素。像素与取消分开跨域，没有到达先后保证。三个复位输入须共同断言、按域同步释放。此次只封装接口，保留640×480、黑位65/66/66/67、固定增益493/256/504、Gamma18和既有白纸校准/性能诊断；不是采集提速。</p><p>"""+state+"""</p><p><a href='docs/camera_capture.md'>全部接口、参数、接入实例及Efinity操作</a> · <a href='#style_camera_capture' data-module='style_camera_capture'>展开模块源码和逐端口表</a> · <a href='build/style_video_camera_capture.bit'>采集封装版比特流</a> · <a href='build/camera_capture_receipt.json'>本次构建回执</a></p></section>"""


def ddr_display_detail() -> str:
    path=ROOT/'build/ddr_display_modules_receipt.json'
    state='DDR/显示模块验证与Efinity构建进行中；当前无新版实板反馈。'
    if path.exists():
        record=json.loads(path.read_text(encoding='utf-8'))
        state=f"模块版已构建，WNS {record.get('wns_ns')}ns、WHS {record.get('whs_ns')}ns；验证记录合计{record.get('test_count')}项，实板验证{'已有记录' if record.get('hardware_tested') else '待拿到板子后进行'}。"
    return """<section id='ddr-display-modules'><h2>三模块接口：采集 → DDR帧缓存 → HDMI显示</h2><p><b>style_camera_capture</b>输出统一RGB流；<b>style_ddr_framebuffer</b>管理四DMA、帧槽、CNN接口和CPU控制；<b>style_hdmi_display</b>接收配对RGB流并完成显示FIFO、720p时序、诊断和HDMI编码。物理CSI、DDR控制器/PHY及高速串化引脚保留板级封装。</p><p>当前默认布局：<b>左图x0..639/y120..599为原始预处理画面；右图x640..1279/y120..599为黑色CNN预留区</b>，上下状态区及RESULT标题保留。右黑遮罩位于全部叠加和欠载保护之后；隐藏右图仍消费COPY结果token，不破坏行序，不代表已经运行CNN或减少DDR流量。</p><p><b>RISC-V从哪里接：</b>顶层<code>framebuffer</code>实例的APB3端口<code>paddr/psel/penable/pwrite/pwdata/prdata/pready/pslverr</code>和<code>irq</code>。当前APB仍接空闲常数；Sapphire队友分配外设系统基址、连接APB/中断，先读IDENT=0x53565931。时钟不同则用APB跨域桥。</p><p>CNN接<code>framebuffer.accel_*</code>；完整算法接好后将FORCE_BYPASS设0、软件清CONTROL.bit2，再在准备命令加<code>--show-result</code>令显示RESERVE_CNN=0。当前RESERVE_CNN=1覆盖APB显示模式，单独写DISPLAY_MODE=0不会显示右图。</p><p>"""+state+"""</p><p><a href='docs/ddr_display_modules.md'>完整接口与RISC-V/CNN接线步骤</a> · <a href='#style_ddr_framebuffer' data-module='style_ddr_framebuffer'>DDR模块全部端口</a> · <a href='#style_hdmi_display' data-module='style_hdmi_display'>显示模块全部端口</a> · <a href='build/style_video_ddr_display_modules.bit'>模块版比特流</a> · <a href='build/ddr_display_modules_receipt.json'>构建回执</a></p></section>"""


def build() -> dict:
    modules = [parse_module(path) for path in sorted((ROOT / "rtl").glob("style_*.sv"))]
    modules += [parse_module(path) for path in sorted((ROOT / "rtl").glob("style_*.v"))]
    names = {item["name"] for item in modules}
    order = {name: i for i, name in enumerate(DESCRIPTIONS)}
    modules.sort(key=lambda item: (order.get(item["name"], 100), item["name"]))
    sim_label, sim_receipt = read_receipt("validation_receipt.json")
    ef_label, ef_receipt = read_receipt("efinity_receipt.json")
    nav = "<a href='#overview'>架构与数据流</a><a href='#integration'>队友接入与职责</a><a href='#memory'>DDR布局与帧所有权</a><a href='#registers'>APB寄存器</a><a href='#efinity'>Efinity使用步骤</a><a href='#development'>修改与重新生成</a><a href='#validation'>验证证据</a>"
    nav += "<a href='#performance-monitor'>性能监测与延迟</a>"
    nav += "<a href='#camera-capture-interface'>独立采集模块接口</a>"
    nav += "<a href='#ddr-display-modules'>DDR/显示模块与RISC-V入口</a>"
    last_group = None
    bodies = []
    for module in modules:
        name, desc = module["name"], module["desc"]
        if desc["group"] != last_group:
            nav += f"<p class='nav-group'>{escaped(desc['group'])}</p>"; last_group = desc["group"]
        nav += f"<a href='#{name}' data-module='{name}'>{escaped(desc['title'])}</a>"
        search_text = " ".join([name, *desc.values(), module["source"]]).lower()
        body = f"<details class='module' id='{name}' data-search='{escaped(search_text)}'><summary>{escaped(desc['title'])} <span class='module-title'>{name}</span><span class='pill'>{escaped(desc['group'])}</span></summary>"
        body += f"<p>{escaped(desc['purpose'])}</p><p class='muted'>时钟域：{escaped(desc['domain'])}。复位极性以实际端口及下方源码为准。</p>"
        for title, key in [("实现逻辑", "logic"), ("握手与时序", "handshake"), ("状态与流程", "states"), ("错误处理与恢复", "recovery")]:
            body += f"<h3>{title}</h3><p>{escaped(desc[key])}</p>"
        body += "<h3>实际参数</h3>" + (table(["参数", "源码默认值"], module["parameters"]) if module["parameters"] else "<p>无可配置模块参数。</p>")
        body += "<h3>全部实际端口</h3>" + table(["端口", "方向", "位宽声明", "用途与约定"], [(*p,port_meaning(name,p[0],p[1])) for p in module["ports"]])
        body += f"<p class='source-link'>源文件：<a href='{escaped(module['path'])}'>{escaped(module['path'])}</a>；下方内嵌当前源码，可直接在网页搜索。</p>"
        body += f"<details><summary>展开完整源码</summary><pre><code>{escaped(module['source'])}</code></pre></details></details>"
        bodies.append(body)
    reg_table = table(["Offset", "名称", "权限", "行为"], [("0x"+r[0],*r[1:]) for r in REGISTERS])
    slots = "".join(f"<div class='slot{' result' if slot>=4 else ''}'>{'输入' if slot<4 else '结果'} {slot if slot<4 else slot-4}<br><code>0x{0x01000000+slot*0x00200000:08X}</code></div>" for slot in range(6))
    output = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>赛题一 · Ti60 视频平台代码说明</title><style>{CSS}</style></head>
<body><header><div class="eyebrow">EFINIX TI60 · STYLE VIDEO PLATFORM</div><h1>你的采集、DDR 和显示平台</h1><p>从官方物理接口到通用 RGB 流，再到帧池、DDR 和 720p 显示。点击架构中的模块可展开接口、实现逻辑和源代码；队友完成 RISC-V / CNN 后沿预留接口接入。</p><span class="badge">Efinity sv_09</span><span class="badge">640×480 RGB888处理流</span><span class="badge">720p60目标显示</span><span class="badge">COPY占位 · 无CPU/CNN实例</span></header>
<div class="layout"><aside aria-label="文档导航">{nav}</aside><main>
{ddr_display_detail()}
{camera_capture_detail()}
{perf_monitor_detail()}
<section id="overview"><h2>完整数据与控制框架</h2><div class="callout">当前代码是独立视频平台和复制验证路径。它不表示已经完成实时神经风格迁移；MIPI、DDR和HDMI最终状态以当前构建及实板记录为准。</div>{diagram(names)}<p class="muted">你负责实线的视频基础平台。RISC-V队友负责未来的软件控制；卷积队友交付完整处理模块。官方MIPI/DDR/PLL/高速输出封装保留在Efinity工程内。</p></section>
<section id="wb-calibration"><h2>新版按键白平衡</h2><p>新增KEY2白纸校准、KEY3恢复默认；KEY1仍调右图对比度。按键后四个新完整帧统计→黑位扣除→Q8比值→下个摄像头SOF锁存→原像素/Gamma/DDR通路。校准影响实际DDR/CNN输入，两侧显示同时改变；不是只给右图调色。</p><p>底部WB CAL 01显示DEFAULT / SAMPLE / CALC / APPLY / LOCKED / REJECT与实际R/B增益。默认仍493/256/504，过暗、均值接近饱和、增益超限或超时保留原参数。它是人为选择中性目标的一次校准，不是持续AWB，也不保证修复全部天空色差。</p><p><a href='docs/wb_calibration.md'>按键操作、模块接口、状态与Efinity重建说明</a> · <a href='build/wb_calibration_receipt.json'>新版独立构建回执</a>。新版实板画质和计数待用户验证；历史固定版30fps反馈保留在旧回执。</p></section>
<section id="flow"><h2>一帧如何走完系统</h2><div class="sequence"><div class="step"><b>1 · 采集入库</b>RAW预处理为640×480，标志完整且最后DDR写响应成功后，输入槽进入READY。</div><div class="step"><b>2 · 执行任务</b>选最早READY输入和空结果槽；当前复制，未来由队友CNN计算。</div><div class="step"><b>3 · 完整结果</b>整帧输出与写响应确认后，保留对应原图，成为pending pair。</div><div class="step"><b>4 · 安全显示</b>旧AXI读取排空、FIFO清空，再在安全窗口发布配对原图/结果。</div></div></section>
<section id="integration"><h2>和两位队友怎样接</h2>{table(['负责人','当前交付边界','集成条件'],[('你','MIPI/预处理/CDC/DDR DMA/帧池/布局/OSD/HDMI/物理工程','先用COPY验证数据完整、帧保护和显示'),('RISC-V队友','Sapphire/BSP/C驱动/摄像头配置/权重加载/调度','分配APB系统基址，连接irq，明确I²C控制权'),('卷积队友','RGB输入→完整网络→RGB输出；内部权重和特征管理','ready/valid、SOF/EOL/EOF、frame_id、640×480输出全部遵守契约')])}<p>当前平台包含图像输入读DMA和结果写DMA。若队友已有AXI主机加速器，需要另外扩展仲裁和控制接口；不能同时让两套DMA读写同一个未完成结果。</p><p><a href="docs/interface_contract.md">完整接入契约</a> · <a href="docs/camera.md">摄像头说明</a> · <a href="docs/memory.md">DMA与帧池说明</a> · <a href="docs/display.md">显示说明</a> · <a href="docs/camera_hardware_fix.md">首次硬件问题与修复</a></p><p>统一流：<code>rgb[23:0], valid, ready, sof, eol, eof, frame_id[31:0]</code>。等待ready时所有payload保持；frame_id关联原画与结果。APB系统基址待Sapphire集成时分配。原生CSI VS/HS高有效：VS上升SOF、下降EOF，默认和物理顶层VS_ACTIVE=1。</p></section>
<section id="memory"><h2>DDR布局与所有权</h2><p>每帧640×480，RGBX8888，stride=2560字节，有效帧1,228,800字节。word=<code>0x00RRGGBB</code>，LE字节顺序为<code>B,G,R,0</code>。AXI128一拍四像素，最早像素在低32位。</p><div class="frame-slots">{slots}</div><p>每槽2MiB。输入状态 <code>FREE → CAPTURE → READY → PROCESS → RETAIN</code>；结果状态 <code>OUT_FREE → OUT_WRITE → OUT_RETAIN</code>。新前台切换完成后旧pair一起释放。没有空槽时丢新输入帧并计数。</p><p class="callout">推理完成不能直接释放原图，原图还要与其结果配对显示。四输入槽与两结果槽分别保护采集、计算和显示的所有权。</p></section>
<section id="registers"><h2>APB3控制寄存器</h2><p>下面都是字节offset。主控DDR帧池基址<code>0x01000000</code>不是CPU外设寄存器基址。PREADY=1，非法访问PSLVERR，IRQ为使能后sticky事件的电平。</p>{reg_table}</section>
<section id="efinity"><h2>在 Efinity IDE 使用</h2><ol><li>下载稳定bit可以直接使用Programmer，不要求再次综合。需要在IDE重新综合时，优先 File → Open Project 打开当次回执project指定的完整快照：<a href="{escaped(efinity_project_path())}">{escaped(efinity_project_path())}</a>，核对两个新增style_camera_reg模块均在Design Files。</li><li>若回到主<code>efinity/style_video.xml</code>开发，先关闭旧工程，再运行prepare选择camera-profile，再重新打开生成的XML。IDE旧缓存的76项源清单曾覆盖主XML，首次综合报新模块unknown；关闭工程时也可能保存旧清单，因此顺序是先关闭、再prepare、再重开。不要在仍打开的旧缓存工程中直接Compile并假定新源已加载。</li><li>构建脚本独立快照会补齐复制的项目RTL、检查源路径存在且清单无重复；225018快照补入2个模块、共有78项源条目。具体数量和project以当次回执为准。核对器件Ti60F225I3、语言sv_09、顶层style_ti60_top，摄像头1920×1080 RAW10。</li><li>在Interface Designer核对MIPI/DDR/PLL/高速输出，HDMI目标74.25/371.25MHz。修改源码后先<code>python scripts/run_checks.py</code>，再<code>python scripts/build_efinity.py --build</code>，核对资源、布局布线、setup/hold和错误。</li></ol><p>工具基线Efinity2026.1.132.4.5。主prepare按项目全部RTL生成完整清单；构建快照和报告位于build/efinity，稳定bit及回执记录其身份，不覆盖原始官方资料。没有Sapphire实例，软件仍为占位。</p><div class="callout">保留active CSI RTL5.15（HS_BYTECLK70）；同包settings.json的5.16/50不代表当前使用它。不要在IP Manager自动升级或重生成替换保留版本。</div><p>采集DMA等待DDR校准与164个配置命令结束。config_done不检查NACK、传感器ID或有效读回；短曝光30fps已有用户反馈；当前图像质量仍待优化。</p></section>
<section id="development"><h2>维护与重新生成</h2><p><code>rtl/style_platform_core.sv</code>由<code>scripts/generate_core.py</code>生成；修改核心逻辑时改生成器，先运行<code>python scripts/generate_core.py</code>再仿真和构建。<code>style_ti60_top.v</code>和<code>style_camera_initializer.v</code>由<code>prepare_efinity.py</code>生成，物理PHY宏参数来自已验证参考包。调整物理封装、时钟、peri/SDC模板时维护生成脚本，不直接批改厂商IP或旧outflow。</p><p>本网页、README与接口契约由<code>build_docs.py</code>生成，源码或收据变化后重新生成说明；任何重生成后仍须重新核对对应源码哈希和验证记录。</p></section>
<section id="validation"><h2>当前验证记录</h2><p><b>{escaped(sim_label)}</b>；<b>{escaped(ef_label)}</b>。网页依据项目build记录生成，不凭旧bit文件判断成功。</p>{implementation_detail()}{camera_fix_detail()}{short_exposure_detail()}{color_phase_detail()}{color_probe_detail()}{bggr_gamma_detail()}{gamma18_detail()}{contrast_probe_detail()}{black_level_detail()}{white_balance_detail()}{performance_detail()}<details><summary>RTL验证记录</summary><pre class="receipt">{escaped(sim_receipt)}</pre></details><details><summary>Efinity记录</summary><pre class="receipt">{escaped(ef_receipt)}</pre></details><p>2026-10-14首次有OSD但FRAME/FPS0，20:53仅为旧bit文件时间，实际运行指纹未核实。随后经历VS修复半幅紫色、128拍读稳定13fps；2026-10-15短曝光文件获用户CAP/COPY30、UF/ERR/DROP0且稳定的反馈，随后GBRG2失败；最新PROBE01右图BGGR3颜色正确但偏暗，正式BGGR+gamma颜色已获确认，图像质量待优化。<a href="docs/camera_hardware_fix.md">完整历史</a>保留，<a href="build/active_hardware_image.json">active marker</a>记录当前用户报告。COPY不是CNN，神经推理>15fps未验证。</p></section>
<section id="modules"><h2>模块、全部接口和代码解释</h2><label for="module-search">搜索模块、端口、状态或源码</label><div class="toolbar"><input id="module-search" type="search" placeholder="例如：m_axi_rresp、frame_id、FIFO、C_ABORT"><button id="clear-search" type="button">清空搜索</button><button id="expand-all" type="button">展开匹配模块</button><button id="collapse-all" type="button">收起全部</button></div><p id="match-count" class="muted"></p><p id="no-matches" class="empty" hidden>没有匹配模块，试试其他端口或状态名。</p></section>
{''.join(bodies)}</main></div><footer>由 scripts/build_docs.py 从当前源码与记录生成 · {datetime.now().strftime('%Y-%m-%d %H:%M')} · 离线打开，无网络依赖</footer><script>{JS}</script></body></html>"""
    (ROOT / "architecture.html").write_text(output, encoding="utf-8")
    md_rows = "\n".join("|0x"+r[0]+"|"+"|".join(r[1:])+"|" for r in REGISTERS)
    (ROOT / "docs" / "interface_contract.md").write_text(INTERFACE_MD+"|Offset|名称|权限|行为|\n|---|---|---|---|\n"+md_rows+"\n",encoding="utf-8")
    (ROOT / "README.md").write_text("""# Ti60 赛题一视频平台

当前阶段完成你负责的视频基础平台：摄像头RAW10预处理、RGB流、CDC、DDR DMA、帧所有权和720p显示。队友的Sapphire/RISC-V和CNN尚未接入，默认使用COPY占位；不能据此宣称完成神经风格迁移赛题。

**本次GitHub模块交付入口：[三模块交付说明](docs/module_delivery.md)**。包含采集/DDR/显示职责、左原图/右黑布局、RISC-V与CNN接入位置、2026-10-20本地验证摘要及未上传的Efinity/IP/仿真依赖说明。

最新新增[按键白平衡校准](docs/wb_calibration.md)：KEY2对白纸采四个新完整帧、在摄像头SOF锁存增益，KEY3恢复默认，KEY1保留对比度。底部标记WB CAL 01；新版候选见[构建回执](build/wb_calibration_receipt.json)，实板待测。重建需显式运行`python scripts/prepare_efinity.py --contrast-probe --wb-calibration`。

- [独立采集模块](docs/camera_capture.md)：`style_camera_capture`封装RAW10预处理、Gamma、图像/取消CDC和计数，统一core域RGB888接口。MIPI接收IP、I²C和DDR DMA独立保留；封装版未上板，构建状态见`build/camera_capture_receipt.json`。顶层连接由`scripts/camera_capture_shell.py`维护，原图像参数保持。当前带全部诊断功能的重建命令仍为`python scripts/prepare_efinity.py --contrast-probe --wb-calibration --performance-monitor`。
- [DDR/显示独立模块及RISC-V接线](docs/ddr_display_modules.md)：`style_ddr_framebuffer`提供APB/IRQ、CNN流口、AXI128和帧管理；`style_hdmi_display`完成显示FIFO/时序/诊断/HDMI编码。默认左原图、右图像区黑色预留CNN；`--show-result`解除预留，未接CNN时右图仍是COPY。模块版构建见`build/ddr_display_modules_receipt.json`，实板待测。

- [被动性能监测与延迟说明](architecture.html#performance-monitor)：同帧CAP/JOB/QUEUE/TOTAL、平台AXI流量/等待及FIFO高水位，详见0x100..17C寄存器表。启用命令为`python scripts/prepare_efinity.py --contrast-probe --wb-calibration --performance-monitor`。独立候选为`build/style_video_performance.bit`，实板待验收。
- [可离线打开的架构和代码解释](architecture.html)：点击模块、搜索全部实际端口/源码、查看实现与恢复逻辑。
- [队友接口契约与APB寄存器](docs/interface_contract.md)
- [摄像头预处理](docs/camera.md)、[DMA与帧池](docs/memory.md)、[显示与OSD](docs/display.md)
- [首次硬件问题与高极性修复记录](docs/camera_hardware_fix.md)

## Efinity IDE

```powershell
python scripts/run_checks.py
python scripts/build_efinity.py --build
python scripts/build_docs.py
```

稳定bit可直接交给Programmer，无需重新综合。IDE再次综合推荐打开当次完整构建快照XML，入口见本文末尾的efinity_receipt.project链接。若用主`efinity/style_video.xml`开发，先关闭旧工程，再prepare并重开生成XML，核对Design Files包含style_camera_reg_rom与style_camera_reg_set；不要在旧已打开的缓存工程里直接Compile。IDE曾将76项旧源清单保存回主XML，使新增模块unknown；225018构建快照补齐2项到78项并检查源路径存在、清单无重复。关闭也可能保存旧清单，故必须先关闭、再prepare、再重开。主prepare本身按全部项目RTL完整生成清单。

器件Ti60F225I3，SystemVerilog语言sv_09，物理顶层`style_ti60_top`。Efinity工具基线2026.1.132.4.5，复用官方V4/J5物理配置；像素时钟74.25MHz、串化371.25MHz。必须检查当次setup/hold与错误；独立工程保留官方加密IP和配置，不更改原厂例程。

实际综合CSI RTL是原已验证5.15版本（HS_BYTECLK参数70），同包settings.json记录5.16/50。保持源版本，不在IP Manager自动升级或重生成。未使用的fabric USER1调试JTAG已移除，下载器硬件JTAG不变。

## 默认数据与分工

处理流640×480 RGB888，显示两张640×480 1:1并排于720p画面。DDR采用RGBX8888 LE字0x00RRGGBB，stride2560，每帧1,228,800字节；4输入槽+2结果槽，每槽2MiB，基址0x01000000。输入保留至配对显示结束。外部DDR为AXI128/ID4；图像读写DMA由平台提供。

Efinix原生CSI输出VS/HS高有效：VS上升沿开始帧、下降沿结束帧；默认和物理顶层显式VS_ACTIVE=1，物理s_valid=CSI DE&HS，与已验证官方frame_buffer一致。低极性通用输入仍可显式设置0。原低极性RTL错误已确认；第一轮VS修复bit曾出现下半图紫色，当前128拍读候选已获用户短时画面稳定确认。

控制接口是APB3 byte offsets，未来SoC寄存器基址由RISC-V队友分配；软件目录仍为原有占位，不包含可运行驱动。卷积队友需接RGB流式整网模块，若交付AXI主机需先重定义接入方案。当前FORCE_BYPASS=1，CONTROL复位enable/auto/bypass都开启；上板前使用COPY连通摄像头、DDR和显示。

采集DMA启动要求DDR校准就绪、摄像头164个ROM事务完成并经核心域同步、abort队列正常。`config_done`只表示命令序列完成；当前没有NACK或ID检查，不能证明传感器应答、型号和寄存器值正确。后续RISC-V接管I²C时必须选择单一主机。

## 验证状态

当次行为仿真与Efinity结果分别保存build/validation_receipt.json和build/efinity_receipt.json。历史包括无图、半幅紫色、13fps、短曝光30fps偏色、GBRG2实物失败；最新用户确认COLOR PROBE01标记及RGB白灰条正确，右BGGR3颜色正确但暗，CAP/COPY30、UF/ERR/DROP0。当前摄像头/ROI/方向的有效Bayer3已获观察，正式gamma版本颜色已获确认，图像质量待优化。没有精确观察时长或运行bit独立读回，COPY不是CNN，神经推理>15fps未验证。

历史实物诊断：[style_video_color_probe.bit](build/style_video_color_probe.bit)的版本标记和RGB白灰条正确，右BGGR3颜色正确但偏暗，CAP/COPY30、UF/ERR/DROP0；依据[probe回执](build/color_probe_receipt.json)及[active marker](build/active_hardware_image.json)，有效Bayer3针对当前摄像头/ROI/方向已获观察。正式候选[style_video_bggr_gamma.bit](build/style_video_bggr_gamma.bit)与[候选回执](build/bggr_gamma_receipt.json)另记，颜色已获确认，亮度和锐度仍未验收。历史13fps、短曝光30fps、GBRG2失败和早期半幅紫色记录均保留；用户观察不等于长期稳定性、DDR实测吞吐或电气签核。

短曝光恢复同模式v1三个曝光字后已获30fps反馈，曝光和DDR不再改变。原BGGR3+gamma22基线去掉probe/右图交换/黄框/标准条，camera_preprocess→style_rgb_gamma→camera_cdc，三通道使用同一离线256×8 LUT：round(255*(x/255)^(1/2.2))。没有运行浮点、白平衡或完整ISP；官方2P2.mem为x^2.2压暗，不能复用。该gamma22基线的DDR和未来CNN输入是近似gamma2.2编码RGB888；当前gamma18候选则为近似gamma1.8编码，非精确sRGB；需要线性输入时用--tone-profile linear。

历史GBRG2文件红变绿、蓝变黑、绿变粉紫，颜色失败，见[原回执](build/camera_color_phase_receipt.json)。随后COLOR PROBE01以左RGGB0/右BGGR3完成实物对照，右图正确但暗；诊断本身左图不是正式正确颜色输出，也没有提供RAW四位置数值。操作和历史见[docs/color_probe.md](docs/color_probe.md)。正式BGGR+gamma已获颜色正确反馈，但模糊和低对比仍待排查，不能写成图像质量全面验收。

gamma18文件为[style_video_bggr_gamma18.bit](build/style_video_bggr_gamma18.bit)，实物反馈仍明显发灰且完全遮镜也灰，CAP/COPY30、UF/ERR/DROP0，见[gamma18回执](build/bggr_gamma18_receipt.json)；原gamma22文件及实物记录保留。style_rgb_gamma支持GAMMA_TENTHS=18/22，普通默认18，ENABLE=0透传。1.8减弱中暗部提亮，未新增独立对比度、黑电平或锐化；不预先保证灰感改善。用户已确认镜头可手动对焦，尚无调焦后清晰度结论。

旧[style_video_contrast_probe.bit](build/style_video_contrast_probe.bit)已获标记/KEY1正常、CAP/COPY30及零错误反馈；遮镜A041/B042/C042/D043、右1.50较自然，见[contrast_probe回执](build/contrast_probe_receipt.json)。使用`--contrast-probe`、Bayer3和gamma18准备，与`--color-probe`互斥。左图保留基线，右图KEY1循环五档对比度（默认1.50倍，20ms消抖、帧边界应用）；RAW A/B/C/D均值用于遮镜观察，现已测得暗场65/66/66/67，但该显示模块不自动BLC。仅显示端改变，不回写DDR/CNN输入；不保证根治灰感，详见[诊断说明](docs/color_probe.md)。

当前实物文件[style_video_black_level.bit](build/style_video_black_level.bit)已获遮镜纯黑、RIGHT1.00最自然、CAP/COPY30及UF/ERR/DROP0反馈，状态见[黑位回执](build/black_level_receipt.json)。用户仍报告轻微偏绿、魔方大致正确，白平衡和清晰度未验收；后续白纸RAW09C/0F5/0F5/0A0已收到；该BLC历史位流尚无WB，新固定WB候选待实屏。物理2×2 RAW10四位置固定扣除实测65/66/66/67并钳位0，再Debayer/缩小/gamma18；DDR和CNN输入数值随之改变。复用CONTRAST PROBE01标题，不能据标记唯一识别新版，需选择新文件；原始RAW统计在BLC前，遮镜仍可显示041..043。复现该已测BLC命令为`python scripts/prepare_efinity.py --camera-profile short_exposure --bayer-pattern 3 --tone-profile gamma18 --black-level-profile measured --white-balance-profile none --contrast-probe --contrast-initial-level 2`；需要复现旧gamma18/22或旧contrast时显式`--black-level-profile none`。普通默认measured仅配short_exposure/Bayer3，color-probe强制none。无白点拉伸、曝光/白平衡更改；已测位流启动1.50，用户改选1.00；当前WB版本物理启动默认1.00，尚未实板通过，通用模块默认仍1.50。

新候选为[style_video_white_balance.bit](build/style_video_white_balance.bit)，见[固定WB回执](build/white_balance_receipt.json)，已实测不发绿及30fps，室外天空微红待诊断。白纸RAW156/245/245/160扣黑后RGB93/179/91，按当前光照固定Q8增益493/256/504，在G均值后、RGB8/gamma前21bit乘加舍入饱和；均值预测RGB10各179、RGB8各44，不保证每个像素相等。物理启动对比度1.00、KEY1保留，RAW统计仍在BLC/WB前。它不是AWB或完整ISP，R/B增益可能放大噪声或造成高光饱和；DDR/CNN数值语义变为扣黑+固定WB+gamma18。当前准备：`python scripts/prepare_efinity.py --camera-profile short_exposure --bayer-pattern 3 --tone-profile gamma18 --black-level-profile measured --white-balance-profile measured --contrast-probe --contrast-initial-level 0`。measured WB仅支持当前BGGR3/短曝光/measured BLC；旧BLC须WB none和初档2，旧无BLC诊断默认WB none/初档2。

普通gamma18准备：`python scripts/prepare_efinity.py --camera-profile short_exposure --bayer-pattern 3 --tone-profile gamma18`，再回归及`python scripts/build_efinity.py --build`。当前正常默认Bayer3/gamma18，原gamma22需显式选择；诊断需显式`--bayer-pattern 0 --color-probe`，未给tone时默认linear，color-probe+gamma18或gamma22会被拒绝。正常linear可用--tone-profile linear关闭gamma，位宽/握手/字节序不变但亮度数值语义不同，队友输入须匹配。实际源配置见source_receipt.json的tone_profile和camera_rgb_encoding；位流不随源码准备自动更新，必须核对当次回执身份。

性能证据分两类：原16拍读、首R等待48周期的紧凑640×48实验实际复现了中途欠载和剩余粉色像素，其回执明确不通过；全640×480双图、720p60、30fps输入的首R等待96周期/读128拍测试按当前性能回执判断。另一个持续密集COPY的无限读请求模型在96周期/128拍时平均56.728M像素/秒，低于双图显示在图像区域期间所需57.6M像素/秒，仍是带宽边界失败，不能把它写成通过。正常帧调度负载与持续无限请求假设不同，均不能替代实际DDR带宽和显示验收。

显示欠载后核心立即abort/drain旧读，FIFO清空与帧释放仍等安全窗口，避免本帧停止消费误触发读DMA看门狗。DROP_COUNT和ERROR_COUNT为阶段事件合计，可能多次记录同一坏帧，不是按frame_id去重的唯一坏帧数。

## 修改与重新生成

`rtl/style_platform_core.sv`由`scripts/generate_core.py`生成，核心逻辑应维护生成器；修改后先运行`python scripts/generate_core.py`，再运行仿真及Efinity构建。`rtl/style_ti60_top.v`、`rtl/style_camera_initializer.v`由`scripts/prepare_efinity.py`生成；物理PHY宏参数来自已验证参考包，物理封装/时钟/peri/SDC的定制维护在准备脚本中。不直接批改厂商加密IP或outflow。

README、architecture.html和接口契约由build_docs.py生成；调整说明时维护生成器，再按最新源码和收据刷新。重新生成代码后必须重新验证相应快照，旧bitstream不自动覆盖新源码的验证状态。

"""+readme_implementation_summary()+"\n\n"+efinity_project_summary()+"\n",encoding="utf-8")
    receipt = {"modules": len(modules), "ports": sum(len(m["ports"]) for m in modules),
               "module_names": [m["name"] for m in modules], "all_source_paths_exist": all((ROOT/m["path"]).exists() for m in modules),
               "source_sha256": {m["path"]: hashlib.sha256((ROOT/m["path"]).read_bytes()).hexdigest() for m in modules},
               "external_dependencies": False, "rtl_modified": False}
    out = ROOT / "build" / "docs"
    out.mkdir(parents=True,exist_ok=True)
    (out / "framework.svg").write_text(diagram(names),encoding="utf-8")
    receipt.update(validate_page(output,names))
    (out / "generation_receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding="utf-8")
    return receipt

def validate_page(source: str, expected_names: set[str]) -> dict:
    class PageParser(HTMLParser):
        def __init__(self):
            super().__init__();self.ids=set();self.duplicates=[];self.modules=[];self.links=[];self.external=[]
        def handle_starttag(self,tag,attrs):
            data=dict(attrs)
            if "id" in data:
                if data["id"] in self.ids:self.duplicates.append(data["id"])
                self.ids.add(data["id"])
            if tag=="details" and data.get("class")=="module":
                self.modules.append({"id":data["id"],"search":data["data-search"]})
            if tag=="a":self.links.append(data)
            if (tag=="script" and "src" in data) or (tag=="link" and "href" in data):self.external.append(data)
    parsed=PageParser();parsed.feed(source)
    assert not parsed.duplicates,parsed.duplicates
    assert {m["id"] for m in parsed.modules}==expected_names
    assert all(link.get("href","")[1:] in parsed.ids for link in parsed.links if link.get("href","").startswith("#"))
    assert not parsed.external
    assert all(i in parsed.ids for i in ["module-search","expand-all","collapse-all","clear-search","match-count","no-matches"])
    # Mock DOM executes the actual page script without invoking any browser.
    fixture={"modules":parsed.modules,"links":[link for link in parsed.links if "data-module" in link]}
    mock_js="""const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('../../architecture.html','utf8');
const fixture=FIXTURE;
function element(id,classes=[]){return {id,value:'',hidden:false,open:false,textContent:'',dataset:{},handlers:{},classList:{contains:c=>classes.includes(c)},addEventListener(type,fn){this.handlers[type]=fn},focus(){this.focused=true},scrollIntoView(){this.scrolled=true}}}
const elements=new Map(),cards=fixture.modules.map(m=>{const e=element(m.id,['module']);e.dataset.search=m.search;elements.set(e.id,e);return e});
for(const id of ['module-search','expand-all','collapse-all','clear-search','match-count','no-matches'])elements.set(id,element(id));
const links=fixture.links.map(l=>{const e=element('');e.dataset.module=l['data-module'];return e});
const document={getElementById:id=>elements.get(id),querySelectorAll:selector=>selector==='details.module'?cards:selector==='aside a[data-module]'?links.filter((_,i)=>i<fixture.modules.length):selector==='a[data-module]'?links:[]};
const window={history:{replaceState(){}}};
vm.runInNewContext(html.match(/<script>([\\s\\S]*?)<\\/script>/)[1],{document,window});
assert.equal(elements.get('match-count').textContent,cards.length+' / '+cards.length+' 个模块');
const search=elements.get('module-search');search.value='m_axi_rresp';search.handlers.input();
const matched=cards.filter(c=>!c.hidden);assert(matched.length>0&&matched.length<cards.length);
elements.get('expand-all').handlers.click();assert(matched.every(c=>c.open));
elements.get('collapse-all').handlers.click();assert(cards.every(c=>!c.open));
search.value='no_such_module_9285';search.handlers.input();assert(cards.every(c=>c.hidden));assert.equal(elements.get('no-matches').hidden,false);
elements.get('clear-search').handlers.click();assert(cards.every(c=>!c.hidden));assert(search.focused);
search.value='no_such_module_9285';search.handlers.input();
const target=links.find(l=>l.dataset.module==='style_display_sink');target.handlers.click({preventDefault(){}});
assert(elements.get('style_display_sink').open);assert(elements.get('style_display_sink').scrolled);assert(cards.every(c=>!c.hidden));
console.log('PASS controls: search, empty state, expand/collapse, clear, click-to-open all work');
""".replace("FIXTURE",json.dumps(fixture,ensure_ascii=False))
    (ROOT/"build"/"docs"/"control_check.js").write_text(mock_js,encoding="utf-8")
    return {"unique_ids":True,"module_coverage_complete":True,"anchor_links_valid":True,"no_external_scripts_or_styles":True,"mock_dom_script":"build/docs/control_check.js"}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(build(),ensure_ascii=False,indent=2))
