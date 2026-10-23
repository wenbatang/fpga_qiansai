# 公共 PPI 摄像头实现

> 2026-10-19已用正确20261012原理图修正两个按键并重新生成bit；当前电气依据、时序与指纹见[最新统一复核](../../../../docs/Ti60_correct_schematic_review.md)。本文2026-10-16的原PDF与签核数据仅保留历史记录，不能当作当前文件指纹。


2026-10-16。新工程入口为 `build/camera_ppi/ti60_camera.xml`，顶层 `rtl/ti60_camera_ppi_top.sv`。这是独立替代实现；旧 `build/camera_vga` 的 CSI5.15 候选及调查材料保留。没有取得易灵思对5.15内部 word_count 稳定窗口的确认，不能把新工程的结果写成旧IP已修复或已获厂商签核。

## 为什么改接口

本机安装的 D-PHY RX5.8 提供公开的 PPI 字节接口。新实现只用这个接口，将四lane数据及关联状态作为同一个44位记录跨域，CSI包头、word count、CRC和RAW10组装全部留在100MHz UI域。原来有争议的 byte2pixel/pixel_bits_cnt 模块不再实例化，不需要假定多位元数据的稳定窗口，也未解密或修改保护IP。

数据流：SC431HAI → 专用MIPI RX/原厂D-PHY → PPI44异步FIFO → 自编CSI RAW10解析 → Bayer2×2合成/裁剪640×480 → 三原画DDR bank → 五层定点CNN → 两风格bank → 安全消隐提交 → HDMI720p30。Sapphire3.4.0仍负责I²C、ID/尺寸读回、真实权重加载、START及PLIC IRQ16。四种学习模型和旧串口工程不变。

## 接口、时钟与错误恢复

- 字节域来自模组，按70MHz约束；四路8bit数据，`RxValidHS/RxSyncHS/RxErrSotSyncHS`各4bit。记录低32位为lane0至lane3数据，随后依次valid、sync、SoT错误。支持lane间0–3拍错位的已测用例。
- 实际Efinix异步FIFO为512×44、FWFT、两级Gray指针同步。不能只同步valid后直接采样原始word count。Gray路径保留物理最大延迟约束，后级同步寄存器正常检查时序。
- D-PHY控制域为100MHz；HS settle/StopState向字节域的8个首级，仅在原生STA确认唯一后继为对应第二级且无组合逻辑后，精确例外到首级D。没有整组异步切断或多周期放宽。
- UI域接受VC0、RAW10；默认1920×1080，每行2400字节，RAW宽度须为16的倍数。每5字节还原4个10bit像素，最早像素放在低10位。输出4像素/拍，带valid气泡。CRC16反射多项式0x8408，初值0xffff；包头ECC检错，单比特错误也拒绝而不纠正。
- 当前范围为**一个CSI包对应一次HS传输**；包尾HS trailing数据等待下一次SoT丢弃。已用厂家TX模型验证这一模式，**尚未实测SC431HAI是否采用相同包/突发关系**。不支持同一HS突发内紧接多个CSI包；若实物为此模式，须扩展解析器并重新仿真/构建，不能直接宣称兼容。
- FS升VS、FE降VS；行数、字数、CRC/ECC、SoT和帧超时共同决定帧有效性。半帧、丢FE、打断包不会发布。FIFO溢出保持传输故障，必须整机复位恢复。普通包错误使当前帧作废，下一完整FS重新同步。

## 已运行的验证

`sim/check_dphy_bridge.py`使用合法Questa模型运行原厂TX与D-PHY RX、实际异步FIFO、自编解析器和Bayer。六组相位、LP接收字节时钟实际停振、慢UI与中途复位用例通过；启动时至多丢弃一不完整帧，首个好帧之后不允许坏帧。`--full`验证1920×1080 RAW10到640×480，3个完整好帧、0坏帧，逐RAW像素独立对照。

`sim/check_ppi_faults.py`覆盖lane偏斜、CRC/ECC错、字数错、包中断、丢帧尾、部分SoT、超时、FIFO溢出与复位恢复，7好帧/6个预期坏帧。已有四模型整数对照、DDR采集/所有权/背压、真实Sapphire运行C固件测试继续核对源码与初始化指纹。数字仿真不模拟亚稳态或证明模拟接口质量。

CAD状态以新目录 `signoff.json` 为准。报告、原生STA链证明、源码/固件/模型/bit指纹均在该目录；旧候选状态不能代替此工程的签核。物理供电跳线、摄像头包模式/Bayer/亮度、真实采集和推理FPS、DDR/HDMI并发、真实CPU中断仍须上板验收。

## 本地复现

所有命令工作目录使用项目自己的构建目录；准备/生成源文件与CAD运行不能并发。先运行 `scripts/generate_dphy_probe.py` 对应的本地工具封装生成D-PHY，再运行 `scripts/prepare_camera_ppi.py`。随后依次运行模块/PPI仿真、`build_camera_ppi.py --flow map`、`--flow interface`、第一次 `--flow route`、`prove_dphy_cdc.py`、第二次 `--flow route`、`prove_dphy_cdc.py --final`。最终审查通过后 `--flow config` 只生成配置文件，`camera_ppi_signoff.py`再核对bit并写入PASS记录。均不连接或烧写板卡。

本轮限制CAD为单任务、4线程。工作区 `.dideignore` 排除厂商资料、build/vendor/IP/仿真等索引范围，`.vscode/settings.json`减少文件监控；未删除资料，也不改变综合源清单。DIDE需重载窗口后观察内存，不能把配置写入当作内存已下降的证据。

保护IP保留版权、仅按本机授权使用；[Efinix D-PHY RX产品说明](https://www.efinixinc.com/support/ip/mipi-dphy-rx.php)及[公开PPI用户指南](https://www.efinixinc.com/docs/mipi-dphy-rx-core-ug-v2.0.pdf)提供接口依据。build/vendor/sim/固件仍按现有Git规则留本地。
