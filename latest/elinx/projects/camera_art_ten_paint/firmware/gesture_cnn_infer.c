/* Small spatial CNN on the existing Sapphire RV32M, integer-only inference.
 * Conv0 k5/s4/p2; Conv1,2 k3/s2/p1; NCHW flatten then 11-class FC.
 */
#include <stdint.h>
#ifndef GC_MODEL_HEADER
#define GC_MODEL_HEADER "gesture_cnn_model.h"
#endif
#include GC_MODEL_HEADER
struct gesture_neural_metrics {int32_t best_logit,margin;uint32_t best_class,reason;};
static uint8_t gc_a0[GC_C0*16*16],gc_a1[GC_C1*8*8],gc_a2[GC_C2*4*4];
static int32_t gc_logits[GC_CLASSES];
static int32_t gc_round(int32_t value,unsigned shift){
 if(!shift)return value;
 int32_t biased=value+(int32_t)(1u<<(shift-1));
 if(biased>=0)return (int32_t)((uint32_t)biased>>shift);
 return -(int32_t)(((uint32_t)(-biased)+((1u<<shift)-1u))>>shift);
}
static void gc_conv(const uint8_t *in,unsigned cin,unsigned side,uint8_t *out,unsigned cout,unsigned outside,
 unsigned kernel,unsigned stride,int padding,const int8_t *weights,const int32_t *bias,const uint8_t *shifts){
 for(unsigned o=0;o<cout;o++)for(unsigned y=0;y<outside;y++)for(unsigned x=0;x<outside;x++){
  int32_t sum=bias[o];
  for(unsigned i=0;i<cin;i++)for(unsigned ky=0;ky<kernel;ky++){
   int iy=(int)(y*stride+ky)-padding;if(iy<0 || iy>=(int)side)continue;
   for(unsigned kx=0;kx<kernel;kx++){
    int ix=(int)(x*stride+kx)-padding;if(ix<0 || ix>=(int)side)continue;
    sum+=(int32_t)in[(i*side+(unsigned)iy)*side+(unsigned)ix]*weights[((o*cin+i)*kernel+ky)*kernel+kx];
   }
  }
  int32_t value=gc_round(sum,shifts[o]);out[(o*outside+y)*outside+x]=(uint8_t)(value<0?0:value>255?255:value);
 }
}
int gesture_cnn_predict(const uint8_t image[4096],struct gesture_neural_metrics *metrics){
 gc_conv(image,1,64,gc_a0,GC_C0,16,5,4,2,gc_w0,gc_b0,gc_s0);
 gc_conv(gc_a0,GC_C0,16,gc_a1,GC_C1,8,3,2,1,gc_w1,gc_b1,gc_s1);
 gc_conv(gc_a1,GC_C1,8,gc_a2,GC_C2,4,3,2,1,gc_w2,gc_b2,gc_s2);
 for(unsigned o=0;o<GC_CLASSES;o++){
  int32_t sum=gc_b3[o];
  for(unsigned i=0;i<GC_C2*16;i++)sum+=(int32_t)gc_a2[i]*gc_w3[o*(GC_C2*16)+i];
  int32_t value=gc_round(sum,gc_s3[o]);gc_logits[o]=value<-32768?-32768:value>32767?32767:value;
 }
 unsigned best=0;for(unsigned o=1;o<GC_CLASSES;o++)if(gc_logits[o]>gc_logits[best])best=o;
 int32_t second=-32768;for(unsigned o=0;o<GC_CLASSES;o++)if(o!=best && gc_logits[o]>second)second=gc_logits[o];
 metrics->best_logit=gc_logits[best];metrics->margin=gc_logits[best]-second;metrics->best_class=best;
 if(gc_logits[best]<gc_logit_min[best] || metrics->margin<gc_margin_min[best]){metrics->reason=7;return -2;}
 metrics->reason=best==10?1:0;return best==10?-1:(int)best;
}
/* Numeric validation reads exact activations/logits through this local wrapper. */
void gesture_cnn_logits(int32_t out[GC_CLASSES]){for(unsigned i=0;i<GC_CLASSES;i++)out[i]=gc_logits[i];}
