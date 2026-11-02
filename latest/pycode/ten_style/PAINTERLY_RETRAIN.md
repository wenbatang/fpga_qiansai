# 十风格绘画纹理重训（2026-11-02）

> 后续部署已完成：[camera_art_ten_paint新版bit](../../elinx/projects/camera_art_ten_paint/build/720p/outflow/ti60_camera.bit)及[使用说明](../../elinx/projects/camera_art_ten_paint/README.md)。新bit包含下述同一检查点，另加增强手势/640框，最终时序与fresh复查PASS。以下“未生成bit”描述记录算法阶段当时状态，原UI项目/bit仍保留。

本轮针对用户反馈“梵高只变蓝，旧四风格的磨砂感消失”。独立检查点和参数包已生成，当前可下载的camera_art_ten_ui bit、全部手势/UI逻辑及旧模型均保持。这里的图是软件真实定点输出，尚未生成这组参数对应的新bit。

## 改动与原因

保留版十风格主要回归C8整数输出，原训练损失5×像素L1＋3×粗尺度L1；教师空间尺度不同，又强调逐像素接近，容易让高频笔触在学生中被压平。旧四风格painterly模型则直接用绘画/风格参考的VGG纹理统计，梵高的细笔触明显更强。

本轮以保留四风格paint_final的梵高、剪纸、漫画、水墨分支初始化相应槽；其它六槽保留原十风格初始化。直接训练参考图的VGG多层Gram纹理，提高局部梯度能量约束，显著降低像素和平滑回归权重。四类使用高容量绘画教师，另外六类C8预测仅作为较弱空间锚点。没有给输出贴噪声、叠图、另加传统滤镜或降分辨率。

先做梵高1500步试训，再为十槽做12000步硬件算术QAT，总新增13500步。梵高合计5193次更新，其余每种923次更新。模型step27500是沿用原14000步后的累计记录，不表示每风格均训练27500步。训练固定512张，验证24张，34张用户照片按SHA256排除出训练；三张自然验证照片用于质检，另输出两张用户照片，均未加入训练。

参考编号与0–9槽顺序保持0,2,3,4,34,7,9,15,31,40。槽4采用保留水墨参考/绘画教师恢复黑白笔触，仍属于原水墨槽；本轮并非逐像素复刻原47风格模型。剪纸/漫画的参考包含此前用户认可的AI概念图，不把它们标作名画原作。

## 查看结果

- [梵高三张自然照片对照](results/painterly_v2_final/vangogh_compare.png)：原图／当前十风格／本轮重训。
- [十风格：餐桌](results/painterly_v2_final/000000002157_comparison.png)
- [十风格：食物](results/painterly_v2_final/000000424721_comparison.png)
- [十风格：飞机](results/painterly_v2_final/000000404128_comparison.png)
- [十风格：用户照片0001](results/painterly_v2_final/0001_comparison.png)
- [十风格：用户照片0005](results/painterly_v2_final/0005_comparison.png)

十风格对照的列顺序为原图／当前十风格／保留四风格／本轮重训；没有对应旧四风格的六槽，第三列留空。

梵高自然照片的平均亮度梯度能量由4.34/2.96/2.18提高到10.59/10.62/9.15，接近旧四风格的11.25/11.27/9.88，支持细纹理已恢复的观察；这不是艺术质量评分。梵高仍保留明显蓝黄倾向，输出偏局部短笔触、磨砂纹理，并没有实现大尺度“星月夜”旋涡的语义重构。浮世绘和部分几何类仍有偏淡或偏边缘处理的限制，不宣称十种画质都已通过用户验收。

## 模型、数学与参数包

最终模型为runs/ten_painterly_v2/model.pt，SHA256 7250b683772fdd9c3756f9f062ce639aadfcbfbc49eb64e6ac2e15588e489e86。原型仍为十个独立C6/RF31，全720p、无池化；每槽396卷积权重、216加载事务，十槽ROM7360B。没有增加通道、层数或改变FPGA接口。

50个完整1280×720案例（五张图×十风格）通过NumPy int64、GPU整数与实际折叠QAT逐值对照，误差0；另40个极小/奇数尺寸案例通过。实际十层输出张量均为720×1280。最大保守累加绝对界239482，小于2^21，系数裁剪0，保持22位累加/23位舍入约定。

独立参数包为runs/ten_painterly_v2/package，含parameters/c6十组NPZ/MEM/BIN和build/720p/weights.mem，已经逐字节反拼ROM并确认7360B。package/verification.json和results/painterly_v2_final/audit.json绑定当前模型、训练源、画作参考、实际预测与参数包。没有写入任何已冻结FPGA工程，当前bit不包含新模型；后续部署仍需新构建、资源/时序签核和真实摄像头画质验证。

## 复现入口

- retrain_painterly.py：保留的1500步梵高试训，run ten_painterly_probe_v1。
- retrain_painterly_v2.py：独立十槽12000步，起点为上述试训检查点；已有run禁止覆盖。
- evaluate_painterly.py：真实对照和全尺寸定点验证，输出目录独立。
- package_painterly.py：只导出独立参数包，不改FPGA工程。
- audit_painterly.py：复查训练行数、十槽范围、源/输出哈希、参数包和旧bit保持。

训练/权重/图片/参数包继续本地保存，Git只收录脚本与说明。本轮未操作摄像头、串口/JTAG、Flash或Git推送。
