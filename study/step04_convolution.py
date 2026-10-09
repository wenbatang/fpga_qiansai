"""第四课：单通道二维卷积的前向计算，stride=1、padding=0。"""


def conv2d_valid(image, kernel, bias=0.0):
    height, width = len(image), len(image[0])
    kernel_height, kernel_width = len(kernel), len(kernel[0])
    if kernel_height > height or kernel_width > width:
        raise ValueError('卷积核不能大于输入图像')
    output = []

    for row in range(height - kernel_height + 1):
        output_row = []
        for col in range(width - kernel_width + 1):
            value = bias
            for ky in range(kernel_height):
                for kx in range(kernel_width):
                    value += image[row + ky][col + kx] * kernel[ky][kx]
            output_row.append(value)
        output.append(output_row)
    return output


def show_matrix(title, matrix):
    print(title)
    for row in matrix:
        print(' '.join(f'{value:7.2f}' for value in row))


def main():
    image = [[1, 2, 3, 4], [5, 6, 7, 8],
             [9, 10, 11, 12], [13, 14, 15, 16]]
    kernel = [[1, 0, -1], [1, 0, -1], [1, 0, -1]]
    show_matrix('输入图像 4×4：', image)
    show_matrix('卷积核 3×3：', kernel)
    show_matrix('输出特征图 2×2：', conv2d_valid(image, kernel))
    print('第一个输出：1-3 + 5-7 + 9-11 = -6')


if __name__ == '__main__':
    main()
