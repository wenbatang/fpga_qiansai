# 独立四分支绘画风格重训

对应新工程 `elinx/projects/camera_art_interactive`。保留原C6/C8/RF33检查点，新的梵高、剪纸、漫画、水墨分别独立学习全部空间层和head，单风格396个卷积权重。推理无池化，每层保持输入空间尺寸。详细结构、量化格式和限制见工程 `docs/model.md`。

本地运行环境为 `E:/software/anaconda/envs/yolo/python.exe`、PyTorch/CUDA、RTX5070。`train.py` 固定训练划分，先各1600步感知教师，再14000步学生；`refine.py` 追加3000步实际折叠整数QAT。已存在的run不能覆盖，重做实验应新建run或显式修改实验路径。

```powershell
& 'E:/software/anaconda/envs/yolo/python.exe' -B '.\pycode\painterly_style\train.py'
& 'E:/software/anaconda/envs/yolo/python.exe' -B '.\pycode\painterly_style\refine.py'
```

`hardware_qat.py` 将BN/条件仿射真实折叠，再量化int8/22位偏置/右移；与 `integer.py` 的NumPy int64和GPU整数路径对照。`sim/check_hardware_math.py --checkpoint <最终检查点>` 检查极小与非均匀输入的实际QAT数学。`evaluate.py` 生成两张留出照片、四风格的完整720p实际输出、旧模型/新教师/新学生对照与数值回执；它们不是板上采集结果。

`export.py` 只在工程尚未冻结构建输入时导出ROM/NPZ。已映射后禁止原地换权重；需要记录原候选及重新构建。`paint_final/model.pt` 仅在3000步定点精修全部完成后写入，GUI停止再开始会加载它。

所有数据集、风格参考、训练检查点、图片、build、sim只留本地。参考和用户照片来自既有工作区，未上传摄像头图像。
