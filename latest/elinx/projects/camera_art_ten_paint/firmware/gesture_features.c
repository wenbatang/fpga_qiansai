/* Integer-only 64x64 RGB565 -> 256 features, identical in training and RV32.
 * Features: 4x4 cells x8 signed HOG bins, 8x8 normalized luma, 8x8 skin density.
 * Skin is an auxiliary feature; it never gates image acceptance by itself.
 */
#include <stdint.h>
#include "gesture_color.c"
struct gesture_input_metrics {uint32_t strict_hits,wide_hits,mean_rgb,luma_span,edge_energy;};
static uint8_t gd_gray[4096];
static uint32_t gd_luma[64],gd_skin[64],gd_hist[128];
static uint32_t gd_r,gd_g,gd_b,gd_strict,gd_wide;
void gesture_features_begin(void){
 for(unsigned i=0;i<64;i++){gd_luma[i]=0;gd_skin[i]=0;}
 for(unsigned i=0;i<128;i++)gd_hist[i]=0;
 gd_r=gd_g=gd_b=gd_strict=gd_wide=0;
}
void gesture_features_push(unsigned word_index,uint32_t word){
 for(unsigned half=0;half<2;half++){
  unsigned i=2*word_index+half,x=i&63,y=i>>6;
  uint16_t p=(uint16_t)(word>>(half*16));
  unsigned r=(p>>11)&31,g=(p>>5)&63,b=p&31;
  r=(r<<3)|(r>>2);g=(g<<2)|(g>>4);b=(b<<3)|(b>>2);
  unsigned l=(r+(g<<1)+b)>>2,cell=((y>>3)<<3)|(x>>3);
  unsigned skin=gesture_skin565(p,2);
  gd_gray[i]=(uint8_t)l;gd_luma[cell]+=l;gd_skin[cell]+=skin;
  gd_strict+=gesture_skin565(p,0);gd_wide+=skin;
  gd_r+=r;gd_g+=g;gd_b+=b;
 }
}
void gesture_features_end(uint8_t f[256],struct gesture_input_metrics *m){
 uint32_t energy=0;unsigned lo=255,hi=0;
 for(unsigned i=0;i<64;i++){
  unsigned value=gd_luma[i]>>6;gd_luma[i]=value;
  if(value<lo)lo=value;if(value>hi)hi=value;
 }
 for(unsigned y=1;y<63;y++)for(unsigned x=1;x<63;x++){
  unsigned i=(y<<6)|x;
  int dx=(int)gd_gray[i+1]-(int)gd_gray[i-1];
  int dy=(int)gd_gray[i+64]-(int)gd_gray[i-64];
  unsigned ax=dx<0?(unsigned)-dx:(unsigned)dx,ay=dy<0?(unsigned)-dy:(unsigned)dy;
  unsigned bin;
  if(ax>(ay<<1))bin=dx>=0?0:4;
  else if(ay>(ax<<1))bin=dy>=0?2:6;
  else if(dx>=0)bin=dy>=0?1:7;
  else bin=dy>=0?3:5;
  unsigned mag=ax+ay;gd_hist[(((y>>4)<<2)|(x>>4))*8+bin]+=mag;energy+=mag;
 }
 for(unsigned cell=0;cell<16;cell++){
  unsigned sum=0;for(unsigned k=0;k<8;k++)sum+=gd_hist[cell*8+k];
  for(unsigned k=0;k<8;k++)f[cell*8+k]=(uint8_t)(sum?(gd_hist[cell*8+k]*255u)/sum:0);
 }
 for(unsigned i=0;i<64;i++){
  f[128+i]=(uint8_t)(hi>lo?((gd_luma[i]-lo)*255u)/(hi-lo):128u);
  f[192+i]=(uint8_t)((gd_skin[i]*255u)>>6);
 }
 m->strict_hits=gd_strict;m->wide_hits=gd_wide;
 m->mean_rgb=((gd_r>>12)<<16)|((gd_g>>12)<<8)|(gd_b>>12);
 m->luma_span=hi-lo;m->edge_energy=energy;
}
/* Host/ISA fixture convenience; firmware streams directly through push(). */
void gesture_features(const uint32_t words[2048],uint8_t features[256],struct gesture_input_metrics *metrics){
 gesture_features_begin();for(unsigned i=0;i<2048;i++)gesture_features_push(i,words[i]);
 gesture_features_end(features,metrics);
}
