# 本轮清理与分支上传范围

用户本轮授权清理不重要的中间文件，并提交、推送到既有 `imezpy` 分支。`main` 不变；厂商demo V7/V9、用户的 `style_model` 参考目录不修改、不加入本次提交。

## 清理

扫描715份JSON来源/签核记录、3568条绝对路径引用后，删除新交互工程 `sim/` 下20个未被引用的Questa编译 `work/` 库，共383文件、1105059808B，约1.03GiB。每个目标先验证在本项目sim目录内、无符号链接或junction，且不含源码、学习参数、bit、初始化数据、报告或日志。没有删除原始仿真输入、验证回执、原始日志、实际映射网表、IP、工程配置和可用bit。

清理计划和回执只留本地：`elinx/projects/camera_art_interactive/build/cleanup_repository_20261030_{plan,result}.json`。`tools/cache_inventory.py` 只负责只读盘点，不提供删除接口；下次清理仍须审查具体目录。之前一轮删除约2.71GiB的6个编译库属于先前清理，不计入本次1.03GiB。

## 上传

本次选择此前尚未提交的以下关键改动：

- RF33帧率实验、三源/三输出缓冲、写仲裁和相关说明。
- 独立 `camera_art_30`、`camera_full720_30`、最新 `camera_art_interactive` 的手写RTL、Python工具、README和架构图。
- `pycode/full720_style`、`pycode/painterly_style` 的训练、定点参考与导出代码，以及 `pycode/gesture_demo` 主机摄像头手势演示。
- 工作区约束、Ti60使用指南、依赖清单和忽略规则。

本地保留权重、数据集、图片、训练结果、bit、C/ASM固件、约束、IP、工程XML、vendor、环境与仿真产物。导出为Verilog的 `tiny_shared_params.sv` / `full_shared_params.sv` 也属于学习参数，不上传。本仓库遵循既有源码上传策略，**不是包含所有本地依赖的完整可重建工程归档**。

## 最新版本

入口为 `elinx/projects/camera_art_interactive/README.md` 和 `architecture.html`。本地bit的SHA256为 `9c6d490b2354fa84202c07772671aea949b5cde4768cc04f959418ec1e26858c`，21类验证、79脚/12Bank和原生STA已签核。清理后fresh审核再次PASS，记录 `build/post_cleanup_repository_review.log`；清理与Git上传不等于重新上板，实际画质与持续30fps仍待实测。

本次提交范围共284个源码/文档文件，约1.4MiB；逐项检查文件扩展名及目录排除，无厂商参考目录、构建、仿真或模型文件混入。

三份独立工程继承的 `rtl/hdmi_encoder.sv` 带有相同的历史行尾空格，按原字节保留以维护已有签核指纹，不为格式化重写生产源码；其他暂存文件通过空白检查。
