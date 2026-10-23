# Ti60 V4接口电平与逻辑专项复查

> 当前按正确20261012原理图修正KEY1=P14、KEY2=N14并重新构建；最新bit/时序/电气依据见[统一复核](../../../../docs/Ti60_correct_schematic_review.md)。下方早期构建数值若不同，以新复核为准。


2026-10-13，范围为本项目720p与VGA两套实际生成配置。依据本地V4原理图PDF第3页供电、第4页FT4232、第6页按键、第7页DDR、第8/9/10页FPGA引脚、第13页HDMI耦合网络、第14页晶振；已提取并视觉核对。所有临时表格/渲染留在`build/electrical_review/`。未下载板卡。

## 结论与范围

没有发现当前66个使用中的封装引脚电压标准与V4供电相冲突、UART方向接反、按键误配置输出，或未分配GPIO主动驱动的配置。DDR总线/输出使能与原厂V4接口一致，HDMI四对P/N交叉补偿正确。该结论是配置与逻辑审查，不是实体供电、电流、温升或信号完整性测量。

| 接口 | 实际配置 | 板级核对 |
|---|---|---|
| UART | RX R4输入、TX R14输出；BL/BR 3.3V LVCMOS | FT4232 CDBUS0经33Ω到R4，CDBUS1接R14；板载USB链路电平一致 |
| KEY0/1/2/3 | C4/P14/N14/A3，仅输入，3.3V | 外部10k上拉，按下接地，低有效；两级同步/10ms去抖/长按去重 |
| 晶振 | J2 25MHz、H2 27MHz；1A/1B 1.8V输入 | 晶振1.8V供电；未用R13的50MHz，不驱动晶振网络 |
| DDR | 3B/4A/4B 1.5V SSTL；DQ16位、DQS差分双向 | VDD/VDDQ1.5V；VREF分压约0.75V；VCCAUX1.8V；CK400MHz/UI100MHz |
| HDMI输出 | 3A 1.8V专用LVDS串化；74.25/371.25MHz | TX连接器及50Ω/0.1µF耦合网络；四对FPGA P/N与连接器P/N交叉，RTL全字取反 |
| 其他IO/MIPI | 未分配GPIO为输入弱上拉；无未分配主动输出；MIPI注册表为空 | 未启用摄像头/I2C/其他高速收发器；2A/2B跳帽电源不能据此算已验证 |

本版仅使用板载FT4232 UART。若外接串口，电平须3.3V并共地；不可直接连接5V TTL或RS-232正负电压信号。HDMI接板上输出接口。

## 本轮发现并修复

1. 旧适配脚本只匹配无空格的`ASYNC_REG="TRUE"`，漏掉UART与reset_sync中的带空格属性写法。修正为按空白可变格式转换，使用Efinity原生`async_reg="true"`、`syn_srlstyle="registers"`。当前实际网表确认3个UART同步FF和9个复位同步FF带原生async_reg，没有映射成SRL。syn_srlstyle由综合阶段消费，检查实际EFX_FF而不错误要求其在网表继续保留。
2. 新增PLL停钟且CAL_DONE保持旧值的极端数字测试，复现旧顶层像素复位未覆盖核心/DDR PLL失锁。现在任何一个PLL失锁都会复位DDR控制器、UI与像素域，避免依赖厂商内部是否及时清零CAL_DONE；各域按三个时钟沿同步释放，DDRCAL成功后才启动。HDMI失锁也复位全链路，避免单独复位一个握手端残留旧请求。PLL本身复位仍由独立25MHz启动逻辑控制，没有锁定条件互相等待的环路。

失锁或组合键复位后，原画/风格的有效标记及作业状态清除，需要重新上传完整图片。不得把复位前DDR内容当作有效源帧。

## 逻辑检查与实际测试

- 原图0x00400000；显示bank0/1为0x00000000/0x00200000。720p一帧1,843,200字节，VGA614,400字节，均小于2MiB bank，原图/两显示bank无重叠。
- 独立穷举完整尺寸DMA：720p115,200个128bit输出字、VGA38,400字，全部且仅写一次；有效源读段在帧内、256字节对齐、16拍突发不跨4KB。
- 实际DDR所有IO/OE端口绑定原控制器，未改DQ/DQS输出使能极性或PHY时钟。DDR内核包含厂商保护内容，未解密；检查来源一致、外部复位/时钟/接口及CAD时序，不能称其内部已逐行审阅或模拟真实DDR校准。
- 四种真实模型整链路仿真重新PASS：COBS/CRC、同步包RAM、源图缓存、四键、忙BEGIN/半帧/ABORT、重复END、错误保留前台、安全消隐提交。分条算子与原模型未改变，原完整尺寸软件零误差结论继续适用。
- 停钟/非边沿异步复位立即断言、没有时钟不释放、精确三边沿同步释放PASS；实际顶层所有PLL失锁、旧CAL_DONE、停钟与启动校准门控PASS。
- 100MHz/2Mbps UART六种字节模式及错误停止位拒绝PASS。
- 现有FIFO顺序/跨环/复位、TMDS控制码/P-N/RGB解码、完整720p30时序/下溢恢复记录保持有效：这些数据通路源文件未更改。

## 本轮最终配置

| 配置 | 建立最小ns | 保持最小ns | 核心建立ns | 使用封装引脚 |
|---|---|---|---|---|
| 720p | +0.387 | +0.026 | +3.436 | 66 |
| vga | +0.215 | +0.028 | +3.572 | 66 |

- [720p当前bitstream](../build/720p/outflow/ti60_style.bit)，SHA256 `dfae2093b2b13cc33b1a901b1d431c3946cfc774309dab86255112f48a45aef8`；[同次签核](../build/720p/signoff.json)。

- [vga当前bitstream](../build/vga/outflow/ti60_style.bit)，SHA256 `d80ea36150647f6d96120302dd13be82322be1c8dd95b428ab25416052c03ae7`；[同次签核](../build/vga/signoff.json)。

未修改模型、权重、原Xilinx工程或原Ti60 VGA基线。复查前两套分条bit、源文件与报告留在`build/pre_electrical_review_20261013/`；以当前bitstream指纹为准。

## 尚不能由文件检查排除的项目

Interface Designer仍提示`lvds_rule_tx_distance`：HDMI时钟对与DDR CK所在GPIO较近，可能耦合。保持V4原厂引脚与驱动参数，不能通过忽略警告来宣称已消除，需要DDR/HDMI同时工作时实板校准与误码/图像稳定性检查。实际电源轨、跳帽、焊接/连接、电流与温升未测；如果异常应停止运行排查。MIPI未启用，该复查不覆盖后续摄像头端口供电。

## 全部66端口独立核对表

表中DDR单端信号的`.P/.N`表示该单端信号选用差分对中的哪一个物理pad，不代表逻辑取反。HDMI与DQS/CK则是实际差分对。

| 信号 | 球位 | 方向 | Bank | 电压 | 标准 |
|---|---|---|---|---|---|
| CLK_25M.P | J2 | Input | 1A | 1.8 V | 1.8 V LVCMOS |
| CLK_27M.P | H2 | Input | 1B | 1.8 V | 1.8 V LVCMOS |
| ddr_addr[0].N | K15 | Output | 3B | 1.5 V | 1.5 V SSTL |
| ddr_addr[10].P | H10 | Output | 3B | 1.5 V | 1.5 V SSTL |
| ddr_addr[11].N | J10 | Output | 3B | 1.5 V | 1.5 V SSTL |
| ddr_addr[12].P | L12 | Output | 3B | 1.5 V | 1.5 V SSTL |
| ddr_addr[13].N | J12 | Output | 3B | 1.5 V | 1.5 V SSTL |
| ddr_addr[1].N | L13 | Output | 3B | 1.5 V | 1.5 V SSTL |
| ddr_addr[2].P | K12 | Output | 3B | 1.5 V | 1.5 V SSTL |
| ddr_addr[3].N | K6 | Output | 4B | 1.5 V | 1.5 V SSTL |
| ddr_addr[4].P | L11 | Output | 3B | 1.5 V | 1.5 V SSTL |
| ddr_addr[5].P | K8 | Output | 4A | 1.5 V | 1.5 V SSTL |
| ddr_addr[6].P | K10 | Output | 3B | 1.5 V | 1.5 V SSTL |
| ddr_addr[7].N | J13 | Output | 3B | 1.5 V | 1.5 V SSTL |
| ddr_addr[8].N | K11 | Output | 3B | 1.5 V | 1.5 V SSTL |
| ddr_addr[9].N | J14 | Output | 3B | 1.5 V | 1.5 V SSTL |
| ddr_ba[0].N | L7 | Output | 4B | 1.5 V | 1.5 V SSTL |
| ddr_ba[1].N | L9 | Output | 4A | 1.5 V | 1.5 V SSTL |
| ddr_ba[2].P | K14 | Output | 3B | 1.5 V | 1.5 V SSTL |
| ddr_cas_n.N | M15 | Output | 3B | 1.5 V | 1.5 V SSTL |
| ddr_ck.N | H15 | Output | 3B | 1.5 V | 1.5 V Differential SSTL |
| ddr_ck.P | J15 | Output | 3B | 1.5 V | 1.5 V Differential SSTL |
| ddr_cke[0].N | L8 | Output | 4A | 1.5 V | 1.5 V SSTL |
| ddr_cs_n[0].N | M8 | Output | 4B | 1.5 V | 1.5 V SSTL |
| ddr_dm[0].P | M9 | Output | 4A | 1.5 V | 1.5 V SSTL |
| ddr_dm[1].P | R8 | Output | 4B | 1.5 V | 1.5 V SSTL |
| ddr_dq[0].P | R9 | Bidirectional | 4A | 1.5 V | 1.5 V SSTL |
| ddr_dq[10].P | R6 | Bidirectional | 4B | 1.5 V | 1.5 V SSTL |
| ddr_dq[11].P | N8 | Bidirectional | 4B | 1.5 V | 1.5 V SSTL |
| ddr_dq[12].N | P6 | Bidirectional | 4B | 1.5 V | 1.5 V SSTL |
| ddr_dq[13].P | N6 | Bidirectional | 4B | 1.5 V | 1.5 V SSTL |
| ddr_dq[14].P | R5 | Bidirectional | 4B | 1.5 V | 1.5 V SSTL |
| ddr_dq[15].N | P5 | Bidirectional | 4B | 1.5 V | 1.5 V SSTL |
| ddr_dq[1].N | M10 | Bidirectional | 4A | 1.5 V | 1.5 V SSTL |
| ddr_dq[2].P | R10 | Bidirectional | 4A | 1.5 V | 1.5 V SSTL |
| ddr_dq[3].N | P9 | Bidirectional | 4A | 1.5 V | 1.5 V SSTL |
| ddr_dq[4].N | P12 | Bidirectional | 4A | 1.5 V | 1.5 V SSTL |
| ddr_dq[5].P | N10 | Bidirectional | 4A | 1.5 V | 1.5 V SSTL |
| ddr_dq[6].N | P10 | Bidirectional | 4A | 1.5 V | 1.5 V SSTL |
| ddr_dq[7].P | P11 | Bidirectional | 4A | 1.5 V | 1.5 V SSTL |
| ddr_dq[8].N | P8 | Bidirectional | 4B | 1.5 V | 1.5 V SSTL |
| ddr_dq[9].N | M6 | Bidirectional | 4B | 1.5 V | 1.5 V SSTL |
| ddr_dqs[0].N | R11 | Bidirectional | 4A | 1.5 V | 1.5 V Differential SSTL |
| ddr_dqs[0].P | R12 | Bidirectional | 4A | 1.5 V | 1.5 V Differential SSTL |
| ddr_dqs[1].N | P7 | Bidirectional | 4B | 1.5 V | 1.5 V Differential SSTL |
| ddr_dqs[1].P | R7 | Bidirectional | 4B | 1.5 V | 1.5 V Differential SSTL |
| ddr_odt[0].P | M7 | Output | 4B | 1.5 V | 1.5 V SSTL |
| ddr_ras_n.P | M14 | Output | 3B | 1.5 V | 1.5 V SSTL |
| ddr_reset_n.N | H11 | Output | 3B | 1.5 V | 1.5 V SSTL |
| ddr_we_n.P | L15 | Output | 3B | 1.5 V | 1.5 V SSTL |
| style_keys_n[0] | C4 | Input | TL | 3.3 V | 3.3 V LVCMOS |
| style_keys_n[1] | P14 | Input | BR | 3.3 V | 3.3 V LVCMOS |
| style_keys_n[2] | N14 | Input | BR | 3.3 V | 3.3 V LVCMOS |
| style_keys_n[3] | A3 | Input | TL | 3.3 V | 3.3 V LVCMOS |
| tmds_tx_clk.N | H12 | Output | 3A | 1.8 V | 专用LVDS |
| tmds_tx_clk.P | H13 | Output | 3A | 1.8 V | 专用LVDS |
| tmds_tx_data0.N | F15 | Output | 3A | 1.8 V | 专用LVDS |
| tmds_tx_data0.P | G15 | Output | 3A | 1.8 V | 专用LVDS |
| tmds_tx_data1.N | G14 | Output | 3A | 1.8 V | 专用LVDS |
| tmds_tx_data1.P | H14 | Output | 3A | 1.8 V | 专用LVDS |
| tmds_tx_data2.N | F13 | Output | 3A | 1.8 V | 专用LVDS |
| tmds_tx_data2.P | G13 | Output | 3A | 1.8 V | 专用LVDS |
| uart_rx | R4 | Input | BL | 3.3 V | 3.3 V LVCMOS |
| uart_tx | R14 | Output | BR | 3.3 V | 3.3 V LVCMOS |
| verf0.P | K7 | Input | 4A | 1.5 V | 1.5 V SSTL |
| verf1.P | L6 | Input | 4B | 1.5 V | 1.5 V SSTL |
