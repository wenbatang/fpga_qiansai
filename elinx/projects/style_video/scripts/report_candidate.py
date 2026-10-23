"""Record actual candidate results, including failed STA, without generating bit."""
from pathlib import Path
import hashlib,json,re,sys
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'build/camera_vga'
sys.path.append(str(ROOT/'scripts'))
from camera_signoff import electrical,audit
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 text=(BUILD/'outflow/ti60_camera.timing.rpt').read_text()
 summary=text.split('---------- 2. Clock Relationship Summary (begin) ----------')[1].split('---------- Clock Relationship Summary (end)')[0]
 setup,hold=summary.split('Hold (Min) Clock Relationship')
 def rows(s):return [{'launch':m[1],'capture':m[2],'slack_ns':float(m[3])} for m in re.finditer(r'^\s*(\S+)\s+(\S+)\s+-?\d+\.\d+\s+(-?\d+\.\d+)\s+\(R-R\)',s,re.M)]
 result={'status':'NOT_SIGNED_OFF','setup':rows(setup),'hold':rows(hold),'board_programmed':False,'configuration_generated':False,
  'electrical':electrical(),'manifest_sha256':sha(BUILD/'manifest.json'),
  'reports_sha256':{n:sha(BUILD/'outflow'/n) for n in ['ti60_camera.map.rpt','ti60_camera.place.rpt','ti60_camera.timing.rpt','ti60_camera.pinout.csv']}}
 try:audit(require_bit=False)
 except (AssertionError,ValueError,KeyError) as error:result['audit_failure']=str(error)
 else:result['status']='CAD_PASSED_NO_BIT'
 result['negative_setup']=[r for r in result['setup'] if r['slack_ns']<0]
 result['negative_hold']=[r for r in result['hold'] if r['slack_ns']<0]
 (BUILD/'candidate_status.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(result['status'],result.get('audit_failure',''),json.dumps(result['negative_setup']))
if __name__=='__main__':main()
