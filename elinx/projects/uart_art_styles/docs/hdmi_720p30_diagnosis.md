# 720p30「输入不支持」排查（2026-10-22）

用户已在 Ti60 V4 运行 UART＋HDMI 版，显示器持续提示输入不支持。没有取得实测 HDMI 波形、EDID 或完整 UART END ACK，因此目前不能确认唯一根因，也不能宣称已经实屏修复。

## 已确认的代码事实

- 原发布版 `build/720p/` 的像素时钟配置 74.25 MHz、串化半速时钟 371.25 MHz，行总周期 3300、场总行数 750，确实为 1280×720p30。不是误配为 60 Hz。
- 原 `tmds_efx.sv` 仅做 DVI 式视频 TMDS 编码，没有 HDMI 数据岛和 AVI InfoFrame。接口名叫 HDMI 不等同于发送了 HDMI 格式声明。V7 则含 AVI／辅助包发送端。
- 原顶层把 `!calibrated` 接入像素域和串化器复位。DDR 未校准时，同步信号也被保持复位；不能用「没有正常 HDMI 输出」单独判断显示器兼容性。
- 原引脚、Bank、电平、DDR 参数和已签核 bit 未修改。没有访问串口／JTAG、下载或固化。

## 独立诊断配置

目录 `build/720p30_diag/`，保持 **1280×720 输入／CNN、720p30 输出**、2 Mbps UART 和四组学习参数。

1. 在所有 PLL 锁定后，像素域同步释放复位，暂不等待 DDR 校准；UART、CNN、DMA 继续等 DDR 校准，不能提前访问存储。
2. 没有已提交前台图像时输出八色竖彩条。传图完成、最后 AXI B 响应和安全消隐提交后，显示风格图；源图和输出所有权不改变。
3. 通过公开端口复用 demo10 V7 的 HDMI 发送模块，指定 RGB／VIC 62。原厂受保护模块和依赖逐字节复制到本项目本地 `vendor/hdmi_v7/`，保留声明；没有解密、改 demo 或升级 IP。
4. 所有 PLL 失锁仍复位 DDR／UI／像素域，按键复位和停钟保护保留。没有改变实际 66 脚、电平、LVDS 驱动配置或 PLL 参数。

已实际完成 Efinity 2026.1.132／I3 综合、接口、布局布线和配置生成，`signoff.json=PASS`。RAM10 **223/256**，DSP **144/160**，XLR **27241/60800**；最小 setup **+0.449 ns**、hold **+0.029 ns**。66 实际脚／12 Bank 与原签核版一致，12 个原生 UART／复位同步 FF 属性及 116 条 Gray 路径约束复核通过，没有整组异步时钟切断或放宽时钟。

- [本次诊断 bit](../build/720p30_diag/outflow/ti60_style.bit)
- [工程入口](../build/720p30_diag/ti60_style.xml) · [签核](../build/720p30_diag/signoff.json) · [最终旧版保护复核](../build/720p30_diag/final_review.json)
- SHA256：`bc4ddc979570d54dc6ecededd9962f8747359d542b8186687cced22686f8d62e`。

旧七套发布的源码／配置／报告／bit 指纹全部保持一致。保留原 HDMI 邻近耦合警告、V7 仿真中的 4 项受保护端口位宽及 2 项未驱动内部线警告；没有为了消除警告改电平、解密或修改原厂 IP。当前验证范围不等于实板接受或 HDMI 合规认证。停止的 `build/720p60/` 实验不是可用程序。

## 已运行的仿真

- Questa 10.7c 正常运行 V7 受保护模块，观察其公开 TMDS 并行输出；两完整 3300×750 帧、启动彩条、921600 源像素读出、RGB565／TMDS 解码通过。
- 从真实输出按 HDMI 前导／保护符解析数据岛，33 个 AVI 包的头、VIC 62、RGB 格式、校验和及五组 BCH 通过。输入 DE 不能直接当作发送端 DE：V7 有内部视频缓冲延迟。
- 记录到 V7 公开行同步边沿有 6 次 ±1 像素周期差异，范围 3299–3301，场周期保持 2475000 像素。此行为如实保存在回执中，不据此宣称 HDMI 合规认证或实物锁定。
- 实际诊断顶层／boot／reset 测试通过：未校准时 HDMI 可释放、DDR 客户端仍复位；三 PLL 分别失锁、时钟停振、长按复位及恢复均通过。其余模块为明确黑盒／强制校准状态，不是完整 SoC 或模拟电气仿真。
- CNN、UART、权重、条带和 DDR 访问源文件与原签核版保持一致，复用原仿真证据，不把本次显示侧测试说成整机重新上板成功。

## 实板使用和结果判断

Programmer 使用上面链接的 `build/720p30_diag/outflow/ti60_style.bit`、JTAG 模式。不要选摄像头版、旧 `build/720p/` 或停止的 60 Hz 候选。本轮只生成本地文件，没有代为下载或写 Flash。

本地重建入口为 `scripts/hdmi30/build.py prepare`（首次生成候选，拒绝覆盖既有目录），先运行 `sim/check_hdmi30.py` 和 `sim/check_hdmi30_reset.py`，再执行 `scripts/hdmi30/build.py compile`；已有候选核对使用 `scripts/hdmi30/build.py audit`。运行目录使用本项目 `build/`，CAD 单任务四线程，模型和候选源文件不得在运行中更改。

- **下载后先不要上传图片**：应先出现彩条。彩条出现说明当前屏幕已经锁定这一份 720p30 输出，但不代表 DDR 或 CNN 已验收。
- 再用原 GUI，选 720p、2000000 波特率、正确 COM 上传图片。完整 END ACK 后应从彩条切到风格图，按原四键切换。
- 彩条正常、上传超时：继续检查 UART／DDR 校准／处理链，不再首先怀疑屏幕分辨率。
- 彩条仍提示输入不支持：本地检查不能确定是否为屏幕模式支持、PLL／串化实际波形或信号完整性；需读取屏幕输入信息／EDID或测量像素与 TMDS 时钟。不能靠降低 CNN 帧率或改 GPIO 电压解决。

720p30 在 HDMI 1.4 中对应 VIC 62，但标准定义某模式不代表每个屏幕都必须支持该模式。可参考 [Analog Devices 模式支持表](https://www.analog.com/static/imported-files/eval_boards/AD9889B-to-ADV7513-Changeover-Guide.pdf)。
