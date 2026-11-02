"""Read-only CAM7 ten-style/ten-gesture diagnostics; never sends board commands."""
from pathlib import Path
import argparse,json,re
ROOT=Path(__file__).resolve().parents[1]
SOURCE_IDS=[0,2,3,4,34,7,9,15,31,40]
STYLE_LABELS=['梵高旋涡厚涂','浮世绘海浪','彩色剪纸','复古漫画','竹林水墨','阿什维尔抽象','形体对比','蒙德里安几何','彩色马赛克','雨夜厚涂']
REASONS={0:'有效数字候选',1:'背景或无手',7:'分类置信度不足',0x80:'识别禁用或风格界面暂停',0x81:'模式epoch改变，重新取样',0x82:'无对应请求或请求年龄超过0.6秒',0x83:'新报告间隔超过1.6秒',0x84:'读取时快照变化或分类后过期',0x85:'重复的快照序号',0x90:'等待板上手势校准',0x91:'请清空框并采集背景',0x92:'等待或正在录入该类样本',0x93:'录入样本被拒绝'}
MODES=['原图','风格图','左原右风格']
def decode(line):
    text=line.decode('ascii') if isinstance(line,bytes) else line
    fields=text.strip().split(',')
    if len(fields)!=34 or fields[0]!='@CAM7' or any(re.fullmatch(r'[0-9A-Fa-f]{8}',x) is None for x in fields[1:]):
        raise ValueError('Expected CAM7 with 33 HEX32 fields; use the previous project viewer for CAM5/CAM6')
    data=[int(x,16) for x in fields[1:]];mode=data[32];status=(mode>>21)&2047;code=status&15
    result=dict(protocol='CAM7',boot=data[0],capture_frames=data[6],inference_frames=data[7],capture_errors=data[8],engine_cycles=data[11],raw=bool(mode&1),engine_raw=bool(mode&2),loaded_style=(mode>>2)&15,requested_style=(mode>>6)&15,front_raw=bool(mode&(1<<10)),display_mode=(mode>>11)&3,front_mode=(mode>>13)&3,job_mode=(mode>>15)&3,front_style=(mode>>17)&15,gesture_code=code,gesture=code-1 if code else None,gesture_windows=(status>>4)&7,gesture_blocked=bool(status&128),gesture_enabled=bool(status&256),gesture_trigger_parity=bool(status&512),all_fields=data)
    result['learning']=bool(status&1024)
    if code>10 or result['gesture_windows']>4:raise ValueError('Invalid CAM7 status bits')
    if any(result[k]>2 for k in ['display_mode','front_mode','job_mode']):raise ValueError('Invalid CAM7 display mode')
    if any(result[k]>9 for k in ['loaded_style','requested_style','front_style']):raise ValueError('Invalid CAM7 style ID')
    reason=data[26]&255;profile=(data[26]>>8)&255;classifier_code=(data[26]>>16)&255;score=data[28]>>16
    if score&32768:score-=65536
    rgb=data[29];state=data[31]
    result['diagnostics']=dict(snapshot_sequence=data[24],cpu_reports=data[25],reason=reason,reason_text=REASONS.get(reason,f'未定义原因0x{reason:02X}'),profile=profile,classifier='NN' if profile==255 else str(profile),classified_code=classifier_code,classified_digit=classifier_code-1 if 1<=classifier_code<=10 else None,strict_skin_hits=data[27]&65535,wide_skin_hits=data[27]>>16,best_logit=score,logit_margin=data[28]&65535,mean_rgb=[(rgb>>16)&255,(rgb>>8)&255,rgb&255],classification_ticks=data[30],classification_ms=data[30]/100000,snapshot_epoch=state>>17,snapshot_samples=(state>>4)&8191,snapshot_enabled=bool(state&8),snapshot_pending=bool(state&4),snapshot_active=bool(state&2),snapshot_ready=bool(state&1),raw_hex=[f'{v:08X}' for v in data[24:32]])
    if profile==254:
        d=result['diagnostics'];d.update(classifier='板上校准模板',foreground_pixels=data[27]&65535,noise_threshold=data[27]>>16,best_distance=data[28]&65535,distance_margin=data[28]>>16)
        for key in ['strict_skin_hits','wide_skin_hits','best_logit','logit_margin']:d.pop(key)
    return result
def labels():
    return dict(enumerate(STYLE_LABELS))
def describe(result,names):
    slot=result['front_style'];loaded=result['loaded_style'];digit='-' if result['gesture'] is None else str(result['gesture']);d=result['diagnostics']
    detail=(f"前景像素={d['foreground_pixels']} 噪声阈值={d['noise_threshold']} 距离={d['best_distance']} margin={d['distance_margin']}" if d['profile']==254 else f"logit={d['best_logit']} margin={d['logit_margin']} 肤色像素(严格/宽松)={d['strict_skin_hits']}/{d['wide_skin_hits']}")
    return (f"CAM7 boot={result['boot']:08X} C={result['capture_frames']} I={result['inference_frames']} errors={result['capture_errors']} view={MODES[result['front_mode']]} S={slot}/{names[slot]}(source={SOURCE_IDS[slot]}) loaded={loaded} requested={result['requested_style']} {'L' if result['learning'] else 'G'}={digit} {'A' if result['learning'] else 'P'}={result['gesture_windows']}/{3 if result['learning'] else 4} learning={result['learning']} enabled={result['gesture_enabled']} blocked={result['gesture_blocked']}"
        f" | 快照={d['snapshot_sequence']} CPU报告={d['cpu_reports']} 原因={d['reason']:02X}/{d['reason_text']} classifier={d['classifier']} 分类数字={d['classified_digit']} {detail} 均值RGB={d['mean_rgb']} 分类={d['classification_ms']:.2f}ms 取样={d['snapshot_samples']}/4096 ready={d['snapshot_ready']} active={d['snapshot_active']} pending={d['snapshot_pending']}")
def self_test():
    count=0
    for slot in range(10):
        for code in range(11):
            for windows in range(5):
                values=[0]*33;values[0]=3;values[6]=100;values[7]=90
                status=code|(windows<<4)|128|256|512
                values[32]=(slot<<2)|((9-slot)<<6)|(1<<10)|(2<<11)|(1<<13)|(2<<15)|(slot<<17)|(status<<21)
                result=decode(('@CAM7,'+','.join(f'{v:08X}' for v in values)).encode())
                assert result['loaded_style']==slot and result['requested_style']==9-slot and result['front_style']==slot
                assert result['gesture']==(code-1 if code else None) and result['gesture_windows']==windows
                assert result['gesture_blocked'] and result['gesture_enabled'] and result['gesture_trigger_parity']
                assert not result['learning']
                assert (result['display_mode'],result['front_mode'],result['job_mode'])==(2,1,2)
                count+=1
    for code in range(11):
        values=[0]*33;values[32]=((1024|256|(3<<4)|code)<<21)
        d=decode('@CAM7,'+','.join(f'{v:08X}' for v in values))
        assert d['learning'] and d['gesture']==(code-1 if code else None)
        assert 'L=' in describe(d,labels()) and 'A=3/3' in describe(d,labels());count+=1
    values=[0]*33;values[24:32]=[17,12,0|(255<<8)|(1<<16),321<<16|3,(0xffec<<16)|77,0x7b9a39,3963428,(7<<17)|(4096<<4)|9]
    d=decode('@CAM7,'+','.join(f'{v:08X}' for v in values))['diagnostics']
    assert d['classifier']=='NN' and d['classified_digit']==0 and d['best_logit']==-20 and d['logit_margin']==77
    assert d['mean_rgb']==[123,154,57] and d['classification_ms']==39.63428 and d['snapshot_samples']==4096
    assert d['snapshot_epoch']==7 and d['snapshot_enabled'] and d['snapshot_ready'];count+=1
    values[26]=(254<<8)|(10<<16);values[27]=(15<<16)|2080;values[28]=(456<<16)|123
    d=decode('@CAM7,'+','.join(f'{v:08X}' for v in values))['diagnostics']
    assert d['classifier']=='板上校准模板' and d['foreground_pixels']==2080 and d['noise_threshold']==15 and d['best_distance']==123 and d['distance_margin']==456 and d['classified_digit']==9
    assert 'best_logit' not in d and 'strict_skin_hits' not in d;count+=1
    for reason in REASONS:
        values[26]=reason
        assert decode('@CAM7,'+','.join(f'{v:08X}' for v in values))['diagnostics']['reason_text']==REASONS[reason];count+=1
    bad=['@CAM6,'+','.join(['00000000']*33),'@CAM7,'+','.join(['00000000']*32),'@CAM7,'+','.join(['-0000001']*33),'@CAM7,'+','.join(['ZZZZZZZZ']*33)]
    for mode in [11<<21,5<<25,3<<11,10<<2,10<<6,10<<17]:
        values=[0]*33;values[32]=mode;bad.append('@CAM7,'+','.join(f'{v:08X}' for v in values))
    for text in bad:
        try:decode(text)
        except ValueError:count+=1
        else:raise AssertionError('Malformed/reserved CAM7 accepted')
    return dict(result='PASS',synthetic_cases=count,source_ids=SOURCE_IDS,labels=labels(),hardware_accessed=False)
def main():
    parser=argparse.ArgumentParser(description=__doc__);group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--port');group.add_argument('--list',action='store_true');group.add_argument('--self-test',action='store_true');group.add_argument('--line',help='离线解析一条完整CAM7，不打开串口');args=parser.parse_args()
    if args.self_test:print(json.dumps(self_test(),ensure_ascii=False));return
    names=labels()
    if args.line:
        result=decode(args.line);print(describe(result,names));print(json.dumps(result,ensure_ascii=False,indent=2));return
    import serial,serial.tools.list_ports
    if args.list:
        for port in serial.tools.list_ports.comports():print(port.device,port.description)
        return
    link=serial.Serial(port=None,baudrate=115200,timeout=2);link.dtr=False;link.rts=False;link.port=args.port
    try:
        link.open()
        while True:
            line=link.readline()
            if not line:continue
            try:print(describe(decode(line),names),flush=True)
            except (ValueError,UnicodeError):continue
    finally:link.close()
if __name__=='__main__':main()
