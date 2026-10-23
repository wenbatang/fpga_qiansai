# 四种有区别的画风与四键控制

用户认可的上一版模型与工程继续保留：`runs/fpga_student_phase`、`runs/optimized_teacher_v2`、`styles/` 原参考以及 `xilinx/projects/uart_style_hdmi`。另外保存的完整基线在 `xilinx/projects/uart_style_hdmi/build/phase_baseline_20261012`，186 个文件均逐项验证 SHA256，包含两套签核 bitstream、模型、权重、源码、参考与报告。这个备份不上传 Git。

新工程为 `xilinx/projects/uart_style_keys`，图片仍由 UART 上传，物理 KEY2–KEY5 切换四种风格并重新处理缓存原图。旧版版画不删除，本轮新四槽改用彩色油画；旧版风格槽顺序与新版本不同。

| 槽 | 风格 | 新参考 | 色彩目标 |
|---|---|---|---|
| 0 / KEY2 | 梵高星空 | 《星月夜》，1889；裁取上方 80% 主体天空 | 蓝色、黄色亮部与密集笔触 |
| 1 / KEY3 | 浮世绘 | 北斋《凯风快晴》，又称《赤富士》 | 红蓝色块和轮廓 |
| 2 / KEY4 | 水墨国画 | 保留石涛山水的原参考 | 黑白、留白与墨线 |
| 3 / KEY5 | 彩色油画 | 雷诺阿《露台上的两姐妹》，1881 | 多色柔和笔触，保留彩色层次 |

参考获取入口为 `prepare_distinct_styles.py`，所有图和来源记录位于独立 `styles/distinct_v1`。保存下载 URL、作品来源、裁剪、许可描述、原始文件和训练图 SHA256；已有记录的训练图必须匹配哈希，不覆写旧参考。

来源：[MoMA 星月夜](https://www.moma.org/collection/works/79802)、[星月夜公版图文件页](https://commons.wikimedia.org/wiki/File:Van_Gogh_-_Starry_Night_-_Google_Art_Project.jpg)、[Met 赤富士](https://www.metmuseum.org/art/collection/search/36490)、[Art Institute 雷诺阿作品](https://www.artic.edu/artworks/14655)、[雷诺阿公版图文件页](https://commons.wikimedia.org/wiki/File:Pierre-Auguste_Renoir_-_Two_Sisters_(On_the_Terrace)_-_Google_Art_Project.jpg)。部分博物馆图像接口当前不可用，实际图像 URL 与作品元数据来源分别记录，未虚构 API 成功。

也查阅了[《鬼灭之刃》官方视觉素材](https://kimetsu.com/anime/)。动漫视觉与传统浮世绘有区别，本轮使用《赤富士》训练传统画风，没有把动漫海报或角色标签当作浮世绘参考；官方素材没有被标为 CC0。后续若单独尝试动漫风格，需另开实验并保留该区别。

## 针对灰黑同质化的改变

旧水墨和版画模型都是单通道输出，本轮仅水墨保留单通道，星空、浮世绘与油画均为三通道彩色。教师仍通过冻结 VGG19 的内容、Gram 风格与平滑损失训练；新增 RGB 以及 R−G、B−(R+G)/2 色差通道的排序分位分布损失，直接约束参考作品的色彩分布。这项损失只用于训练，不给 FPGA 添加颜色滤镜或额外计算模块。

第一轮教师 `distinct_teacher_v1` 使用原训练集的 2048 张确定子集、192 像素随机裁剪、每种 8 轮，在旧彩色教师基础上调整参考与色彩，水墨则在旧水墨教师上细化。第二轮 `distinct_teacher_v2` 用全部 4928 张训练图片、256 像素裁剪、每种 12 轮；分位分布损失系数由 35 提至 120，进一步细化颜色与笔触。两轮均沿用原有 72 张留出图片，前 24 张用于选最佳模型。

`distinct_student_v1` 蒸馏到与原 FPGA 兼容的五层六通道模型，膨胀率 1/1/2/4/8、模 4 坐标特征，冻结 BN 折叠，训练中模拟 int8 权重、uint8 激活及 RGB565 输入。使用全部 4928 张训练照片，192 像素裁剪、12 轮；教师输出 L1 蒸馏系数 24，颜色分布系数 120。油画从旧彩色梵高学生初始化，保留三通道；不从单通道版画假装扩展成彩色。实际初始化和教师的 SHA256 均在检查点内。

学生结构不增加卷积 DSP 数量，旧参数和新参数分开放置。训练出的可学习颜色与纹理效果仍受五层六通道、33 像素感受野限制，不能据此保证任意照片都出现参考画完整的星体或大范围漩涡。

## 评估与生成结果

两轮教师和四种学生均已完成训练。最终使用 `compare_styles.py --catalog distinct` 生成每种风格 72 张结果、6 页各 12 对的“上原图、下风格化”对比，以及同图四风格总览。教师与定点学生分开输出，不把 PC 教师图冒充 FPGA 结果。结果入口分别为 `results/distinct_teacher_v2/overview_four_styles.jpg` 与 `results/distinct_student_v1/overview_four_styles.jpg`。

`evaluate_distinct.py` 使用第 25–72 张共 48 张开发回归图片，记录内容误差、Gram、色彩分布、平均色差、裁剪比例、教师差异以及风格两两输出差异；该集合已经用于开发，不是盲测。每种取 6 张对照独立 int64 整数参考，要求误差为零，再用四种实际导出权重验证 RTL。

进入 FPGA 时四槽顺序为 `vangogh, ukiyoe, inkwash, oilpainting`。新工程构建只接受实际风格元数据匹配的对应目录；不将随机权重用于风格效果或性能验收。

## 本轮实际结果

每种学生完成 12 轮、4932 个训练步；下表记录选中的最佳检查点，非最后一轮自动覆盖。平均色差是归一化 RGB 最大通道减最小通道的平均值；用于检查颜色是否坍缩，不能作为艺术质量评分。

| 风格 | 最佳轮次 | 平均色差 | 极值裁剪比例 | 学生与教师 L1 |
|---|---:|---:|---:|---:|
| 梵高星空 | 12 | 0.18978 | 0.07635% | 0.11298 |
| 浮世绘 | 12 | 0.15838 | 0.44762% | 0.11850 |
| 水墨 | 6 | 0.00802 | 0.00979% | 0.08899 |
| 彩色油画 | 8 | 0.11404 | 0.02358% | 0.09911 |

四风格两两输出 L1 在 0.09674–0.32166 之间；星空与油画仍最接近，不能据此宣称风格完全分离。评估详情、检查点 SHA256 和逐项数值保存在 `results/distinct_evaluation/evaluation.json`。4,718,592 个通道值的 CPU QAT 与 NumPy int64 参考对照最大误差为 0。

另用用户实际 `xilinx/projects/uart_hdmi/images/0001.png` 的原生 1280×720 图，四种模型各比较 2,764,800 个通道值，合计 11,059,200，逐层整数误差均为 0。保存逐层输出、RGB565 结果和 [实际 720p 对比图](../results/distinct_real_720p/comparison.jpg)；这是定点软件参考，尚不是 HDMI 屏幕照片。
