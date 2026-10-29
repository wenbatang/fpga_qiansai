"""Rotation-invariant landmark rules and a strict four-second fresh-frame gate."""
from dataclasses import dataclass
import math
import numpy as np


def angle(a,b,c):
    u=a-b;v=c-b;n=np.linalg.norm(u)*np.linalg.norm(v)
    return math.degrees(math.acos(float(np.clip(np.dot(u,v)/n,-1,1)))) if n>1e-10 else 0.


def classify(points,details=None):
    """Return1..4 or None. Thumb+index+middle is also accepted as Chinese3."""
    p=np.asarray(points,dtype=np.float64)
    if p.shape!=(21,3) or not np.isfinite(p).all():return None
    width=np.linalg.norm(p[5]-p[17])
    if width<1e-5:return None
    bits=[];info=details if details is not None else {};info['fingers']=[]
    for mcp in [5,9,13,17]:
        a=angle(p[mcp],p[mcp+1],p[mcp+2]);b=angle(p[mcp+1],p[mcp+2],p[mcp+3])
        tip=np.linalg.norm(p[mcp+3]-p[0]);pip=np.linalg.norm(p[mcp+1]-p[0])
        info['fingers'].append(dict(pip_angle=round(a,1),dip_angle=round(b,1),tip_ratio=round(tip/max(pip,1e-9),3)))
        if a>145 and b>140 and tip>pip*1.02:bits.append(1)
        elif a<145 or tip<pip:bits.append(0)
        else:bits.append(None)
    near_index=np.linalg.norm(p[4]-p[5])/width
    thumb_angle=angle(p[2],p[3],p[4])
    spread=np.linalg.norm(p[4]-p[17])/max(np.linalg.norm(p[3]-p[17]),1e-9)
    # An extended thumb can bend at its IP joint in a natural Chinese "3".
    # Its separation from the index MCP and palm edge is more useful than
    # requiring an almost straight thumb. Keep a rejection band for a relaxed
    # thumb beside a "2", rather than guessing between two and three.
    if near_index<.55 or spread<=1.04:thumb=0
    elif near_index>.72 and spread>1.08 and thumb_angle>115:thumb=1
    elif thumb_angle>150 and near_index>.60 and spread>1.06:thumb=1
    elif thumb_angle<115:thumb=0
    else:thumb=None
    info.update(pattern=[thumb,*bits],thumb_angle=round(thumb_angle,1),thumb_near_index=round(near_index,3),thumb_spread=round(spread,3))
    result={(0,1,0,0,0):1,(0,1,1,0,0):2,(0,1,1,1,0):3,(1,1,1,0,0):3,(0,1,1,1,1):4}.get((thumb,*bits))
    info['reason']=('中国式三：拇指＋食指＋中指' if result==3 and thumb==1 else '手势明确') if result else '手指尚未形成1–4标准姿势'
    return result


@dataclass
class GateState:
    gesture:int|None=None
    seconds:float=0.
    windows:int=0
    blocked:bool=False
    triggered:int|None=None
    reason:str='等待手势'


class HoldGate:
    def __init__(self,hold=4.,sample_period=1.,max_gap=.4,release=.5):
        self.hold=hold;self.period=sample_period;self.max_gap=max_gap;self.release=release
        self.last_seq=-1;self.last_time=None;self.candidate=None;self.since=None;self.next_sample=None;self.windows=0;self.blocked=False;self.absent_since=None
    def clear(self):self.candidate=None;self.since=None;self.next_sample=None;self.windows=0
    def update(self,seq,timestamp,gesture,hand_present,enabled=True):
        state=GateState(blocked=self.blocked)
        if seq<=self.last_seq or self.last_time is not None and timestamp<=self.last_time:
            state.reason='忽略重复或过期帧';return state
        gap=self.last_time is not None and timestamp-self.last_time>self.max_gap
        self.last_seq=seq;self.last_time=timestamp
        if not enabled:
            self.clear();self.absent_since=None;state.reason='风格界面：手势暂停';return state
        if not hand_present:
            self.clear()
            if self.absent_since is None or gap:self.absent_since=timestamp
            if timestamp-self.absent_since>=self.release:self.blocked=False
            return GateState(blocked=self.blocked,reason='请伸出1–4；触发后先移开手')
        self.absent_since=None
        if self.blocked:return GateState(blocked=True,reason='已确认，请移开手后再选择')
        if gap or gesture not in [1,2,3,4]:
            self.clear();return GateState(reason='帧间隔过大或手势不明确，重新计时')
        if gesture!=self.candidate:
            self.candidate=gesture;self.since=timestamp;self.next_sample=timestamp+self.period;self.windows=0
        elif timestamp>=self.next_sample:
            # Never fill missing one-second windows from one late frame.
            if timestamp-self.next_sample>self.max_gap:self.clear();return GateState(reason='采样逾时，重新计时')
            self.windows+=1;self.next_sample+=self.period
        elapsed=timestamp-self.since
        if elapsed>=self.hold and self.windows>=math.ceil(self.hold/self.period):
            self.blocked=True;self.clear();return GateState(gesture=gesture,seconds=self.hold,windows=4,blocked=True,triggered=gesture,reason='风格已确认')
        return GateState(gesture=gesture,seconds=elapsed,windows=self.windows,reason='保持同一手势满4秒')
