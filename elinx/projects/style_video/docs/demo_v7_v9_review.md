# demo10 V7 / V9 与当前工程复查

2026-10-17。按用户要求，只把 demo10 的 V7、V9 作为本次参考，不使用 V6，不修改 demo。本次检查现有工程，不替换生产 RTL、固件、模型、约束或 bit，不下载板卡。

## 参考范围

两份原始参考位于 `elinx/elinxdemo/Ti60F225_DemoBoard_v4/10_Ti60f225_sc431hai2hdmi_demo/` 下的 `Ti60f225_sc431hai2hdmi_v7/Ti60f225_sc431hai2hdmi_v7/` 和 `Ti60f225_sc431hai2hdmi_v9/Ti60f225_sc431hai2hdmi_v9/`。

当前准备、固件提取和电气检查脚本使用 V7 路径；两套交付 XML 的综合源清单均无 V6 路径，也没有实例化 demo 的 `raw_to_rgb.v`、`rgb_gain_v1.v` 或 `sensor_clipper.v`。串口版从 PC 接收 RGB565，不经过摄像头 Bayer 处理。

对比的 V7 / V9 参考源码和配置分别为 119 / 121 个文件，复查前后 SHA256 一致。它们的 `ti60f225_oob.peri.xml`、SDC、原 `rtl/csi_rx_controller.sv` 和全部 `rtl/ddr3_controller/` 文件逐字节一致；本轮不需要因 V9 的图像修复调整引脚电平或 DDR 参数。

## V9 具体修复了什么

以下依据实际启用的源码差异和综合源清单；源码说明不是 V9 在本板上运行成功的证明。

| 位置 | V7 → V9 差异 | 与画面问题的关系 |
|---|---|---|
| `rtl/debayer/raw_to_rgb.v` | VS/HS/DE/valid/X/Y 从两级延迟补成三级；输出门控一起延后 | 对齐三级数据通路，避免两像素一组的横向错位和行尾丢像素 |
| 同文件 Bayer 插值 | 按窗口中心所在行修正奇偶分支；修正一个绿色位置的 R/B 插值来源 | 避免周期性 Bayer 相位错误、红蓝格状串色和彩边 |
| `rtl/debayer/rgb_gain_v1.v` | BGGR 偶行为低 B / 高 G，奇行为低 G / 高 R，增益路由随之修正 | 避免给不同颜色施加错误通道增益 |
| `rtl/ti60f225_oob_top.v` | RAW 字节顺序、DDR 读出后两像素顺序及 HDMI R/B 输入作配套调整 | 像素顺序、Bayer 相位与最终颜色必须整体对应，不能孤立复制一个字节交换 |
| 新增 `rtl/sensor_clipper.v` | 每行裁出 480 个四像素组，共 1080 行，数据/控制一起寄存 | 限定进入帧缓存的有效区域；该模块未实现低通抗混叠滤波 |

因此，V9 包含能解释用户所述锯齿改善的像素对齐和颜色相位修复。它没有新增通用抗锯齿滤波器，不能把全部细线、斜线和缩小后的台阶都归为同一个错误。

## 当前独立 Bayer 路径的对应检查

当前 [camera_bayer_reduce.sv](../rtl/camera_bayer_reduce.sv) 直接消费低位最早的四个 RAW10 像素。偶数源行存 RAM，下一行将上/下两个像素对一起锁存，`pending`、`selected` 与它们同拍更新，下一拍同时生成两个 RGB565 和 `pixel_valid`。默认 BGGR 使用左上 B、右下 R、另两点 G 的平均值；不复用 demo 中的三拍插值通路或增益模块。

新增独立仿真 [check_bayer_alignment.py](../sim/check_bayer_alignment.py)，在项目自己的 `sim/bayer_alignment/` 输出结果，原签核测试回执不覆盖。测试包含：

- 64×32 → 16×12 和完整 1920×1080 → 640×480 两种裁剪尺寸。
- BGGR、RGGB、GBRG、GRBG 四种相位，每种连续测试两种图案，共 16 帧、2,459,136 个输出像素。
- 饱和红/蓝交替边界、各颜色不同的 X/Y 坐标变化；逐个对照所有输出，包括首尾行列。
- 行内 valid 空隙、帧头锁存 Bayer 相位、最后 HS 与 EOF 同拍下降。

该测试只验证数字像素的颜色映射与对齐。真实模组经过裁剪/镜像后的 Bayer 排列仍须实物色卡确认；2×2 合成也不是完整 ISP 或高质量抗混叠缩放器。

## 为什么本轮没有直接替换 V9 摄像头配置

V7 有 164 条有效 ROM 命令，含显式 1920×1080 输出、裁剪和 `0x3221=0x66` 镜像设置。当前固件保留其中 163 条待机命令，把开流推迟到 ID、尺寸、VTS 和模型验证完成之后。

V9 只有 146 条有效命令，原来的 `0x3200..0x3221` 裁剪/尺寸/镜像写入已注释，并修改了部分模拟调节和曝光参数；它另接入 FPGA 的 `sensor_clipper`。仅凭这些差异不能确认模组实际输出尺寸和 Bayer 相位。

当前 PPI 解析器检查 RAW10、1920 像素、每行 2400 字节及 1080 行。如果只换成 V9 寄存器表而不一起核实传感器尺寸和接收/裁剪链路，可能使帧被尺寸检查拒绝。保留已签核 V7 采集模式，按 V9 的修复点复查独立数据通路，可以避免这种配置混用；本轮没有声称现有 bit 已移植 V9 全部图像链路。

## 电平、时序和交付文件

复用 [两套工程只读检查](../scripts/check_download_pair.py)，重新验证源码/固件/模型与 bit 指纹、所有实际脚、12 个 Bank 配置及既有最终时序报告：

| 项目 | 封装脚 | 最小 setup / hold | 当前处理配置 |
|---|---|---|---|
| 串口 `uart_style_tiles/build/720p` | 66 | +0.387 / +0.026 ns | 1280×720 RGB565，720p30 显示 |
| 摄像头 `style_video/build/camera_ppi` | 79 | +0.289 / +0.026 ns | 1080p RAW10 → 640×480，720p30 居中 |

MIPI Bank2A/2B 配置 1.2V；摄像头 SCL/SDA/RESET 按配套 V4 模组为 3.3V；DDR 为 1.5V。用户已确认 J4、J2/J3 均为 2–3。复核细节与供电边界见 [上电前检查](preflight_review_20261016.md)，操作见 [下载指南](../../../../docs/Ti60_programming_guide.md)。

本轮没有重新布局布线或生成新 bit，没有测量供电、电流、温升或实际画面。原 Flash 内容未知的问题仍然存在；现有 bit 的检查不覆盖未知的上电程序。

本地证据：`build/programming_review_20261017/demo_v7_v9_before.json`、`demo_v7_v9_review.json`、`pair_720p.json`，以及 `sim/bayer_alignment/verification.json`。复核脚本 [review_demo_v7_v9.py](../scripts/review_demo_v7_v9.py) 只读参考和签核文件，写独立复查记录，不调用 CAD 或硬件。
