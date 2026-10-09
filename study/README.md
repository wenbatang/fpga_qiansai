# 神经网络与卷积神经网络：从零读懂代码

这里是本地学习区。整个 `study/` 已被根目录 `.gitignore` 排除，不上传 Git。

目标：先能解释代码里的输入、权重、计算和输出，再理解训练流程，最后读懂一个完整的 CNN。每次只学一课，不需要一次看完。

## 如何开始

使用 Python 3，仅用标准库，无需安装 NumPy、PyTorch 或下载数据集。在 PowerShell 中执行：

```powershell
cd F:\fpga_qiansai
python study/step01_neuron.py
```

若系统没有 `python` 命令，可尝试 `py -3` 替代。当前工作区已用 Python 3.12.4 运行验证。

先读 [第一课](lessons/01_单个神经元.md)，再对照代码运行。每一课都按“概念 → 手算 → 代码 → 输出 → 修改实验 → 自检”学习。没有理解自检问题，就先停在这一课。

## 学习顺序

| 课次 | 核心问题 | 讲解 | 运行命令（在工作区根目录执行） |
| --- | --- | --- | --- |
| 01 | 一个神经元怎么计算？ | [单个神经元](lessons/01_单个神经元.md) | `python study/step01_neuron.py` |
| 02 | 权重怎么被学出来？ | [第一次训练](lessons/02_第一次训练.md) | `python study/step02_training.py` |
| 03 | 多层神经网络怎么连起来？ | [多层网络](lessons/03_多层网络.md) | `python study/step03_mlp.py` |
| 04 | 卷积核怎么在图像上移动？ | [卷积运算](lessons/04_卷积运算.md) | `python study/step04_convolution.py` |
| 05 | 一张图经过 CNN 会变成什么？ | [CNN 前向流程](lessons/05_CNN前向流程.md) | `python study/step05_cnn_forward.py` |
| 06 | 怎样训练完整 CNN？ | [CNN 训练流程](lessons/06_CNN训练流程.md) | `python study/step06_cnn_training.py` |

术语先记这几个：输入 `input`、权重 `weight`、偏置 `bias`、激活 `activation`、预测 `prediction`、损失 `loss`、梯度 `gradient`。

## 这套示例的范围

第 1～3 课学习普通神经网络；第 4～6 课学习图像卷积和小型分类 CNN。第 5 课只做前向计算，第 6 课才真正训练卷积核和分类层。

CNN 输入是程序生成的 6×6 单通道横线/竖线图，类别 0 表示横线，类别 1 表示竖线。数据小到能逐项查看，结果只用于教学，不代表真实图像任务的能力。

这里采用浮点 Python，侧重理解计算。竞赛的风格迁移需要输出图像，还需要训练好的风格模型、BN/IN、定点化、FPGA 数据流、DDR 和板卡验证。本教程不是竞赛实现，也没有进行综合或上板验证。读懂这六课后，再学习 PyTorch、图像到图像网络以及定点卷积，会更容易。

## 和讲解一起学

建议先只运行第 1 课。之后可以说“开始教我第 1 课”或“第 1 课的 ReLU 我没懂”，我们就对照文件，一段一段讲、算、修改。后面的课程已经准备好，但不用提前读。
