"""第六课：手写 CNN 反向传播，训练卷积层和全连接层。

复用第五课的前向函数，避免训练和推理各写一套不同计算。
仅用于 6×6 横线/竖线教学数据，不是风格迁移模型。
"""

import random

from step05_cnn_forward import (cross_entropy, forward, make_image,
                                new_model, predict)


def backward(image, target, model, cache):
    """先计算所有梯度，不在这里更新参数。"""
    # 1. softmax + 交叉熵对 logits 的导数为 probability - one_hot。
    dlogits = cache['probabilities'][:]
    dlogits[target] -= 1.0
    dfc_weights = [[dlogits[label] * cache['flat'][i] for i in range(8)]
                   for label in range(2)]
    dfc_bias = dlogits[:]

    # 2. 全连接层把梯度传给 8 个输入特征。
    dflat = [sum(dlogits[label] * model['fc_weights'][label][i]
                 for label in range(2)) for i in range(8)]

    # 3. 反向展平 + 平均池化 + ReLU。
    dconv_z = [[[0.0] * 4 for _ in range(4)] for _ in range(2)]
    for channel in range(2):
        for row in range(2):
            for col in range(2):
                index = channel * 4 + row * 2 + col
                for dy in range(2):
                    for dx in range(2):
                        y, x = row * 2 + dy, col * 2 + dx
                        # 平均池化的四个输入各分到 1/4 梯度。
                        # ReLU 在负数处梯度为 0，在正数处为 1。
                        # 零点不可导，本例约定零点梯度为 0。
                        if cache['conv_z'][channel][y][x] > 0:
                            dconv_z[channel][y][x] = dflat[index] / 4.0

    # 4. 共享卷积核：把全部输出位置贡献累加到同一个核权重。
    dkernels = [[[0.0] * 3 for _ in range(3)] for _ in range(2)]
    dconv_bias = [0.0] * 2
    for channel in range(2):
        for row in range(4):
            for col in range(4):
                grad = dconv_z[channel][row][col]
                dconv_bias[channel] += grad
                for ky in range(3):
                    for kx in range(3):
                        dkernels[channel][ky][kx] += grad * image[row + ky][col + kx]

    # 原始输入不是参数，无需更新它；本网络没有卷积之前的可训练层。
    return {'kernels': dkernels, 'conv_bias': dconv_bias,
            'fc_weights': dfc_weights, 'fc_bias': dfc_bias}


def update(model, gradients, learning_rate):
    """所有梯度计算完成后，统一做一次 SGD 参数更新。"""
    for channel in range(2):
        for ky in range(3):
            for kx in range(3):
                model['kernels'][channel][ky][kx] -= (
                    learning_rate * gradients['kernels'][channel][ky][kx])
        model['conv_bias'][channel] -= learning_rate * gradients['conv_bias'][channel]
    for label in range(2):
        for i in range(8):
            model['fc_weights'][label][i] -= learning_rate * gradients['fc_weights'][label][i]
        model['fc_bias'][label] -= learning_rate * gradients['fc_bias'][label]


def make_dataset(seed_base, repeats):
    # 两类 × 四种位置 × repeats 组独立噪声。不同 seed_base 区分训练/测试。
    samples = []
    for label in range(2):
        for position in range(1, 5):
            for repeat in range(repeats):
                seed = seed_base + label * 100 + position * 10 + repeat
                samples.append((make_image(label, position, noise=0.08, seed=seed), label))
    return samples


def evaluate(samples, model):
    total_loss = 0.0
    correct = 0
    for image, target in samples:
        cache = forward(image, model)
        total_loss += cross_entropy(cache['logits'], target)
        label = max(range(2), key=lambda i: cache['probabilities'][i])
        correct += int(label == target)
    return total_loss / len(samples), correct / len(samples)


def train(epochs=100, learning_rate=0.05):
    model = new_model(seed=7)
    train_samples = make_dataset(seed_base=1000, repeats=2)
    test_samples = make_dataset(seed_base=2000, repeats=4)
    rng = random.Random(11)
    loss, accuracy = evaluate(train_samples, model)
    print(f'训练前：loss={loss:.6f}，训练正确率={accuracy:.1%}')

    for epoch in range(epochs):
        rng.shuffle(train_samples)
        # batch size=1：每个样本前向、反向、更新一次，称为 SGD。
        for image, target in train_samples:
            cache = forward(image, model)
            gradients = backward(image, target, model, cache)
            update(model, gradients, learning_rate)

        if epoch in (0, 9, 49, epochs - 1):
            loss, accuracy = evaluate(train_samples, model)
            print(f'更新后 epoch={epoch:3d}：loss={loss:.6f}，训练正确率={accuracy:.1%}')

    loss, accuracy = evaluate(test_samples, model)
    print(f'独立噪声测试集（32 张）：loss={loss:.6f}，正确率={accuracy:.1%}')
    return model


def main():
    model = train()
    for target in (0, 1):
        image = make_image(target, position=3, noise=0.08, seed=3000 + target)
        probabilities = forward(image, model)['probabilities']
        print(f'新图目标={target}，预测={predict(image, model)}，'
              f'概率={[round(p, 4) for p in probabilities]}')
    print('训练后的第一个卷积核：')
    for row in model['kernels'][0]:
        print(' '.join(f'{value:.4f}' for value in row))


if __name__ == '__main__':
    main()
