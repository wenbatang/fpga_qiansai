# CSI 5.15 跨域调查（2026-10-16）

结论：已将问题从整机隔离，并验证控制方向 8 条路径是两级同步链的首级采样。独立 STA 会话中的精确首级例外试验有效，未切断第二级时序。仍需确认的是原始 `word_count` 到像素计数器的 16 个寄存器端点及其稳定采样窗口。生产 RTL、CSI 版本、SDC、模型和 bit 均未更改；整机继续保持未签核。

## 新找到的官方依据与版本边界

- [CSI RX 用户指南 v3.3，第21页](https://www.efinixinc.com/docs/mipi-csi2-rx-core-ug-v3.3.pdf)：新增时序约束章节，说明 IP 各时钟域按异步设计、内部处理 CDC，要求配套时钟关系约束。第27页修订项 `DOC-2988` 对应 **IP 5.16 / 2026年7月**。
- [v3.4，第21、27页](https://www.efinixinc.com/docs/mipi-csi2-rx-core-ug-v3.4.pdf)：保留该说明；文档最新对应 IP 5.17。不能因为文档变新，就认为本机的 5.15 已升级或已被追溯确认。
- 本机 `ip_component.xml`、实际 `settings.json` 均为 **5.15**。该版本生成的开发板示例也包含整组 `set_clock_groups -exclusive`，属于厂商设计意图的线索；它没有给出这条元数据路径的采样使能、稳定窗口或物理延迟上限。
- 旧 v3.2 对应 5.13，缺少新增约束章节。此前只参考旧指南不完整；新版说明让调查方向更明确，但版本差异仍须处理。

全系统的 `core_clk` 同时供给 CPU、DDR UI、CNN 和 CSI；没有把例程中的整组时钟例外搬到整机。也没有添加任意多周期约束。

## 最小工程实际复现

位置：`build/csi_cdc_515/`。沿用 Ti60F225 **I3**、当前完整 CSI 5.15 文件、四 lane RAW10、侧带打开、70MHz 字节时钟预算和 100MHz 控制/像素时钟。只保留 CSI、复位同步与像素校验和输出；移除 DDR、CPU、CNN、HDMI 数据通路。接口取自当前 V4 工程，仅供 CAD 诊断，不是上板应用。

实际完成 Efinity 2026.1.132 综合、Interface Designer、布局布线、原生 STA；资源 **11 RAM / 0 DSP**。同域 setup：byte **+8.664ns**、core **+4.873ns**。双向异步关系仍复现负裕量：

| 范围 | byte → core | core → byte |
|---|---:|---:|
| 当前整机原约束 | −0.561ns | −0.528ns |
| CSI 最小工程，争议路径保持普通检查 | −0.472ns | −0.529ns |
| 最小工程的限定 CDC 例外实验 | −0.472ns | +9.277ns |

最后一行仅是独立 STA 会话的诊断实验，不是新的整机时序或 CDC 签核。跨域普通建立时间预算为 **0.002ns**；实际正向数据路径只有约零点几纳秒。不能把这类异步采样问题当作 CNN 算力不足，也不能通过改成更凑巧的时钟数值来消除报告。

### 已确认的控制同步链

用厂商公开 STA 接口导出首级到所有可达寄存器的路径，没有解密、导出或改写保护体：

```
HS_ENA / RxStopState（core）
        ↓ 异步首级采样
RxHS_settle_1P / RxStopState_1P（byte）
        ↓ 无组合逻辑，每个首级只有一个报告中的寄存器终点
RxHS_settle_2P / RxStopState_2P（byte）
```

四 lane、两类信号共 **8 条链**，最小工程和整机都确认。整机级间最小 setup **+13.085ns**；最小工程 **+13.402ns**。这些是拓扑及物理时序证据，不包含模拟亚稳态分析或定量 MTBF 认证。

限定实验仅对已验证的 8 个首级 D 引脚、已命名侧带同步器首级做例外；FIFO 的 22 位 Gray 指针仍各有 **9.8ns** 最大路径延迟约束，后级仍按本域时钟检查。实验文件 `build/csi_cdc_515/scoped_experiment_only.sdc` 未加入生产工程。

### 尚未闭合的元数据传输

原生 STA 显示原始 `word_count` 可直接影响 `byte2pixel_inst/pixel_bits_cnt[18:3]`，共 **16 个唯一寄存器端点**。IP 另外存在名为 `syncreg_wordcount` 的同步链，但仅凭名字或像素侧带正确，不能证明计数器这条直接路径的采样条件。

必须明确：原始行长度在哪个 byte 边沿更新、在哪个 pixel 条件下装载、该条件如何跨域，以及源数据在采样前后至少稳定多久。之后才能决定采用有依据的限定延迟约束，或使用厂商修复后的实现。没有把这16条路径设为 false path。

## 新增功能压力仿真

Questa 10.7c 合法运行当前 CSI 5.15 与厂商 TX 模型，经公开端口检查 RAW10 像素、行长度侧带、完整帧与 Bayer 模块。独立接收字节时钟在 LP 期间实际停振，TX 参考时钟继续运行；门控使能在下降沿更新，避免人为制造窄脉冲。

| 用例 | 完整好帧 | 坏帧 |
|---|---:|---:|
| 自由运行参考 | 50 | 0 |
| 停振，phase 参数 1ps | 50 | 0 |
| 停振，phase 参数 4999ps | 50 | 0 |
| 停振，phase 参数 7000ps | 50 | 0 |
| 停振，phase 参数 9999ps | 50 | 0 |
| 停振，像素时钟约60MHz | 29 | 0 |
| 停振，中途复位并重新收帧 | 46 | 0 |

总计 **325 个小尺寸好帧、0 坏帧**。复位用例要求复位后额外收到至少两帧，不能依靠复位前的结果通过。现有完整1080p输入到640×480/360验证记录继续保留。

限制：本批输入为64×16、固定RAW10/WC80；零延迟数字仿真不模拟亚稳态、物理HSIO FIFO和电气行为，也未覆盖连续不同包长。原有测试虽然把 IP 配成 Discontinuous，但其接收字节参考时钟一直自由运行；本次才补上显式停启覆盖。不能将这些仿真当作内部稳定窗口证明或实板成功。

## 已准备的厂商核对问题

本地自包含复现资料位于 `build/csi_cdc_515/support_reproducer/`，未发送给任何人，也未上传仓库。

1. `DOC-2988` 的异步设计/约束说明能否用于 **5.15**？5.15→5.16 是否改变了 word_count 的 CDC 实现，还是仅补充说明？需要对应版本的正式依据。
2. `word_count → pixel_bits_cnt[18:3]` 的采样使能与最小稳定时间是什么？请给出可核对的时序说明、推荐的精确约束及其适用参数，而非仅提供整组时钟切断。
3. 四 lane 的 `RxHS_settle_1P/2P`、`RxStopState_1P/2P` 是否是厂商预期同步链？5.15 综合是否保留正确同步属性和必要的布局要求？
4. 新版指南第19页提出低速下的 HS_TRAIL 考虑；按本工程70MHz预算、四lane，建议值公式得到约128.6ns。该条是否适用于5.15？实际SC431HAI时钟和拖尾时间尚未测量，不能直接修改未知摄像头寄存器。

若厂商确认当前版本的稳定窗口及约束，即可把经过核对的精确规则加入独立工程并重新布局布线；若属于5.15实现缺陷，保留基线，仅验证指定修复版本。后续还须重新核对全部79脚、所有时序关系、模型/固件/源码指纹，才可生成可交付 bit。

## 复现与证据

```powershell
python scripts/investigate_csi_cdc.py --flow prepare
python scripts/investigate_csi_cdc.py --flow map
python scripts/investigate_csi_cdc.py --flow interface
python scripts/investigate_csi_cdc.py --flow route
python scripts/investigate_csi_cdc.py --flow sta
python scripts/investigate_csi_cdc.py --flow scoped-sta
python scripts/investigate_csi_cdc.py --flow production-sta
python sim/stress_csi_cdc.py
python scripts/summarize_csi_cdc.py
```

`production-sta` 只读现有整机数据库并导出新命名的调查报告；不重新生成整机或修改其约束。`prepare` 会重建最小工程配置，须在其他诊断 CAD 流程停止后执行。

机器可核对结论与指纹：`build/csi_cdc_515/investigation.json`。原生路径报告在同目录 `outflow/`；压力仿真与输入指纹在 `sim/csi_cdc_stress/verification.json`。脚本检查报告非空、端点未达到截断上限、8条首级唯一后继、后级时序为正，并拒绝把工具退出码0但未写出报告的情况算作成功。
