# 六风格镜像去框版验证（2026-10-19）

本轮已完成数字验证及两配置新bit签核，未下载或固化。使用同一批art6_v2学习参数，只更改逐层边界取样；训练参数、图像尺寸、UART协议与外部引脚不变。旧补零版97文件含两bit在build/baseline_zero_border_20261019中保留，均经指纹复核。

## 效果与数值

- 原因及规则见[边框修复说明](border_fix_20261019.md)。正常图像逐层reflect-101，长度<=dilation的小轴回退edge；不是裁掉外圈像素。
- 六模型完整1280×720，各2764800个RGB值与独立NumPy int64参考误差0。距边缘31像素以外RGB565输出与原版逐值相同。
- 六模型各4组73×79纯色输入，输出边缘与内部的最大差值为0，无凭空色框。三张原有开发照片，每模型589824个RGB值整数误差0，仍属于开发检查，不是盲测。
- [用户图片前后对比](../../../../pycode/results/art6_border_v1/board_preview/ukiyoe_before_after.png)、[六风格新版](../../../../pycode/results/art6_border_v1/board_preview/six_720p_comparison.png)、[三张照片新版](../../../../pycode/results/art6_border_v1/student/six_styles_comparison.png)均为实际定点软件输出，非AI概念图/实板照片。去框不等于解决小网络纹理偏重与造型表达不足。

## 当前RTL验证

| 范围 | 结果与边界 |
|---|---|
| 六真实学习模型与保留编号 | 71×69×8，39192像素与整数参考一致；6/7回退0，含输入/输出停顿 |
| 小轴边界 | 1×1×8、2×3×8、1×33×8，共320像素一致，验证镜像与edge回退 |
| 初步回归 | 19×17×8，2584像素一致 |
| COBS/UART→DDR→CNN→显示 | 六模型64×8，写响应/错误恢复、重复END不重复推理、最终B和安全消隐提交通过；不是完整尺寸SoC帧 |
| 完整1280×720 CNN | 冻结梵高slot0，921600像素与整数参考一致；17000005周期；完整尺寸仅一模型，不是六种整机实板FPS |
| 按键、PC和显示 | 实现及接口未改；现有按键/控制、FakePort与完整显示回执保留；联合测试覆盖当前新CNN |

所有当前回执绑定当前RTL指纹。build/learning_acceptance.json、两份signoff.json与build/release_audit.json分别记录学习/功能、CAD和独立最终复核。完整CNN仿真的slot0权重也与最终编译ROM逐项核对。

## 布局布线、资源与电平

| 配置 | 输入/CNN | LUT | FF | RAMB36等价 | DSP | setup WNS | hold WHS | pulse WPWS |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 720p | 1280×720 | 25668 | 16251 | 367/445 | 750/840 | +0.206ns | +0.053ns | +0.143ns |
| vga | 640×480 | 25164 | 15921 | 184/445 | 750/840 | +0.461ns | +0.050ns | +0.143ns |

第一轮通用32位镜像计算setup −0.564ns，已拒绝交付。最终采用九tap显式译码、限宽行龄和环形地址，重新跑上述仿真及综合布局布线；没有新增时序例外，没有用降低时钟或多周期掩盖路径。

两配置实际88脚逐项与BaseC FMC原理图核对：Bank14/15=3.3V，Bank32/33=1.5V，VCCAUX_IO NORMAL/1.8V；DDR3-800、200MHz参考、100MHz UI、HDMI74.25/371.25MHz。KEY2/J26、KEY3/E26仍是LVCMOS33输入。无无时钟/内部未约束端点/组合环；两处MIG复位同步器属性提示及既有DSP/BRAM/MIG建议警告保留审查，不称零警告。

异步复位输入以及DDR复位、UART TX、TMDS输出不使用常规外部input/output-delay；内部STA和引脚配置核对不代表板级眼图或电压实测。真实上板效果、完整END ACK用时及FPS尚未验证。720p RGB565在2Mbps 8N1的纯线速下限9.216秒，仍要加协议、推理与消隐时间。本次去框不改变输入尺寸或传输预算。

## 最终产物

- 720p：[bit](../vivado/uart_style.runs/impl_1/uart_style_top.bit)，SHA256 `5d28c2c9e856df0d43e614aaff16a434f59f6ad30c23b9a8299d77ea96a6831c`。
- vga：[bit](../vivado_vga/uart_style.runs/impl_1/uart_style_top.bit)，SHA256 `17ecf121c1cd401d178f1628568cd28f078ab570f750902345f02518dde62295`。

六组检查点及ROM与昨天完全一致；新bit指纹不同。旧四风格37个基线文件、两旧bit和本轮原训练启动源码指纹保持不变。易灵思项目未修改。
