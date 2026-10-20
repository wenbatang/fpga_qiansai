# COLOR PROBE 01：实际颜色排列诊断

历史诊断实物结论：用户确认COLOR PROBE01标记和红/绿/蓝/白/灰条正确，右侧BGGR3的颜色正确但偏暗，CAP/COPY均30、UF/ERR/DROP均0。该对照为当前摄像头/ROI/方向的有效Bayer3提供观察证据；没有提供A/B/C/D数值或精确观察时长，运行中bit身份未独立读回。依据 [color_probe_receipt.json](../build/color_probe_receipt.json) 与 [active_hardware_image.json](../build/active_hardware_image.json)，GBRG2失败历史继续保留。

2026-10-15，用户对GBRG候选报告：红色物体显示绿色、蓝色显示黑色、绿色显示粉紫；CAP/COPY均30，UF/ERR/DROP保持0。该候选颜色测试失败，不能当作正确颜色基线。本地综合日志、映射网表和位流SHA都确认候选确实使用BAYER_PATTERN=2，但运行中版本未独立读回。

诊断文件为 `build/style_video_color_probe.bit`。右图颜色已经用户确认，左RGGB0仍是诊断对照；不能把右图通过写成整个正式双图版本已验收。下一步正式候选 `build/style_video_bggr_gamma.bit` 显式BGGR3并增加亮度编码，状态见 `build/bggr_gamma_receipt.json`，颜色已获确认，亮度和锐度仍未验收。原短曝光文件与失败GBRG文件保留。

## 下载后观察

1. 通过Efinity Programmer的JTAG下载诊断文件，摄像头保持J5。
2. 确认屏幕底部出现 `COLOR PROBE 01` 和 `LEFT 0 RIGHT 3`。这只是可视版本标记，不是独立位流读回。
3. 最底部五块参考色从左到右应为红、绿、蓝、白、灰。这些颜色直接在显示端生成，不经过摄像头、DDR或右图红蓝交换。若参考条本身错误，应先检查输出通道或实际下载身份。
4. 左图按RGGB0解释RAW；右图对相同COPY图像仅交换红蓝，等效于BGGR3。观察哪侧的红、绿、蓝物体更接近实际。右侧在此版本是诊断对照，不是神经网络处理。
5. 如两侧仍不明确，用同一个红、绿、蓝物体分别填满图中的黄色小框，保持约1秒，记录底部A/B/C/D四个三位十六进制数。若需要后续白平衡，也记录白纸或灰卡的四个数。颜色区域应均匀，避免反光和过曝。

## 四个读数是什么

统计源RAW的中心128×128区域：x896..1023、y476..603；每种位置4096个10bit样本，分别求均值。黄色框对应缩放后左图x299..341、y332..388，右图横坐标加640。读数范围000..3FF，不预先将它们命名为颜色。

| RAW行列奇偶 | 偶列 | 奇列 |
|---|---|---|
| 偶行 | A | B |
| 奇行 | C | D |

| 参数 | 排列 | A | B | C | D |
|---|---|---|---|---|---|
| 0 | RGGB | R | G | G | B |
| 1 | GRBG | G | R | B | G |
| 2 | GBRG | G | B | R | G |
| 3 | BGGR | B | G | G | R |

用红色和蓝色物体的响应位置判断R、B所在位置，再确定两个G的位置。实际光谱、曝光和物体反射会影响数值，不能只把任意场景中的最大读数机械当作R或B。测量能排除仅凭寄存器窗口推断相位的歧义；颜色相位确认后再处理白平衡和gamma。

读数来自最近完整RAW帧，并非与当前显示前台帧逐帧绑定；等待物体稳定后再记录。`---`表示尚无有效统计或统计FIFO发生过溢出，需要复位后检查。短行、长行、短帧或ROI样本不完整均不发布新均值；诊断不会更改主链路的CAP/COPY/UF/ERR/DROP统计。

## 实现与重新构建

`style_cfa_stats`旁路观察CSI，在真实VS结束后发布40bit整组均值。`color_stats_cdc`异步FIFO把整组数据转到HDMI像素域，y640边界锁存一次，保证底部整组文字稳定。`style_color_probe_overlay`在视频端组合覆盖文字、边框、参考条及右图通道交换，HS/VS/DE保持原连接。

诊断仅在显式开启时加入物理顶层：

```powershell
python scripts/prepare_efinity.py --camera-profile short_exposure --bayer-pattern 0 --tone-profile linear --color-probe
python scripts/run_checks.py
python scripts/build_efinity.py --build
```

正常版本省略--color-probe，物理默认Bayer3，通用预处理仍默认RGGB0。probe要求显式--bayer-pattern 0，防止标签与实际不符；未指定tone时诊断默认linear，显式color-probe+gamma18或gamma22会被拒绝。编译使用当次回执project完整快照，源数量和补入数以回执动态记录为准，不把历史76/78项当成当前完整清单。

本次不修改传感器曝光/增益、CSI IP、DDR参数、缓冲管理或HDMI刷新率，也不加入白平衡或gamma校准。COPY仍是CNN接入口的占位实现。

## 从诊断到正式BGGR+亮度候选

正式候选去掉probe、右侧R/B交换、黄色框、CFA统计覆盖层和标准参考条，在camera_preprocess RGB输出到camera_cdc入包之间加入纯组合style_rgb_gamma，原valid/ready/帧标志保持。两侧恢复正常原图/COPY显示，曝光和DDR不改。

gamma22 LUT离线生成256个8位值，公式为 `y=floor(255*(x/255)^(1/2.2)+0.5)`，同一函数独立作用于R/G/B；硬件不做浮点/幂运算，不加流水拍。ENABLE=0/--tone-profile linear为24位透传。官方2P2.mem采用x^2.2压暗，方向相反，不能直接复用。本候选是显示编码近似，不是精确sRGB、白平衡或完整ISP，已获颜色正确反馈，模糊和低对比仍待排查。

正常准备可显式 `python scripts/prepare_efinity.py --camera-profile short_exposure --bayer-pattern 3 --tone-profile gamma22 --black-level-profile none`复现旧gamma22基线，再回归并构建。当前正常未指定tone时默认gamma18，重建该基线须显式gamma22；如队友需要线性输入，选择--tone-profile linear。gamma在CDC前，意味着DDR及未来CNN输入的亮度数值语义也改变，虽然RGB888位宽、字节序和握手保持。当前实际tone配置见source_receipt.json。


正常BGGR+gamma版本后续已获用户“颜色没问题”的反馈，但图像模糊、低对比仍待优化；照片显示CAP/COPY30、UF/ERR/DROP0，仅代表拍摄瞬间。镜头距魔方约10cm，尚无远距焦点对比。亮度与锐度没有全面验收，运行bit身份未独立读回。详见[camera.md](camera.md)与[bggr_gamma_receipt.json](../build/bggr_gamma_receipt.json)。


## gamma18实物反馈：仍明显发灰，遮镜也灰

针对原gamma22画面偏灰、低对比，本轮仅把Gamma从2.2减为1.8；BGGR3、曝光、DDR和HDMI保持。新候选名为[style_video_bggr_gamma18.bit](../build/style_video_bggr_gamma18.bit)，当次构建和实物状态以[bggr_gamma18_receipt.json](../build/bggr_gamma18_receipt.json)为准。原style_video_bggr_gamma.bit及其颜色正确但灰/糊的反馈保留，不能把旧版反馈当成新候选通过。

style_rgb_gamma新增GAMMA_TENTHS=18（支持18/22），ENABLE=0仍透传，LUT按`floor(255*(x/255)^(10/GAMMA_TENTHS)+0.5)`离线生成。prepare支持`--tone-profile linear/gamma18/gamma22`，普通默认gamma18，color-probe仍须Bayer0和linear。RGB位宽、顺序与握手不变，DDR/COPY及未来CNN的数值语义随tone变化，队友需匹配训练输入；这是构建选项，不是在线寄存器开关。

gamma18比gamma22少提升中暗部，仍是逐像素组合映射，无新增流水拍；没有实现独立对比度、FPGA黑电平校准或锐化，用户已反馈仍明显发灰，CAP/COPY30、UF/ERR/DROP0，完全遮镜后仍明显灰；尚无数值黑位测量。用户已确认手动对焦镜头，尚未给出调焦后的清晰度结论；不将Gamma调节当作失焦修复。


## CONTRAST PROBE01实物：暗场读数与1.50倍偏好

gamma18实物反馈仍灰，完全遮镜也明显灰；这说明需要测量暗场，但尚未确定灰位来自传感器、黑电平、显示映射或其他环节。新诊断保持gamma18摄像头与DDR内容，左图是基线，仅右图x640..1279、y120..599在显示端调节对比度。KEY1依次循环1.00/1.25/1.50/1.75/2.00倍，默认1.50倍；20ms消抖、帧边界生效。映射不回写DDR，也不改变未来CNN输入。

底部出现CONTRAST PROBE01、RAW A/B/C/D均值、档位/KEY1提示和参考色条。复用中心128×128区的四奇偶位置统计，只有完整合法帧发布40bit整组结果，经异步FIFO和像素域整组锁存；并非与显示前台逐帧绑定。请完全遮镜、等待读数稳定后记录A/B/C/D，再打开镜头比较各档和左图。本次遮镜测得65/66/66/67，成为后续固定黑位候选的依据；旧诊断本身没有自动BLC、锐化或CNN处理。

使用`python scripts/prepare_efinity.py --camera-profile short_exposure --bayer-pattern 3 --tone-profile gamma18 --black-level-profile none --contrast-probe`复现旧未扣黑诊断；它与`--color-probe`互斥并要求Bayer3/gamma18，普通版本仍默认gamma18，旧color-probe要求Bayer0/linear。候选名为[style_video_contrast_probe.bit](../build/style_video_contrast_probe.bit)，完成状态见[contrast_probe_receipt.json](../build/contrast_probe_receipt.json)。原gamma18/22位流和实物历史保留；该诊断已获用户标记/KEY1正常，CAP/COPY30、UF/ERR/DROP0；遮镜A041/B042/C042/D043，右侧1.50倍较自然。正式画质仍没有通过验收。

模块`style_contrast_probe`的接口为：输入`clk/rst_n/key1_n`、`x[15:0]/y[15:0]`、`input_rgb[23:0]`、`cfa_means[39:0]`、`sample_valid`；输出组合`rgb[23:0]`与帧内稳定`level[2:0]`。参数`DEBOUNCE_CYCLES=1485000`对应74.25MHz下20ms，`INITIAL_LEVEL=2`对应1.50倍。KEY1低有效、2FF同步，稳定按下才循环请求档位，释放也消抖，长按不重复；当前档位仅在x=y=0应用，同一拍新按下可到下一帧生效。

精确数值公式为`clip[0,255](floor(((code-128)*(4+level)+514)/4))`，level0严格透传；13bit有符号中间值、算术右移、舍入后饱和。它围绕显示码值128拉开差异，增大档位会将部分暗/亮细节压到0/255，不等于传感器黑位校正。RGB逐通道组合映射、无新增像素延迟。A/B/C/D位于cfa_means低位到高位每项10bit，sample_valid为0时显示`---`。

页脚版本/LEFT BASE位于y644..657，A/B/C/D和RIGHT档位/KEY1位于y664..677；参考条位于y692..711，红/绿/蓝/白/灰各256像素。标准条由显示端直接生成，不受摄像头、DDR或右图档位影响。


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
