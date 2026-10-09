# 本机构建问题与修复

目标：Vivado 2023.2，`xc7k325tffg676-2`，独立 UART→DDR3→720p HDMI 工程。所有仿真、诊断和构建输出位于项目内部，未烧写板卡。

## 创建失败的原因

1. 参考资料已由用户改为 `xilinx/xc7k325tffg_base/`，原创建脚本仍写旧的中文目录。已改用实际存在的英文目录，并更新来源 manifest 和 Git IP 排除规则。
2. Windows 退出码 `0xC0000135` 出现在进入 Tcl 之前。进程局部 loader trace 显示子进程继承了桌面应用包身份，使用 packaged DLL search path，忽略 Vivado `lib/win64.o` 的 PATH 搜索，因此找不到 `librdi_common.dll` / `librdi_commonmain.dll`。DLL 本身存在且能够加载，不是 HDL 错误，也不能仅归因于中文项目路径。
3. 工程内 `scripts/desktop_process.py` 使用 [Windows 官方桌面应用进程策略](https://learn.microsoft.com/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute) 启动兼容子进程，仅对新进程生效，不修改注册表、系统 DLL 或 Vivado 安装。在普通终端中直接使用常规启动方式。此方式已成功运行 Vivado、xvlog、xelab 和 xsim。
4. Windows 控制台采用 GBK 时，混合编码的厂商日志会使 Python 输出抛 `UnicodeEncodeError`，但已启动的 Vivado 仍会继续。兼容启动器已改用 UTF-8、替换无法解码字符；检查实际 Vivado 日志与退出码，不以 Python 输出中断判断 FPGA 构建失败。

## 首次实现发现的问题（历史过程，随后电气审查又降频）

首次 bitstream 已生成，但不满足时序，不能作为合格交付：WNS −3.929ns、WHS +0.052ns、WPWS −0.158ns。

- **时钟额定速率**：原例程用 BUFG 分发 800MHz；当前器件最小周期要求 1.408ns，实际为 1.250ns。独立 MIG 配置改用 200MHz 输入，由 MIG 内部 PLL 产生 800MHz DDR 和 200MHz UI，内存周期仍为 1250ps。只修改可编辑 XML/IP 参数并重新生成，不修改厂商生成 RTL。生成 RTL 的输入周期 5000ps、PLL 倍频8、DDR输出除2、UI除8，与目标一致。
- **异步复位时序**：MIG UI 域信号驱动像素域复位同步器的 PRE 引脚，异步断言、三级同步释放。首次约束仅从外部按键切路径，导致内部复位仍被按两域同步恢复检查。现在 `cdc.xdc` 只在实现阶段约束映射后的 CLR/PRE 和单比特同步器首级；同步器各级之间的数据路径仍检查。
- **并行时钟相位**：视频 MMCM 原来与 MIG PLL 并列，出现 TIMING-51。现在从 MIG UI 时钟级联视频 MMCM。未使用全域 `set_clock_groups` 掩盖 FIFO Gray 指针约束；保留 XPM 原生最大延迟及 bus skew 检查。
- **重复时钟定义**：板级 XDC 不再重复覆盖 Clock Wizard 的50MHz输入时钟约束。
- **CDC-10 组合复位**：像素域的外部复位、视频锁定、DDR 校准和 UI 复位分别使用三级同步释放，再在像素域组合，不在同步器前混合多个独立复位源。
- **CDC-11 重复同步**：XPM 的 `wr_rst_busy` 内部等待读域复位断言和解除，再回到写域空闲态；原先额外同步 `rd_rst_busy` 形成跨域扇出。顶层现在只用写域 busy 等待完整握手，读域 busy 仍在像素域直接门控。通用 `frame_reader` 接口仍支持其他 FIFO 的单独读 busy；XPM 集成时该输入接0。厂商模型新增断言验证 `wr_rst_busy=0` 时 `rd_rst_busy` 已为0，覆盖启动及中途复位。

## 验证入口与记录

- 模块仿真：`sim/run_checks.py`；记录 `build/logs/module_tests.log`。
- 厂商模型：`sim/run_vendor.py`；记录 `build/logs/vendor_tests.log` / `sim/vendor/`。
- 工程：`vivado/uart_hdmi.xpr`。
- 重建：`create_project.py --build --resume --reset-synth`。
- 更新 IP 参数时另加 `--update-ip`；只改 RTL 时复用已生成的独立 IP。
- 最终报告：`vivado/timing_summary.rpt`、`drc.rpt`、`cdc.rpt`、`bus_skew.rpt`、`methodology.rpt`、`check_timing.rpt`、`utilization.rpt`。

## 电气与逻辑审查后的最终配置

用户确认「Kindex Base7 FMC版」。依据原理图修正为VCCAUX_IO=1.8V/NORMAL、DDR3-800（400MHz DDR / 100MHz UI）、CL6/CWL5。UART和超时计数按100MHz配置；视频保持74.25/371.25MHz。详见[电气与逻辑复核](electrical_logic_review.md)。原来2.0V/HIGH、DDR3-1600版本和SHA256 `7A3C92C65ED2F8A287FD2902A8666FE296F1A36AD959D145F30CEF3BED7428DD` 已被替代，不能作为本板当前交付。

修复packet_rx单独转义字节不触发超时的问题，新增恢复回归。新增真实XPM/MMCM联合仿真：两个完整720p帧逐像素对照，AXI背压、双缓冲消隐期交换，零错误、零欠载。

脚本使用Vivado正式的NORMAL属性表示1.8V。自动审查最初误用LOW标签导致报告阶段失败，已纠正；不影响此前生成的NORMAL实现，但最终以完整退出码0记录为准。Vivado还设置了其自带Python3.8的PYTHONHOME/PYTHONPATH，调用本项目解释器必须使用`-I`隔离启动，否则会产生SRE模块版本冲突。只隔离检查子进程，没有修改全局环境。

工程生成仅在内容变化时写入源文件、约束与配置，避免无变化重复准备触发过期run；继续构建自动检查NEEDS_REFRESH，完成的run不重复launch。构建结束导出`io.rpt`/`pin_audit.tsv`，执行`scripts/check_board.py`，检查全部84个引脚与配置Bank电压。

## 第二轮复核：异常路径

对上一版RTL新增测试，分别复现了`LATE_COMMIT`（DDR响应拖过消隐后在有效区切换前台）与`BAD_BEAT`（错误RLAST拍进入FIFO）；修复后同一测试通过。实现增加寄存的安全换帧窗口、两级同步和提前一行关闭的余量，错过窗口等下一次消隐；FIFO写入前同时检查RRESP与RLAST。改动不涉及板级引脚、I/O标准、供电或PLL频率。详细流程见[电气与逻辑复核](electrical_logic_review.md)。

第二轮模块仿真、异常回归、真实XPM/MMCM正常两帧视频集成均通过。补充三帧长DDR停顿集成：首帧末尾暂停响应、第二帧有效区恢复，期间有效区不发布；计数两帧欠载、第三帧完整921,600个像素正确。这是故障注入验证，不能把故障帧计数隐藏为“零欠载”。

日志：`build/logs/recheck_baseline.log`、`fault_tests.log`、`module_tests.log`、`integration_tests.log`、`integration_late_tests.log`。构建与签核：`build/logs/recheck_signoff.log`。运行入口包含`sim/run_fault_checks.py`与`sim/run_integration.py --late`。厂商原语未改变，OSERDES/PLL单独验证沿用已通过的`vendor_tests.log`；XPM/MMCM与新逻辑的集成已经重新运行。

输出增加`vivado/clocks.tsv`与`build_settings.tsv`，自动确认实际200MHz参考、400MHz DDR、100MHz UI、74.25/371.25MHz视频时钟；实际器件为xc7k325tffg676-2，工具2023.2，UART_BAUD=115200。

`build/build_receipt.json`保存19个RTL/约束/IP参数/构建脚本输入的SHA256、实际工具/器件/generic和bitstream SHA256；构建期间输入不变，交付时再次逐项匹配。上一轮bitstream SHA256 `21EBF59ECE926F6B000EE920B2FF1CF6E4C458E4AA800C58BDC898ED7C5BCE7B`已被本轮逻辑修正版替代。

## 最终结果

最终bitstream生成时间：2026-10-09 16:03:10；签核见`build/logs/recheck_signoff.log`，进程退出码0。WNS +0.893ns、WHS +0.026ns、WPWS +0.143ns，全部失败端点为0，无未约束内部端点。资源：9444 LUT、9085寄存器、4个RAMB36。全部84个布线后端口匹配原理图，无引脚冲突。窗口同步器为CDC-3，XPM bus skew通过。

bitstream：`vivado/uart_hdmi.runs/impl_1/uart_hdmi_top.bit`，11,443,722字节。

SHA256：

```text
F49F6537055ED83CFEDDDF5FB6E838071BD6918DAC87CC13F80EF33AAD1836F1
```

DRC 0错误、5警告：4条BUFC-1（MIG的DQS IBUFDS输出无负载）、1条REQP-1709（MIG PLL输出缓冲类型）。CDC 0严重项、2条MIG CDC-8复位属性警告。方法学无严重项，4条LUTAR-1、1条XDCB-5、32条SERDES复位advisory。未改写原厂生成文件或降级规则。

`check_timing.rpt`无缺失时钟、无组合环、无未约束内部端点。外部提示为复位/UART RX共2项input delay和DDR reset、TMDS时钟/3个数据输出、UART TX共6项output delay；内部时序通过不等于外部接口完整签核。

本次未下载板卡或写入Flash。实板电源、DDR校准、串口完整传图、HDMI显示、启动与按键复位仍需上板验证。

## 最终复核（2026-10-09）

本轮新增异常协议、复位、双缓冲内容及AXI稳定性测试，并复跑模块和DDR异常回归，全部通过。19份构建输入、实际构建参数和上述bitstream的SHA256再次核对一致，无需重新生成bitstream。完整结果见[电气与逻辑复核记录](electrical_logic_review.md)，新增本地日志为`build/logs/final_checks.log`、`build/logs/final_fault_checks.log`。仿真仅使用行为AXI模型，真实MIG校准与完整实板链路仍未验证。

## 独立RGB565提速版（2026-10-09 17:46）

用户随后要求先保持RGB565并尝试10秒以内。独立`vivado_fast`工程已生成：2Mbps串口、16KB包缓存、113个DATA；标准`vivado`产物未覆盖。此后共享源码/生成脚本增加参数，上述标准版指纹为历史记录，新的当前源码签核在`build/fast/`。

实际`UART_BAUD=2000000 UART_PAYLOAD_BYTES=16384`，Vivado 2023.2全流程退出码0；WNS +0.893ns、WHS +0.054ns、WPWS +0.143ns；LUT 13158、FF 9197、RAMB36 4。84个端口和时钟复核通过，DRC/CDC保留既有MIG警告。提速bitstream SHA256为`DEC993B588B3F9589B64392EB770535DF722B2DB9E04B6F653EB0596A4EC671B`。构建输入19份和bitstream最终指纹核对通过。

完整16KB缓存、实际2Mbps UART→收包→DDR行为模型、GUI完整720p的113个DATA与尾包/重传回归通过。34张图片线速预算9.2475–9.7876秒，尚未加USB/DDR/软件等待。未烧写实板，不能据此宣称实测总用时达到10秒。入口、测试和限制详见[RGB565提速说明](transfer_speed.md)。
