# 串口与帧发布协议

本工程只传原始 RGB565。PC 解码 PNG/JPEG，不在 PC 风格化，FPGA 没有压缩图片解码器。默认 1280×720，可选独立 `vga` bitstream 处理 640×480；两者均输出标准 720p60。输入配置必须与 FPGA bitstream 匹配，错误尺寸的 ACK 会使发送器明确报错。

## 包头与编码

请求：`00 + COBS(包头 + payload + CRC32) + 00`。回复：原显示工程的 SLIP，`7E` 分隔、`7D` 转义；不能与旧 SLIP 请求工具混用。

包头为小端 `<BBHIIHHHBB>`，固定 20B：

| 字段 | 字节 | 值/意义 |
| --- | ---: | --- |
| version / command | 1 / 1 | version=1；回复 command=request OR 0x80 |
| sequence | 2 | 停等包序号 |
| frame / offset | 4 / 4 | 源帧编号 / 像素数据字节偏移；METRICS 回复 offset 为推理周期 |
| payload_length | 2 | 最大 16384B，DATA 为 16B 的整数倍 |
| width / height | 2 / 2 | 1280×720 或 640×480，需匹配构建配置 |
| format / reserved | 1 / 1 | format=1 RGB565，reserved=0 |

CRC32 为标准 IEEE CRC32，与 Python `zlib.crc32` 一致，覆盖包头和 payload，不覆盖编码/分隔字节；末尾四字节小端。完整帧 CRC 仅覆盖顺序排列的全部原始 RGB565 数据。

| 命令 | 编号 | payload 与完成条件 |
| --- | ---: | --- |
| BEGIN | 1 | 四字节完整帧 CRC；初始化上传会话 |
| DATA | 2 | 像素数据；顺序 offset，DDR B 响应成功后 ACK |
| END | 3 | 空，offset=帧字节数；完整校验、CNN、写回和安全发布后 ACK |
| ABORT | 4 | 空，退出上传；保留已发布前台 |
| QUERY | 5 | 空，会话状态查询 |
| STYLE | 6 | 一个字节：0浮世绘、1梵高、2水墨、3版画；仅空闲时修改 |
| METRICS | 7 | 空，回复 offset 为最近成功转换的 UI 周期数，时钟100MHz |

回复 payload 为一个状态字节。状态0成功；1包头/尺寸、2CRC/编码、3顺序、4忙、5DDR、6帧CRC、7超时、8未校准、9转换失败。通用坏包 NACK 用 command=0x80、sequence=0xFFFF。发送器仅对CRC/忙/未校准及丢ACK做有限重试，其他错误交由显式恢复。

每次发送先 ABORT，选择 STYLE，BEGIN、顺序 DATA、END，最后 METRICS。同一成功 DATA/END 的重传不会重复写入/推理；提交等待期间后台受保护。请求停等，只有处理完当前包后才发送下一包。会话无进展超时5秒，COBS字节间超时1秒；下一次发送从 ABORT/BEGIN 恢复。

## 像素与 DDR

RGB565 小端，R[15:11]、G[10:5]、B[4:0]；行优先、stride=width×2、无行填充。128位 AXI 数据低16位为第一个像素，一拍八个像素，地址单位字节。640×480 与1280×720的帧长度分别为614400B和1843200B，均整除256B读突发。

源区基址4MiB，显示A/B基址0/2MiB。UART只能写源区；CNN只能写空闲显示后台；显示只能读前台。END不允许直接把原图区发布为风格结果。

## 用时与错误边界

2Mbps、8N1每字节十位。720p RGB565纯像素需9.216秒；COBS和ACK带来的预算约9.25–9.28秒，另加USB调度、每包DDR写响应、最终推理、消隐等待及重试。此预算不能当作实测十秒通过。

FPGA推理计时从engine启动到最后一个成功输出写响应，包含DDR背压和显示仲裁，不包含串口上传或等待垂直消隐。PC分别报告总用时、上传至END ACK用时和FPGA周期。单帧周期可换算等效fps，连续摄像头fps仍需最终视频系统实测。

AXI错误时保持已有VALID直到握手，排空未完成事务后报错，受损后台不发布。永久不响应的总线不能靠撤回VALID“恢复”，需硬件复位。错误帧、半帧、CRC失败帧和未收到最终B响应的帧都不可替换屏幕前台。
