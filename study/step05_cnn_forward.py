"""第五课：完整 CNN 前向计算。单张图，没有 batch 维度。

输入 [6][6] → 卷积 [2][4][4] → ReLU → 平均池化 [2][2][2]
→ 展平 [8] → 全连接 [2] → softmax [2]。
"""

import math
import random

from step04_convolution import conv2d_valid, show_matrix


def make_image(label, position=2, noise=0.0, seed=0):
    """0=横线，1=竖线；单通道浮点值 0～1，按行列存储。"""
    if label not in (0, 1) or not 0 <= position < 6:
        raise ValueError('label 必须为 0/1，position 必须为 0～5')
    rng = random.Random(seed)
    image = []
    for row in range(6):
        line = []
        for col in range(6):
            is_line = (row == position) if label == 0 else (col == position)
            pixel = float(is_line) + rng.uniform(-noise, noise)
            line.append(min(1.0, max(0.0, pixel)))
        image.append(line)
    return image


def new_model(seed=7):
    """生成随机初始参数；这里尚未训练。共 38 个参数。"""
    rng = random.Random(seed)
    return {
        'kernels': [[[rng.uniform(-0.15, 0.15) for _ in range(3)]
                     for _ in range(3)] for _ in range(2)],
        'conv_bias': [0.1, 0.1],
        'fc_weights': [[rng.uniform(-0.2, 0.2) for _ in range(8)]
                       for _ in range(2)],
        'fc_bias': [0.0, 0.0],
    }


def forward(image, model):
    # 1. 两个卷积核，各产生一个 4×4 特征图。
    conv_z = [conv2d_valid(image, model['kernels'][c], model['conv_bias'][c])
              for c in range(2)]

    # 2. 对特征图逐元素应用 ReLU；维度不变。
    activated = [[[max(0.0, value) for value in row] for row in channel]
                 for channel in conv_z]

    # 3. 不重叠的 2×2 平均池化，stride=2；4×4 变成 2×2。
    pooled = []
    for channel in activated:
        pooled_channel = []
        for row in range(0, 4, 2):
            pooled_row = []
            for col in range(0, 4, 2):
                total = sum(channel[row + dy][col + dx]
                            for dy in range(2) for dx in range(2))
                pooled_row.append(total / 4.0)
            pooled_channel.append(pooled_row)
        pooled.append(pooled_channel)

    # 4. 展平顺序：先通道，再行，再列。共 2×2×2=8 个数。
    flat = [value for channel in pooled for row in channel for value in row]

    # 5. 全连接层输出两个分数，称为 logits。
    logits = [sum(model['fc_weights'][label][i] * flat[i] for i in range(8))
              + model['fc_bias'][label] for label in range(2)]

    # 6. softmax：减去最大值避免 exp 溢出，概率总和为 1。
    maximum = max(logits)
    exps = [math.exp(value - maximum) for value in logits]
    probabilities = [value / sum(exps) for value in exps]

    # 保留中间值，第六课的反向传播会使用它们。
    return {'conv_z': conv_z, 'activated': activated, 'pooled': pooled,
            'flat': flat, 'logits': logits, 'probabilities': probabilities}


def cross_entropy(logits, target):
    """交叉熵等于 -log(正确类别概率)，用稳定的 logits 形式计算。"""
    maximum = max(logits)
    log_sum_exp = maximum + math.log(sum(math.exp(z - maximum) for z in logits))
    return log_sum_exp - logits[target]


def predict(image, model):
    probabilities = forward(image, model)['probabilities']
    return max(range(2), key=lambda label: probabilities[label])


def main():
    target = 0
    image = make_image(target)
    model = new_model()
    cache = forward(image, model)
    show_matrix('输入：6×6 单通道横线图，目标类别 0', image)
    for channel in range(2):
        show_matrix(f'卷积输出通道 {channel}：4×4', cache['conv_z'][channel])
        show_matrix(f'ReLU 输出通道 {channel}：4×4', cache['activated'][channel])
        show_matrix(f'平均池化通道 {channel}：2×2', cache['pooled'][channel])
    print('展平 8 个数：', [round(x, 4) for x in cache['flat']])
    print('两个原始分数 logits：', [round(x, 4) for x in cache['logits']])
    print('概率 [横线, 竖线]：', [round(x, 4) for x in cache['probabilities']])
    print(f"交叉熵 loss={cross_entropy(cache['logits'], target):.6f}")
    print('当前参数是随机初始化的，不代表网络已经学会分类。')


if __name__ == '__main__':
    main()
