# 按键白平衡校准

当前新增功能为手动触发的一次性白平衡。它根据白纸或中性灰目标计算增益并锁定，不会持续跟随整个场景自动调整。默认仍采用此前实测的红/绿/蓝 Q8 增益493/256/504，黑位65/66/66/67、BGGR3和Gamma1.8保持。

## 上板操作

使用通过构建检查后打包的 `build/style_video_wb_calibration.bit`。以 `build/wb_calibration_receipt.json` 为构建结果依据；生成成功不代表已完成实板验证。

1. 下载后底部应出现 **WB CAL 01 DEFAULT**。RIGHT保持1.00。
2. 在实际拍摄光照下，让均匀受光的白纸尽量填满画面。避开反光，保持稳定。
3. 按一下 **KEY2**，继续保持白纸约1秒。状态经过SAMPLE/CALC/APPLY后显示 **LOCKED**，表示新增益已经在摄像头帧起点生效。采样期间左图中央有黄色区域框。
4. 移开白纸观察图像。更换光照时可重新校准；不要对有颜色的物体执行此操作。
5. **KEY3**恢复默认固定白平衡，状态回到DEFAULT；掉电也恢复默认。KEY1仍然只调整右图对比度。

REJECT表示测量或计算不适用，保留先前生效的增益。可调整白纸亮度后重试。页脚R/B是Q8十六进制数，100表示1倍、200表示2倍；绿色固定为100。原始A/B/C/D统计在扣黑和白平衡之前，不会因为校准而变成相同读数。

新版需确认CAP/COPY是否仍为30，UF/ERR/DROP是否保持0，以及默认、校准、恢复三种状态能否正常切换。目前旧固定版有30fps/零错误的用户反馈，新版实板结果待用户确认。

## 实现与接口

`style_cfa_stats`输出每个完整合法帧中心128×128区域的四个RAW10均值。`style_wb_calibrator`在50MHz摄像头域对KEY2/KEY3做双触发器同步与20ms消抖，按键后先等一个新SOF，再接收四个新完成帧的统计；已在拍摄中的旧帧不参与校准。

BGGR3下按物理位置扣黑：R=max(D−67,0)，B=max(A−65,0)，G=floor((max(Bsite−66,0)+max(Csite−66,0))/2)。每帧检查四个扣黑分量均不低于32、原始四均值均小于960，然后分别累加四帧RGB均值并向下取平均。均值检查不能排除ROI中个别像素饱和，也不能自动判断目标是否中性。

以G为基准，计算红增益floor((G×256+floor(R/2))/R)及蓝增益floor((G×256+floor(B/2))/B)。共用19位逐位除法器，每个通道19拍，无组合可变除法器。任一增益不在64至1024（0.25至4倍）之间时拒绝更新；等待、采样或运算累计超过2秒也拒绝。无有效帧时不会沿用旧统计冒充新测量。

两个请求增益先整体算完，`style_camera_preprocess`在下一个输入SOF同时锁存R/G/B，整帧使用同一组增益。先在RAW10上乘加、舍入、饱和至1023，再转RGB8并进入原Gamma/CDC/DDR通路。DYNAMIC_WB默认0，旧工程不连接新端口仍保留原行为。颜色函数显式接收增益，确保纯色输入不变时切换增益也能重新计算。

`style_wb_calibrator`同时报告已应用增益和状态。顶层通过26bit异步FIFO传递状态和R/B增益，发送端在背压时保持整组数据；像素域在HDMI帧起点锁存后由`style_wb_overlay`显示。状态变化即触发传递，不依赖摄像头继续出帧，因此超时也能显示。OSD可能比摄像头生效稍晚，不能用它绑定某个显示帧的精确frame_id。

校准改变左右两图及DDR中的实际像素值，未来CNN训练/输入预处理需要保持一致。此功能不能保证消除同一画面里所有物体的色差，也没有加入颜色矩阵、曝光自动控制或镜头光学补偿。

## Efinity重建

关闭旧IDE工程后执行：

```powershell
python scripts/prepare_efinity.py --contrast-probe --wb-calibration
python sim/wb_calibration/run_control.py
python sim/wb_calibration/run_pipeline.py
python scripts/build_efinity.py --build
python scripts/build_docs.py
```

IDE入口为新生成的`efinity/style_video.xml`；实际签核与打包使用`build/efinity/<时间>/efinity/style_video.xml`独立快照。源清单包含`style_wb_calibrator.sv`和`style_wb_overlay.sv`，顶层校准连接模板位于`scripts/wb_calibration_shell.vh`。不改变V4/J5引脚、时钟、摄像头寄存器和DDR参数。

新增仿真包括180组增益/范围计算、四帧平均、旧帧忽略、按键消抖/长按、过暗/过亮拒绝、超时、默认恢复；实际RAW→统计→控制→像素链路检查纯色场景的整帧切换；动态像素→Gamma→异步FIFO用独立参考检查背压下像素、SOF/EOL/EOF与frame_id。
