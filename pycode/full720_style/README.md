# 全720p六通道风格网络

对应[独立Ti60工程](../../elinx/projects/camera_full720_30/README.md)。网络不做池化/下采样；所有逻辑特征层保持输入的宽高，完整720p每种风格396个卷积权重，四风格联合训练参数747。

| 文件 | 作用 |
| --- | --- |
| network.py | C6、四组膨胀DW/PW、条件风格、冻结BN、QAT和RGB残差 |
| train.py | 只读C8教师蒸馏、感知/风格/内容联合训练，固定划分 |
| integer.py | BN折叠/量化导出及独立NumPy int64整数参考 |
| export.py | 四组模型、共享常量RTL、2944B ROM与216事务布局 |
| evaluate.py | 两张留出照片的八个完整720p整数对照与实际预览 |

本轮c6_v1实际完成6000步，96×96训练裁剪、batch12、末段QAT；训练裁剪不会降低完整图像推理分辨率。教师来自只读style_model原槽0/3/4/5，训练划分复用512张固定训练集，用户演示照片留出。原C8和已认可RF33权重均保留。

在相应项目build目录运行软件入口可避免输出污染根目录：

```powershell
python -B F:/fpga_qiansai/pycode/full720_style/train.py --run c6_v2 --steps 6000
```

不要在已签核项目上重新导出参数。export.py检测build_inputs.json后会拒绝覆盖；新训练实验须导出到独立项目/目录，并重新做整数、RTL、映射数值及CAD签核。evaluate.py当前针对冻结c6_v1与camera_full720_30，不会自动选训练中的新检查点。

依赖现有PyTorch/CUDA、NumPy和Pillow，VGG19感知权重使用本地主机已有缓存；数据集、checkpoint、训练日志和预览仅留本地。实际结果入口为Ti60项目build/quality，详细网络和量化契约见[model.md](../../elinx/projects/camera_full720_30/docs/model.md)。
