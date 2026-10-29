# 模块、接口与数据流

工程入口build/720p/ti60_camera.xml；顶层build/720p/rtl/ti60_camera_ppi_top.sv。此独立工程从camera_art_30复制经核对的板级链路，新增全分辨率C6网络。旧工程、demo V7/V9及style_model均保留。

## 从摄像头到显示器

1. RISC-V启动后保持摄像头受控复位，执行开漏I²C、ID/尺寸检查、V7寄存器配置，最后开流。错误进入安全失败状态。
2. SC431HAI的四lane RAW10经过厂商D-PHY公开PPI与原子异步FIFO，在UI域解析包头/ECC/CRC/RAW10；错误或不完整帧不发布。
3. Bayer预处理将1920×1080原始采集转换为1280×720 RGB565，写入三原图bank之一。只有完整EOF及最终AXI B成功后，才发布最新完整源帧。
4. 作业控制器锁住一份完整源图，锁存本次原画/神经网络模式、风格和输出bank。转换时按四条读取，经过异步FIFO送入独立CNN时钟域。
5. 全分辨率C6逐像素产生输出；每条只写中央320列到同一输出bank。打包队列将8个RGB565组成128bit写拍；最后DDR B完成后才能报告整帧成功。
6. 三输出bank解耦引擎与显示。reader排空旧事务、跨域FIFO退出busy且处于安全消隐窗口后，才ACK并释放旧前台。不会在有效显示区换帧。
7. HDMI按74.25MHz像素时钟连续输出1280×720p60。显示刷新率60Hz与摄像头约30fps、CNN完成FPS分别计数。

## 主要手写模块

| 模块 | 时钟及主要接口 | 功能与关键契约 |
| --- | --- | --- |
| 顶层ti60_camera_ppi_top | 板级25MHz/PLL、MIPI、DDR、TMDS、UART、四键 | 封装厂商IP、复位和板级接口；任何相关PLL失锁使数据流复位 |
| csi_ppi_bridge_recover | UI域，PPI FIFO记录→RAW流 | 包头/WC/ECC/CRC/帧检查，保留SoT诊断和限定空闲边界恢复 |
| Bayer预处理/帧writer | UI域，RAW10→RGB565→AXI128 | 完整1280×720源图；无背压输入发生溢出则整帧作废 |
| video_job_control_fps | UI域，源claim/release、engine、commit/ACK | 三原图/三输出所有权，保留最新风格请求，front和engine不冲突 |
| video_tile_engine_async | UI域，源/输出地址、AXI128、CNN握手 | 四条320核心+16 halo；全部条、全部像素及最终B后完成 |
| video_cnn_async | UI↔CNN，cfg/start稳定邮箱及两组像素FIFO | cfg48位、起点邮箱、请求ACK及完成toggle；稳定参数先送达再START |
| full_view | CNN域，RGB valid/ready、raw标志 | 原图复制或full_kernel；整作业锁存模式，原图不计推理I |
| full_kernel | CNN域，RGB888流、origin_x、cfg、start/done | stem→4组DW/PW→head；原RGB延迟FIFO与自身残差逐像素配对 |
| full_pointwise | CNN域，特征/skip/inside valid/ready，cfg地址/数据 | 1×1卷积，两个输出通道并行、四上下文，固定索引写入避免映射错位 |
| full_dw3x3 | CNN域，特征 valid/ready、start/origin_x | 6通道DW卷积，d=1/2/4/8，三个列bank每拍读三个tap；边界冲突增加读相位 |
| style_line_ram | CNN域，同步读写地址与数据 | 片内行历史；读延迟通过tag同步，停顿不丢像素 |
| full_shared_params | 常量总线 | 冻结共享DW/head学习参数；非运行时任意更新RAM |
| video_control_apb_fast | APB、cfg_ready、IRQ/START | 从ROM生成216个配置写入，验证地址和完成，最后真实ACK后允许运行 |
| axi_write_pair_fps | UI域，两写主AXI仲裁 | 每主一笔、总两笔在途，AW/W成对保序，B响应决定信用归还 |
| video reader/FIFO/raster | UI↔像素域，AXI读取、RGB/DE/HS/VS | 排空/消隐换帧、每像素对齐、欠载可见及下帧恢复 |
| FPS/诊断模块 | UI↔像素域，C/I/H与CAM4 | I只计完整CNN作业；UART115200只输出诊断，不上传摄像头图像 |

## CNN流接口

`clk`为CNN时钟，`reset`高有效，`start`启动一条并重置空间状态；只有空闲且配置完成后发start。`origin_x`为有符号全局起点，第一条含负halo。RGB888总线[7:0]R、[15:8]G、[23:16]B。隐藏特征按通道连续打包，每通道8位。

`valid && ready`才传输一个像素；valid高、ready低时数据必须保持。`done`只在最后输出像素被接受后产生，不等同于DDR已完成；整机完成还要等待全部条及最终写响应。`cfg_valid`配合16位地址、32位数据，系统使用完整有序216次写入；不能把正在运行的模型改写成另一风格。共享常量层不因配置事务被动态覆写。

DW行缓存的读地址/使能通过寄存流水：先算全局反射坐标，再选列bank和冲突相位，行基址也提前寄存。这样避免全局坐标、模3除法和RAM读使能落入一个长组合路径。三个水平tap并行、三行分时；内部区域保持四拍一个DW输出像素，边界多相位和背压按真实情况计入吞吐。

## 时钟、缓冲和固定地址

| 域 | 频率/用途 |
| --- | --- |
| DDR/UI/CPU | UI100MHz；DDR PHY400MHz，保持原厂时钟和电气参数 |
| CNN | 166.667MHz目标；功能吞吐仿真周期6.002ns，略慢于精确目标 |
| HDMI | 像素74.25MHz，720p60；串化由已核对PLL/LVDS实现 |
| PPI字节域 | 来自实际D-PHY，允许LP期间停振；通过异步FIFO进入UI域 |

原图三bank为4/6/8MiB，输出三bank为0/2/10MiB；每幅720p RGB565为1843200B，小于2MiB槽间隔。帧内从左到右、从上到下、无行padding；128bit写拍装8个RGB565，低地址像素在低位。硬件接口的RGB888展开和RGB565截断已包含在独立整数对照中。

CDC约束只针对有证明的首级同步器、Gray最大延迟和稳定邮箱；不使用整组异步切断或无依据多周期。板级peri沿用正确V4原理图配置，资源/时序与79脚12Bank复核共同作为放行条件。

## RISC-V参数

每种风格有效712B、按736B对齐，四风格ROM共2944B；每风格216次配置事务。固件包含在bit内，不需要另下载firmware.bin。当前全C6参数与旧C8的346写入、RF33的365写入不兼容，不能混用固件/ROM/bit。

启动原图，四个KEY依次请求梵高、剪纸、漫画、水墨；KEY1+KEY2约0.5秒回原图，KEY0+KEY3约1秒复位。按键三种显示界面及实际手势识别尚未加入，本版本聚焦全720p轻量化和吞吐。
