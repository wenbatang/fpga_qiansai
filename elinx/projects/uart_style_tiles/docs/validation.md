# 分条工程验证记录

> 当前按正确20261012原理图修正KEY1=P14、KEY2=N14并重新构建；最新bit/时序/电气依据见[统一复核](../../../../docs/Ti60_correct_schematic_review.md)。下方早期构建数值若不同，以新复核为准。


本轮2026-10-13，Ti60F225 DemoBoard V4 / I3 / Efinity2026.1.132。四种distinct_student_v1权重未改，通用RTL及原Xilinx/VGA基线未改。未下载板卡。

## 完整CAD配置

| 配置 | 输入/输出 | 显示 | RAM10 | DSP | XLR | 最小建立ns | 最小保持ns | 核心建立ns |
|---|---|---|---|---|---|---|---|---|
| 720p | 4条，1280×720 | 720p30 | 171/256 | 144/160 | 30877/60800 | +0.387 | +0.026 | +3.436 |
| vga | 2条，640×480 | 720p30 | 171/256 | 144/160 | 30971/60800 | +0.215 | +0.028 | +3.572 |

资源取整机place报告；CNN行缓存由旧640宽的161块降至352宽的99块。总RAM由旧完整VGA工程240块降至171块，节省69块；目前两配置剩85块RAM、16DSP，不能据此保证未来所有IP一定可直接加入。

- [720p配置](../build/720p/outflow/ti60_style.bit)；[签核与源/模型/配置指纹](../build/720p/signoff.json)；SHA256 `dfae2093b2b13cc33b1a901b1d431c3946cfc774309dab86255112f48a45aef8`。
- [vga配置](../build/vga/outflow/ti60_style.bit)；[签核与源/模型/配置指纹](../build/vga/signoff.json)；SHA256 `d80ea36150647f6d96120302dd13be82322be1c8dd95b428ab25416052c03ae7`。

全部66个使用中的封装引脚、方向、Bank、电平逐项核对V4；DDR/晶振/PLL与原独立V4工程保持一致，UART/按键3.3V，DDR1.5V，HDMI Bank3A1.8V并保留四对P/N补偿。100MHz核心、400MHz DDR PHY、74.25MHz像素、371.25MHz串化都计时；单比特首级12处、异步复位SR521处、注册Gray最大延迟116条，同步链为FF。无忽略/无效SDC警告。

两配置通过各自profile头文件与各自ROM路径构建，共享RTL字节一致；已重新检查720p源指纹未因生成VGA配置而失效。脚本生成配置不等于program，未连接/下载JTAG。

## 实际运行的检查

| 检查 | 结果与范围 |
|---|---|
| check_tiles | PASS；128×24/32核心列，四种真实权重，全部输出与整图整数参考零误差；拼接、图边、phase、AXI背压、末B、RRESP/提前RLAST/BRESP、恢复 |
| check_link | PASS；128×8四条真实模型，COBS/CRC/同步包RAM、一次上传多次换风格、BUSY BEGIN、半帧/ABORT、失败保留前台、重复END、安全消隐提交 |
| check_full_reference | PASS；完整1280×720与640×480，共8个四风格软件案例，最大整数误差0；RGB565量化输入/原图与四风格预览留本地 |
| check_video | PASS；完整3300×750时序，显式VGA居中；720p满画布也已PASS，每刷新921600次读像素、下溢后停止消费及下一帧恢复 |
| check_fifo / check_tmds | PASS；本项目厂商副本11200像素顺序/跨环/背压/非空复位，POR/组合键；控制码、P/N补偿、RGB与独立解码 |
| check_camera | PASS；三个不同完整上传、最新帧、忙/NACK/丢END ACK、两种停止、释放与GUI参数快照；不是真摄像头/串口 |

当前仿真不是完整尺寸RTL吞吐测试。软件reference_seconds只是CPU参考运算时间，不能当成FPGA耗时。实际持续640×480>15fps、720p推理FPS、十秒以内END ACK、DDR校准/HDMI/按键/重置恢复仍待实板测量。

## 性能上限与下一步

缓存容量已经解决，计算吞吐仍需分开优化。模型每像素有1296次普通乘加，另108次相位乘积用移位加法。144DSP×100MHz理论仅14.4G普通乘加/秒；720p×15fps需要约17.92G，尚未计10%分条重叠及管线空闲，因此当前结构不能保证720p>15fps。赛题基础640×480×15fps约需5.97G普通乘加/秒，仍需实板验证有效利用率。

若要720p实时>15fps，需要提高CNN独立时钟、减少每像素排空周期，或调整并行结构；不能仅把DDR UI100MHz直接提高破坏原PHY时钟关系。先接MIPI并完成640×480基础指标，再实现独立CNN时钟/FIFO与连续像素MAC流水，重新逐像素/CDC/STA验证。

SC431HAI实物已确认，ID/模式与完整实施顺序见[camera_next](camera_next.md)。MIPI/RISC-V/动态权重/FPS叠加当前尚未实现。

原例程存在LVDS/DDR CK邻近耦合提示，保留并需实板联合压力验证；复位链D=GND同步释放、原厂RTL以及参考IV配置提示也保留，不宣称零警告。

2026-10-13接口/逻辑专项复查已修正同步属性格式与PLL失锁门控；重新运行整链路、复位/停钟与UART测试，并重新生成两套CAD配置。完整66端口、OE、未分配GPIO与全尺寸DMA独立审查已通过，详见[electrical_logic_review](electrical_logic_review.md)。未下载板卡，耦合/实体供电验证范围仍保留。
