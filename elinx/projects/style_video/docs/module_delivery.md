# 摄像头、DDR 与 HDMI 模块交付说明

日期：2026-10-20。平台：Efinix Ti60F225I3，DemoBoard V4、摄像头 J5，工具基线 Efinity 2026.1.132.4.5。本说明随 `zyx` 分支源码提交，供 RISC-V 和 CNN 队友接入。

## 本次提供什么

|公共模块|源码|职责|
|---|---|---|
|style_camera_capture|[采集接口](../rtl/style_camera_capture.sv)|RAW10×4、高有效VS/HS/DE输入；黑位、Bayer转RGB、白平衡、缩放、Gamma、图像/取消CDC及计数；输出core域RGB888流|
|style_ddr_framebuffer|[DDR接口](../rtl/style_ddr_framebuffer.sv)|内部复用style_platform_core，管理四DMA、帧槽所有权、AXI128仲裁、完整帧配对发布、APB控制和CNN流口|
|style_hdmi_display|[显示接口](../rtl/style_hdmi_display.sv)|显示FIFO、720p60时序、状态跨域、诊断叠加和保留的HDMI编码器；默认左原图、右图像区黑色|

```text
官方CSI接收器 → camera_capture → framebuffer ←→ 官方DDR控制器/PHY
                                     ↕ accel_*         ↕ DDR3
                                  队友完整CNN
                                     │
                         framebuffer → hdmi_display → 板级串化 → HDMI
                              ↕ APB / IRQ
                         Sapphire RISC-V / C驱动
```

公共模块依赖本目录 `rtl/` 中的其他子模块，不能仅下载三个同名文件。厂商D-PHY/CSI、DDR物理控制器、PLL、HDMI高速串化配置仍按官方工程保留。

## 当前行为与图像格式

- 预处理输出640×480 RGB888，每拍一个像素；有效握手为valid&&ready，等待期间RGB、标志和编号保持。SOF首像素、EOL每行末像素、EOF整帧末像素；所有像素frame_id一致。
- 当前物理配置为BGGR，RAW黑位A/B/C/D=65/66/66/67，固定白平衡Q8增益R/G/B=493/256/504，Gamma1.8；可选KEY2白纸校准、KEY3恢复。ORIGINAL表示预处理后的原图。
- DDR使用RGBX8888，小端32位字0x00RRGGBB，stride=2560；四原图槽、两结果槽，每槽2MiB，地址范围0x01000000–0x01BFFFFF须在CPU内存布局中保留。
- HDMI采用1280×720、60Hz；左图x0..639/y120..599，右图x640..1279/y120..599为黑色CNN预留区，上下文字/诊断区保留。
- 当前无Sapphire、无CNN、无权重加载实现。内部仍用COPY建立完整帧pair；隐藏右图仍读取并消费其像素，不代表减少DDR流量或提高帧率。

## 队友从哪里接

### RISC-V 队友

连接板级顶层 `framebuffer` 实例的APB3端口：paddr[11:0]、psel、penable、pwrite、pwdata[31:0]、prdata[31:0]、pready、pslverr，以及irq。目前这些请求端口接空闲常数，返回数据悬空；Sapphire集成时替换为真实总线连接。

APB侧建议与core_clk同为100MHz。若不同域使用完整跨时钟桥；若只导出AXI/AHB，先接总线到APB桥和地址译码。外设基址由实际SoC/BSP分配，不能把DDR帧池基址当成寄存器基址。先读IDENT偏移0x000，应得0x53565931，再调CONTROL/START/STATUS和中断。

当前I²C硬件初始化主机保留；RISC-V接管摄像头时需停用原主机，并另接I²C控制器。权重接口需要与CNN队友单独约定，当前不是现成的APB权重DMA。

### CNN 队友

连接 `framebuffer.accel_input_*` / `accel_output_*`、`accel_start`、`accel_abort`，在core域处理完整640×480 RGB帧。输出帧编号须与输入一致；正常遵守背压，abort时取消并清空旧任务。平台负责原图读DMA、结果写DMA及最终DDR写响应后的完整结果确认。

接入完整CNN后同时完成：顶层FORCE_BYPASS=0、软件清CONTROL.bit2、准备工程时加`--show-result`解除显示RESERVE_CNN。未接CNN时单独解除右黑只显示COPY。若算法模块自带AXI主机，先重新定义DDR仲裁和帧所有权，不能直接套RGB流接口。

## 本地验证记录

以下是本地已完成结果，不表示已完成本次版本实板验收：

|项目|结果|
|---|---|
|新增模块仿真|8项通过：DDR封装4项、显示封装3项、完整显示尺寸1项|
|配置生成检查|普通/颜色诊断/对比度/白纸校准/性能监测共5种通过|
|其他源码未变的验证记录|95项校验源码哈希后复用；合计108项记录|
|完整显示模型|左侧307200个原图像素顺序正确，右侧307200个像素全黑，614400个token完整消费，UF=0，RAW/WB诊断CDC通过|
|Efinity实现|综合、物理接口、布局布线、位流生成通过；89项设计源，95个引脚映射及既有时钟配置核对一致|
|时序|WNS +0.399ns，WHS +0.026ns；模块CDC约束匹配，无新增未匹配FIFO约束|
|资源|LUT4=20102，FF=14948，DSP48=6，RAM10=109|
|本次实板验证|待拿到板子后验证；此前CAP/COPY30FPS和零错误反馈属于旧版本|

本地候选文件为`build/style_video_ddr_display_modules.bit`，SHA256：`ceabdd0c619b36634cdedec2185fe23130f56db5301196729f6ab21d2642c60f`。详细回执为`build/ddr_display_modules_receipt.json`。理想AXI/像素模型结果不是实际DDR带宽或CNN性能测量。

## GitHub 源码范围与 Efinity 使用

本提交提供项目自有RTL、Python/RTL生成脚本、Markdown说明和`architecture.html`。依仓库既有策略，`sim/`、`build/`、位流/回执、Efinity XML/peri/SDC、初始化文件和厂商生成IP不上传；厂商资料的本地副本也不包含在本次提交中。因此本提交是模块源码交付，不能仅凭一次git clone直接重建整个物理工程。

队友需要配套官方Ti60F225 V4/J5资料及对应IP/物理配置，再按接口文档接入。当前prepare脚本的默认参考输入为本地`../demo10_official/build/run_v6_v4_j5_keys_reset`，并校验原官方摄像头ROM；本地完整仿真也依赖未上传的sim文件。

在已有完整本地依赖的工作区，先关闭IDE旧缓存工程，再执行：

```text
python scripts/prepare_efinity.py --contrast-probe --wb-calibration --performance-monitor
python scripts/run_checks.py --collect
python scripts/build_efinity.py --build
python scripts/build_docs.py
```

`--collect`仅复核已有通过记录与当前源码哈希；没有本地仿真回执时不能替代真实测试。完整仿真运行`run_checks.py`，需要配套本地sim。之后重新打开`efinity/style_video.xml`，确认顶层style_ti60_top、器件Ti60F225I3、语言sv_09和两个新增公共模块源文件。不要自动升级保留的CSI IP。

维护入口：采集模块为手写RTL；DDR公共接口由`generate_ddr_wrapper.py`生成；核心逻辑维护在`generate_core.py`；顶层接线维护在`camera_capture_shell.py`和`video_module_shell.py`；网页/README/接口契约由`build_docs.py`生成。修改生成文件后应同步其生成器。

详细阅读：[完整接口契约](interface_contract.md)、[采集模块](camera_capture.md)、[DDR/显示与RISC-V接线](ddr_display_modules.md)、[离线架构网页](../architecture.html)。GitHub上可查看HTML源码，下载后本地打开网页交互界面。
