"""Read-only CAM4 viewer for local four-style IDs; no transmitted commands."""
from pathlib import Path
import argparse,json,re
ROOT=Path(__file__).resolve().parents[1]
LABELS={'vangogh':'梵高','papercut':'剪纸','comic':'漫画','inkwash':'水墨'}
def decode(line):
    text=line.decode('ascii') if isinstance(line,bytes) else line
    fields=text.strip().split(',')
    if len(fields)!=34 or fields[0]!='@CAM4' or any(re.fullmatch(r'[0-9A-Fa-f]{8}',x) is None for x in fields[1:]):
        raise ValueError('Expected CAM4 with 33 HEX32 fields')
    data=[int(x,16) for x in fields[1:]];mode=data[32]
    return dict(boot=data[0],capture_frames=data[6],inference_frames=data[7],capture_errors=data[8],engine_cycles=data[11],raw=bool(mode&1),engine_raw=bool(mode&2),loaded_style=(mode>>2)&63,requested_style=(mode>>8)&63,front_raw=bool((mode>>14)&1),all_fields=data)
def labels():
    selected=json.loads((ROOT/'build/model_selection.json').read_text(encoding='utf-8'))['styles']
    assert [(r['slot'],r['name']) for r in selected]==[(0,'vangogh'),(1,'papercut'),(2,'comic'),(3,'inkwash')]
    return {r['slot']:LABELS[r['name']] for r in selected}
def self_test():
    count=0
    for slot in range(4):
        for flags in [0,1,2,3,1<<14]:
            values=[0]*33;values[0]=3;values[6]=100;values[7]=90;values[32]=(slot<<2)|((3-slot)<<8)|flags
            text='@CAM4,'+','.join(f'{v:08X}' for v in values)
            decoded=decode(text.encode('ascii'))
            assert decoded['loaded_style']==slot and decoded['requested_style']==3-slot
            assert decoded['raw']==bool(flags&1) and decoded['engine_raw']==bool(flags&2) and decoded['front_raw']==bool(flags&(1<<14))
            count+=1
    for bad in ['@CAM3,'+','.join(['00000000']*33),'@CAM4,'+','.join(['00000000']*32),'@CAM4,'+','.join(['-0000001']*33),'@CAM4,'+','.join(['ZZZZZZZZ']*33)]:
        try:decode(bad)
        except ValueError:count+=1
        else:raise AssertionError('Malformed CAM4 accepted')
    assert list(labels().values())==['梵高','剪纸','漫画','水墨']
    return dict(result='PASS',synthetic_cases=count,local_style_labels=labels(),hardware_accessed=False)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port');parser.add_argument('--list',action='store_true');parser.add_argument('--self-test',action='store_true');args=parser.parse_args()
    if args.self_test:print(json.dumps(self_test(),ensure_ascii=False));return
    import serial,serial.tools.list_ports
    if args.list:
        for port in serial.tools.list_ports.comports():print(port.device,port.description)
        return
    if not args.port:raise ValueError('Use --port COMxx or --list')
    names=labels();link=serial.Serial(port=None,baudrate=115200,timeout=2);link.dtr=False;link.rts=False;link.port=args.port
    try:
        link.open()
        while True:
            line=link.readline()
            if not line:continue
            try:
                result=decode(line);slot=result['loaded_style'];label=names.get(slot,'invalid')
                print(f"boot={result['boot']:08x} C={result['capture_frames']} I={result['inference_frames']} errors={result['capture_errors']} raw={result['raw']} loaded={slot:02d}/{label} requested={result['requested_style']:02d} cycles={result['engine_cycles']}",flush=True)
            except (ValueError,UnicodeError):continue
    finally:link.close()
if __name__=='__main__':main()
