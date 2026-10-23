# V4 电气与逻辑移植检查

> 当前按正确20261012原理图修正KEY1=P14、KEY2=N14并重新构建；最新bit/时序/电气依据见[统一复核](../../../../docs/Ti60_correct_schematic_review.md)。下方早期构建数值若不同，以新复核为准。


用户2026-10-13确认实板对应 `Ti60F225_DemoBoard_v4`，先串口路线、后MIPI。依据 `TI60F225I3-V4_SCH-20261012（原理图）.pdf` 第3/4/6/7/8/10/13/14页与本地V7 DDR/HDMI、UART例程。提取与渲染文件留项目 `build/`；未修改原理图或厂商工程。

## 端口与电源

- 按键KEY0 C4/GPIOL_07、KEY1 P14/GPIOR_22、KEY2 N14/GPIOR_21、KEY3 A3/GPIOL_03，TL/BR为3.3V，外部上拉、按下接地。全部用于风格选择；组合KEY0+KEY3长按1秒复位，POR等待100ms，PLL锁定/DDR校准后释放各域复位。
- UART FT4232：FPGA输入R4/GPIOL_02来自FTDI_TX，输出R14/GPIOR_28去FTDI_RX；BL/BR 3.3V。保留实际方向，不因原理图网络名UART_TX/RX与FPGA方向不同而接反。接口GPIO不再用旧27MHz寄存器采样，UART内部100MHz同步/发送。
- 晶振CLK_25M、CLK_27M取现有1.8V接口；DDR MT41J128M16JT-125、16bit DQ、14bit行地址、3bit Bank、400MHz CK，128bit AXI。3B/4A/4B为1.5V，保留SSTL、VREF、DDIO、校准相位与板级布线。删除原接口中的未使用地址14/15输出定义，与实际14bit控制器一致，未用引脚保持输入弱上拉。
- HDMI为Bank3A 1.8V差分接口，由板上电阻/耦合网络接HDMI；不改成3.3V GPIO、不套用Xilinx OBUFDS电平。第10页确认FPGA_N连接TMDS_P、FPGA_P连接TMDS_N，四对均交叉，必须把三个规范编码字及时钟字全部取反；与V7实际顶层相同。
- 2A/2B为MIPI/LVDS可选电源区，本阶段未启用这些接口；未来接MIPI仍须核对跳帽/摄像头实物，SC432HAI不默认等同SC431HAI。

## 时钟与封装

本轮用户指定720p30：74.25MHz像素与371.25MHz串化不变，水平总周期3300、垂直750，H_FRONT=1760。640×480原尺寸居中，黑边直接生成；详见[尺寸与显示说明](display_720p30.md)。

DDR3_PLL使用原校准400MHz相位输出，输出4/clk_100m只支持rclk，不能驱动核心。核心100MHz复用参考MIPI_TX_PLL原core_clk的全局路径，独立命名CORE_PLL；去除不用的MIPI输出。USER_PLL保留2.970GHz VCO，通过40/8分频得到74.25/371.25MHz，避免把VCO降到设备允许范围之外。Interface Designer检查真实配置与分配，不能只靠计算结果。

Xilinx MIG、XPM FIFO、MMCM、OSERDESE2、OBUFDS全部由V4 DDR控制器、Efinix FIFO、PLL和LVDS串化接口替代。普通卷积、定点、UART、帧所有权、仲裁与720p视频时序沿用已验证代码。CNN与UI 100MHz；像素74.25MHz；串化371.25MHz；DDR校准/PHY 400MHz；启动控制25MHz。

## 发现并修正的移植问题

1. 16KB包RAM的组合读在Ti60会消耗大量逻辑，改为同步块RAM读；frame_writer的HEADER、BEGIN_CRC、LOAD各增加一个读等待周期。真实四风格64×8整链路对照通过，未改协议或发送数据格式。
2. 原Efinix FIFO wrapper没有向内部传递独立a_wr_rst/a_rd_rst端口，BYPASS模式会失去有效复位；采用整体复位与内部同步释放，外围增加两域忙状态和读侧释放确认，不改原厂文件。
3. 原FIFO 128→16 FWFT最先读高位通道，当前RGB565最早像素在低16bit；写入FIFO前反转八个像素通道。11200像素顺序、跨环、满/背压与非空复位均通过原IP RTL仿真。
4. 综合器曾把FIFO同步链实现为SRL8。依据本机官方 `syn-attr-async_reg.html`、`syn-attr-srlstyle.html`，仅对新工程副本添加 `syn_srlstyle="registers"`，并使用小写async_reg属性。重新映射检查同步链均为FF，原厂资料未改；新副本版权与原始SHA保持记录。
5. Interface Designer生成的pt.sdc不会自动进入用户SDC，最初只计时25MHz启动电路；构建器显式合入当前生成的PLL、DDR、LVDS约束，过滤未填值模板行，确认core100MHz与HDMI、PHY时钟都被计时。
6. CDC例外仅作用于确认的单比特同步器首级D及异步复位SR；注册Gray指针跨域路径使用最大延迟约束，第二级和内部运算继续计时。不使用整条时钟域排除来掩盖真实路径失败。

## 验证范围

`sim/check_link.py`使用最终四种不同学习权重，包含同步包RAM、真实控制/CNN/仲裁/显示读取、错误/半帧恢复、一次上传多次按键、安全换帧。`check_fifo.py`使用实际新副本IP RTL，检查11200像素、满/背压/指针回绕/非空复位以及POR/组合键复位。`check_video.py`新增720p30连续三幅完整3300×750时序，检查VGA居中、黑边、同步宽度、帧边界请求、安全窗口及下溢计数/恢复；`check_tmds.py`检查四种消隐控制码、P/N补偿、RGB通道与独立TMDS解码；未验证真实LVDS串行电气或HDMI屏幕。

布局布线、STA、引脚签核与配置指纹以同次报告为准。Efinity的pnr PASS或生成hex，不保证时序已通过；保留实际负裕量并修复，签核之前不交付为上板通过版本。实际串口总时间、DDR校准、四按键、实屏颜色、复位/PLL失锁恢复和稳定处理FPS尚未测；不会自动下载板卡或固化Flash。

Interface Designer保留参考板固定位置产生的 `lvds_rule_tx_distance` 提示：TMDS时钟附近的DDR CK GPIO可能耦合，需要实屏和DDR同时工作时验证。不能据此说“所有警告为0”。Ti60可用256 RAM10和160DSP，完整串口VGA方案接近存储上限，后续摄像头/RISC-V集成需要进一步资源规划。

最终签核：66个使用中的封装引脚；100MHz核心建立+3.810ns，全表建立最小+0.419ns、保持最小+0.031ns。完整资源240 RAM10、144 DSP、26,955 XLR。12个单比特同步首级、521个明确异步复位SR例外、116个已注册Gray首级路径最大延迟约束；Gray起点使用Efinity实际支持的FF|CLK端口，禁止使用无效Q起点后把忽略警告当成通过。后一级仍正常计时。SDC无忽略/无效约束警告。

阶段结果的raw timing、模型/权重/源码/工程配置指纹和bit SHA256在 `build/vga/signoff.json`；每次更改需重新签核。复位链的D端为GND会产生SyncHeadDrivenByNonSeq提示，其功能是异步断言、移位同步释放；输出被新帧覆盖前的RAM内容不可依赖。遗留IV提示来自参考安全配置，bitstream加密未启用，不涉及本机烧写。所有实际警告与未测项保留。
