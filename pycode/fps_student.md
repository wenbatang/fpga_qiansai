# 六通道轻量风格网络：先比较画质，再决定是否上板

日期：2026-10-23。此实验只新增训练代码和本地候选模型，没有替换已经认可的四组十二通道模型，也没有改变摄像头工程的固件、RTL、电平、工程文件或 bit。

## 结论和使用边界

已真实训练梵高、剪纸、漫画、水墨四种风格的两组候选，共八个定点学生。两个候选都是五层、六通道，没有额外 X/Y 相位输入：

| 配置 | 隐藏通道 | 五层 dilation | 理论感受野 | 最小完整 halo | 彩色模型有效像素 MAC 数 |
|---|---:|---|---:|---:|---:|
| 当前已认可模型 | 12 | 1 / 2 / 4 / 8 / 16 | 63×63 | 31，工程取32 | 4536 |
| `rf33` 轻量候选 | 6 | 1 / 1 / 2 / 4 / 8 | 33×33 | 16 | 1296 |
| `rf63` 画质对照候选 | 6 | 1 / 2 / 4 / 8 / 16 | 63×63 | 31，工程可取32 | 1296 |

彩色网络计算量降为原来的约 **1/3.5**。水墨最后一层只计算一个灰度通道，旧/新为4320/1188 MAC，约为1/3.64。MAC统计包括九个tap，按有效图像像素计算，不含扫描补边、halo重算、总线背压或跨域等待，所以这些比例**不能直接写成FPGA帧率加速比**。

较小的通道数可让六个输出通道全部并行，避免现有十二通道模型的多组输出复用；`rf33`还可以缩短行缓存并减少halo重算。是否能满足资源、时序和真实15fps，仍需对对应RTL做布局布线及整机实测。训练脚本没有产生可下载bit。

已经查看实际比较图：六通道模型保留了轮廓和不同风格的主色，但细笔触普遍减少；RF63通常比RF33更接近当前十二通道输出。尤其梵高更平滑，不能替用户认定它的画质已经可接受。当前正式bit和参数仍保留，轻量版只是候选。

## 先看哪些文件

下列目录全部位于本工作区 `F:\fpga_qiansai`：

| 文件或目录 | 作用 |
|---|---|
| `pycode/results/fps_student_v1/refined/four_styles_overview.png` | 同一张留出照片，四风格逐行，原图/当前12通道/6通道RF33/6通道RF63四列 |
| `pycode/results/fps_student_v1/refined/vangogh_comparison.png` | 梵高四张不同照片，同样四列 |
| `pycode/results/fps_student_v1/refined/papercut_comparison.png` | 剪纸四张不同照片 |
| `pycode/results/fps_student_v1/refined/comic_comparison.png` | 漫画四张不同照片 |
| `pycode/results/fps_student_v1/refined/inkwash_comparison.png` | 水墨四张不同照片 |
| `pycode/results/fps_student_v1/refined/images/` | 上述比较图中每张完整1280×720预测，未经预览缩小 |
| `pycode/results/fps_student_v1/refined/evaluation.json` | 原参数/候选指纹、逐图指标、整数误差与测试范围 |
| `pycode/results/fps_student_v1/refined/integer_cases/` | 小尺寸测试的输入、每层期望/实际/误差；完整720p测试保存输入和最终期望/实际/误差 |
| `pycode/runs/fps_student_v1/refined/{rf33,rf63}/export/{style}/` | 候选权重、偏置、shift、manifest和weights.npz，兼容现有`load_export`读取 |

比较图的每个预测先在 **1280×720** 上执行网络，再缩到384×216排版，完整预测另存。它们来自真实训练模型，既不是概念图，也没有用额外图像滤镜代替CNN。

## 留出集上的定量对照

以下为12张开发预览留出照片的均值；它们没有用于训练，也没有用于挑选训练轮次。为了批量统计，指标使用同图同裁剪的384×216输入。对照目标是**当前已认可的十二通道定点模型**，不是原照片。

| 风格 | 候选 | L1，0–1尺度 | PSNR/dB | SSIM |
|---|---|---:|---:|---:|
| 梵高 | RF33 | 0.0643 | 21.71 | 0.443 |
| 梵高 | RF63 | 0.0616 | 22.08 | 0.483 |
| 剪纸 | RF33 | 0.0707 | 17.32 | 0.472 |
| 剪纸 | RF63 | 0.0461 | 22.02 | 0.580 |
| 漫画 | RF33 | 0.0948 | 16.85 | 0.476 |
| 漫画 | RF63 | 0.0691 | 19.01 | 0.663 |
| 水墨 | RF33 | 0.0544 | 22.69 | 0.619 |
| 水墨 | RF63 | 0.0480 | 23.69 | 0.643 |

PSNR/SSIM衡量候选与教师的接近程度，不是独立审美分数；数值更高也不表示用户一定更喜欢。PSNR是逐图计算后求均值。SSIM按RGB逐通道、11×11高斯窗口、sigma=1.5、总体协方差、K1=0.01/K2=0.03计算，有效窗口再平均。所有统计均经过最终RGB565打包/位复制展开，匹配显示颜色精度。

## 训练数据与流程

1. 延续`runs/art6_v2/split.json`的固定训练/验证分离，不从验证照片取训练块。
2. 从原训练集按固定seed `20261023`抽768张照片；选择验证用原验证集前24张；只用于结果展示的照片用原验证集第25–36张。
3. 每张训练照片确定性裁剪、随机镜像并缩到128×128。每五张之一做0.4–0.8倍亮度增强，覆盖部分暗光输入；具体随机种子固定。
4. 输入先做RGB565往返，与现有板上输入颜色精度一致。
5. 冻结当前`art6_v2/student/{style}/model.pt`十二通道参数，按当前逐层镜像边界运行，缓存真实uint8整数预测作为蒸馏目标。
6. 用教师中按后继权重绝对值重要性选出的六个通道初始化学生；选中的通道编号写入每个模型的`configuration.json`，初始化后学生所有卷积和BN参数都参与训练。
7. 每个学生训练100轮浮点，再24轮QAT，共5952步，batch16。保存浮点最佳/末轮、QAT起点、QAT最佳/末轮，保留训练CSV。
8. 蒸馏损失包括像素L1、多尺度L1、边缘差、颜色均值、归一化空间结构和空间标准差。QAT冻结BN，学习率降至浮点初始学习率的0.005倍，再衰减。
9. 用24张选择验证照片的结构损失选择最佳QAT轮次，并要求空间标准差比例和跨照片差异比例均不低于教师的0.4，以防常色塌缩。
10. 导出int8权重、int32偏置、每层统一的2次幂shift，运行独立整数逐层回归和真实留出照片比较。

浮点初始学习率0.001。CUDA为RTX5070，PyTorch 2.11.0+cu128，禁用TF32，随机种子、源文件、照片和教师权重哈希都留存。GPU训练秒数不作为FPGA吞吐证据。

目标是保持已认可风格，因此暗光时教师固有的蓝/粉/绿/白主色也会被蒸馏保留。此实验没有修改曝光、Bayer、白平衡或增加完整ISP，也不宣称已经解决所有暗光偏色。

## 首轮失败实验如何保留

最早14轮浮点+8轮QAT的快速实验在梵高上出现了常色输出。仅按像素L1挑选，会偏向教师的中位颜色，因此该版本没有用于交付。

原始失败模型保留在`runs/fps_student_v1/rf33/`和`rf63/`，初版源代码在`initial_sources/`，日志在`initial_training.log`。**不要将它们当本轮候选。**经过空间结构约束、训练延长和QAT降学习率的最终实验统一在`runs/fps_student_v1/refined/`。

## 定点与边界约定

- 输入RGB uint8，层间uint8；隐藏激活实际量程0–6，对应scale=6/255；输入/输出scale=1/255。
- 所有卷积3×3，有符号int8权重，int32累加与偏置，BN affine和running statistics折叠进权重/偏置，不等同于运行时IN。
- 每层舍入为`floor((acc + 2^(shift-1)) / 2^shift)`，shift=0时不加偏移；负数也采用同一定义。输出饱和到0–255。
- 每一层真实全图边缘使用reflect101；当某轴长度不大于本层dilation时，该轴用edge复制回退，兼容极小控制测试。
- 人工条带边界不可反射，应通过完整halo依赖得到中心输出；RF33 halo16，RF63至少31。
- 单色水墨输出一个uint8，再复制到R/G/B；RGB565的R/B5位、G6位量化可能引入最多几级的展开差异，不应误认为三个独立颜色模型。
- `export_hardware.load_export()`可以直接读新导出。该工具原来的`integer_network()`默认zero padding，**不能直接用于本候选**；要使用`art6_border.integer_network()`或本实验的`forward()`。
- 原`HardwareNetwork.forward()`也默认zero padding。仅加载新checkpoint后调用`model(x)`并非本实验预测；应调用`fps_student.forward(model,x)`。保留旧类行为是为了不改变旧签核依赖。

## 验证范围

八组候选分别在37×31、9×5和1×1随机输入上检查五层输出，NumPy整数参考与Torch QAT逐层误差全部为0，输入/权重/每层期望/实际/误差均保存。两组梵高另各跑一个完整1280×720输入，最终2764800个RGB数值误差为0。

这些是软件数值一致与真实网络画质预览；不是RTL整机、映射后网表、布局布线、摄像头并发、DDR竞争或实板帧率证明。任何后续硬件实现都需按具体通道数/并行度重新验证，尤其不能沿用十二通道运行时偏置写入曾出错版本的映射结论。

## 复现实验

使用本机既有训练环境，工作目录可设`F:\fpga_qiansai\pycode`：

```powershell
& 'E:/software/anaconda/envs/yolo/python.exe' train_fps_student.py --revision refined --float-epochs 100 --qat-epochs 24
& 'E:/software/anaconda/envs/yolo/python.exe' evaluate_fps_student.py --revision refined --full-integer
```

已完成模型会保留，不覆盖。缓存数据、split或输入尺寸与给定参数不一致时会拒绝复用；新实验请用另一个独立run目录，或明确扩展脚本，不能覆盖本轮结果来伪装复现。

本地证据包括`runs/fps_student_v1/refined/launch.json`、每组`configuration.json/training.csv/experiment.json`、`refined/sources/`源快照、`runs/fps_student_v1/cache/sources.json`照片哈希、`preserved_teachers.json`教师哈希与`results/.../evaluation.json`。训练、数据、图片、导出权重仍按现有Git规则留本地；新增Python和本说明可收录仓库。
