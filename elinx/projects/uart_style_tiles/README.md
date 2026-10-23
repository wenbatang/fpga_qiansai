# Ti60 V4：真正720p四风格CNN，重叠分条缓存

> **2026-10-19 已更换正确原理图并重建签核。KEY1=P14、KEY2=N14；J8不是UART。** 当前六套bit指纹、时序及电气核对以[本次复核](../../../docs/Ti60_correct_schematic_review.md)为准。720p：setup +0.416 ns / hold +0.029 ns；vga：setup +0.535 ns / hold +0.026 ns。原错误引脚bit已保存快照；下文早期构建数值如有不同属于历史记录。


本工程将1280×720原图分成四条352×720计算，再拼回完整1280×720风格结果；每条中央320列有效，左右各16列卷积上下文。使用用户认可的星空、浮世绘、水墨、彩色油画四种原权重，既不缩小到VGA，也不修改模型参数。显示按用户要求720p30。

入口：[离线架构图](architecture.html) · [分条算法与整帧工作流](docs/tiling.md) · [验证记录](docs/validation.md) · [接口电平与逻辑专项复查](docs/electrical_logic_review.md) · [已确认SC431HAI及最终链路步骤](docs/camera_next.md)。原`../uart_style_keys`项目和旧bitstream保持独立。

首次上板请看[两套Ti60工程下载与使用](../../../docs/Ti60_programming_guide.md)。2026-10-17已复核本项目`build/720p`现有bit的源码/模型/配置/时序与66脚，未重建或下载；摄像头版是另一个`style_video/build/camera_ppi`工程，不能与本项目的PC串口操作混用。

## 配置与使用

| 配置 | 串口输入与真实CNN输出 | 条数 | HDMI |
|---|---|---|---|
| `720p`（默认） | 1280×720 RGB565 | 四条352×720 | 720p30满画布 |
| `vga`（显式） | 640×480 RGB565 | 两条352×480 | 720p30居中 |

输入逐行、RGB565小端、无额外stride padding。每个像素保留与原软件模型相同的定点结果；不同条的像素按整图stride写入同一后台bank，全部写响应成功后才发布。

```powershell
python F:/fpga_qiansai/elinx/projects/uart_style_tiles/pc/send_style_gui.py
# 自动采集主机摄像头并逐张上传：
python F:/fpga_qiansai/elinx/projects/uart_style_tiles/pc/camera_gui.py
```

选择真正的UART COM、2000000波特率和与本工程bitstream一致的配置。GUI默认720p，支持完整帧后暂停与立即停止；完整帧暂停后可用板上四键重新转换同一张照片。相机连续采集只保留最新帧，END ACK后才发送下一张；UART仍是数秒一张的原始照片路线。

KEY0星空、KEY1浮世绘、KEY2水墨、KEY3彩色油画；KEY0+KEY3同时长按1秒复位，上电自动复位。引脚、电平、DDR器件与PLL沿用已核对的V4独立工程，不沿用Xilinx原语。依赖为`pc/camera/requirements.txt`。

## 构建与验证

手写RTL在`rtl/`，厂商受保护副本在本地`vendor/`，仿真在`sim/`，生成工程和权重分别在`build/720p/`、`build/vga/`。准备脚本记录来源SHA，保持Efinity2026.1.132/I3与原厂IP基线，不升级IP。需要本地V4例程、原四种模型导出与Torch/NumPy/lxml环境。

```powershell
cd F:/fpga_qiansai/elinx/projects/uart_style_tiles/build
python ../scripts/prepare.py --profile 720p
python ../sim/check_tiles.py
python ../sim/check_link.py --export F:/fpga_qiansai/pycode/runs/distinct_student_v1/export
python ../scripts/build.py --profile 720p --flow compile
python ../scripts/signoff.py --profile 720p
# 同样可显式构建vga；两配置的宏与ROM路径保存在各自build目录。
```

`compile`只综合、布局布线与生成配置，不访问JTAG/串口，不下载、不固化Flash。每次修改后的源码、权重、bitstream和时序必须重新对应签核。

准备与构建按配置顺序执行；不要在另一个配置的综合过程中运行`prepare.py`重写共享源文件。模型更新后两套都需重新构建。配置独立指各自尺寸宏、权重文件和工程/产物独立，不代表允许并发修改共同RTL。

## 当前范围

两配置均已完成CAD构建、工作时钟与66个引脚核对；资源和SHA见[验证记录](docs/validation.md) · [接口电平与逻辑专项复查](docs/electrical_logic_review.md)。四模型缩小尺寸RTL、整链路协议/按键/换帧、完整720p/VGA软件整数结果、视频/FIFO/TMDS/主机GUI均单独验证。

尚未下载实板，完整尺寸RTL吞吐与真实板FPS未测。MIPI采集、RISC-V控制、动态权重加载和FPS叠加仍需集成；它们不在当前bitstream中。分条解决缓存容量，不能据此宣称最终实时赛题已完成。

2026-10-13专项复查：修正UART/复位原生同步属性，补齐所有PLL失锁时全链路复位；两配置重新生成。请使用当前签核指纹对应bitstream，复查前配置仅作回退档案。
