"""Insert actual signed build data into the hand-written offline architecture."""
from pathlib import Path
import json,re
ROOT=Path(__file__).resolve().parents[1]
def main():
    receipts={}
    for profile,rel in [('720p','build/signoff.json'),('vga','build/vga/signoff.json')]:
        p=ROOT/rel
        if not p.exists():raise FileNotFoundError('Signoff must complete before updating: '+str(p))
        receipts[profile]=json.loads(p.read_text(encoding='utf-8'))
    rows=[]
    for profile,r in receipts.items():
        rows.append(f"<tr><td>{profile}</td><td>{r['wns_ns']:+.3f}ns</td><td>{r['whs_ns']:+.3f}ns</td><td class='mono'>{r['bitstream_sha256']}</td></tr>")
    block="<p><span class='good'>两套完整 bitstream 已生成并签核</span> · 最终实际四风格权重、88 端口和时序已审查；新版本未下载实板。</p><div class='table'><table><tr><th>配置</th><th>WNS</th><th>WHS</th><th>bitstream SHA256</th></tr>"+''.join(rows)+"</table></div><p>完整资源、仿真范围和警告见验证记录。640×480 与默认720p必须分别核对完整帧结果；推理周期等效FPS并非实板连续视频测试。真实 UART 十秒上传、实屏效果和按键响应仍需上板实测。</p>"
    path=ROOT/'architecture.html';text=path.read_text(encoding='utf-8-sig')
    text=re.sub(r'(<div class="status" id="validation-status">).*?(</div>)',r'\g<1>最终四种模型已训练、整数导出与仿真验证；720p/VGA 两套完整工程已生成 bitstream 并通过时序与 88 端口电气签核。新版本尚未上板。\g<2>',text,flags=re.S)
    text=re.sub(r'(<div id="signoff-details">).*?(</div><p>模块验证)',lambda m:m[1]+block+m[2],text,flags=re.S)
    path.write_text(text,encoding='utf-8')
    print('Updated architecture from both signed receipts')
if __name__=='__main__':main()
