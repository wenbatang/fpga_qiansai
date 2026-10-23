"""Update only the offline HTML build status from audited artifacts."""
from pathlib import Path
import json,re
ROOT=Path(__file__).resolve().parents[1]
def main():
 from verification import comparison
 comp=comparison();(ROOT/'build/resource_comparison.json').write_text(json.dumps(comp,ensure_ascii=False,indent=2),encoding='utf-8')
 text=(ROOT/'architecture.html').read_text(encoding='utf-8')
 a,b=(comp['probes'][str(n)]['resources'] for n in [4,6])
 table='<table><tr><th>仅 CNN 核心综合原语</th><th>四风格</th><th>六风格</th></tr>'
 for key,label in [('EFX_RAM10','RAM10'),('EFX_DSP48','DSP48'),('EFX_LUT4','LUT4'),('EFX_ADD','ADD'),('EFX_FF','FF')]:
  table+=f'<tr><td>{label}</td><td>{a[key]:,}</td><td>{b[key]:,}</td></tr>'
 table+='</table>'
 text=re.sub(r'(<h2>风格数量会不会增加资源？</h2>.*?)<table>.*?</table>',lambda m:m[1]+table,text,flags=re.S)
 for profile in ['720p','vga']:
  p=ROOT/'build'/profile/'signoff.json'
  if p.exists():
   from signoff import audit
   r=audit(p.parent)
   body=f"CAD/66脚签核通过：setup +{r['setup_min_ns']:.3f} ns，hold +{r['hold_min_ns']:.3f} ns。"+'；'.join(f"{k} {v['used']}/{v['available']}" for k,v in r['resources'].items())
   body+=f'<p><a href="build/{profile}/outflow/ti60_style.bit">{profile} bit</a> · <a href="build/{profile}/ti60_style.xml">工程</a> · <a href="build/{profile}/signoff.json">签核</a></p><code>{r["bitstream_sha256"]}</code>'
   opt=r['resource_optimization'];old=opt['before'];now=opt['after']
   body+=f'<p>本次优化：RAM10 {old["ram10"]["used"]}→{now["ram10"]["used"]}，DSP {old["dsp"]["used"]}→{now["dsp"]["used"]}，XLR {old["xlr"]["used"]}→{now["xlr"]["used"]}。模型、分辨率、电平配置及已验证周期不变；<a href="docs/resource_optimization.md">优化与电气复查记录</a>。</p>'
  else:body='当前配置尚未完成 CAD 签核，暂无可交付的新 bit。'
  text=re.sub(r'(<article id="'+profile+r'">).*?(</article>)',lambda m:m[1]+body+m[2],text,flags=re.S)
 (ROOT/'architecture.html').write_text(text,encoding='utf-8')
 print('Updated offline architecture')
if __name__=='__main__':main()
