# def relu(x):
#     return max(0.0,x)

# def neuron(inputs, weights, bias):
#     if len(inputs) != len(weights):
#         raise ValueError("inputs and weights must have the same length")
    
#     total = 0.0
#     for i in range(len(inputs)) :
#         product = inputs[i] * weights[i]
#         total += product

#     total += bias
#     return relu(total)

# def main():
#     inputs = [2.0, 3.0]
#     weights = [0.5, -1.0]
#     bias = 0.2
#     output = neuron(inputs, weights, bias)
#     print("Output:", output)

# if __name__ == "__main__":
#     main()

# def train(epochs=200, learning_rate=0.05) :
#     samples = [(0.0, 1.0), (1.0, 3.0), (2.0, 5.0), (3.0, 7.0)]
#     weight = 0.0
#     bias = 0.0
#     for epoch in range(epochs) :
#         loss = 0.0
#         grad_weight = 0.0
#         grad_bias = 0.0

#         for x, target in samples :
#             prediction = weight * x + bias
#             error = prediction - target
#             loss += error ** 2
#             grad_weight += 2.0 * error * x
#             grad_bias += 2.0 * error
        
#         count = len(samples)
#         grad_weight /= count
#         grad_bias /= count

#         if (epoch+1) % 50 == 0 :
#             print(f"Epoch:, {(epoch+1):3d}, Loss:, {loss:.6f}, Weight:, {weight:.4f}, Bias:, {bias:.4f}")
#         weight -= learning_rate * grad_weight
#         bias -= learning_rate * grad_bias
    
    
    

#     return weight, bias

# def main():
#     weight, bias = train()
#     print("Final Weight:", weight)
#     print("Final Bias:", bias)

# if __name__ == "__main__":
#     main()

# import math
# import random

# def sigmoid(value):
#     if value >= 0 :
#         return 1.0 / (1.0 + math.exp(-value))
#     exp_value = math.exp(value)
#     return exp_value / (1.0 + exp_value)

# def forward(inputs,model) :
#     hidden = []
#     for index in range(4) :
#         z = sum(inputs[j] * model['w1'][index][j] for j in range(2))
#         z += model['b1'][index]
#         hidden.append(math.tanh(z))
#     z_out = sum(hidden[j] * model['w2'][j] for j in range(4)) + model['b2']
#     return hidden, sigmoid(z_out)

# def train(epochs=6000, learning_rate=0.1) :
#     rng = random.Random(7)
#     model = {
#         'w1': [[rng.uniform(-1,1) for _ in range(2)] for _ in range(4)],
#         'b1': [0.0] * 4,
#         'w2': [rng.uniform(-1,1) for _ in range(4)],
#         'b2': 0.0
#     }
#     samples = [([0.0, 0.0], 0.0), ([0.0, 1.0], 1.0),([1.0, 0.0],1.0), ([1.0, 1.0], 0.0)]
#     for epoch in range(epochs) :
#         dw1 = [[0.0] * 2 for _ in range(4)]
#         db1 = [0.0] * 4
#         dw2 = [0.0] * 4
#         db2 = 0.0
#         loss = 0.0
#         for inputs, target in samples :
#             hidden, prediction = forward(inputs,model)
#             loss += (prediction - target) ** 2
#             dz_out = 2 * (prediction - target) * prediction * (1.0 - prediction) # sigmoid求导加x**2求导
#             for i in range(4) :
#                 dw2[i] += dz_out * hidden[i]
#                 dz_hidden = dz_out * model['w2'][i] * (1.0 - hidden[i] ** 2)
#                 db1[i] += dz_hidden
#                 for j in range(2) :
#                     dw1[i][j] += dz_hidden * inputs[j]
#         if epoch in (0,999,2999,epochs-1) :
#             print(f"Epoch:, {(epoch+1):3d}, Loss:, {loss:.6f}")
#         scale = learning_rate / len(samples)
#         for i in range(4) :
#             for j in range(2) :
#                 model['w1'][i][j] -= scale * dw1[i][j]
#             model['b1'][i] -= scale * db1[i]
#             model['w2'][i] -= scale * dw2[i]
#         model['b2'] -= scale * db2

#     return model

# def main():
#     model = train()
#     for inputs, target in [([0, 0], 0), ([0, 1], 1), ([1, 0], 1), ([1, 1], 0)]:
#         _, prediction = forward(inputs, model)
#         label = int(prediction >= 0.5)
#         print(f"输入={inputs}，输出={prediction:.4f}，判定={label}，目标={target}")


# if __name__ == '__main__':
#     main()

# def conv2d_valid(image, kernel, bias=0.0):
#     height, width = len(image), len(image[0])
#     kernel_height, kernel_width = len(kernel), len(kernel[0])
#     if kernel_height > height or kernel_width > width:
#         raise ValueError("Kernel dimensions must be less than or equal to image dimensions")
#     output = []

#     for row in range(height - kernel_height + 1):
#         output_row = []
#         for col in range(width - kernel_width + 1):
#             value = bias
#             for i in range(kernel_height):
#                 for j in range(kernel_width):
#                     value += image[row + i][col + j] * kernel[i][j]
#             output_row.append(value)
#         output.append(output_row)
#     return output

# def show_matrix(title, matrix):
#     print(title)
#     for row in matrix:
#         print(' '.join(f'{value:7.2f}' for value in row) )


# def main():
#     image = [[1, 2, 3, 4], [5, 6, 7, 8],
#              [9, 10, 11, 12], [13, 14, 15, 16]]
#     kernel = [[1, 0, -1], [1, 0, -1], [1, 0, -1]]
#     show_matrix('输入图像 4×4：', image)
#     show_matrix('卷积核 3×3：', kernel)
#     show_matrix('输出特征图 2×2：', conv2d_valid(image, kernel))
#     print('第一个输出：1-3 + 5-7 + 9-11 = -6')


# if __name__ == '__main__':
#     main()


import math
import random

from step04_convolution import conv2d_valid, show_matrix

def make_image(label, position=2 , noise=0.0, seed=0) :
    if label not in (0,1) or not 0 <= position < 6 :
        raise ValueError("Invalid label or position")
    rng = random.Random(seed)
    image = []
    for row in range(6) :
        line = []
        for col in range(6) :
            is_line = (row == position) if label == 0 else (col == position)
            pixel = float(is_line) + rng.uniform(-noise, noise)
            line.append(min(1.0, max(0.0, pixel)))
        image.append(line)
    return image

def new_model(seed=7) :
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
