# 全720p四风格轻量化实验

> 离线签核PASS · 全720p四风格最低39.084974fps模型吞吐 · RAM10 220/256、DSP 142/160、XLR 52326/60800 · setup/hold +0.043/+0.026ns。未下载，实板持续30fps待测。

本工程使用重新训练的六通道C6网络：**输入、所有逻辑特征层和输出均1280×720，无池化或2×2残差放大**。四种风格为梵高、剪纸、漫画、水墨。每种风格396个卷积权重，比保留的C8模型减少49.49%。旧RF33、C8工程和参数均保留。

当前放行状态请看[验证说明](docs/validation.md)与本地build/720p/signoff.json；只有当前签核PASS并且fresh audit通过的bit才作为可下载版本。目标为每秒30张不同的风格化帧，HDMI持续720p60；功能仿真吞吐不等于实板帧率。

- [离线架构图](architecture.html)
- [网络、训练、整数运算与画质对照](docs/model.md)
- [模块、接口、缓冲和工作流程](docs/implementation.md)
- [算力、资源与30fps预算](docs/performance.md)
- [实际照片对照0001](build/quality/0001_comparison.png) / [0005](build/quality/0005_comparison.png)
- [工程入口](build/720p/ti60_camera.xml) / [bit位置](build/720p/outflow/ti60_camera.bit)

## 使用

平台为Ti60F225I3 V4，SC431HAI配套模组。摄像头J4、J2/J3均2–3的接法已由用户核对，沿用正确20261012版原理图的接口配置。不要使用旧图J8接UART；诊断通过板载USB串口，115200/8N1。此工程从摄像头采集，不通过PC上传图像。

用户自行验证时，选择本目录工程及其同次签核bit，先使用Programmer的JTAG模式进行易失性下载。bit已包含本项目RISC-V固件，不需额外烧写firmware.bin。一次只运行一套FPGA程序；此工程没有多镜像Flash管理。

启动显示原图；KEY0/1/2/3分别选择梵高/剪纸/漫画/水墨，KEY1+KEY2保持约0.5秒回原图，KEY0+KEY3约1秒复位。`Cxx`表示完整采集帧率，`Ixx`表示完整CNN作业完成帧率，`H60`为HDMI刷新配置。原图复制和重复显示不会增加I。

```powershell
python -B pc/camera_view.py --self-test
python -B pc/camera_view.py --list
python -B pc/camera_view.py --port COMxx
```

CAM4工具只读诊断，不发送命令。先关闭占用同一个COM口的串口助手。实际是否稳定30fps，需要连续运行后观察I、错误/欠载和显示效果；不能由H60推断。

## 本地构建与回归

在本项目build目录运行，使用现有安装NumPy/PyTorch的Python环境。厂商工具及许可按本地环境使用。下面省略了极小边界、按键/控制/真实Sapphire、调度/显示/故障保护等完整回归，正式放行由signoff.py逐项绑定全部证据。

```powershell
python -B ../sim/check_kernel.py
python -B ../sim/check_dma.py
python -B ../sim/check_dma.py --pressure
python -B ../sim/check_dma.py --full --styles 0 1 2 3
python -B ../scripts/build.py map
python -B ../scripts/build.py interface
python -B ../scripts/build.py route
python -B ../scripts/build.py prove
python -B ../scripts/build.py route
python -B ../scripts/build.py prove-final
python -B ../scripts/probe.py
python -B ../sim/check_mapped.py
python -B ../scripts/probe.py --dma
python -B ../sim/check_mapped.py --dma
python -B ../scripts/build.py config
python -B ../scripts/build.py audit
python -B ../scripts/final_review.py
```

`config`先离线审计再生成文件，不访问板卡。`prepare.py`只用于首次复制，已有工程不要重跑；模型导出在映射输入冻结后也禁止覆盖。改变RTL/参数后要重新综合及相关回归，不能沿用旧签核。

build、sim、vendor、参数、生成的full_shared_params.sv权重常量、固件C/ASM/LD、工程XML/SDC按工作区Git规则仅留本地。仓库中的Python、手写RTL和说明不是完整可重建工程归档；必须保留本地厂商IP、初始化数据、报告及数值验证日志。手势识别和按键三界面不属于本版本已集成功能。
