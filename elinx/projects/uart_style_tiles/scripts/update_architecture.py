from pathlib import Path
import json,re
ROOT=Path(__file__).resolve().parents[1]
def main():
    r=json.loads((ROOT/'build/720p/signoff.json').read_text(encoding='utf-8'))
    from signoff import audit
    audit(ROOT/'build/720p');audit(ROOT/'build/vga')
    res=r['resources'];ram=res['ram10'];dsp=res['dsp'];xlr=res['xlr']
    path=ROOT/'architecture.html';text=path.read_text(encoding='utf-8')
    status=f'''完整720p分条工程已完成综合、接口检查、布局布线及配置生成；当前源码、四种权重、全部工作时钟和{r['active_package_pins']}个实际使用封装引脚已签核。最小建立裕量+{r['setup_min_ns']:.3f}ns，保持+{r['hold_min_ns']:.3f}ns，核心100MHz建立+{r['core_setup_ns']:.3f}ns。<br>资源：{ram['used']}/{ram['available']} RAM10，{dsp['used']}/{dsp['available']} DSP，{xlr['used']:,}/{xlr['available']:,} XLR；输入/输出1280×720，CNN每条352×720，HDMI720p30。<br>注册Gray跨域{r['gray_paths']}条受约束，单比特首级{r['scalar_first_stages']}处，异步复位SR{r['async_reset_pins']}处；同步链均为FF，未用宽泛时钟组掩盖内部路径。<br><a href="build/720p/outflow/ti60_style.bit">本地V4配置文件</a> · <a href="build/720p/signoff.json">签核指纹</a> · <a href="pc/camera_gui.py">配套摄像头GUI，默认720p</a><br>bit SHA256：<code>{r['bitstream_sha256']}</code><br><strong>没有下载实板；串口、DDR校准、实屏与处理FPS仍待实测。MIPI与RISC-V尚未集成。</strong>'''
    text=re.sub(r'(<div id="build-status" class="note">).*?(</div>)',lambda m:m[1]+status+m[2],text,flags=re.S)
    v=json.loads((ROOT/'build/vga/signoff.json').read_text(encoding='utf-8'))
    vstatus=f'''显式VGA配置也完成独立综合/布线/66引脚签核：640×480，两条352×480，720p30居中显示。建立+{v['setup_min_ns']:.3f}ns，保持+{v['hold_min_ns']:.3f}ns，100MHz核心+{v['core_setup_ns']:.3f}ns；资源{v['resources']['ram10']['used']}/256 RAM10，{v['resources']['dsp']['used']}/160 DSP，{v['resources']['xlr']['used']:,}/60,800 XLR。<br><a href="build/vga/outflow/ti60_style.bit">VGA配置bitstream</a> · <a href="build/vga/signoff.json">VGA签核</a>；GUI需显式选择vga。SHA256：<code>{v['bitstream_sha256']}</code>。它不是默认720p输入配置。'''
    text=re.sub(r'(<div id="vga-status" class="note">).*?(</div>)',lambda m:m[1]+vstatus+m[2],text,flags=re.S)
    path.write_text(text,encoding='utf-8');print('Updated V4 architecture from actual signoff')
if __name__=='__main__':main()
