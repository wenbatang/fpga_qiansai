"""Actual C enrollment/runtime plus classifier; host MMIO/camera are models."""
from pathlib import Path
import ctypes,hashlib,json,os,re,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];WS=ROOT.parents[2]
FIXTURES=WS/'pycode/gesture_digits/calibrated_reference'
sys.path.insert(0,str(FIXTURES));sys.path.insert(0,str(ROOT/'scripts'))
from check_calibrated import frame
from desktop_process import run

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 out=ROOT/'sim/calibration_runtime';out.mkdir(exist_ok=True)
 source=ROOT/'firmware/gesture_runtime.c';text=source.read_text(encoding='utf8')
 # Exact source inclusion; MMIO pointer instrumentation is bounded by these
 # access contracts, without rewriting assignments or stubbing classification.
 assert len(re.findall(r'REG\(0xb4\)',text))==2,'Model assumes one command read and one W1C write per poll'
 assert len(re.findall(r'REG\(0xb8\)',text))==2,'Model assumes guarded slot write then result read'
 globals=[]
 for declaration in re.findall(r'^static uint32_t ([^;]+);',text,re.M):
  globals.extend(name.strip() for name in declaration.split(',') if name.strip().startswith('gs_'))
 assert 'gs_seen_seq' in globals and 'gs_have_seen_seq' in globals
 code=r'''#include <stdint.h>
#include <stdlib.h>
static uint32_t regs[64],words[2048],buttons,late_buttons,enabled,ready,active,pending,epoch,seq,now;
static uint32_t write_offset,b4_access,b8_access,roi_reads,ack_after_reads,request_count,ack_count,style_changes,current_style;
static uint32_t after_c_hook,late_hook,late_write_hook,violation;
static uint32_t guard_phase,guard_kind,guard_requests,guard_accepts;
static void guard_interrupt(void){
 epoch++;ready=active=pending=0;
 if(guard_kind==1){regs[0x28/4]=current_style=7;style_changes++;}
 else if(guard_kind==2)enabled=0;
 else if(guard_kind==3)buttons|=1;
}
static void flush(void){
 if(regs[0x28/4]!=current_style){current_style=regs[0x28/4];style_changes++;}
 if(write_offset==0x8c){
  uint32_t v=regs[0x8c/4];
  if(v==1){if(enabled && !ready && !active){pending=1;request_count++;}}
  else if(v==2){ready=active=pending=0;ack_count++;ack_after_reads=roi_reads;}
  else violation=1;
  regs[0x8c/4]=0;
 }else if(write_offset==0xb4){buttons=(buttons&~regs[0xb4/4])|late_buttons;late_buttons=0;regs[0xb4/4]=buttons;}
 else if(write_offset==0xbc && guard_phase==2){guard_interrupt();guard_phase=0;}
 else if(write_offset==0xb8){
  /* Write acceptance happens before the next B8 read. Same-edge cancel
   * defeats guard_enabled with the PRE-edge epoch, as in the RTL. */
  uint32_t slot=regs[0xb8/4],cancel=guard_phase==3;
  uint32_t allowed=enabled && !cancel && !(regs[0x90/4]&1024u) && !(buttons&1u);
  regs[0xb8/4]=slot>=10?4:regs[0xbc/4]!=epoch?2:!allowed?3:1;
  guard_requests++;
  if(regs[0xb8/4]==1){guard_accepts++;regs[0x28/4]=current_style=slot;style_changes++;}
  if(cancel){guard_interrupt();guard_phase=0;}
 }
 if(write_offset==0xb0 && late_write_hook){epoch++;ready=active=pending=0;late_write_hook=0;}
 write_offset=0;
}
static uint32_t *address(uint32_t o){
 flush();
 if(o==0xbc && guard_phase==1){guard_interrupt();guard_phase=0;}
 if(o==0x48){
  if(roi_reads && after_c_hook){epoch++;ready=active=pending=0;after_c_hook=0;}
  if(roi_reads && late_hook){now+=70000000u;late_hook=0;}
  regs[o/4]=now;
 }else if(o==0x80)regs[o/4]=(enabled?8u:0u)|(pending?4u:0u)|(active?2u:0u)|(ready?1u:0u);
 else if(o==0x84)regs[o/4]=seq;
 else if(o==0x88)regs[o/4]=epoch;
 else if(o==0xb4){regs[o/4]=buttons;if(b4_access++)write_offset=o;}
 else if(o==0xb8){if(!b8_access++)write_offset=o;}
 if(o==0x8c || o==0x90 || o==0x94 || o==0xa0 || o==0xa4 || o==0xa8 || o==0xac || o==0xb0 || o==0xbc)write_offset=o;
 if(o>=sizeof(regs))violation=2;
 return &regs[o/4];
}
static uint32_t roi(unsigned index){
 if(index>=2048)violation=3;
 /* ACK may clear ready only after the classifier's final immutable read. */
 if(ack_after_reads!=0xffffffffu)violation=4;
 roi_reads++;return words[index];
}
#define REG(o) (*address(o))
#define GESTURE_ROI_WORD(i) roi(i)
'''
 code+='#include "'+source.as_posix()+'"\n'
 code+='''void host_reset(void){
 for(unsigned i=0;i<64;i++)regs[i]=0;
 buttons=late_buttons=ready=active=pending=seq=now=write_offset=b4_access=b8_access=roi_reads=request_count=ack_count=style_changes=current_style=0;
 guard_phase=guard_kind=guard_requests=guard_accepts=0;
 enabled=epoch=1;after_c_hook=late_hook=late_write_hook=violation=0;ack_after_reads=0xffffffffu;cal_reset();
'''+''.join(n+'=0;' for n in globals)+'''
}
void host_poll(uint32_t t){now=t;b4_access=b8_access=0;roi_reads=0;ack_after_reads=0xffffffffu;gesture_poll();flush();}
void host_buttons(uint32_t bits,uint32_t simultaneous){buttons|=bits;late_buttons=simultaneous;}
void host_mode(uint32_t en,uint32_t change){enabled=en;if(change){epoch++;ready=active=pending=0;}if(!en)ready=active=pending=0;}
void host_label(uint32_t value){regs[0x28/4]=current_style=value;epoch++;ready=active=pending=0;}
int host_begin_frame(void){if(!enabled || !pending || ready)return 0;pending=0;active=1;return 1;}
int host_deliver(const uint32_t *p,uint32_t sequence){
 if(!enabled || !(active || pending) || ready)return 0;
 for(unsigned i=0;i<2048;i++)words[i]=p[i];seq=sequence;ready=1;active=pending=0;return 1;
}
void host_unrequested(const uint32_t *p,uint32_t sequence){for(unsigned i=0;i<2048;i++)words[i]=p[i];seq=sequence;ready=1;active=pending=0;}
void host_hook(uint32_t kind){after_c_hook=kind==1;late_hook=kind==2;late_write_hook=kind==3;}
void host_guard_fault(uint32_t phase,uint32_t kind){guard_phase=phase;guard_kind=kind;}
uint32_t host_reg(uint32_t o){flush();return o==0xb4?buttons:regs[o/4];}
uint32_t host_state(uint32_t id){flush();switch(id){
 case 0:return ready;case 1:return pending;case 2:return active;case 3:return request_count;case 4:return ack_count;
 case 5:return roi_reads;case 6:return ack_after_reads;case 7:return violation;case 8:return cal_valid_mask();
 case 9:return cal_background_count();case 10:return style_changes;case 11:return epoch;
 case 12:return guard_requests;case 13:return guard_accepts;
'''
 for i,name in enumerate(globals):code+=f' case {100+i}:return {name};\n'
 code+='''default:return 0;}}
uint32_t host_class_count(uint32_t label){return cal_class_count(label);}
void host_gate_prepare(void){gs_epoch=epoch;regs[0x90/4]=256;}
void host_gate(uint32_t t,uint32_t s,int id){now=t;b4_access=b8_access=0;roi_reads=0;ack_after_reads=0xffffffffu;gesture_accept_report(t,s,id);flush();}
'''
 wrapper=out/'host.c';wrapper.write_text(code,encoding='ascii')
 os.environ['PATH']='E:/software/mingw/ucrt64/bin;'+os.environ['PATH'];temp=out/'tmp';temp.mkdir(exist_ok=True);os.environ['TMP']=os.environ['TEMP']=str(temp)
 assert run(['E:/software/mingw/ucrt64/bin/gcc.exe','-shared','-O2',str(wrapper),'-o',str(out/'runtime.dll')],out,out/'compile.log')==0
 lib=ctypes.CDLL(str(out/'runtime.dll'));ptr=ctypes.POINTER(ctypes.c_uint32)
 lib.host_poll.argtypes=[ctypes.c_uint32];lib.host_buttons.argtypes=[ctypes.c_uint32]*2;lib.host_deliver.argtypes=[ptr,ctypes.c_uint32];lib.host_deliver.restype=ctypes.c_int;lib.host_unrequested.argtypes=[ptr,ctypes.c_uint32]
 lib.host_mode.argtypes=[ctypes.c_uint32]*2;lib.host_state.argtypes=[ctypes.c_uint32];lib.host_state.restype=ctypes.c_uint32;lib.host_reg.argtypes=[ctypes.c_uint32];lib.host_reg.restype=ctypes.c_uint32;lib.host_gate.argtypes=[ctypes.c_uint32,ctypes.c_uint32,ctypes.c_int]
 lib.host_guard_fault.argtypes=[ctypes.c_uint32]*2
 names={name:100+i for i,name in enumerate(globals)};records=[];sequence=0;t=0.
 def state(name):return lib.host_state(names[name])
 def tick(value):
  lib.host_poll(round(value*100000000)&0xffffffff);assert lib.host_state(7)==0,'MMIO/ownership violation'
 def press(bits,value,late=0):lib.host_buttons(bits,late);tick(value)
 def deliver(image,value,seq=None):
  nonlocal sequence
  sequence=sequence+1 if seq is None else seq
  assert lib.host_deliver(image.ctypes.data_as(ptr),sequence)==1,'No real REQUEST/active frame'
  tick(value);assert lib.host_state(6)==lib.host_state(5),'ACK before final ROI read'
 def sample_once(digit,value,seq=None,hook=0):
  tick(value);assert lib.host_state(1)==1,'CPU did not request new snapshot'
  assert lib.host_begin_frame()==1
  if hook:lib.host_hook(hook)
  deliver(frame(digit),value+.02,seq)
 def sample(digit,value,seq=None,hook=0):
  # Actual three-snapshot majority, spaced within one second. Source faults
  # are exercised as one physical frame so retries cannot hide the result.
  if seq is not None or hook:sample_once(digit,value,seq,hook);return
  for offset in [0,.3335,.667]:sample_once(digit,value+offset)
 def enroll(record=True):
  nonlocal t,sequence
  lib.host_reset();sequence=0;t=0
  tick(0);assert lib.host_state(3)==0 and lib.host_reg(0xa4)&255==0x90
  press(1,.01);assert state('gs_learning')==1 and lib.host_reg(0xb4)==0
  assert lib.host_reg(0x90)&1024 and lib.host_reg(0x90)&256 and lib.host_reg(0x90)&15==0
  press(2,.02)
  for n in range(3):
   if n:tick(.02+.25*n)
   deliver(frame(),.04+.25*n);assert lib.host_state(9)==n+1
  assert not state('gs_capturing') and lib.host_reg(0x28)==0
  t=1.
  for digit in range(10):
   assert lib.host_reg(0x28)==digit
   press(2,t)
   for n in range(4):
    if n:tick(t+.25*n)
    deliver(frame(digit),t+.02+.25*n)
    assert lib.host_class_count(digit)==n+1
   assert not state('gs_capturing');t+=1.
  assert lib.host_state(8)==1023 and not state('gs_learning')
  if record:records.append(dict(case='complete_enrollment',frames=43,requests=lib.host_state(3),acks=lib.host_state(4)))
 enroll()
 # Real REQUEST -> SOF/active -> immutable ready -> C extraction -> ACK for
 # all ten digits. Five fresh reports and four full seconds are required.
 t=20.
 for digit in range(10):
  before=state('gs_active')
  for n in range(5):
   sample(digit,t+n)
   assert state('gs_active')==before+(n==4),(digit,n,state('gs_active'))
   published=lib.host_reg(0x90);assert (published&15)==digit+1 and ((published>>4)&7)==n and not (published&1024)
  assert lib.host_reg(0x28)==digit and state('gs_blocked')==1
  # Ambiguous geometric input (thin foreground) is not absence and cannot rearm.
  mask=frame();p=mask.copy();values=np.empty(4096,np.uint32);values[::2]=p&65535;values[1::2]=p>>16;values=values.reshape(64,64);values[20:40,20:24]=0x19c4;p=np.ascontiguousarray(values.ravel()[::2]|(values.ravel()[1::2]<<16),np.uint32)
  
  for offset in [0,.3335,.667]:
   tick(t+5+offset);assert lib.host_begin_frame()==1;deliver(p,t+5.02+offset)
  assert state('gs_blocked')==1
  sample(None,t+6);assert state('gs_blocked')==1
  sample(None,t+7);assert state('gs_blocked')==0
  records.append(dict(case='fresh_four_seconds',digit=digit,trigger_time=t+4.687));t+=10
 assert lib.host_state(12)==10 and lib.host_state(13)==10
 # An epoch cancellation after the classifier mutates scratch on the fifth
 # report must not cause the otherwise-due style switch.
 previous=state('gs_active')
 for n in range(4):sample(1,120+n)
 sample(1,124,hook=1);assert state('gs_active')==previous and state('gs_candidate')==0 and lib.host_reg(0xa4)&255==0x84
 records.append(dict(case='normal_epoch_cancels_fifth_report'))
 # A new request receiving an old seq is rejected even after clear() erased
 # the qualified-report history. gs_seen_seq remains an independent guard.
 sample(1,130);old=sequence;reports=state('gs_reports');sample(1,131,old);assert state('gs_reports')==reports and lib.host_reg(0xa4)&255==0x85
 sample(1,132,old);assert state('gs_reports')==reports and lib.host_reg(0xa4)&255==0x85
 records.append(dict(case='duplicate_after_clear_rejected'))
 # Unrequested ready cannot qualify, and no classifier input may be read.
 lib.host_unrequested(frame(1).ctypes.data_as(ptr),sequence+1);tick(133);assert lib.host_reg(0xa4)&255==0x82 and lib.host_state(5)==0
 # Timeout while pending and active both cancel, and later retries are real.
 tick(134);assert lib.host_state(1);tick(134.7);assert not lib.host_state(1) and lib.host_reg(0xa4)&255==0x82
 tick(134.71);assert lib.host_begin_frame()==1;tick(135.41);assert not lib.host_state(2) and lib.host_reg(0xa4)&255==0x82
 tick(135.42);assert lib.host_begin_frame()==1;deliver(frame(1),136.12);assert lib.host_state(5)==0 and lib.host_reg(0xa4)&255==0x82
 records.append(dict(case='pending_active_ready_timeout'))
 # Disable/reenable and changed epoch clear current gate; long pause must not
 # suffer the former signed-deadline21s delay.
 lib.host_mode(0,1);tick(140);assert state('gs_candidate')==0 and not state('gs_pending')
 lib.host_mode(1,1);tick(170);assert lib.host_state(1)==1
 assert lib.host_begin_frame()==1;lib.host_hook(2);deliver(frame(1),170.02);assert lib.host_reg(0xa4)&255==0x84 and state('gs_candidate')==0
 records.append(dict(case='mode_epoch_long_pause_post_age'))
 # Learning partial class invalidation and post-C mutation rollback.
 press(1,180);press(2,180.01)
 # Background mutates first, then the hook changes epoch before validation.
 assert lib.host_begin_frame()==1;lib.host_hook(1);deliver(frame(),180.03);assert lib.host_state(9)==0 and not state('gs_capturing')
 press(2,180.2);assert lib.host_begin_frame()==1;lib.host_hook(3);deliver(frame(),180.22);assert lib.host_state(9)==0 and not state('gs_capturing')
 press(2,181)
 for n in range(3):
  if n:tick(181+.25*n)
  deliver(frame(),181.02+.25*n)
 press(2,182);deliver(frame(0),182.02);assert lib.host_class_count(0)==1
 lib.host_label(1);tick(182.3);assert lib.host_class_count(0)==0 and not state('gs_capturing')
 press(2,183);assert lib.host_begin_frame()==1;lib.host_hook(1);deliver(frame(1),183.02);assert lib.host_class_count(1)==0 and not state('gs_capturing')
 press(2,184);assert lib.host_begin_frame()==1;lib.host_hook(3);deliver(frame(1),184.02);assert lib.host_class_count(1)==0 and not state('gs_capturing')
 press(2,185);deliver(frame(1),185.02);assert lib.host_class_count(1)==1
 # A new capture action restarts an interrupted class; no stale sample joins.
 press(1,185.1);assert not state('gs_learning');press(1,185.2);assert lib.host_state(9)==0 and lib.host_state(8)==0
 records.append(dict(case='learning_partial_label_epoch_rollback'))
 # W1C model explicitly gives a simultaneous new event priority over clear.
 lib.host_reset();press(1,0,late=2);assert lib.host_reg(0xb4)==2;tick(.01);assert state('gs_capturing') and lib.host_reg(0xb4)==0
 records.append(dict(case='w1c_event_wins'))
 # Atomic style consumption tests include the ACTUAL image classifier and a
 # complete fresh enrollment before each race. No stale frame or soft-check
 # window may overwrite a manual choice or advance blocked/active.
 guard_cases=[]
 for phase,kind in [(p,k) for p in [1,2,3] for k in [0,1]]+[(3,2),(3,3)]:
  enroll(False)
  for n in range(4):sample(2,20+n)
  assert state('gs_active')==0 and lib.host_reg(0x28)==9
  accepts=lib.host_state(13);requests=lib.host_state(12)
  lib.host_guard_fault(phase,kind);sample(2,24)
  result=lib.host_reg(0xb8);expected=2 if phase in [1,2] else 3
  assert result==expected,(phase,kind,result)
  assert lib.host_reg(0x28)==(7 if kind==1 else 9),(phase,kind,lib.host_reg(0x28))
  assert state('gs_active')==0 and state('gs_blocked')==0 and state('gs_candidate')==0 and state('gs_windows')==0
  assert ((lib.host_reg(0x90)>>4)&7)==0 and not (lib.host_reg(0x90)&128),'Rejected commit published P4/blocked'
  assert lib.host_reg(0xa4)&255==0x86 and lib.host_state(13)==accepts and lib.host_state(12)==requests+1
  assert lib.host_state(8)==1023
  guard_cases.append(dict(phase=phase,kind=kind,result=result,requested_style=lib.host_reg(0x28)))
 records.append(dict(case='atomic_epoch_style_guard',races=guard_cases))
 # Reproduce the former one-shot latch using real classified ROI frames.
 # Changing a valid digit requires a new full four seconds, without waiting
 # for the green/noisy background to classify as explicit no-hand.
 enroll(False)
 for digit in range(3):
  before=state('gs_active')
  for n in range(5):
   sample(digit,20+digit*7+n)
   assert state('gs_active')==before+(n==4)
  sample(digit,25+digit*7);sample(digit,26+digit*7)
  assert state('gs_active')==before+1,'Held confirmed digit retriggered'
 assert state('gs_active')==3
 records.append(dict(case='repeat_different_digits_without_absence',digits=[0,1,2],confirmations=3))
 # The STYLE view disables sampling. Returning to RAW/SPLIT must rearm even
 # when the user has not removed the hand, without losing learned templates.
 lib.host_mode(0,1);tick(50);assert not state('gs_blocked') and lib.host_state(8)==1023
 lib.host_mode(1,1)
 for n in range(5):
  sample(2,52+n);assert state('gs_active')==3+(n==4)
 records.append(dict(case='return_view_rearms_same_digit',templates_retained=True,confirmations=4))
 # A one-frame wrong/unknown candidate must not alter a 1Hz decision.
 enroll(False)
 for n in range(5):
  before=state('gs_active')
  for offset,digit in [(0,2),(.3335,7),(.667,2)]:sample_once(digit,20+n+offset)
  assert state('gs_active')==before+(n==4)
 assert lib.host_reg(0x28)==2
 records.append(dict(case='majority_rejects_single_frame_wrong_digit',physical_frames=15,accepted=2))
 enroll(False)
 for n in range(5):
  for offset,digit in [(0,2),(.3335,7),(.667,8)]:sample_once(digit,20+n+offset)
 assert state('gs_active')==0 and state('gs_windows')==0
 records.append(dict(case='no_majority_never_qualifies',physical_frames=15))
 # Isolated gate-only timing checks complement, rather than replace, the full
 # real-frame workflow above. No claim that these use an image classifier.
 gate_cases=0
 def gate_reset():lib.host_reset();lib.host_gate_prepare()
 for digit in range(10):
  gate_reset()
  for n in range(5):lib.host_gate(n*100000000,n+1,digit)
  assert state('gs_active')==1 and state('gs_blocked')==1
  lib.host_gate(450000000,6,-2);assert state('gs_blocked')==1
  lib.host_gate(500000000,7,-1);lib.host_gate(549000000,8,-1);assert state('gs_blocked')==1
  lib.host_gate(550000000,9,-1);assert state('gs_blocked')==0;gate_cases+=1
 gate_reset()
 for n in range(10):lib.host_gate(n*10000000,n+1,3)
 assert state('gs_active')==0;gate_cases+=1
 gate_reset();start=0xf0000000
 for n in range(5):lib.host_gate((start+n*100000000)&0xffffffff,n+1,0)
 assert state('gs_active')==1;gate_cases+=1
 gate_reset();lib.host_gate(0,1,2);lib.host_gate(170000000,2,2);assert state('gs_candidate')==0;gate_cases+=1
 files=[source,ROOT/'firmware/gesture_calibrated.c',Path(__file__),wrapper,FIXTURES/'reference.py',FIXTURES/'check_calibrated.py']
 result=dict(result='PASS',workflows=records,atomic_guard_races=guard_cases,gate_only_cases=gate_cases,globals_reset=globals,sources_sha256={str(p):sha(p) for p in files},logs_sha256={str(p):sha(p) for p in out.glob('*.log')},scope='Actual runtime.c and calibrated.c on host. MMIO/REQ/SOF/ready/ACK/W1C/epoch and B8 atomic acceptance plus camera silhouettes are explicit models, no direct gs_pending injection. B8 write is committed before its next result read, same-edge cancel uses the pre-edge epoch and disables acceptance. Separate gate-only cases prepare matching token epoch and are labeled. Not Sapphire instruction timing, actual hardware hand accuracy or complete camera SoC.')
 (out/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(dict(result='PASS',workflow_cases=len(records),gate_only_cases=gate_cases,reset_globals=len(globals)),indent=2),flush=True)
if __name__=='__main__':main()
