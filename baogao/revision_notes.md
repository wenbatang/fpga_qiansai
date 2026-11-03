# 队友报告参考与本轮修订

本轮参考本目录的《芯绘丹青_技术报告_成果展示修订版_模板页眉横线.pdf》，保留原文件，不覆盖、不将其旧版本事实直接移植进正文。

## 采用的组织方式

- 封面保留项目名称、技术报告定位与模板页眉横线；当前第1页为babyblue团队封面，第2–3页项目速览，目录从第4页开始。
- 第二部分承接整体介绍，依次说明训练原理、硬件部件和运行时软硬件协作。硬件用小幅原理图局部展示I²C上拉与一个按键回路。
- 风格统计采用白底三栏原理图。信号和时序采用可编辑的TikZ图，分别对应帧调度、条带邻域和手势四秒判定。
- 两幅名画在十槽上的实际预测仍在成果章节。

## 未沿用的旧版本内容

队友报告对应四风格、KEY3长按复位及CAM5等旧接口。本版对照 camera_art_ten_paint 的实际源文件，采用十风格、KEY3 UI开关、CAM7、当前手势模板和当前CAD签核。旧版的“整机检查正常”不直接成为当前bit持续30fps的证明。

## 技术核对入口

以 latest/elinx/projects/camera_art_ten_paint 为前缀：

- rtl/sot_recovery/csi_ppi_bridge_recover.sv：44位PPI记录、VC0 RAW10、SoT/ECC/CRC、包状态及传输故障。
- rtl/p720/camera_bayer_720.sv、camera_pack_720.sv、camera_frame_writer_720.sv：RAW插值、双像素顺序、179位记录、完整EOF与B响应。
- rtl/source_frame_pool.sv、video_job_control.sv、frame_reader.sv：三个源槽、三个输出槽、领取/释放、队列和晚ACK。
- rtl/p720/video_tile_engine_async.sv、video_cnn_async.sv：四条带、缓存、写队列、精确跨域握手。
- rtl/full_dw3x3.sv、full_pointwise.sv、full_parameter_bank.sv：行历史、多上下文、定点及配置存储。
- rtl/hdmi60/video_raster60.sv：1650×750、正HS/VS、欠载与安全换帧窗口。
- rtl/p720/video_control_apb_fast.sv、firmware/main.c：APB寄存器、216项事务、参数身份、I²C和PLIC。
- rtl/gesture_snapshot.sv、firmware/gesture_runtime.c、gesture_calibrated.c：64²快照、192维特征、拒绝阈值、4秒确认、seq/epoch与重复识别。
- latest/pycode/ten_style/retrain_painterly_v2.py、hardware_qat.py、export.py：损失、实际训练调度、数值尺度、打包格式。
- release/evidence/：既有CAD、电气、指纹及验证回执；本轮为文档修订，没有重跑硬件CAD或上板。

## 版式与成果范围

使用XeLaTeX两遍更新目录/交叉引用，Poppler渲染检查封面、速览、全部页面缩略图和新增技术页。构建日志不含Overfull、Missing character、未定义引用或过大浮动体。PDF更新同步到latest/report.pdf，并重新计算归档manifest；生产RTL、固件、配置、模型和bit不变。
