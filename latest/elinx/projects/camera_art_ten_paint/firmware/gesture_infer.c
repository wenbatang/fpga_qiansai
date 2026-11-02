/* RV32I integer MLP, no hardware multiply required. Input is 256 uint8 features.
 * Hidden scale6/255, output logits1/64. Class10=background, digit0 is valid.
 */
#include <stdint.h>
#ifndef GD_MODEL_HEADER
#define GD_MODEL_HEADER "gesture_model.h"
#endif
#include GD_MODEL_HEADER
struct gesture_neural_metrics {int32_t best_logit,margin;uint32_t best_class,reason;};
static int32_t gd_product(uint8_t feature,int8_t weight){
 unsigned magnitude=weight<0?(unsigned)-(int)weight:(unsigned)weight;
 unsigned value=feature,product=0;
 while(magnitude){if(magnitude&1u)product+=value;value<<=1;magnitude>>=1;}
 return weight<0?-(int32_t)product:(int32_t)product;
}
static int32_t gd_round(int32_t value,unsigned shift){
 if(!shift)return value;
 int32_t biased=value+(int32_t)(1u<<(shift-1));
 if(biased>=0)return (int32_t)((uint32_t)biased>>shift);
 return -(int32_t)(((uint32_t)(-biased)+((1u<<shift)-1u))>>shift);
}
int gesture_predict(const uint8_t f[GD_FEATURES],struct gesture_neural_metrics *metrics){
 uint8_t hidden[GD_HIDDEN];int32_t logits[GD_CLASSES];
 for(unsigned o=0;o<GD_HIDDEN;o++){
  int32_t sum=gd_b0[o];
  for(unsigned i=0;i<GD_FEATURES;i++)sum+=gd_product(f[i],gd_w0[o][i]);
  int32_t v=gd_round(sum,gd_s0[o]);hidden[o]=(uint8_t)(v<0?0:v>255?255:v);
 }
 for(unsigned o=0;o<GD_CLASSES;o++){
  int32_t sum=gd_b1[o];for(unsigned i=0;i<GD_HIDDEN;i++)sum+=gd_product(hidden[i],gd_w1[o][i]);
  int32_t v=gd_round(sum,gd_s1[o]);logits[o]=v<-32768?-32768:v>32767?32767:v;
 }
 unsigned best=0;for(unsigned o=1;o<GD_CLASSES;o++)if(logits[o]>logits[best])best=o;
 int32_t second=-32768;for(unsigned o=0;o<GD_CLASSES;o++)if(o!=best && logits[o]>second)second=logits[o];
 metrics->best_logit=logits[best];metrics->margin=logits[best]-second;metrics->best_class=best;
 if(logits[best]<gd_logit_min[best] || metrics->margin<gd_margin_min[best]){metrics->reason=7;return -2;}
 metrics->reason=best==10?1:0;return best==10?-1:(int)best;
}
