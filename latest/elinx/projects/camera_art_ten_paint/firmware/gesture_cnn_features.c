/* 64x64 RGB565 -> normalized grayscale NCHW input. Same C in data preparation.
 * Color/skin counters are diagnostics only; no threshold removes image pixels.
 */
#include <stdint.h>
#include "gesture_color.c"
struct gesture_input_metrics {uint32_t strict_hits,wide_hits,mean_rgb,luma_span,edge_energy;};
static uint8_t *gc_image;
static unsigned gc_lo,gc_hi;
static uint32_t gc_r,gc_g,gc_b,gc_strict,gc_wide;
void gesture_cnn_features_begin(uint8_t image[4096]){
 gc_image=image;gc_lo=255;gc_hi=0;gc_r=gc_g=gc_b=gc_strict=gc_wide=0;
}
void gesture_cnn_features_push(unsigned word_index,uint32_t word){
 for(unsigned half=0;half<2;half++){
  unsigned i=word_index*2+half;uint16_t p=(uint16_t)(word>>(half*16));
  unsigned r=(p>>11)&31,g=(p>>5)&63,b=p&31;
  r=(r<<3)|(r>>2);g=(g<<2)|(g>>4);b=(b<<3)|(b>>2);
  unsigned l=(r+(g<<1)+b)>>2;gc_image[i]=(uint8_t)l;
  if(l<gc_lo)gc_lo=l;if(l>gc_hi)gc_hi=l;
  gc_r+=r;gc_g+=g;gc_b+=b;gc_strict+=gesture_skin565(p,0);gc_wide+=gesture_skin565(p,2);
 }
}
void gesture_cnn_features_end(struct gesture_input_metrics *m){
 unsigned span=gc_hi-gc_lo;
 for(unsigned i=0;i<4096;i++)gc_image[i]=(uint8_t)(span?((gc_image[i]-gc_lo)*255u)/span:128u);
 uint32_t energy=0;
 for(unsigned y=1;y<63;y++)for(unsigned x=1;x<63;x++){
  unsigned i=(y<<6)|x;int dx=(int)gc_image[i+1]-(int)gc_image[i-1],dy=(int)gc_image[i+64]-(int)gc_image[i-64];
  energy+=(uint32_t)(dx<0?-dx:dx)+(uint32_t)(dy<0?-dy:dy);
 }
 m->strict_hits=gc_strict;m->wide_hits=gc_wide;
 m->mean_rgb=((gc_r>>12)<<16)|((gc_g>>12)<<8)|(gc_b>>12);m->luma_span=span;m->edge_energy=energy;
}
void gesture_cnn_features(const uint32_t words[2048],uint8_t image[4096],struct gesture_input_metrics *metrics){
 gesture_cnn_features_begin(image);for(unsigned i=0;i<2048;i++)gesture_cnn_features_push(i,words[i]);gesture_cnn_features_end(metrics);
}
