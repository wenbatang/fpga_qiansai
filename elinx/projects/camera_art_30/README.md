# 四风格 720p / 30fps 独立实验

> **2026-10-30最终离线签核：** 离线签核 PASS · 四风格完整720p CNN/DMA最低 35.47837fps · RAM10 174/256，DSP 100/160，XLR 53603/60800 · setup/hold +0.309/+0.026ns。未连接板卡、未下载、未写Flash；实板持续30fps待测。
> [bit文件](build/720p/outflow/ti60_camera.bit) · [工程入口](build/720p/ti60_camera.xml) · [完整验证与操作](docs/validation.md) · [实际对照图](build/quality/000000220310_comparison.png)

入口：[离线架构说明](architecture.html)、[参考工程分析](docs/reference_review.md)、[画质对照](docs/model_quality.md)。当前构建与验证结论以 `build/720p/signoff.json` 为准；没有 PASS 签核的新候选不可作为下载版本。

本工程借鉴 `style_model/elinx/`，使用其已经训练的梵高、剪纸、漫画、水墨 C8 参数（来源槽 0/3/4/5，本项目槽 0/1/2/3）。并未重新训练，也未替换原 RF33 可用工程。输入和 HDMI 有效画面均为 1280×720；CNN 特征分支先做 2×2 平均池化，在 640×360 特征上计算，最终残差回加完整 720p RGB。它的画质与旧 RF33 不同，不能称作原模型的无损提速。

针对参考设计改进逐点卷积的双上下文流水、DDR 输出打包、三输出 bank 与安全消隐提交，并缩减参数 ROM。UI/CPU 100MHz、CNN 166.667MHz、DDR PHY 400MHz、HDMI 74.25MHz/720p60，均沿用核对过的接口配置。本轮没有连接板卡或写 Flash。

板上 KEY0/1/2/3 分别请求梵高/剪纸/漫画/水墨；KEY1+KEY2 保持约 0.5 秒进入原图；KEY0+KEY3 长按逻辑复位。启动先显示原图。按键忙时保留最新请求，模型切换完整执行 346 次带确认的配置事务后才能启动。

`Cxx` 为 DDR 完整采集帧率，`Ixx` 为神经网络完整作业完成帧率，`H60` 为 HDMI 刷新配置。UART 115200/8N1 的 CAM4 是诊断输出，查看工具 `pc/camera_view.py`，不用于上传摄像头图像。

构建从本项目 `build/` 目录运行，Python 使用安装了 NumPy/PyTorch 的现有环境：

```powershell
python -B ../scripts/firmware.py
python -B ../sim/check_kernel.py --styles 0 1 2 3
python -B ../sim/check_dma.py
python -B ../sim/check_dma.py --full
python -B ../scripts/build.py map
python -B ../scripts/build.py interface
python -B ../scripts/build.py route
python -B ../scripts/build.py prove
python -B ../scripts/build.py route
python -B ../scripts/build.py prove-final
python -B ../scripts/probe.py
python -B ../sim/check_mapped.py
python -B ../sim/check_control.py
python -B ../sim/check_sapphire.py
python -B ../sim/check_top_safety.py
python -B ../scripts/build.py config
python -B ../scripts/build.py audit
python -B ../scripts/final_review.py
```

`config` 仅离线生成 bit，先检查功能、参数、固件、电气和原生时序；没有下载命令。`prepare.py` 是首次复制入口，已有工程禁止重跑，不能用原47风格的集成脚本覆写本项目新控制逻辑。所有仿真、参数、厂商依赖与构建产物按工作区规则留在本地。C/ASM/LD固件、XML/SDC及参数初始化也不在当前Git白名单；仓库中的RTL、Python和说明不是完整的可重建工程归档，须保留本地依赖。
