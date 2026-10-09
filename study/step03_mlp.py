"""第三课：2 个输入 → 4 个 tanh 隐藏神经元 → 1 个 sigmoid 输出，学习 XOR。"""

import math
import random


def sigmoid(value):
    # 分两种情况写，避免 exp 对很大的正数溢出。
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exp_value = math.exp(value)
    return exp_value / (1.0 + exp_value)


def forward(inputs, model):
    hidden = []
    for index in range(4):
        z = sum(inputs[j] * model['w1'][index][j] for j in range(2))
        z += model['b1'][index]
        hidden.append(math.tanh(z))
    z_out = sum(hidden[i] * model['w2'][i] for i in range(4)) + model['b2']
    return hidden, sigmoid(z_out)


def train(epochs=6000, learning_rate=0.1):
    rng = random.Random(7)
    model = {
        'w1': [[rng.uniform(-1, 1) for _ in range(2)] for _ in range(4)],
        'b1': [0.0] * 4,
        'w2': [rng.uniform(-1, 1) for _ in range(4)],
        'b2': 0.0,
    }
    samples = [([0.0, 0.0], 0.0), ([0.0, 1.0], 1.0),
               ([1.0, 0.0], 1.0), ([1.0, 1.0], 0.0)]

    for epoch in range(epochs):
        # 每一轮清零梯度，累计同一批四个样本的贡献。
        dw1 = [[0.0] * 2 for _ in range(4)]
        db1 = [0.0] * 4
        dw2 = [0.0] * 4
        db2 = 0.0
        loss = 0.0

        for inputs, target in samples:
            hidden, prediction = forward(inputs, model)
            loss += (prediction - target) ** 2
            # loss → sigmoid 输出之前的 z_out。
            dz_out = 2 * (prediction - target) * prediction * (1 - prediction)
            db2 += dz_out
            for i in range(4):
                dw2[i] += dz_out * hidden[i]
                # z_out → 隐藏输出 → tanh 之前的 z。
                dz_hidden = dz_out * model['w2'][i] * (1 - hidden[i] ** 2)
                db1[i] += dz_hidden
                for j in range(2):
                    dw1[i][j] += dz_hidden * inputs[j]

        if epoch in (0, 999, 2999, epochs - 1):
            print(f"更新前 epoch={epoch:4d}, MSE={loss / len(samples):.6f}")
        scale = learning_rate / len(samples)
        for i in range(4):
            for j in range(2):
                model['w1'][i][j] -= scale * dw1[i][j]
            model['b1'][i] -= scale * db1[i]
            model['w2'][i] -= scale * dw2[i]
        model['b2'] -= scale * db2

    return model


def main():
    model = train()
    for inputs, target in [([0, 0], 0), ([0, 1], 1), ([1, 0], 1), ([1, 1], 0)]:
        _, prediction = forward(inputs, model)
        label = int(prediction >= 0.5)
        print(f"输入={inputs}，输出={prediction:.4f}，判定={label}，目标={target}")


if __name__ == '__main__':
    main()
