# RGB565 串口提速

目标：先保留现有1280×720 RGB565像素精度，尝试将单图传输压到10秒以内。本次增加独立`fast`配置：2,000,000 baud、16,384字节DATA上限、相同包头/CRC/停等握手、相同DDR双缓冲和720p60显示。GUI和命令行均可选择配置；不能只改PC波特率。

## 数据量和实际余量

一帧为1,843,200字节，8N1每字节在线路上使用10bit。以下只算像素，不包含协议、驱动或DDR等待：

| 波特率 | 纯像素下限 |
|---|---:|
| 115200 | 160.000s |
| 921600 | 20.000s |
| 1500000 | 12.288s |
| 2000000 | 9.216s |

板上CH340E在[沁恒产品表](https://www.wch-ic.com/products/productsCenter/mcuInterface?categoryId=1)中标为最高峰值2Mbps；这不是对此板、驱动和线缆持续吞吐的实测保证。当前100MHz FPGA UI时钟可精确除50得到2Mbps，保持8N1和原3.3V引脚标准。

原1KB方案需要1800个DATA；16KB方案仅需113个DATA（112×16384 + 8192），加ABORT、BEGIN、END共116次停等事务。大包减少USB/Windows/软件逐次等待，也降低包头和ACK开销；不移除CRC、不提前ACK，不发送尚未完成的帧。

`pc/estimate_transfer.py`逐字节构造SLIP转义、CRC及成功ACK，统计当前34张图片的线速预算：**9.2475–9.7876秒**，对应图片0014和0004。估算固定frame_id=0，帧号和CRC变动会带来少量差异。最难图片只有约0.2124秒余量，USB驱动、DDR写入、Python解码、界面调度、显示边界等待和重传都还要加在其上，因此不能承诺所有图片必定小于10秒。图像内容本身影响转义开销。

预算结果保存在`build/fast/wire_estimates.json`和`build/fast/logs/wire_estimates.log`，不是上板性能记录。真实GUI成功日志另显示从任务开始到解码、打开串口和全部命令确认的总用时，供实际测量。

PC转换使用可选NumPy加速，未安装时保留原Python方法。当前环境已有NumPy，34张实际图片逐字节对照一致；本机仅转换的平均用时由0.1360秒降至0.0065秒，额外减少约0.13秒开销。该计时不包括PNG解码和串口传输，不能用它声称实板达到10秒。

## 独立配置和使用

```powershell
& 'F:/fpga_qiansai/xilinx/projects/uart_hdmi/.venv/Scripts/python.exe' 'F:/fpga_qiansai/xilinx/projects/uart_hdmi/create_project.py' --profile fast --build
# 已有提速工程继续构建：加 --resume；需要重综合时加 --reset-synth
```

- 标准旧产物继续保存在`vivado/`；提速工程为`vivado_fast/uart_hdmi.xpr`，bitstream为`vivado_fast/uart_hdmi.runs/impl_1/uart_hdmi_top.bit`。
- 提速报告写入`vivado_fast/`，日志/构建指纹写入`build/fast/`，不覆盖原115200产物，也不修改原厂参考工程。
- 本次共享源码增加容量参数。原115200 bitstream的历史构建凭据只对应当时源码；不能再说它与已改动的共享源码逐份哈希相同。标准参数行为已由回归测试检查，旧bitstream文件本身保留。
- 需要使用提速版FPGA配置后，重启GUI并点击“提速2Mbps / 16KB”，再选图片发送。默认仍是标准115200 / 1KB，避免误连旧配置。PC每包大小不可超过FPGA缓存上限。
- 若仍然出现COM29拒绝访问，先在其他串口程序中停止/关闭该端口，一次只保留一个使用串口的程序；波特率调整不能解除占用。

命令行提速：

```powershell
& 'F:/fpga_qiansai/xilinx/projects/uart_hdmi/.venv/Scripts/python.exe' 'F:/fpga_qiansai/xilinx/projects/uart_hdmi/pc/send_image.py' --port COM29 --baud 2000000 --chunk-bytes 16384 --image 'F:/fpga_qiansai/xilinx/projects/uart_hdmi/images/0001.png'
```

## 实现与验证

`UART_PAYLOAD_BYTES`参数贯穿顶层、包缓存和写入器。16KB DATA的解码后完整包为16408字节，地址和长度扩展为15bit；保持16字节对齐、RGB565小端、32bit帧偏移、16bit包序号与原CRC算法。端口引脚、IO电平、DDR配置、帧所有权与显示时钟不变。

- `sim/test_fast_uart.py`：标准行为回归、完整16KB缓存边界、15bit地址、重复大包、溢出/CRC错误恢复、8KB尾包、AXI背压和DDR内容逐字节核对；实际100MHz/2Mbps分频、连续8N1和独立相位/493–507ns bit周期。
- `sim/test_fast_serial_chain.py`：实际UART RTL串行接收一个完整16KB转义包，经过收包CRC和写入器，验证1024个AXI128bit字及B响应后应答。
- `sim/test_sender_gui.py`：真实PC协议、完整720p、113个DATA、8KB尾包、分段write/read、丢ACK重发、停止/关闭、串口错误、GUI配置与预览布局。模拟串口成功不等于CH340硬件的实测时间。
- `sim/test_rgb565_pack.py`：全部34张图片加速/原方法逐字节一致，红绿蓝基色及小端打包核对通过；缺少NumPy时沿用原算法。
- Vivado综合、布局布线、时序、CDC及84引脚审计的最终状态以提速版构建报告和凭据为准；未烧写实板，实际高波特率误码与总用时需要测量。

### 最终构建结果

2026-10-09 17:46完成Vivado 2023.2构建，退出码0，bitstream生成成功，11,443,722字节。实际设置为`UART_BAUD=2000000 UART_PAYLOAD_BYTES=16384`。WNS=+0.893ns、WHS=+0.054ns、WPWS=+0.143ns，失败端点全部为0；LUT=13158、FF=9197、RAMB36=4。

DRC 0错误/5条既有MIG警告；CDC 0严重项/2条既有MIG复位警告；方法学保留4条LUTAR-1、1条XDCB-5及32条SERDES复位advisory。没有降低检查级别；外部input/output delay提示保持原状。板级审计再次检查84个端口，所有引脚、方向、IO标准、Bank及DDR辅助电压一致，目标时钟正确。实际UART→16KB收包→DDR行为模型测试已通过，完整GUI回归及新构建19份输入指纹检查通过。

提速bitstream SHA256：`DEC993B588B3F9589B64392EB770535DF722B2DB9E04B6F653EB0596A4EC671B`。凭据为`build/fast/build_receipt.json`与`build/fast/final_signoff.json`。旧标准bitstream哈希仍为`F49F6537055ED83CFEDDDF5FB6E838071BD6918DAC87CC13F80EF33AAD1836F1`，没有覆盖。

**未烧写板卡，10秒以内尚未实测。** GPIO电平配置保持不变，但高波特率实际稳定性需用完整帧校验与实板总用时判断。

先测RGB565提速版。若实测仍超过10秒，再决定继续优化帧编码/传输接口，或采用用户后续确认的低位宽颜色格式；本次尚未切换RGB332/RGB232。
