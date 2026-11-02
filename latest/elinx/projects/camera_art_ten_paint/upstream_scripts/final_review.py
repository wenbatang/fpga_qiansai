"""Fresh ten-style/CAM7/optional-enrollment review. No hardware commands."""
from pathlib import Path
import hashlib,importlib.util,json,sys
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'build/720p';sys.path.insert(0,str(ROOT/'scripts'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def review():
    from signoff import audit,verify
    result=audit(True);assert result==json.loads((B/'signoff.json').read_text(encoding='utf-8'))
    calibration,calibration_sha=verify(ROOT/'sim/calibration_firmware/verification.json')
    assert calibration['firmware_bytes']==result['firmware']['firmware_bytes']
    assert calibration['loaded']==[*range(10),0] and calibration['parameter_writes']==2376
    reports=calibration['reports'];assert calibration['roi_complete']==len(reports)==58
    assert [r['label'] for r in reports[:43]]==[None]*3+[i for i in range(10) for _ in range(4)]
    assert all(r['roi_words']==2048 for r in reports)
    normal=reports[43:];assert len(normal)==15 and all(r['label']==0 and r['status']&15==1 for r in normal[2:])
    qualified_seconds=(normal[-1]['report_tick']-normal[2]['report_tick'])/100000000
    assert qualified_seconds>=4 and (normal[-1]['status']>>4)&7==4
    assert calibration['guard_requests'][-1]['slot']==0 and calibration['guard_requests'][-1]['result']==1
    assert calibration['completion_during_roi']>=1 and calibration['interrupts']>=1 and calibration['m_instructions']>2
    spec=importlib.util.spec_from_file_location('ten_cam7',ROOT/'pc/camera_view.py')
    parser=importlib.util.module_from_spec(spec);spec.loader.exec_module(parser);parser_cases=parser.self_test()
    for learning in [False,True]:
        for code in range(11):
            for progress in range(5):
                fields=[0]*33;status=code|(progress<<4)|(1<<8)|(int(learning)<<10)
                fields[32]=status<<21
                d=parser.decode('@CAM7,'+','.join(f'{v:08X}' for v in fields))
                assert d['gesture']==(code-1 if code else None) and d['gesture_windows']==progress and d['learning']==learning
    docs=[ROOT/'README.md',ROOT/'architecture.html',ROOT/'docs/project.md']
    assert all(p.is_file() for p in docs)
    from html.parser import HTMLParser
    class Links(HTMLParser):
        def handle_starttag(self,tag,attrs):
            for key,value in attrs:
                if key=='href':assert (ROOT/value).exists(),value
    Links().feed((ROOT/'architecture.html').read_text(encoding='utf-8'))
    return dict(result='PASS',bitstream_sha256=result['bitstream_sha256'],signoff_sha256=sha(B/'signoff.json'),
        reviewer_sha256=sha(Path(__file__)),process=[1280,720],display=[1280,720,60],styles=10,
        source_style_ids=result['models']['source_ids'],style_checkpoint_sha256=result['models']['checkpoint_sha256'],
        gesture_digits=list(range(10)),gesture_classifier='enhanced personal calibration: robust largest component, four192-feature exemplars/mirror, three-capture votes',
        gesture_requires_enrollment=True,gesture_default_autoswitch=False,calibration_persistent=False,
        gesture_roi=[0,40,640,640],snapshot=[64,64,'RGB565'],decision_period_seconds=1,physical_samples_per_decision=3,calibration_templates_per_digit=4,
        hold_seconds=4,minimum_fresh_reports=5,protocol='CAM7',parser_self_test=parser_cases,
        atomic_style_commit=True,auto_style_on_raw_confirmation=True,ui_toggle_key=3,
        ui_toggle_resets_board=False,different_digit_requalifies=True,view_return_rearms=True,stack_headroom_bytes=result['stack_headroom_bytes'],firmware_bytes=result['firmware']['firmware_bytes'],
        resources=result['resources'],xlr_used=result['xlr_used'],setup_min_ns=result['setup_min_ns'],hold_min_ns=result['hold_min_ns'],
        full720_slot0_split_model_fps=result['full720_split_model_fps'],simulations=result['simulations'],
        supplemental_calibration_firmware=dict(receipt_sha256=calibration_sha,roi_complete=58,
            enrolled_digits=list(range(10)),parameter_writes=calibration['parameter_writes'],
            qualified_model_seconds=qualified_seconds,instructions=calibration['instructions'],
            scope=calibration['scope']),
        sapphire_single_fist_ms=verify(ROOT/'sim/sapphire_latency/verification.json')[0]['classification_ms'],
        sapphire_latency_scope='Standalone cycle probe with explicitly prepared other-class prototypes; not production enrollment, worst-case, or real-camera accuracy',
        docs_sha256={str(p):sha(p) for p in docs},board_programmed=False,board_fps_verified=False,
        gesture_accuracy_verified=False,gesture_processing_cycles_verified=False,
        limitations='Current ten painterly models checked in RTL/EFX plus full720 slot0 SPLIT, software50 full720/40 tiny. Enhanced classifier has controlled C/Python and synthetic old/new robustness checks, not real human accuracy. True Sapphire tests ten-style control/M/IRQ with hand MMIO disabled; calibration/4s handshake uses actual C and a supplementary actual RV32IM machine-code run in explicit camera/MMIO/timer models, not measured Sapphire processing cycles. Public neural hand classifiers failed quality checks and are not active. Real enrolled-user accuracy, full-system continuous FPS, physical rail/current/temperature are not measured.')
def main():
    try:value=review()
    except Exception as e:
        (B/'final_review.json').write_text(json.dumps(dict(result='FAIL',reason=str(e))),encoding='utf-8');raise
    (B/'final_review.json').write_text(json.dumps(value,indent=2),encoding='utf-8');print(json.dumps(value,indent=2))
if __name__=='__main__':main()
