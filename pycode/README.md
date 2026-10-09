# 四种风格转换网络

在 `pycode/convertpic/val2017/` 的照片上训练四个独立前馈 CNN：浮世绘、梵高、水墨国画、油墨版画。结果布局为每页 12 组，6 列、两块“上排原图 / 下排风格化”，右上角显示参考风格图。

## 本轮实验

- 用户最初要求三种风格，随后决定同时保留“水墨国画”和“油墨版画”，因此共四种。
- 从 5,000 张照片中按固定种子 `20261008` 留出 72 张，只用其余 4,928 张训练。留出名单和训练名单保存在运行目录的 `split.json`。
- 每个模型训练 3 个 epoch；256×256 随机裁切、水平翻转，batch size 8，Adam 学习率 0.001。每轮 616 步，每种共 1,848 步。
- 训练使用冻结的 ImageNet 预训练 VGG19 感知特征、内容损失、Gram 风格损失和 TV 正则。VGG 不参与权重更新，也不参与最终前馈推理。
- 风格参考图来自 The Met Open Access 公开领域作品；下载脚本核实 API 的公开状态，保存来源和 SHA256。水墨参考裁切掉大部分题字/装裱，并用 1% autocontrast 调整扫描纸面范围；水墨和版画参考转为灰度。
- 训练环境：RTX 5070 12GB；现有 `yolo` Conda 环境，Python 3.13、PyTorch 2.11.0+cu128、torchvision 0.26.0+cu128。训练卷积使用 BF16，参数、Gram 矩阵和损失使用 FP32。
- 正式输出为独立模型推理结果。输入照片不是风格化配对标签，没有用预处理好的结果图冒充网络输出。

| 名称 | CLI 名称 | 风格参考 |
| --- | --- | --- |
| 浮世绘 | `ukiyoe` | 北斋《神奈川冲浪里》：[来源](https://www.metmuseum.org/art/collection/search/45434) |
| 梵高 | `vangogh` | 梵高《麦田与柏树》：[来源](https://www.metmuseum.org/art/collection/search/436535) |
| 水墨国画 | `inkwash` | 石涛《Landscape with solitary figure》：[来源](https://www.metmuseum.org/art/collection/search/49171) |
| 油墨版画 | `inkprint` | 丢勒《犀牛》木刻版画：[来源](https://www.metmuseum.org/art/collection/search/356497) |

本轮已完成训练和 72 张留出图片的评估，结果如下。风格误差采用冻结 VGG 的 Gram 矩阵 MSE；下降比例相对于相同结构、相同初始化种子的未训练网络，不是“画质准确率”。

| 风格 | 训练步数 | 留出集风格误差 | 相对未训练误差下降 | GPU 单图推理 |
| --- | ---: | ---: | ---: | ---: |
| 浮世绘 | 1,848 | 0.00006232 | 91.4% | 2.36 ms |
| 梵高 | 1,848 | 0.00003993 | 84.0% | 1.74 ms |
| 水墨国画 | 1,848 | 0.00002280 | 69.5% | 2.65 ms |
| 油墨版画 | 1,848 | 0.00004002 | 92.2% | 2.13 ms |

延迟在 RTX 5070 上以 256×256、FP32、batch=1 测量，热身 5 次后平均 30 次；不包括读图和传输。不同参考图的误差绝对值不能用于风格之间的质量排名。已核对 4 份权重的参考图校验和、完整训练日志、24 页对比图和 288 张输出图片；CPU/GPU 在 65×79 非整倍数尺寸下保持宽高一致，最大像素浮点差小于 0.001，两个墨色模型输出的 RGB 通道完全一致。完整尺寸单图 CPU 转换也已运行通过。

## 文件位置

```text
pycode/
  convertpic/val2017/         原始照片，保留本地
  prepare_styles.py          获取/验证官方风格参考图
  style_network.py           前馈网络和权重加载
  train_style.py             独立模型训练、运行记录和断点
  compare_styles.py          留出集转换与对比图排版
  evaluate_styles.py         留出集感知损失与推理延迟评估
  stylize.py                 任意单张图片转换，保留原始宽高
  styles/                    参考图、原始下载、来源/校验记录
  runs/four_styles_v1/
    split.json               固定训练/留出名单
    <style>/model.pt         推理用网络权重和元数据
    <style>/latest.pt        最近完整 epoch 的模型和优化器断点
    <style>/progress.pt      中间检查快照，不用于精确断点续训
    <style>/training.csv     每步损失
    <style>/metrics.json     训练配置、时间、参数和步数
  results/four_styles_v1/
    overview_four_styles.jpg 四种风格的同图总览
    <style>/comparison_01.jpg 至 comparison_06.jpg
    <style>/*_styled.png     各留出图片的风格化结果，共 72 张/风格
    evaluation.json          渲染记录
    validation_metrics.json 留出集误差、随机初始化对照、256×256 延迟
```

单独的 `runs/smoke/` 和 `results/preview/` 用于开发检查，不是最终结果。正式对比图使用同一张照片的固定中心裁切，原图和预测严格配对；单图转换脚本则处理完整照片。

## 运行命令

从工作区根目录执行，选用具有 CUDA 的环境。当前机器可在 PowerShell 中设置：

```powershell
$stylePython = 'E:\software\anaconda\envs\yolo\python.exe'
```

其他机器将 `$stylePython` 改为自己的 Python。所需包为 `torch`、`torchvision`、`Pillow`、`numpy`、`requests`；本轮环境版本记录在 [requirements.txt](requirements.txt)。选择适合本机 CPU/CUDA 的 PyTorch 构建，并另行准备可用的预训练 VGG19 权重。

1. 获取风格参考图（已有文件会核对 SHA256）：

```powershell
& $stylePython pycode/prepare_styles.py
```

如需使用本机已有代理，可加 `--proxy http://127.0.0.1:7897`，端口以自己的代理为准。

2. 训练四种风格：

```powershell
& $stylePython pycode/train_style.py --epochs 3 --workers 2
```

默认读取本机 `~/.cache/torch/hub/checkpoints/vgg19-dcbb9e9d.pth`。可通过 `--vgg-weights` 指定权重位置。本轮直接使用已有缓存；脚本不会静默下载大模型或改动当前 Python 环境。

只训练某种风格，或在完整 epoch 断点上继续训练至总共 5 轮：

```powershell
& $stylePython pycode/train_style.py --style vangogh --epochs 5 --resume --workers 2
```

`--epochs` 是目标总轮数。更换参考图、结构、数据集或损失设置时，使用新的 `--output` 目录；不要在旧实验上无记录地混用参数。随机种子固定数据划分和初始化，CUDA 运行不承诺跨设备逐位复现。

3. 生成四种风格全部 72 张留出图片的对比图：

```powershell
& $stylePython pycode/compare_styles.py
& $stylePython pycode/evaluate_styles.py
```

每种 6 页、每页 12 组；共 24 页对比图、288 张单独风格化图片和一张总览图。`--style` 可选择风格，`--limit` 可减少展示数量。

4. 转换任意单张图片：

```powershell
& $stylePython pycode/stylize.py pycode/convertpic/val2017/000000000139.jpg pycode/results/my_vangogh.png --style vangogh
```

`--cpu` 可用于无 GPU 推理。完整图片保持原始宽高；极小图片（任一边 <16 像素）不支持。

## 网络与 FPGA 的关系

结构为 3×3 Conv/IN/ReLU 编码器（16/32/64 通道，两次 stride=2）、3 个残差块、nearest 上采样解码器和 sigmoid 输出。彩色模型 269,763 个参数；墨色模型用单通道输出后复制为 RGB，269,473 个参数，保证灰度由网络结构产生。

此模型是 PC 端风格效果/训练基线。未量化、未导出 FPGA 权重、未实现 RTL 推理，也未验证 Ti60 帧率。IN 使用当前特征图统计量，不能直接当作固定 BN 折叠；sigmoid、上下采样及多层特征缓存也需要单独实现。参数少于 500KB 的 INT8 理论大小不代表已完成 INT8 量化或满足 FPGA 算力要求。

评估中的 GPU 延迟仅指 256×256、batch=1、FP32、热身后 CNN 推理，不含图片解码、VGG、绘图或传输，不能当作 640×480 摄像头实时系统 FPS。感知误差下降只证明参考风格统计拟合有所改善，画质还需检查对比图；本任务没有像素对齐的艺术目标图，不用原图作为“真值”报告误导性的 PSNR/SSIM。

文件夹虽名为 `val2017`，本实验使用其中大部分图片训练，不把全部目录宣称为训练未见过的验证集。留出的 72 张才是本实验的独立效果检查集。

## Git 上传

遵守根目录白名单：Python、Markdown 和 `requirements.txt` 可以上传；照片、风格参考图、权重、训练日志和 JSON 运行记录保留本地。数据目录仅保留放置说明；训练输入与输出目录整体忽略。队友克隆后需要自己的照片目录、风格参考图和 VGG 权重才能重新训练。

## 方法来源

- [Perceptual Losses for Real-Time Style Transfer and Super-Resolution](https://arxiv.org/abs/1603.08155)
- [PyTorch 官方 fast_neural_style 示例](https://github.com/pytorch/examples/tree/main/fast_neural_style)：参考感知损失/前馈网络方法；本目录实现为独立编写的小型网络。
