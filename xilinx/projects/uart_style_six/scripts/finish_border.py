"""Verify and build mirror-boundary release; no hardware access or retraining."""
from pathlib import Path
import sys,hashlib,json,os,time
ROOT=Path(__file__).resolve().parents[1];WS=ROOT.parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from desktop_process import run


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def stage(name,args):
    print('START',name,flush=True)
    if run([sys.executable,*map(str,args)],ROOT/'build',ROOT/'build'/('border_'+name+'.log')):
        raise RuntimeError('Failed '+name)
    print('PASS',name,flush=True)


def main():
    os.environ['PATH']='E:/softare_FPGA/iverilog/iverilog/bin;'+os.environ['PATH']
    export=WS/'pycode/runs/art6_v2/export'
    for name,w,h in [('border_learned',71,69),('border_tiny',1,1),('border_small_axes',2,3),('border_narrow',1,33)]:
        stage(name,[ROOT/'sim/check_cnn.py','--export',export,'--styles','8','--width',w,'--height',h,'--name',name])
    stage('link',[ROOT/'sim/check_link.py','--export',export])
    full=WS/'pycode/results/art6_border_v1/board_preview/verification.json'
    deadline=time.monotonic()+3600
    while not full.exists():
        if time.monotonic()>deadline:raise TimeoutError('Full-size software proof')
        time.sleep(3)
    checks={}
    for name in ['border_learned','border_tiny','border_small_axes','border_narrow','border_link']:
        receipt=ROOT/'sim'/name/'verification.json';data=json.loads(receipt.read_text());assert 'PASS' in data['result']
        for path,value in data['sha256'].items():assert sha(Path(path))==value,path
        checks[name]=sha(receipt)
    key=ROOT/'sim/keys/result.txt';assert 'PASS control:' in key.read_text()
    proof={'result':'PASS_SOFTWARE_AND_RTL','models':json.loads(full.read_text(encoding='utf-8'))['models'],
        'receipts_sha256':checks,'keys_receipt_sha256':sha(key),
        'keys_source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'rtl/style_keys.sv',ROOT/'rtl/style_key_control.sv',ROOT/'sim/check_keys.py']},
        'full720_software_sha256':sha(full),'full_720p_rtl_frame_simulated':False,'board_programmed':False}
    (ROOT/'build/learning_acceptance.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
    for profile in ['720p','vga']:
        stage('build_'+profile,[ROOT/'create_project.py','--profile',profile,'--build','--resume'])
    deadline=time.monotonic()+3600
    while not (ROOT/'sim/border_720_core/verification.json').exists():
        if time.monotonic()>deadline:raise TimeoutError('Full720 boundary CNN RTL')
        time.sleep(3)
    for profile in ['720p','vga']:
        stage('signoff_'+profile,[ROOT/'scripts/signoff.py','--profile',profile])
    print('BORDER RELEASE BOTH PROFILES SIGNED; NO HARDWARE ACCESS',flush=True)


if __name__=='__main__':main()
