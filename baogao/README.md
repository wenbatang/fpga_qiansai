# 技术报告

入口为 `main.tex`，交付预览为 `main.pdf`。章节遵循官方模板：独立封面（第1页）、单页项目速览（第2页）、目录/摘要、作品概述、系统组成及功能、完成情况和性能、总结、参考文献。正文按主要模块说明输入输出、时钟握手、作用与实现，没有伪造实物照片或板上FPS。

## 生成内容

- `assets/generated/system.png`、`network.png`、`training.png`：内置imagegen工具生成并经技术复核的白底框架图。工具没有“Image2.5”型号选择参数，不能声称指定型号；提示词和修订说明见 `assets/generated/PROMPTS.md`。
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

## 本轮深化

依据队友报告的组织方式扩充采集协议、DDR地址/所有权、AXI背压、卷积流水、HDMI换帧、精确CDC、RISC-V加载、手势分类及训练量化；技术事实按当前十风格源码复核。修订依据见 [revision_notes.md](revision_notes.md)。旧队友PDF保持原样，未混用旧四风格与KEY3复位说明。
