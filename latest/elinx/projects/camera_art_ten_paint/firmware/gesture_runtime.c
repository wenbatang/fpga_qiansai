/* Optional on-board 0..9 enrollment. No PC inference and no Flash writes.
 * Normal: one NEW snapshot/second, >=5 reports and >=4 complete seconds.
 */
#include "gesture_calibrated.c"
static uint32_t gs_candidate,gs_since,gs_last,gs_seq,gs_windows,gs_next_poll,gs_absent,gs_epoch;
static uint32_t gs_blocked,gs_confirmed_code,gs_have_absent,gs_have_report,gs_active;
static uint32_t gs_pending,gs_requested_at,gs_reports,gs_last_reason,gs_qualified_samples;
static uint32_t gs_learning,gs_capturing,gs_capture_kind,gs_capture_label;
static uint32_t gs_seen_seq,gs_have_seen_seq;
static uint32_t gs_vote0,gs_vote1,gs_vote_count;
static void gesture_clear(void){gs_candidate=0;gs_windows=0;gs_qualified_samples=0;gs_have_report=0;gs_have_absent=0;gs_vote_count=0;}
static void gesture_publish(uint32_t enabled){
 uint32_t code=gs_candidate,progress=gs_windows;
 if(gs_learning){
  uint32_t label=REG(0x28)&15u;
  code=cal_background_count()<3?0u:label<10?label+1u:0u;
  progress=cal_background_count()<3?cal_background_count():cal_class_count(label);
 }
 REG(0x90)=(code&15u)|((progress&7u)<<4)|(gs_blocked<<7)|(enabled?256u:0u)|((gs_active&1u)<<9)|(gs_learning<<10);
}
static void gesture_reject(uint32_t reason,uint32_t enabled){
 gesture_clear();gs_last_reason=reason;gs_next_poll=REG(0x48);REG(0xa4)=reason|(254u<<8);gesture_publish(enabled);
}
/* id0..9=valid, -1=empty background, -2=ambiguous; digit0 is not no-hand. */
static void gesture_accept_report(uint32_t now,uint32_t seq,int id){
 int gap=gs_have_report && now-gs_last>160000000u;
 gs_last=now;gs_seq=seq;gs_have_report=1;
 if(id==-1){
  gs_candidate=0;gs_windows=0;gs_qualified_samples=0;
  if(!gs_have_absent || gap){gs_absent=now;gs_have_absent=1;}
  if(now-gs_absent>=50000000u)gs_blocked=0;
 }else{
  gs_have_absent=0;
  /* A different valid digit starts a completely new four-second window.
   * Holding the confirmed digit still cannot repeatedly trigger it. */
  if(gs_blocked && id>=0 && id<=9 && (uint32_t)id+1u!=gs_confirmed_code){
   gs_blocked=0;gs_candidate=0;gs_windows=0;gs_qualified_samples=0;
  }
  if(id<0 || id>9 || gap){gs_candidate=0;gs_windows=0;gs_qualified_samples=0;}
  else if(!gs_blocked){
   uint32_t code=(uint32_t)id+1u;
   if(gs_candidate!=code){gs_candidate=code;gs_since=now;gs_windows=0;gs_qualified_samples=1;}
   else {if(gs_qualified_samples<5)gs_qualified_samples++;gs_windows=(now-gs_since)/100000000u;if(gs_windows>4)gs_windows=4;}
   if(gs_windows==4 && gs_qualified_samples>=5 && now-gs_since>=400000000u){
    /* Hardware consumes slot+epoch in the same APB acceptance edge.
     * A mode/key event between software checks cannot override that event. */
    REG(0xbc)=gs_epoch;REG(0xb8)=(uint32_t)id;
    if(REG(0xb8)==1u){gs_blocked=1;gs_confirmed_code=code;gs_active++;}
    else {gs_candidate=0;gs_windows=0;gs_qualified_samples=0;gs_last_reason=0x86u;REG(0xa4)=0x86u|(254u<<8);}
   }
  }
 }
 gesture_publish(1);
}
/* Three independent fresh captures per decision. Two matching candidates
 * suppress one-frame jumps; uncertain frames never directly qualify time. */
static void gesture_vote_report(uint32_t now,uint32_t seq,int id){
 uint32_t code=id>=0?(uint32_t)id+1u:id==-1?0u:11u;
 if(gs_vote_count==0){gs_vote0=code;gs_vote_count=1;gesture_publish(1);return;}
 if(gs_vote_count==1){gs_vote1=code;gs_vote_count=2;gesture_publish(1);return;}
 gs_vote_count=0;uint32_t voted=gs_vote0==gs_vote1?gs_vote0:code==gs_vote0 || code==gs_vote1?code:11u;
 gesture_accept_report(now,seq,voted==0?-1:voted<=10?(int)voted-1:-2);
}
static void gesture_cancel_capture(void){
 REG(0x8c)=2;gs_pending=0;
 if(gs_capturing && gs_capture_kind==2)cal_restart_class(gs_capture_label);
 gs_capturing=0;
}
static void gesture_poll(void){
 uint32_t now=REG(0x48),status=REG(0x80),epoch=REG(0x88),command=REG(0xb4)&3u;
 if(command)REG(0xb4)=command; /* Event wins same-edge W1C in hardware. */
 if(command&1u){
  gesture_cancel_capture();gesture_clear();gs_learning^=1u;gs_next_poll=now;
  if(gs_learning){cal_reset();REG(0x28)=0;}
  gesture_reject(gs_learning?0x91u:cal_valid_mask()==1023?0u:0x90u,status&8);
 }
 if((command&2u) && gs_learning && !gs_capturing){
  gs_capture_label=REG(0x28)&15u;if(gs_capture_label>=10)gs_capture_label=0;
  gs_capture_kind=cal_background_count()<3?1u:2u;
  if(gs_capture_kind==2)cal_restart_class(gs_capture_label);
  gs_capturing=1;gs_next_poll=now;gesture_clear();
 }
 if(epoch!=gs_epoch){
  gs_epoch=epoch;gs_pending=0;gesture_clear();gs_blocked=0;gs_confirmed_code=0;gs_next_poll=now;
  if(gs_capturing && gs_capture_kind==2 && (REG(0x28)&15u)!=gs_capture_label)gesture_cancel_capture();
 }
 if(!(status&8)){
  gs_pending=0;gs_blocked=0;gs_confirmed_code=0;gesture_reject(0x80u,0);return;
 }
 if(gs_learning){
  if(gs_capturing && gs_capture_kind==2 && (REG(0x28)&15u)!=gs_capture_label)gesture_cancel_capture();
  if(!gs_capturing){gesture_reject(cal_background_count()<3?0x91u:0x92u,1);return;}
 }else if(cal_valid_mask()!=1023){gesture_reject(0x90u,1);return;}
 if(!(status&1)){
  if(gs_pending && now-gs_requested_at>60000000u){
   REG(0x8c)=2;gs_pending=0;gesture_reject(0x82u,1);return;
  }
  if((int32_t)(now-gs_next_poll)>=0 && !(status&6)){
   REG(0x8c)=1;gs_pending=1;gs_requested_at=now;
   gs_next_poll=now+(gs_learning?25000000u:33300000u);
  }
  if(gs_have_report && now-gs_last>160000000u)gesture_reject(0x83u,1);
  return;
 }
 if(!gs_pending || now-gs_requested_at>60000000u){
  REG(0x8c)=2;gs_pending=0;gesture_reject(0x82u,1);return;
 }
 uint32_t seq=REG(0x84),before=REG(0x48);struct cal_metrics metrics;
 if(gs_have_seen_seq && seq==gs_seen_seq){REG(0x8c)=2;gs_pending=0;gesture_reject(0x85u,1);return;}
 metrics.foreground_count=metrics.mean_rgb=metrics.threshold=metrics.margin=metrics.reason=0;metrics.best_distance=65535;
 int id=-2;
 if(gs_learning && gs_capture_kind==1)id=cal_capture_background(cal_background_count());
 else if(gs_learning)id=cal_capture_template(gs_capture_label,cal_class_count(gs_capture_label),&metrics);
 else id=cal_predict(&metrics);
 now=REG(0x48);
 /* Calibration mutates RAM. Discard that class/BG if the source changed. */
 if(REG(0x88)!=epoch || REG(0x84)!=seq || (REG(0x80)&9)!=9 || now-gs_requested_at>60000000u){
  if(gs_learning){if(gs_capture_kind==1)cal_reset();else cal_restart_class(gs_capture_label);gs_capturing=0;}
  REG(0x8c)=2;gs_pending=0;gesture_reject(0x84u,REG(0x80)&8);return;
 }
 REG(0x8c)=2;gs_pending=0;
 gs_seen_seq=seq;gs_have_seen_seq=1;
 REG(0x94)=now-before;++gs_reports;REG(0xa0)=gs_reports;
 uint32_t reason;
 if(gs_learning)reason=id==0?0x92u:0x93u;
 else reason=id>=0?0u:id==-1?1u:metrics.reason==4?0x90u:7u;
 gs_last_reason=reason;
 REG(0xa4)=reason|(254u<<8)|((!gs_learning && id>=0?(uint32_t)id+1u:0u)<<16);
 REG(0xa8)=(metrics.foreground_count&65535u)|((metrics.threshold&65535u)<<16);
 REG(0xac)=(metrics.best_distance&65535u)|((metrics.margin&65535u)<<16);
 REG(0xb0)=metrics.mean_rgb;
 if(REG(0x88)!=epoch || !(REG(0x80)&8) || REG(0x48)-gs_requested_at>60000000u){
  if(gs_learning){if(gs_capture_kind==1)cal_reset();else cal_restart_class(gs_capture_label);gs_capturing=0;}
  gesture_reject(0x84u,REG(0x80)&8);return;
 }
 if(gs_learning){
  if(id!=0){gs_capturing=0;gesture_clear();}
  else if(gs_capture_kind==1 && cal_background_count()==3){gs_capturing=0;REG(0x28)=0;}
  else if(gs_capture_kind==2 && cal_class_count(gs_capture_label)==CAL_TEMPLATES){
   gs_capturing=0;
   if(cal_valid_mask()==1023){gs_learning=0;gesture_clear();gs_next_poll=now+100000000u;}
   else REG(0x28)=gs_capture_label==9?0:gs_capture_label+1u;
  }
  gesture_publish(1);
 }else gesture_vote_report(now,seq,id);
}
