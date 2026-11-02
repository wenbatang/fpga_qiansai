"""Update local documentation only after the same-build offline signoff passes."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1];WS=ROOT.parents[2]


def main():
    signed=json.loads((ROOT/'build/720p/signoff.json').read_text(encoding='utf-8'));assert signed['result']=='PASS'
    reviewed=json.loads((ROOT/'build/720p/final_review.json').read_text(encoding='utf-8'))
    assert reviewed['result']=='PASS' and reviewed['bitstream_sha256']==signed['bitstream_sha256']
    r=signed['resources'];fps=signed['min_model_fps'];setup=signed['setup_min_ns'];hold=signed['hold_min_ns'];bit=signed['bitstream_sha256']
    summary=f"RAM{r['EFX_RAM10']}/256、DSP{r['EFX_DSP48']}/160、XLR{signed['xlr_used']}/60800；setup/hold {setup:+.3f}/{hold:+.3f}ns；最低CNN/DMA模型吞吐{fps:.6f}fps"
    path=ROOT/'README.md';text=path.read_text(encoding='utf-8')
    pending='**当前状态：最终模型与完整整机签核正在进行。尚无可下载的新bit；旧可用版本保持。**'
    assert pending in text
    text=text.replace(pending,'**当前状态：最终离线签核与fresh复查通过，已生成新bit；旧可用版本保持。实板画质与30fps仍待测试。**')
    text += '\n## 本次交付\n\n'+summary+'。这些是CAD和有界AXI模型结果，不是实板FPS。\n\n[最终bit](build/720p/outflow/ti60_camera.bit) · [工程XML](build/720p/ti60_camera.xml) · [signoff](build/720p/signoff.json) · [fresh复查](build/720p/final_review.json)。\n\nSHA256：`'+bit+'`。本轮只生成文件，未下载或写Flash。\n'
    path.write_text(text,encoding='utf-8')
    for name in ['validation.md','performance.md']:
        path=ROOT/'docs'/name;text=path.read_text(encoding='utf-8')
        if name=='validation.md':text=text.replace('当前交互工程尚在最终模型和整机签核阶段。','最终模型和离线整机签核已完成。')
        text+='\n## 最终签核补充\n\n'+summary+'。21类当前回执、电气79脚12Bank、23标量首级/166 Gray/75稳定束/8精确D-PHY首级、同次模型/固件/ROM/源码/STA与bit共同绑定。四模型各921600像素完整CNN/DMA及一个完整对半帧逐值一致；四模型EFX核和实际对半DMA原语网表也逐值通过。不是完整摄像头SoC实板验收。\n\nbit SHA256：`'+bit+'`。实板持续30fps、主观画质和实际电气测量待验证。\n'
        path.write_text(text,encoding='utf-8')
    path=ROOT/'architecture.html';text=path.read_text(encoding='utf-8')
    start=text.index('<div class="warn" id="release-status">');end=text.index('</div>',start)+6
    text=text[:start]+'<div class="warn" id="release-status">最终离线签核PASS，已生成bit，未代为下载/Flash。'+summary+'。实际板上30fps、画质和供电温升仍待测试。</div>'+text[end:]
    text=text.replace('保护/对半像素/按键/模式身份已有候选回归，最终还需完整四模型720p、实际原语数值、电气、精确CDC及STA共同通过。','最终四模型完整720p、对半像素、按键/模式身份、实际原语数值、电气、精确CDC及STA已经共同通过；上面的候选数字为历史过程。')
    path.write_text(text,encoding='utf-8')
    path=WS/'docs/Ti60_programming_guide.md';lines=path.read_text(encoding='utf-8').splitlines()
    marker='> **新交互版正在签核（2026-10-30）：**'
    indices=[i for i,line in enumerate(lines) if line.startswith(marker)];assert len(indices)==1
    lines[indices[0]]='> **新四风格与三界面（2026-10-30）：** 独立[camera_art_interactive](../elinx/projects/camera_art_interactive/README.md)，[最终bit](../elinx/projects/camera_art_interactive/build/720p/outflow/ti60_camera.bit)、[XML](../elinx/projects/camera_art_interactive/build/720p/ti60_camera.xml)、[架构](../elinx/projects/camera_art_interactive/architecture.html)。新独立空间层模型17000步；KEY0循环原图/风格/左原右风格，KEY1下一风格、KEY2上一风格、KEY3按住约1秒复位，默认原图。真正720p处理、720p60显示；'+summary+'，实板持续30fps待测。Programmer/JTAG临时测试，不另烧固件或串口传图；本轮未下载/Flash。CAM5/115200只读诊断；电脑手势见[独立演示](../pycode/gesture_demo/README.md)，不发板端命令。bit SHA256 `'+bit+'`。下方旧版本继续保留。'
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    path=WS/'AGENTS.md';text=path.read_text(encoding='utf-8')
    text += '\n- 交互版最终签核补充：'+summary+'；四模型完整720p各逐值通过、完整对半帧通过，实际EFX核四模型/实际EFX对半DMA四模型逐值通过，21类最终回执。79脚12Bank、23标量/166Gray/75稳定束/8 D-PHY精确首级及原生STA、同次模型/ROM/3272B固件/源码/bit共同绑定，未提高DDR/UI/外部电平。新bit `camera_art_interactive/build/720p/outflow/ti60_camera.bit` SHA256 `'+bit+'`，signoff/fresh final_review均PASS后才交付。README、architecture、模块/模型/验证/性能及根使用指南已更新；未上板，实际持续30fps、画质、供电温升仍待验收。\n'
    path.write_text(text,encoding='utf-8')
    print('Updated local documentation for signed interactive release')


if __name__=='__main__':main()
