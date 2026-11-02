"""Execute actual RV32M enrollment/guard/weight code, with modeled peripherals.

Ticks increment per instruction while processing. Only idle timer reads jump
to the next request opportunity; these are NOT Sapphire cycle measurements.
"""
from pathlib import Path
import importlib.util,json,sys,time
ROOT=Path(__file__).resolve().parents[1];WS=ROOT.parents[2]
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'sim'))
sys.path.insert(0,str(WS/'pycode/gesture_digits/calibrated_reference'))
from check_calibrated import frame
from simutil import configs,sha
from riscv_m import with_m
ISA=ROOT.parent/'camera_art_styles/sim/check_firmware.py'
spec=importlib.util.spec_from_file_location('calibration_compiled_isa',ISA);base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
base.BUILD=ROOT/'build/720p'

class Bus(base.Bus):
 def __init__(self):
  super().__init__();self.instructions=0;self.enabled=True;self.epoch=1;self.events=0;self.status=0;self.seq=0;self.ready=False
  self.token=0;self.guard_result=0;self.guard_requests=[];self.processing=False;self.wait_target=0;self.req_instructions=0;self.request_tick=0
  self.requests=[];self.reports=[];self.ack_count=0;self.current=None;self.roi_reads=0;self.roi_addresses=set();self.acked=False
  self.capture_actions=set();self.entered=False;self.busy_until=0;self.completed=0;self.completion_during_roi=0;self.start_slots=[]
  self.cfg_log=[];self.command_sets=[configs(i) for i in range(10)];self.rom=[int(v,16) for v in (ROOT/'build/720p/weights.mem').read_text().split()]
  self.images={k:list(map(int,frame(k))) for k in [None,*range(10)]}
 def read(self,address):
  if 0xf8100000<=address<0xf8110000:
   o=address-0xf8100000
   if o==0x48:
    if self.reg[0x60]==3 and not self.processing and not self.ready and self.now<self.wait_target:self.now=self.wait_target
    return self.now&0xffffffff
   if o==0x80:return 8|int(self.ready)
   if o==0x84:return self.seq
   if o==0x88:return self.epoch
   if o==0xb4:return self.events
   if o==0xb8:return self.guard_result
   if o==0xbc:return self.token
   if 0x2000<=o<0x4000:
    assert self.ready and self.processing and not self.acked,'ROI read after ACK or without ownership'
    i=(o-0x2000)//4;self.roi_reads+=1;self.roi_addresses.add(i);return self.current[i]
   if 0x4000<=o<0x5cc0:return self.rom[(o-0x4000)//4]
  return super().read(address)
 def write(self,address,value):
  if 0xf8100000<=address<0xf8110000:
   o=address-0xf8100000
   if o==0x28:self.reg[o]=value if value<10 else 0;return
   if o==0x2c:assert not self.reg[8]&1;self.slot=value if value<10 else 0;return
   if o==0x54:
    assert not self.reg[8]&9
    n=self.reg[0x58];assert n<216 and (self.reg[0x50],value)==self.command_sets[self.slot][n],(self.slot,n)
    self.config[self.reg[0x50]]=value;self.reg[0x58]+=1;self.cfg_log.append([self.slot,self.reg[0x50],value]);return
   if o==0x30:
    if value&2:self.config={};self.reg[0x58]=0;self.reg[8]&=~8
    if value&4:
     assert self.reg[0x58]==216 and self.config==dict(self.command_sets[self.slot]);self.reg[0x2c]=64|self.slot;self.reg[8]|=8;self.loaded.append(self.slot)
    if value&1:
     assert self.reg[8]&8 and not self.reg[8]&1
     self.reg[8]=(self.reg[8]|1)&~4;self.starts+=1;self.start_slots.append(self.slot);self.busy_until=self.instructions+10000
    return
   if o==0xb4:self.events&=~value;return
   if o==0xbc:self.token=value;return
   if o==0xb8:
    self.guard_result=4 if value>=10 else 2 if self.token!=self.epoch else 3 if not self.enabled or self.status&1024 or self.events&1 else 1
    self.guard_requests.append(dict(slot=value,result=self.guard_result,tick=self.now,instruction=self.instructions,normal_reports=sum(not(v['status']&1024) for v in self.reports)))
    if self.guard_result==1:self.reg[0x28]=value;self.reg[8]|=4
    return
   if o==0x8c:
    if value==1:
     assert not self.ready and not self.processing,'Multiple ROI in flight'
     n=len(self.requests);label=None if n<3 else (n-3)//4 if n<43 else 0
     self.seq+=1;self.current=self.images[label];self.ready=True;self.processing=True;self.acked=False;self.roi_reads=0;self.roi_addresses=set()
     self.req_instructions=self.instructions;self.request_tick=self.now
     self.wait_target=self.now+(26000000 if self.status&1024 else 34000000)
     self.requests.append(dict(seq=self.seq,label=label,request_tick=self.now,request_instruction=self.instructions))
    elif value==2:
     if self.ready:
      assert len(self.roi_addresses)==2048,'Partial ROI was ACKed as complete'
      self.ready=False;self.acked=True;self.ack_count+=1
    else:raise AssertionError('Bad capture command')
    return
   if o==0x90:
    self.status=value
    if self.processing:
     assert self.acked,'Published progress before ROI ACK'
     self.reports.append(dict(seq=self.seq,label=self.requests[-1]['label'],status=value,roi_reads=self.roi_reads,roi_words=len(self.roi_addresses),instructions=self.instructions-self.req_instructions,request_tick=self.request_tick,report_tick=self.now))
     self.processing=False
     if self.ack_count==43 and not value&1024:self.wait_target=self.now+34000000
     if self.ack_count%4==3:self.reg[8]|=4
     print('MCU ROI',self.ack_count,'label',self.requests[-1]['label'],'status',hex(value),'instructions',self.reports[-1]['instructions'],flush=True)
    # Explicit user actions, never cal_counts/prototypes or CPU RAM writes.
    if value&1024 and self.ack_count<43 and (self.ack_count==0 or self.ack_count%4==3) and self.ack_count not in self.capture_actions:
     self.events|=2;self.capture_actions.add(self.ack_count)
    self.reg[o]=value;return
   if o in (0x94,0xa0,0xa4,0xa8,0xac,0xb0):self.reg[o]=value;return
  super().write(address,value)
  if address==0xf8100060 and value==3 and not self.entered:self.events|=1;self.entered=True
 def advance(self):
  self.instructions+=1;self.now+=1000 if self.reg[0x60]!=3 else 1
  if self.busy_until and self.instructions>=self.busy_until:
   self.busy_until=0;self.reg[8]&=~1;self.reg[0xc]|=1;self.completed+=1
   if self.processing and self.roi_reads:self.completion_during_roi+=1

class CPU(with_m(base.CPU)):
 def read(self,address,size):
  if 0xf8100000<=address<0xf8110000:return (self.bus.read(address&~3)>>(8*(address&3)))&((1<<(size*8))-1)
  return super().read(address,size)

def main():
 out=ROOT/'sim/calibration_firmware';out.mkdir(exist_ok=True);started=time.monotonic();firmware_sha=sha(ROOT/'build/720p/firmware.bin');bus=Bus();cpu=CPU(bus)
 for n in range(200000000):
  cpu.step()
  if bus.guard_requests and bus.guard_requests[-1]['result']==1 and bus.reg[0x28]==0 and bus.loaded[-1]==0 and bus.completed==bus.starts and bus.reg[0xc]==0 and not bus.processing:break
  if n and n%10000000==0:print('MCU progress',n,'ROI',bus.ack_count,'elapsed',time.monotonic()-started,flush=True)
 else:raise AssertionError(('Machine-code deadline',bus.ack_count,bus.reg,hex(cpu.pc)))
 assert (ROOT/'build/720p/firmware.bin').stat().st_size<14000,'Expected compiled9004B firmware changed; inspect before rerunning'
 assert sha(ROOT/'build/720p/firmware.bin')==firmware_sha,'Firmware changed during the actual machine-code run'
 assert bus.loaded==[*range(10),0] and len(bus.cfg_log)==2376
 assert bus.ack_count>=58 and len(bus.reports)>=58 and len(bus.requests)>=58
 assert [r['label'] for r in bus.reports[:43]]==[None]*3+[i for i in range(10) for _ in range(4)]
 assert all(r['roi_words']==2048 and r['report_tick']-r['request_tick']<=60000000 for r in bus.reports)
 assert all(r['status']&1024 for r in bus.reports[:42]) and not bus.reports[42]['status']&1024,'Learning did not end after class9'
 normal=bus.reports[43:];assert len(normal)>=15 and all((r['status']&15)==1 for r in normal[2:]),'Digit0 confused with nohand code0'
 accepted=bus.guard_requests[-1];assert accepted['slot']==0 and accepted['result']==1 and accepted['normal_reports']>=4
 assert normal[14]['report_tick']-normal[2]['report_tick']>=400000000
 assert any((r['status']>>4)&7==4 and r['status']&128 for r in normal)
 assert bus.completion_during_roi>=1 and bus.traps>=1 and cpu.m_instructions>2
 assert len(bus.sensor.writes)==167 and bus.sensor.writes[-1]==(0x0100,1)
 files=[Path(__file__),ISA,ROOT/'sim/riscv_m.py',ROOT/'scripts/simutil.py',ROOT/'build/720p/firmware.bin',ROOT/'build/720p/weights.mem',*list((ROOT/'firmware').glob('*'))]
 for i in range(10):files.extend(next((ROOT/'parameters/c6').glob(f'{i:02d}_*')).glob('*'))
 files.extend([WS/'pycode/gesture_digits/calibrated_reference/check_calibrated.py',WS/'pycode/gesture_digits/calibrated_reference/reference.py'])
 result=dict(result='PASS',firmware_bytes=(ROOT/'build/720p/firmware.bin').stat().st_size,instructions=n+1,m_instructions=cpu.m_instructions,elapsed_host_seconds=time.monotonic()-started,loaded=bus.loaded,parameter_writes=len(bus.cfg_log),starts=bus.start_slots,completed=bus.completed,interrupts=bus.traps,completion_during_roi=bus.completion_during_roi,roi_complete=bus.ack_count,requests=bus.requests,reports=bus.reports,guard_requests=bus.guard_requests,sources_sha256={str(p):sha(p) for p in files if p.is_file()},scope='Actual RV32IM current byte image/SC431HAI I2C model/43 complete ROI enrollment plus15 three-vote frames/fresh digit0 qualification/atomic guard and real216-write learned weights per target/IRQ. No cal state backdoor. CPU ticks are instruction-based with idle-only time jumps, not Sapphire cycles. Camera, ready publication, video job and IRQ are explicit models; no real hand or board acceptance.')
 (out/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in result.items() if k not in ['sources_sha256','requests','reports']},indent=2),flush=True)
if __name__=='__main__':main()
