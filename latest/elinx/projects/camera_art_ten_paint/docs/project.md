# 十风格工程：模块、接口与验证

## 视频主链路

摄像头与原V4/SC431HAI签核配置相同：受控复位、开漏I²C、ID/尺寸/VTS检查和失败关闭；D-PHY公开PPI经FIFO进入UI域包解析，保留ECC/CRC/尺寸/帧完整性判据。Bayer预处理把1920×1080 RAW转换为1280×720 RGB565，低16位为每拍较左偶像素，高16位为下一像素。

三个原画DDR槽位于4/6/8MiB，三个输出槽位于0/2/10MiB。采集完整好EOF与最后写响应后才发布。CPU领取完整源帧、加载目标模型并启动加速器；输出最后B响应后提交，显示先排空旧读事务和像素FIFO，再在安全消隐确认换帧。RAW、STYLE、SPLIT元数据与bank关联，S显示前台风格，不把尚未完成的请求标为已显示。

`full_kernel.sv`、DW/PW/参数银行、异步引擎/DMA保持原C6数值数学。1×1 stem→四组DW3×3/PW1×1（d1/2/4/8）→有符号RGB残差，RF31；四条中央320列、两侧16列halo，每层全局reflect101。所有逻辑特征层均720p。十组参数在运行时复用同一套运算和行缓存，额外开销主要是ROM。

时钟保持UI/CPU100MHz、CNN166.667MHz、DDR PHY400MHz、HDMI像素74.25MHz。显示是720p60刷新，采集FPS、神经完成FPS与重复显示分别计数。旧CNN/DMA39.084974模型fps不是新整机实板30fps证据。

## 十模型控制

`video_control_apb_fast.sv`允许本地槽0–9，保留编号回默认0。ROM移到0x4000–0x5CBF（相对基址0xF8100000），1840个32位字，避免与0x2000–0x3FFC的8KB手势RGB快照重叠。每模型有效712B、对齐736B，加载216项。权重地址/通道/移位合法性与最后真实ACK核验保持；加载目标与用户后续请求分离锁存，忙中不写当前权重。

`main.c`继续实际RISC-V控制I²C、加载、START及PLIC。原Sapphire IP已具备M扩展；本工程编译RV32IM并在启摄像头前检查misa和乘除自检，不升级或改CPU IP。编译与链接仍受32KB总RAM和至少2KB栈保护。主循环先启动符合条件的视频作业，再服务手势/看门狗，避免只在busy时服务造成长期停采后的取样死等。

## 按键、显示与跨域

`style_keys47.sv`同步并消抖四个3.3V低有效输入，普通KEY0切RAW/STYLE/SPLIT，KEY1/2循环十槽，KEY3每次消抖按下翻转ui_visible，长按只翻一次，不复位。KEY1＋KEY2长按约1秒只发一次学习事件，释放后重武装，并切回RAW。学习时KEY0发录入事件，KEY1/2选择录入标签。

`fps_snapshot.sv`把C/I、G/P或L/A、前台S放进同一个稳定toggle邮箱，直到pixel ACK前数据不变，仅在消隐接收。学习标志与候选编码通过同一邮箱，不能把多位总线直接跨域。G/L的code0为横杠，code1–10对应数字0–9。所有实体引脚、12Bank、PLL参数和整份peri沿用正确20261012原理图版本；新增功能都在内部逻辑。

## 手势取样、校准与分类

`gesture_snapshot.sv`从原图旁路取ROI x0..639/y40..679，640²每10像素取靠近中心的左偶像素，得到64×64 RGB565。低半字是左样本，无stride padding，CPU读2048个32位词。它不反压摄像头，不增加DDR图像读主口。REQUEST至SOF、4096样本、好EOF才ready；CPU持有时不得覆写，读完多次扫描后才能ACK。模式、按键或学习事件使epoch变化，旧快照和资格无效。

`gesture_calibrated.c`的背景与个人原型只在RAM，背景三帧先补偿整体亮度再估计噪声。保留最大8连通区，5/95亮度分位数规范化，192维无向HOG/灰度/轮廓特征，每类四模板并比较镜像。运行时三张独立快照多数投票，五次同类决定且完整四秒才允许原子风格请求。每张请求年龄仍限制0.6秒，最终读取之后ACK；epoch/seq/ready失效使背景或当前类回滚，禁止半份校准成为有效模型。详细实现和限制见下文。

## APB与CAM7

基址0xF8100000。普通寄存器32位对齐；权重ROM允许CPU byte load，返回包含目标字节的完整词，由CPU选择lane。

| 偏移 | 功能 |
|---|---|
| 0x28 / 0x2C / 0x30 | 请求槽 / 加载目标与身份 / clear、commit、START |
| 0x50 / 0x54 / 0x58 | 参数地址 / 数据 / 确认加载数216 |
| 0x80 / 0x84 / 0x88 | ROI ready-active-pending-enable / seq / epoch |
| 0x8C | 1请求，2释放或取消快照 |
| 0x90 | code[3:0]、P/A[6:4]、blocked7、enabled8、trigger parity9、learning10 |
| 0x94 / 0xA0 | CPU处理UI tick / 累计分析报告数 |
| 0xA4 | reason低byte、classifier=0xFE校准模板、有效code第三byte |
| 0xA8 / 0xAC / 0xB0 | 前景数/噪声阈值；距离/间隔；RGB均值 |
| 0xB4 | 学习toggle0、录入1，sticky事件W1C，事件赢同时clear |
| 0xB8 / 0xBC | 带epoch的风格提交与结果 / epoch token；1接受、2过期、3禁用/学习、4非法ID |
| 0x2000–0x3FFC | 2048个RGB565双样本词，只读 |
| 0x4000–0x5CBF | 十组学习权重ROM，只读 |

CAM7仍115200/8N1、33个HEX32字段共304B。前24项保留包/帧/引擎诊断，24–31为快照seq、CPU报告、reason/classifier/code、前景/噪声阈值、距离/间隔、RGB均值、CPU周期、epoch/sample/ready。mode字段32低位：raw0、engine_raw1、loaded[5:2]、requested[9:6]、front_raw10、display[12:11]、front_mode[14:13]、job_mode[16:15]、front_style[20:17]、CPU状态[31:21]。

原因90表示尚未录全、91等空背景、92录入准备或进行、93样本被拒绝；80–85是禁用、epoch、过期、间隙、读中失效、重复源帧，86为原子风格提交拒绝。校准数据是最近观察状态，多个APB字分次更新，不保证与seq是同次报告原子提交；四秒资格不依赖这些诊断字段。

## 本轮验证与实现细节

## 本轮重训与手势增强（2026-11-02）

本目录独立于旧camera_art_ten_ui，旧bit保留。模块接口与实现细节如下，与当前README和RTL对应。

gesture_snapshot.sv默认ROI_X=0、ROI_Y=40、STEP=10、SIDE=64；框640×640而存储仍2048×32bit。每拍两个RGB565像素，取左偶像素，横向偏移4而非5，纵向偏移5，即(4+10n,45+10m)。x/y相位小计数器与SOF、行尾同步，避免对11位像素坐标做动态模10；640框全4096位置及真实EFX RAM回归通过。完整好帧/单CPU所有权、0x2000..3FFC地址范围、最终读后ACK与epoch取消不变。

gesture_calibrated.c背景采集先补偿整体亮度偏移，再估计噪声；二值邻域清理后以标号/union-find保留最大8连通区，利用已有canonical/histogram空间，不加帧RAM。5/95亮度分位数抑制孤立亮斑。192特征=64无向HOG＋64灰度均值＋64轮廓密度，权重1/0.5/2归一化距离；同时比较镜像，十类每类四模板，仍共7680B原型存储。距离阈值和相对类别间隔拒绝不明确结果，数字0与无手严格分开。

运行时约333ms取一张新快照，三张多数投票后才提交给原有四秒资格器；三种不同或不明确则不确认。五次同类投票且完整4秒才BC/B8原子请求，单帧误判不会直接改G。学习250ms请求间隔，每类四新帧；源龄0.6秒/报告看门狗1.6秒/独立seen_seq/失效模板回滚仍覆盖。RAW自动STYLE、SPLIT保持、KEY3 UI开关、busy目标锁存和同源安全换帧保持。

新painterly27500检查点SHA256 7250b683772fdd9c3756f9f062ce639aadfcbfbc49eb64e6ac2e15588e489e86已实际进入当前十组NPZ、ROM和工程，50完整720p软件案例及40极小整数一致；最大保守界239482、0裁剪，层数/通道/尺寸/事务不改。当前硬件新权重十模型RTL/EFX、DMA/背压/异常恢复逐值通过，完整slot0 SPLIT921600像素/2558528 UI周期，模型39.084974fps不是实板FPS。

独立Python oracle与实际C比较26496特征值/565248规范化像素完全一致；受控干扰测试旧29/50正确、新48/50、均0误认，仅是合成模板条件，未实测真人。真实生产机器码58 ROI（三背景＋40模板＋15取样）经过4.08001313秒窗口接受slot0并重载，共2376参数写入；RISC-V真实Sapphire另验证当前生产固件十槽/2160参数/PLIC。独立Sapphire时延程序显式准备其它类原型，单合成握拳3209746周期/32.09746ms，仅作时延，不冒充真实录入/最坏耗时证明。

固件10588B，BSS end0xF90071AC，栈余3668B。seed0最终CNN -0.175ns失败已归档；seed1/beneficial_skew合法布线优化后最终setup/hold +0.108/+0.026ns，D-PHY唯一二级链最小+13.391ns。外部时钟/79脚/12Bank/peri/电平/DDR/MIPI均与保留版相同，精确23/166/87/8 CDC及同次源码、模型、固件、回执、bit共同签核后交付。未上板，真实准确率、FPS、电源温升仍待确认。

最终bit 3193065B，SHA256 `75766d7cdd66154d2d8da1db7a800ed49f38864ae52316c97b2dadaab959a2de`；signoff.json与fresh final_review.json须均PASS。未代为上板或写Flash。
