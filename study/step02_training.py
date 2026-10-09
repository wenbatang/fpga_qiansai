"""第二课：用梯度下降学习 y = 2*x + 1，先不加激活函数。"""


def train(epochs=200, learning_rate=0.05):
    samples = [(0.0, 1.0), (1.0, 3.0), (2.0, 5.0), (3.0, 7.0)]
    weight = 0.0
    bias = 0.0

    for epoch in range(epochs):
        loss = 0.0
        grad_weight = 0.0
        grad_bias = 0.0

        for x, target in samples:
            prediction = weight * x + bias             # 1. 前向计算
            error = prediction - target
            loss += error ** 2                        # 2. 平方误差
            grad_weight += 2.0 * error * x             # 3. 计算梯度
            grad_bias += 2.0 * error

        # 同一批的四个样本取平均；先算完梯度，再更新参数。
        count = len(samples)
        loss /= count
        grad_weight /= count
        grad_bias /= count

        if epoch in (0, 1, 9, 49, epochs - 1):
            print(f"更新前 epoch={epoch:3d} loss={loss:.6f} "
                  f"weight={weight:.4f} bias={bias:.4f}")

        weight -= learning_rate * grad_weight         # 4. 更新参数
        bias -= learning_rate * grad_bias

    return weight, bias


def main():
    weight, bias = train()
    print(f"训练后：weight={weight:.4f}, bias={bias:.4f}")
    x = 4.0
    print(f"新输入 x={x}，预测={weight * x + bias:.4f}，目标规律给出 9.0")


if __name__ == "__main__":
    main()
