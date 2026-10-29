# 数据流、显示模式与主要接口

## 完整帧工作流

1. 25MHz启动保护释放PLL；各时钟域同步释放复位。DDR校准成功后CPU读SC431HAI ID、配置1080p RAW10四lane、检查尺寸/VTS及曝光，加载四风格中的初始模型，再受控开流。失败进入摄像头复位/I²C释放/采集禁止状态。
2. 专用D-PHY RX通过公开PPI输出字节；原子异步FIFO传入100MHz UI域。PPI桥检查VC/RAW10、包头、ECC、CRC和长度；坏帧不发布。保留此前SoT恢复实现，不修改厂商保护IP。
3. Bayer预处理将1080p源转换成1280×720 RGB565，两个像素/有效拍进入打包FIFO，再由采集writer通过AXI128写DDR原图bank。只有完整EOF和最后写响应均成功才发布。
4. 原图池三个bank分别供采集、最新完整帧和推理锁定使用。CPU看到完整源后启动作业。作业控制器领取源、选择空输出bank并启动引擎。
5. 原图模式直接复制完整帧；风格/对比模式依次读取四条352×720输入，中央320列有效、左右16列halo。100MHz DMA经异步FIFO供166.667MHz CNN，每个源像素独立计算。边界使用全局reflect101，条带不单独发布。
6. CNN原RGB对齐FIFO中保存的是与当前输出相同源帧、相同坐标的RGB。对比模式在核心输出处选择全局x<640为原RGB、其余为风格RGB。这样无需延长DDR原图bank锁定，也不用第二套显示读口。
7. 全部四条写完且最终AXI B返回后，作业完成、释放源bank，输出进入完整帧队列。三个输出bank可供前台/待显示/正在计算并行使用。
8. 显示reader排空旧读、复位像素FIFO，并等待安全消隐窗口后ACK；此时提交新bank、源帧号及对应的模式/风格标签。HDMI标准720p60持续重复最近完整帧，不能将刷新当新推理帧。

## 时钟与复位

| 域 | 时钟 | 内容 |
|---|---|---|
| ref | 25MHz/27MHz | 启动、长按复位、PLL参考 |
| PPI byte | 约70MHz，可能停振 | D-PHY输出及原子FIFO写侧 |
| UI | 100MHz | CPU/APB、PPI解析、预处理、DDR仲裁、按键、DMA |
| CNN | 166.667MHz | 定点CNN、核心行缓存、原RGB对齐 |
| DDR PHY | 400MHz | 厂商DDR控制器/PHY |
| HDMI | 74.25MHz像素/约371.25MHz串化 | 1280×720、1650×750、正同步极性 |

按键经过两级同步与10ms消抖；KEY3在独立25MHz域按住约1秒整机复位。CDC使用原子FIFO、请求/应答toggle及稳定邮箱，不直接采样多位总线。Gray保留最大延迟，D-PHY首级例外必须有实际唯一二级拓扑证明；不增加整组异步切断或无依据多周期。

## DDR所有权

| 类型 | 地址 | 释放条件 |
|---|---|---|
| 输出0 | 0MiB | 不属于前台、队列或引擎 |
| 输出1 | 2MiB | 同上 |
| 原图0/1/2 | 4/6/8MiB | 源池按采集/发布/锁定所有权管理 |
| 输出2 | 10MiB | 与输出0/1一致 |

每帧1280×720×2=1843200B，2MiB槽有足够空间。行序从左到右、从上到下，stride2560B，AXI128每拍8个RGB565像素，16拍读取突发。写事务最多两笔跨主机在途，真实B释放信用；完成屏障不能省略。最新完整源帧策略可能主动跳过中间帧，需记录采集、处理、跳帧、错误和显示欠载，不能宣称无丢帧。

## 主要模块接口

| 模块 | 时钟与主要输入 | 输出/职责 |
|---|---|---|
| `board_boot` | ref时钟、低有效四键 | `reset_n`；上电等待、KEY3长按，其他键不复位 |
| `style_keys47` | UI、reset高有效、keys_n | event_valid/event_style、display_mode；0原图/1风格/2对比，raw/split派生 |
| `video_control_apb_fast` | UI、APB、I²C输入、作业状态 | 真实CPU寄存器、开漏释放信号、模型cfg、START/IRQ；busy时不覆盖正在使用的模型 |
| `source_frame_pool` | UI、allocate/publish/claim/release | 三源bank所有权、完整帧号、跳帧统计 |
| `camera_frame_writer_720` | UI、采集FIFO | AXI写及最终B后publish，坏帧abort |
| `video_job_control` | UI、START、claim ACK、done/error、commit ACK | 领取源、输出bank、完整帧队列、完成IRQ；reader晚ACK才释放旧前台 |
| `video_tile_engine_async` | UI+CNN、源/输出地址、style6、raw_mode、cfg | 整帧DMA；锁存模式，跨条带保持，最终B后done；错误先排空 |
| `video_cnn_async` | UI+CNN、像素ready/valid、原子配置邮箱 | 两域复位/FIFO、cfg ACK、启动完成toggle；style[5]复用为split标志，低2位为真实风格 |
| `full_kernel` | CNN、start、origin_x、RGB ready/valid、split_mode | 全分辨率神经网络，原RGB FIFO同像素对齐、全局左右分割 |
| `full_pointwise` | CNN、1×1特征/skip、ready/valid、cfg | 两输出通道/拍、四上下文；含stem、PW、head，停顿保持输出 |
| `full_dw3x3` | CNN、特征ready/valid、origin_x、cfg | 三列BRAM银行并行三tap，冲突第二读相，流水累加及反射边界 |
| `full_parameter_bank` | CNN、cfg_valid/address/data | 运行时有符号权重/偏置/shift；固定索引写者，完整模型加载后才START |
| `frame_reader` | UI、完整输出队列、消隐请求 | AXI读、显示FIFO写、换帧ACK；旧读和FIFO退出后才安全提交 |
| `video_raster60` | pixel、FIFO像素/空状态 | HS/VS/DE、RGB、坐标、欠载计数；标准720p60 |
| `fps_snapshot` | UI计数、pixel域消隐 | 稳定邮箱传递实际C/I到像素域，重复刷新不计I |
| `camera_view_uart` | UI与33个诊断字段 | 115200、每秒CAM5，单向诊断，不接受手势命令 |

ready/valid接口只在两者为1时传输；输出valid且ready=0期间数据保持。复位高有效模块由各自域同步释放。所有延迟由valid/tag同步传递，不把固定周期假设跨越背压。

## CAM5与PC交互边界

前32项延续CAM4，最后mode字按低位：raw0、engine_raw1、loaded_style2–7、requested_style8–13、front_raw14、请求显示15–16、前台显示17–18、作业显示19–20、前台风格21–22。后三组模式在不同阶段反映实际状态，不能把请求模式当作已显示模式。`pc/camera_view.py`只读解析。

PC `gesture_demo` 单独从USB摄像头取原图、MediaPipe提取21点、规则分类1–4、4秒门控确认并在PC改变风格。其确认不驱动当前FPGA。若后续接板端手势，必须把当前实际前台模式、源帧身份和命令确认协议一起设计。
