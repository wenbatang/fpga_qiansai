"""第一课：固定权重的单个神经元。直接运行，不进行训练。"""


def relu(value):
    """激活函数：负数变为 0，非负数保持原值。"""
    return max(0.0, value)


def neuron(inputs, weights, bias):
    """一个输入对应一个权重：先乘加，再加偏置，最后激活。"""
    if len(inputs) != len(weights):
        raise ValueError("输入数量与权重数量必须一致")

    total = 0.0
    for index in range(len(inputs)):
        product = inputs[index] * weights[index]
        total += product
        print(f"第 {index + 1} 项：{inputs[index]} × {weights[index]} = {product:.2f}")

    z = total + bias
    output = relu(z)
    print(f"乘积之和 = {total:.2f}")
    print(f"加偏置：z = {total:.2f} + ({bias:.2f}) = {z:.2f}")
    print(f"激活：ReLU(z) = {output:.2f}")
    return output


def main():
    # 两个输入、两个权重。权重和偏置都是人为给定，还没有学习。
    inputs = [2.0, 3.0]
    weights = [0.5, -1.0]
    bias = 0.2
    output = neuron(inputs, weights, bias)
    print(f"神经元最终输出 = {output:.2f}")


if __name__ == "__main__":
    main()
