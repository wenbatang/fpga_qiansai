# 技术报告

入口为 `main.tex`，交付预览为 `main.pdf`。章节遵循官方模板：独立封面（第1页）、两页项目速览（第2–3页）、目录/摘要、作品概述、系统组成及功能、完成情况和性能、总结、参考文献。正文按主要模块说明输入输出、时钟握手、作用与实现。实物照片与连续帧率测量各有专门的记录栏。

## 生成内容

- `assets/generated/system.png`、`network.png`、`style_principle.png`：内置imagegen工具生成并经技术复核的白底框架图。工具没有“Image2.5”型号选择参数，不能声称指定型号；提示词和修订说明见 `assets/generated/PROMPTS.md`。
- `assets/comparisons/style_00_pairs.png` 至 `style_09_pairs.png`：两张公开名画各运行十风格，全部来自最终模型真实720p整数输出；不是图像生成工具替代效果。每图含两组原图/输出，来源及裁剪见 `verification.json`。
- `assets/source/sources.json`：两张原作的公共领域来源、下载URL及原始指纹。94MB原始《蒙娜丽莎》只留本地；报告使用已归一化后的有效区域。
- `support/make_style_examples.py`：实际模型图生成与逐值核对；`support/package_latest.py`：一次性整理latest的来源脚本。

## 编译

Windows安装XeLaTeX及宋体/Times New Roman/Consolas后，在本目录运行两次：

```powershell
xelatex -interaction=nonstopmode -halt-on-error -output-directory=build main.tex
xelatex -interaction=nonstopmode -halt-on-error -output-directory=build main.tex
```

产物在 `build/main.pdf`；审阅后复制为 `main.pdf`。构建日志、页PNG和历史稿备份仅留在build。原先未引用的旧章节仍保留，不作为本版正文。当前成果边界与后续在线权重下载分别陈述。

## 技术正文与演示入口

第二部分依次为系统整体介绍、风格训练原理与模型设计、硬件系统介绍、软件系统与模块设计。科研示意图说明训练约束，局部电路图说明供电域与输入，三个时序或空间示意分别说明作业提交、条带拼接和四秒确认。

现场演示见 [两分钟实物展示拍摄脚本](两分钟实物展示拍摄脚本.md)，照片编号见 [实拍照片入口](assets/field/README.md)。赛题指标在第3.2节，实拍与测量记录在第3.6节。

教师对照实验见 support/compare_teacher.py 和 assets/comparisons/teacher_benchmark.json。
