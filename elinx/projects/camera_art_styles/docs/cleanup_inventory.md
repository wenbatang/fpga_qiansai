# 独立工程中间文件清理审阅（2026-10-23）

## 范围与结论

本文件记录清理前盘点及本次执行结果。候选清单在本地 `../build/cleanup_all_candidates.json`；删除动作与实际释放空间应以主执行器的清理回执为准。盘点覆盖 `xilinx/projects/` 下四个独立工程、`elinx/projects/` 下五个独立工程，以及 `pycode/__pycache__/`。没有进入或修改 demo，也没有把项目目录、最终产物或必要依赖整体列为可删除对象。

候选为 **305 项，共 1329 个文件、898,115,146 字节（约 856.51 MiB）**。已排除所有符号链接、junction 和其他 reparse point；目录候选若包含此类条目则整项跳过。

| 工程/范围 | 候选项数 | 文件数 | MiB |
|---|---:|---:|---:|
| `xilinx/projects/uart_hdmi` | 36 | 121 | 3.38 |
| `xilinx/projects/uart_style_hdmi` | 45 | 86 | 6.95 |
| `xilinx/projects/uart_style_keys` | 29 | 66 | 3.43 |
| `xilinx/projects/uart_style_six` | 31 | 67 | 12.69 |
| `elinx/projects/camera_art_styles` | 57 | 482 | 723.23 |
| `elinx/projects/style_video` | 41 | 300 | 77.34 |
| `elinx/projects/uart_art_styles` | 34 | 113 | 17.34 |
| `elinx/projects/uart_style_keys` | 10 | 24 | 2.82 |
| `elinx/projects/uart_style_tiles` | 21 | 53 | 9.17 |
| `pycode` | 1 | 17 | 0.16 |

## 可清理的白名单

- Python 字节码缓存：`__pycache__/`、`.pyc/.pyo`，以及存在时的 pytest/mypy/ruff 缓存。
- Vivado 临时与缓存：`.Xil/`、项目中的 `*.cache/`、`.ipcache/`。没有删除整个 `*.runs/`、`*.gen/`、`*.srcs/`、`ip_user_files/` 或 Vivado 工程目录。
- Efinity 工作目录：`work_syn/`、`work_pnr/`。保留同级 `outflow/`、接口/时序报告、项目与约束、固件、bit、映射网表和签核回执。
- Questa/XSim 的编译库 `work/`，以及 Icarus 可重新生成的 `.vvp`、存在时的 `.wlf`。保留测试脚本、Testbench、输入/预期 `.mem`、验证 JSON 与日志。
- 存在时的独立 `sdc_rebuild_review/` 重复副本；保留生产 `.sdc`、重建一致性回执、生成器和原始模型。

## 引用审计与必须保留的例外

扫描了 477 个独立工程 JSON 文件。路径匹配发现 19 条候选相关引用：其中 8 条是历史训练记录中的用户目录 VGG 权重路径，位于本次清理范围之外；其余 11 条都属于下面的历史归档。因此已把整个归档排除：

`elinx/projects/uart_style_keys/build/baseline_720p60_20261013/`

该目录的 `archive_manifest.json` 按文件哈希收录了 `vga/work_pnr/` 中五个文件、`vga/work_syn/RUNMAP_ti60_style` 和 `scripts/__pycache__/` 中五个 Python 字节码。删除它们会使历史归档原始清单不完整；此次保留约 1.79 MiB，而不修改历史证明。

最新版 `camera_720_fast/final_review.json` 仍核验 15 个历史发布版本。映射回归 `sim/p720/mapped/verification.json` 还绑定 `build/cnn_pipe_probe/outflow/cnn_pipe_probe.map.v`、探针项目/顶层、实际 RTL、Testbench、配置 `.mem` 和仿真日志；完整 720p 回归绑定 `raw.mem`、`expected.mem` 和对应日志。这些文件均不是本次删除候选。

## 不能按“中间工程”整体删除的内容

- 全部 `build/`、`sim/` 或旧版工程：里面混有签核依赖、源快照和不可混淆的历史 bit。
- `outflow/` 中的最终 bit、映射网表、最终布局布线/接口/时序报告及日志。
- `vendor/`、`ip/`、Sapphire/DDR/D-PHY 生成源及 RAM 初始化通道：属于当前可重建依赖，不能当普通缓存。
- 已认可的模型、训练检查点、风格参考图、输入数据集、图片上传目录。
- Python `.venv/` 等可用运行环境，用户或厂商示例，所有 `.prj/.xpr/.xml` 等项目入口。
- 审计回执及其引用的所有源文件、配置、`.mem`、原始日志。

## Git 上传范围只读审阅

盘点时，已修改的跟踪文件加未忽略的新文件共 561 个、约 9.65 MiB；最大单文件约 2.13 MiB，未见接近 GitHub 100 MiB 单文件上限的候选。Git 候选中未出现 `vendor/` 或 `/ip/` 路径。针对 GitHub token、OpenAI key、AWS access key、私钥头和 URL 内嵌口令进行高置信度模式扫描，没有匹配；该结果不替代逐项变更审阅。

Git 状态还包含用户新放入的 demo10 V9 树、正确原理图 PDF 和摄像头手册；这些不是此次新编写的关键实现。建议本次选择性暂存独立工程、公共 RTL、Python 和说明文档，避免不加区分地 `git add .` 收入厂商例程。默认忽略规则仍排除构建/仿真/权重/配置/C 固件；上传的源码说明必须明确这不是完整、无需本地依赖的工程归档。

## 执行后验证

删除前应再次解析每个绝对路径，确认位于上述九个独立工程或明确的 `pycode` 缓存内，并确认不经 reparse point。使用同一 PowerShell 会话中的 `Remove-Item -LiteralPath`，不跨 shell 拼接删除命令。删除后保存实际成功/失败列表和释放字节，检查最新版及保留发布的现有 audit，确认 bit、RTL、模型和时序/电气回执指纹没有变化。

本文件为清理范围与上传范围审阅，不表示已执行删除、Git 提交/推送、CAD 重建或板卡下载。

## 本次执行结果

2026-10-23已按清单执行同一PowerShell会话的路径验证与Remove-Item：**305项全部删除、0失败，释放898115146字节（856.51MiB）**。每个目标重新解析绝对路径、限定在九个独立工程/明确pycode缓存中，排除reparse与历史归档。完整回执为本地build/cleanup_all_result.json。

删除后最新版720p `build.py audit`和`final_review.py`均PASS，当前bit保持fbaecb588dbe01c85db920e8fdeae6a1525f5abd2f459ad913afbf163d10aa19，15套历史Ti60发布及其源/配置/报告/权重/启动RAM均复核保持。

另检查8个Xilinx现有bit：6个与记录一致；原uart_hdmi/fast和uart_style_six/默认720p两个bit与所选历史signoff指纹不一致，其文件修改时间早于清理。它们未被清理器删除或修改，本次不把旧签核重新写成PASS，也不重建/推荐这些旧bit；本地cleanup_postcheck.json记录了预期与实际指纹。不能把这条历史差异解释为本次清理导致的位流更改。

Python审计采用-B避免重新生成字节码缓存。未修改demo/必要IP，未重新CAD/下载/写Flash。
