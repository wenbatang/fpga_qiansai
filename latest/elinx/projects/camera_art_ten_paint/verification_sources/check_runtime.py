from pathlib import Path
import ctypes,hashlib,json,sys,os
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(Path(__file__).parent))
from desktop_process import run
from check_classifier import pose


def packed(array):
    words=np.zeros(128,np.uint32)
    for i,value in enumerate(array.flat):words[i//32]|=int(value)<<(i%32)
    return words


def rgb_packed(array,skin=0xa2c7):
    """64x64 immutable RGB565 ROI; low halfword is the left pixel."""
    pixels=np.where(np.asarray(array,dtype=bool),skin,0).astype(np.uint32).reshape(-1)
    assert pixels.shape==(4096,)
    return pixels[0::2]|(pixels[1::2]<<16)


def main():
    folder=ROOT/'sim/runtime';folder.mkdir(exist_ok=True);os.environ['PATH']='E:/software/mingw/ucrt64/bin;'+os.environ['PATH']
    source=folder/'test.c';source.write_text('''#include <stdint.h>
static uint32_t regs[0x4000/4];
#define REG(o) regs[(o)/4]
#include "'''+(ROOT/'firmware/gesture_runtime.c').as_posix()+'''"
static uint32_t test_age=0;
void set_age(uint32_t age){test_age=age;}
void reset_test(void){gs_candidate=gs_since=gs_last=gs_seq=gs_windows=gs_next_poll=gs_absent=gs_blocked=gs_have_absent=gs_have_report=gs_active=gs_pending=gs_requested_at=gs_reports=gs_last_reason=test_age=0;gs_epoch=1;for(unsigned i=0;i<0x4000/4;i++)regs[i]=0;}
uint32_t poll_state(uint32_t now,uint32_t status,uint32_t epoch){
regs[0x48/4]=now;regs[0x80/4]=status;regs[0x88/4]=epoch;regs[0x8c/4]=0;gesture_poll();return regs[0x8c/4];}
uint32_t display_status(void){return regs[0x90/4];}
uint32_t report(uint32_t now,uint32_t seq,uint32_t epoch,uint32_t enabled,const uint32_t *words){
gs_pending=1;gs_requested_at=now-test_age;
regs[0x48/4]=now;regs[0x80/4]=enabled?9:0;regs[0x84/4]=seq;regs[0x88/4]=epoch;regs[0x28/4]=0xffffffff;
for(unsigned i=0;i<2048;i++)regs[0x2000/4+i]=words[i];gesture_poll();return regs[0x28/4];}
''',encoding='utf-8')
    assert run(['E:/software/mingw/ucrt64/bin/gcc.exe','-shared','-O2',str(source),'-o',str(folder/'test.dll')],folder,folder/'compile.log')==0
    lib=ctypes.CDLL(str(folder/'test.dll'));lib.report.argtypes=[ctypes.c_uint32]*4+[ctypes.POINTER(ctypes.c_uint32)];lib.report.restype=ctypes.c_uint32
    lib.poll_state.argtypes=[ctypes.c_uint32]*3;lib.poll_state.restype=ctypes.c_uint32
    lib.display_status.restype=ctypes.c_uint32
    masks={n:rgb_packed(pose(n)) for n in range(1,5)};masks[0]=np.zeros(2048,np.uint32)
    green_masks={n:rgb_packed(pose(n),0x7cc7) for n in range(1,5)}
    def sample(t,seq,digit,epoch=1,enabled=1,green=False):
        words=(green_masks if green and digit else masks)[digit]
        return lib.report(round(t*100000000)&0xffffffff,seq,epoch,enabled,words.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32)))
    scenarios=0
    for digit in range(1,5):
        lib.reset_test();events=[]
        for i in range(31):
            result=sample(i/5,i+1,digit)
            if result!=0xffffffff:events.append((i/5,result))
        assert events==[(4.,digit-1)],events;scenarios+=1
        for i in range(31,50):assert sample(i/5,i+1,4 if digit!=4 else 1)==0xffffffff
        for i in range(50,54):sample(i/5,i+1,0)
        events=[]
        for i in range(54,76):
            result=sample(i/5,i+1,2)
            if result!=0xffffffff:events.append(result)
        assert events==[1];scenarios+=1
    lib.reset_test()
    for i in range(20):assert sample(i/5,1,1)==0xffffffff
    assert sample(4.1,1,1)==0xffffffff;scenarios+=1
    lib.reset_test()
    for i in range(20):sample(i/5,i+1,1)
    assert sample(4.2,21,1,enabled=0)==0xffffffff
    for i in range(22,41):assert sample(i/5,i+1,1,epoch=2)==0xffffffff
    scenarios+=1
    lib.reset_test();start=0xf0000000/100000000;events=[]
    for i in range(22):
        result=sample(start+i/5,i+1,3)
        if result!=0xffffffff:events.append((i,result))
    assert events==[(20,2)];scenarios+=1
    lib.reset_test();lib.set_age(70000000)
    for i in range(30):assert sample(i/5,i+1,3)==0xffffffff,'An old ready snapshot cannot qualify'
    scenarios+=1
    # Real REQUEST path, not the report() helper's injected pending flag.
    # A signed deadline is valid for <2^31 ticks only. Re-enabling after a
    # long pause must reset that deadline and request immediately.
    for initial,pause in [(0,3000000000),(0xf0000000,3000000000),(0,5000000000)]:
        lib.reset_test()
        assert lib.poll_state(initial,8,2)==1,'Enabled epoch must issue REQUEST'
        assert lib.poll_state((initial+1000000)&0xffffffff,0,3)==0,'Disabled view must not request'
        resumed=(initial+pause)&0xffffffff
        assert lib.poll_state(resumed,8,4)==1,'Long mode pause must not postpone capture until timer wrap'
        assert (lib.display_status()&63)==0,'A mode pause must clear candidate/progress'
        scenarios+=1
    for in_flight in [12,10]:  # enabled+pending / enabled+active, no READY
        lib.reset_test()
        assert lib.poll_state(0,8,2)==1
        assert lib.poll_state(70000000,in_flight,2)==2,'Missing/unfinished frame must be cancelled at source-age limit'
        assert lib.poll_state(71000000,8,2)==1,'Cancelled capture must be requestable again'
        scenarios+=1
    lib.reset_test()
    for i in range(7):sample(i/5,i+1,1)
    assert (lib.display_status()&63)==9,'Candidate one must have one complete progress window'
    lib.poll_state(200000000,8,1)
    assert (lib.display_status()&63)==0,'Expired report must clear visible G/P as well as private state'
    scenarios+=1
    # The camera's documented green tendency used to be discarded by R>G
    # in RTL. A G>R synthetic hand must now survive CPU-side segmentation.
    green_records=[]
    for digit in range(1,5):
        lib.reset_test();events=[]
        for i in range(22):
            result=sample(i/5,i+1,digit,green=True)
            if result!=0xffffffff:events.append((i/5,result))
        assert events==[(4.,digit-1)],(digit,events,hex(lib.display_status()))
        green_records.append(dict(digit=digit,rgb565='7cc7',confirmed_at_seconds=events[0][0]));scenarios+=1
    files=[source,Path(__file__),ROOT/'sim/check_classifier.py',ROOT/'firmware/gesture_runtime.c',ROOT/'firmware/gesture_classify.c',ROOT/'firmware/gesture_color.c']
    (folder/'verification.json').write_text(json.dumps(dict(result='PASS',scenarios=scenarios,green_cases=green_records,scope='Actual C RGB565 segmentation/classifier+four-second runtime on host, including real no-ready REQUEST path after long mode pauses; synthetic colors/silhouettes, not real-user accuracy or RV32 cycle model',sources_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}),indent=2),encoding='utf-8');print('PASS runtime',scenarios,'scenarios')


if __name__=='__main__':main()
