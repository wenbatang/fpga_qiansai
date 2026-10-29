# Ti60 全720p四风格与三种显示界面

独立于 `camera_full720_30` 的新工程。摄像头与 CNN 都保持1280×720；HDMI维持已兼容显示器的标准720p60。四种风格是梵高、剪纸、漫画、水墨。新模型独立学习每组空间卷积和输出层，不再共用旧模型的DW/head参数。

**当前状态：最终离线签核与fresh复查通过，已生成新bit；旧可用版本保持。实板画质与30fps仍待测试。** 最终只以本工程 `build/720p/signoff.json` 与 `final_review.json` 同时PASS的产物为交付。没有代为访问板卡、串口、JTAG或Flash。

入口：[架构图](architecture.html)、[模型说明](docs/model.md)、[实现及接口](docs/implementation.md)、[验证边界](docs/validation.md)、[性能说明](docs/performance.md)。主机手势演示见 `pycode/gesture_demo/README.md`。

## 操作变化

| 板载按键 | 操作 |
|---|---|
| KEY0 / C4 | 原图 → 风格图 → 左原右风格 → 原图 |
| KEY1 / P14 | 下一风格，0–3循环 |
| KEY2 / N14 | 上一风格，0–3循环 |
| KEY3 / A3 | 按住约1秒复位；其他键不参与复位 |

启动为原图、默认梵高。处理中的画面模式与风格在作业开始锁存；新的按键请求影响后续完整帧，前台在安全消隐窗口换帧。按住一个普通键只动作一次，释放后才重新武装；KEY1/KEY2同时按下相互取消。

本工程没有在 FPGA 上实现手势分类，也不接收主机手势命令。PC手势演示和板上按键为本阶段两个独立验证入口。

## 本地工程入口

Efinity工程为 `build/720p/ti60_camera.xml`。新模型冻结后依次执行 `scripts/firmware.py`、`scripts/regression.py`、完整CAD及 `scripts/final_review.py`；构建脚本负责失败关闭，不能用旧日志当新结果。最终离线生成目标为同目录 `outflow/ti60_camera.bit`，不是自动烧录。

若最终签核完成，首次仍使用 Efinity Programmer 的 **JTAG + 本工程 .bit** 临时测试；不要混选旧串口版、旧摄像头工程或SPI.hex。C固件与四风格权重均随bit包含，不另烧固件。CAM5诊断115200，`pc/camera_view.py --port COMxx`仅接收日志，使用前关闭其他占用串口程序。

引脚、电平、DDR、MIPI和PLL沿用正确V4原理图及保留全720版；摄像头仍为demo10配套SC431HAI模组、J4，已确认J2/J3均2–3。CAD电气审核只核对数字配置，不能替代实际供电/电流/温升测量，也不能保证未知Flash上电内容安全。

Git保留手写RTL/Python/MD/本架构图；vendor、模型、训练图、约束、C固件、IP及构建/仿真产物仍只留本地，这不是完整可重建的Git归档。

## 本次交付

RAM220/256、DSP142/160、XLR58593/60800；setup/hold +0.084/+0.026ns；最低CNN/DMA模型吞吐39.084974fps。这些是CAD和有界AXI模型结果，不是实板FPS。

[最终bit](build/720p/outflow/ti60_camera.bit) · [工程XML](build/720p/ti60_camera.xml) · [signoff](build/720p/signoff.json) · [fresh复查](build/720p/final_review.json)。

SHA256：`9c6d490b2354fa84202c07772671aea949b5cde4768cc04f959418ec1e26858c`。本轮只生成文件，未下载或写Flash。
