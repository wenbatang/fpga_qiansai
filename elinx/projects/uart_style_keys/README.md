# Ti60F225 DemoBoard V4 串口四风格验证

> **2026-10-19 已更换正确原理图并重建签核。KEY1=P14、KEY2=N14；J8不是UART。** 当前六套bit指纹、时序及电气核对以[本次复核](../../../docs/Ti60_correct_schematic_review.md)为准。vga：setup +0.301 ns / hold +0.028 ns。原错误引脚bit已保存快照；下文早期构建数值如有不同属于历史记录。


用户已确认实板与本地V4资料对应，本轮先“主机相机 → 串口原图 → DDR → FPGA四风格CNN → HDMI”，再接MIPI。独立工程使用现有四种 `distinct_student_v1` 参数，不重新训练；星空、浮世绘、水墨、彩色油画。

入口：[离线架构图](architecture.html) · [电气与移植检查](docs/porting.md) · [处理尺寸与720p30](docs/display_720p30.md) · [主机摄像头用法](../../../xilinx/projects/uart_style_keys/docs/host_camera.md)。

本轮默认显式 **VGA处理配置**：输入/推理640×480、RGB565，输出标准720p30居中显示。Ti60只有256个RAM10、160个DSP，完整VGA工程已占用较高比例；720p输入不能直接用Xilinx同名bitstream，也不能把显示720p说成推理720p。后续MIPI与RISC-V集成还需要留资源。

| V4按键 | 风格 | GPIO / 球位 |
|---|---|---|
| KEY0 | 星空，默认 | GPIOL_07 / C4 |
| KEY1 | 浮世绘 | GPIOR_22 / P14 |
| KEY2 | 水墨 | GPIOR_21 / N14 |
| KEY3 | 彩色油画 | GPIOL_03 / A3 |

四键均为3.3V输入，低有效，两级同步、10ms去抖。上电自动复位；KEY0+KEY3同时长按1秒复位全系统，释放后重新初始化DDR。组合长按期间可能先触发风格预选，复位后源图失效，需重新完整上传。

UART_RX / R4 / GPIOL_02，UART_TX / R14 / GPIOR_28，均3.3V。选板上FT4232的UART通道（原UART_demo能通信的COM），2Mbps；不要把JTAG通道当UART端口。

## 工程与构建

可编辑适配在 `rtl/`，本地受保护厂商副本在 `vendor/`，仿真在 `sim/`，工程、权重、日志和产物在 `build/vga/`。参考 `10_Ti60f225_sc431hai2hdmi_demo/.../Ti60f225_sc431hai2hdmi_v7` 的DDR控制器及接口配置，UART引脚取自 `17_Ti60F225_uart_demo`。保持原版权说明和Efinity2026.1.132基线；不升级CSI IP、不修改原例程。

```powershell
cd F:\fpga_qiansai\elinx\projects\uart_style_keys\build
python ../scripts/prepare.py --profile vga
python ../sim/check_fifo.py
python ../sim/check_tmds.py
python ../sim/check_video.py
python ../scripts/build.py --profile vga --flow compile
```

实际工具与Python路径见脚本，需已有Torch/NumPy/lxml环境及本地四模型导出。`compile`运行综合、接口、布局布线、配置文件生成，**不运行program，不访问JTAG或串口**。生成配置文件还必须检查全部实际时钟、CDC、引脚和时序；签核之前的试验产物不得当作通过版本。

本项目 `pc/` 保存配套主机工具，沿用同一COBS请求/SLIP ACK/RGB565协议，默认显式vga配置，按键文字为V4的KEY0–KEY3。运行 `python pc/camera_gui.py` 自动采集上传，`python pc/send_style_gui.py` 选择已有照片；依赖为 `pc/camera/requirements.txt`。使用原Xilinx GUI也可，但必须**选择vga配置**，它默认720p，尺寸不匹配会立即报错。本轮原始源帧仍保留在DDR，按键可复用同一张图，忙时只记最后一次风格，新BEGIN失效源图，最后写响应与消隐换帧完成后才ACK。

V4 MIPI、SC432HAI寄存器兼容性、RAW/Bayer预处理、RISC-V动态权重/中断、实际FPS叠加尚未完成；串口照片试验不代表最终赛题实时视频已完成。所有板上结果需另外实测。

## 本轮最终签核

720p30当前配置已重新构建与签核；原720p60构建及源码保存在`build/baseline_720p60_20261013/`。尺寸与时序说明见[720p30说明](docs/display_720p30.md)。

- 完整综合、Interface Designer、布局布线、配置生成通过；66个使用中的封装引脚、电平、方向与V4资料核对通过。
- 核心100MHz建立裕量+3.810ns；全表最小建立+0.419ns、保持+0.031ns。所有实际PLL/PHY时钟计时，12处单比特首级、521处异步复位、116条注册Gray跨域分别处理；同步链确认采用FF。
- 整机240/256 RAM10、144/160 DSP、26,955/60,800 XLR；资源接近RAM/DSP上限，不能据此宣称MIPI/RISC-V整机仍可直接放入。
- 本机 [Ti60 V4 bitstream](build/vga/outflow/ti60_style.bit)，SHA256 `15f2f8f32ae6f9990bdc8efdcba04ffcab00c52b2abc6a73170ad6bd13f58d3c`；[签核记录](build/vga/signoff.json)。未下载实板。工具的LVDS邻近耦合、复位同步链输入GND及厂商RTL提示保留，不说零警告。
- 四模型整链路、包RAM等待、FIFO顺序/回绕/复位、TMDS补偿/控制码/解码、主机工具两种停止与资源释放均通过；新增720p30连续三幅全尺寸时序、居中黑边、同步、消隐窗口与下溢恢复仿真通过。实板DDR校准、串口总用时、HDMI颜色与按键、持续推理FPS未测。
