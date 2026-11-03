# 科研示意图生成记录

采用内置 imagegen 工具生成，非CLI。工具没有型号选择参数，无法确认或声称使用用户所称的“Image2.5”。三张均为白底架构示意，不是照片、实验曲线或风格模型输出；正文对接口和算术的说明以RTL和训练代码为准。

## system.png

Use case: infographic-diagram. Create a high resolution landscape scientific system architecture figure for a Chinese FPGA research report, pure white background. Clean professional 2D flat vector-like blocks, dark navy typography, restrained teal and amber accents, no shadows, no decorative art. Title: Ti60 FPGA 实时艺术渲染系统. Main left-to-right data path with correctly directed arrows and six distinct blocks: SC431HAI camera; MIPI D-PHY / RAW10 parser; Bayer to RGB565 / 1280×720; DDR3 frame buffer; C6 CNN accelerator; HDMI 1280×720 60Hz monitor. DDR3 has bidirectional arrows to CNN and a separate read arrow to HDMI. Below show RISC-V controller with dashed control arrows to camera configuration, CNN weights/start/IRQ, display mode. Add KEY0 视图 / KEY1 下一风格 / KEY2 上一风格 / KEY3 UI. Add a separate small gesture branch originating at RGB pixels, labeled 64×64 ROI snapshot → RISC-V gesture analysis → 4秒确认 → 风格选择. Small clock labels UI 100MHz, CNN 166.667MHz, HDMI 74.25MHz. Do not display measured FPS or claim universal gesture accuracy. White margin all around, very legible concise labels. This is a schematic, no board photography, no invented electronic pins.

## network.png

Use case: scientific-educational. High resolution white background landscape academic neural network architecture diagram, clean publication style flat vector-like blocks, navy typography teal/orange modules. Exact architectural content: RGB input H×W×3 → 1×1 Conv 3→6 → four residual blocks → 1×1 Conv 6→3 signed → add ORIGINAL RGB skip → clip → RGB output H×W×3. Four residual blocks are each DW 3×3 depthwise then PW 1×1 6→6 then add block input then clip. Clearly label their dilation rates d=1,2,4,8. Input and every hidden feature remain H×W, no pooling or downsampling. Small bottom annotations: C=6; RF=31×31; 396卷积权重/风格; INT8权重; 22位累加; 十组独立参数共用硬件. Draw global original RGB skip around all blocks to final add, and internal residual loop over one magnified block inset. Chinese title 全分辨率轻量风格迁移网络. Keep mathematically correct arrows, generous white space. No texture samples, no invented performance plot.

## training.png

Use case: infographic-diagram. High resolution white background landscape scientific workflow figure for an FPGA neural style transfer report. Flat clean publication graphics, dark navy text, teal for offline training, orange for quantization, restrained gray for deployment. Three horizontal rows. Top row offline: 内容图像 + 风格参考 → 绘画教师 / VGG感知特征 → 六通道学生训练. Middle row loss detail four parallel boxes: 内容损失; Gram风格损失; 局部纹理能量; 弱像素蒸馏与TV正则 → 损失加权 → 反向传播. Bottom row deployment: 冻结BN折叠 → INT8逐通道权重与移位 → 整数参考逐层核对 → 736B/风格参数包 → RISC-V加载 → FPGA CNN. Separate border note: 模型实际输出用于效果对比，示意图不代表实测结果. Emphasize ten independently trained parameter groups, one reused accelerator. No fabricated loss chart, no claimed accuracy, no photos, pure white background and spacious margins.



## 技术复核后的编辑

- system：移除CNN直达HDMI箭头，保留CNN与DDR双向和DDR至HDMI；显示控制改为原图/风格/对比，避免暗示运行时改时序。
- training：学生输入为RGB3通道、隐藏6通道，风格由独立参数选择；不拼接风格图。纹理能量标注为8×8局部平均梯度幅值，量化框简写权重＋偏置＋右移。均由内置imagegen编辑，保留白底。
- training_log.pdf/png来自12000行真实训练CSV，由matplotlib绘制，未使用图像生成模型制造曲线。

- style_principle.png 为第二部分的绘画原理示意。生成指令要求白底横排三栏：A 同一场景及轮廓，B 笔触与对称通道共现矩阵，C 局部笔触与水平、垂直两个方向的强度变化。文字说明由LaTeX排版。使用内置图像生成工具，接口未返回可核验的“GPT Image 2.5”型号。
