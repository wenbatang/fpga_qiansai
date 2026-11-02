# 十风格全720p C6学生

> 重训参数现已集成到独立[camera_art_ten_paint](../../elinx/projects/camera_art_ten_paint/README.md)，[bit已生成](../../elinx/projects/camera_art_ten_paint/build/720p/outflow/ti60_camera.bit)并签核通过；增强手势采用四模板/三帧投票与640框。旧UI bit保留。

> 2026-11-02新增[绘画纹理重训](PAINTERLY_RETRAIN.md)：恢复旧四风格绘画分支，新增13500步训练，重点梵高细笔触；50个全720p＋40个极小定点案例PASS，独立参数包已导出。当前bit仍使用下文保留的14000步版本，本轮未替换硬件模型。[梵高真实对照](results/painterly_v2_final/vangogh_compare.png)。

从只读`style_model/parameters/c8`所选十组冻结INT8模型蒸馏到十个独立的六通道全分辨率分支，一次只运行一个分支。旧模型、原47风格工程和四风格bit不改。

| 本地槽 / 手势 | 原47风格编号 | 风格 |
|---|---|---|
| 0 | 0 | 梵高旋涡厚涂 |
| 1 | 2 | 浮世绘海浪 |
| 2 | 3 | 彩色剪纸 |
| 3 | 4 | 复古漫画 |
| 4 | 34 | 竹林水墨 |
| 5 | 7 | 阿什维尔抽象 |
| 6 | 9 | 形体对比 |
| 7 | 15 | 蒙德里安几何 |
| 8 | 31 | 彩色马赛克 |
| 9 | 40 | 雨夜厚涂 |

原C8教师内部有2×2池化，其完整图输出作为训练目标；新C6学生stem1×1→四组DW3×3/PW1×1（d=1/2/4/8）→有符号RGB残差，全程每层保持1280×720，没有复制2×2像素或隐藏降采样。教师空间建模与学生不同，不能保证逐像素复现教师，也不能将教师输出称作新模型实板效果。

每风格396个有效卷积权重、567个可训练参数，十组共5670个可训练参数；每组712B有效部署参数、736B对齐、216项真实CPU配置事务，十组ROM7360B。只增加存储并复用计算核，风格数不使DSP乘十。ROM总线地址由硬件工程定义；十组不能继续放0x1000而与0x2000的彩色ROI重叠，当前十风格工程分配0x4000..0x5CBF。

正式基础训练在`runs/ten_c6_v2`，8000浮点步＋3000实际折叠硬件算术QAT步，每步固定一个槽、十槽轮换，batch12、128×128裁剪，512训练照片、24留出照片，34张用户素材按SHA256排除。随后独立`runs/ten_c6_texture_v1`又做3000步QAT，batch6，用冻结VGG浅层Gram和局部梯度能量加强纹理；**最终选用该14000总步版本**。源C8权重和训练划分指纹保留；未重训VGG大教师。输入增强含曝光、gamma和轻度绿偏，目标仍是对应教师的实际整数输出。

`runs/ten_c6_v1`是主动中止的2000步预运行，发现排除校验错误使用字典key而非hash值后，从头启动v2；实际固定数据本身没有重叠，v1不用于交付。训练/模型/图像继续只留本地。

## 复现

从本目录执行，使用本机已有的CUDA/PyTorch环境：

以下基础训练可使用新run名；纹理精修入口固定从保留的`ten_c6_v2`检查点开始，`--run`只更改新结果目录。若更换精修起点，需要独立复制脚本并记录新的源指纹。

```powershell
& E:/software/anaconda/envs/yolo/python.exe -B train.py --run new_ten_run
& E:/software/anaconda/envs/yolo/python.exe -B evaluate.py --checkpoint runs/new_ten_run/model.pt
& E:/software/anaconda/envs/yolo/python.exe -B refine_texture.py --run new_texture_run
& E:/software/anaconda/envs/yolo/python.exe -B evaluate_texture.py --checkpoint runs/new_texture_run/model.pt
& E:/software/anaconda/envs/yolo/python.exe -B export.py --checkpoint runs/new_texture_run/model.pt
```

`hardware_qat.py`和`integer.py`沿用已审查C6数学：i8权重、u8激活、22位有符号累加和23位舍入，逐输出通道移位与饱和；任意uint8输入下保守绝对和必须小于2²¹，无系数裁剪。`teacher_integer.py`保留原C8整数教师数学。`evaluate.py`对两张未训练的用户照片各十风格跑完整720p，独立NumPy int64、GPU整数、折叠QAT逐值比较，并另做40个极小/奇数尺寸案例与实际隐藏层空间尺寸检查。

## 最终结果与限制

最终对照入口为[0001](results/texture/0001_comparison.png)与[0005](results/texture/0005_comparison.png)，每行依次原图、源C8整数教师、新C6整数学生；[离线架构](architecture.html)。20个完整720p案例、40个极小/奇数尺寸案例均通过独立NumPy int64/GPU整数及折叠QAT逐值检查，误差0。十个实际卷积输出张量均720×1280。

`results/texture/verification.json`及`checkpoint_audit.json`绑定最终权重、输出、十教师指纹和7360B实际ROM；最大保守绝对和210951，小于2²¹，0系数裁剪。基础v2的较平滑图和数值回执在`results/final`，其精确部署导出备份在`runs/ten_c6_v2/export`；它们是保留基线，不是当前工程最终参数。`audit_texture.py`检查当前最终参数；旧`audit.py`对应v2，不用于当前导出。

纹理精修较v2有更强线条和色彩，但C6/RF31仍无法完整复现C8半尺寸分支的密集纹理，有些方向仍偏线稿/调色。相对教师平均PSNR15.89dB低于v2的17.52dB；该指标衡量逐像素差异，不能据此单独判艺术质量优劣。软件一致性、与教师的相似性和实板风格画质是不同指标，不把推理GPU计时称作Ti60 FPS。
