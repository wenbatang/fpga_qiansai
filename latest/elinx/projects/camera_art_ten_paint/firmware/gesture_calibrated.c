/* Optional, supervised on-board prototype calibration. No neural-network
 * accuracy claim; RAM templates are lost on reset. Caller owns an immutable
 * RGB565 ROI until this complete function returns; ACK afterwards only.
 */
#include <stdint.h>
#ifndef GESTURE_ROI_WORD
#define GESTURE_ROI_WORD(i) (*(volatile uint32_t *)(uintptr_t)(0xf8102000u+4u*(i)))
#endif
struct cal_metrics {uint32_t foreground_count,mean_rgb,threshold,best_distance,margin,reason;};
#define CAL_TEMPLATES 4
#define CAL_FEATURES 192
static uint8_t cal_bg[4096],cal_canon[4096],cal_f[CAL_FEATURES],cal_proto[10][CAL_TEMPLATES][CAL_FEATURES];
static uint8_t cal_mask[512],cal_clean[512],cal_counts[10],cal_limits[10];
static uint16_t cal_hist[512];static uint32_t cal_hog[64];
static uint32_t cal_bg_count,cal_noise_sum,cal_noise_threshold;
static unsigned cal_abs(int value){return value<0?(unsigned)-value:(unsigned)value;}
static uint16_t cal_pixel(unsigned i){return (uint16_t)(GESTURE_ROI_WORD(i>>1)>>((i&1u)*16));}
static unsigned cal_gray(uint16_t p){
 unsigned r=(p>>11)&31,g=(p>>5)&63,b=p&31;
 r=(r<<3)|(r>>2);g=(g<<2)|(g>>4);b=(b<<3)|(b>>2);return (r+2*g+b)>>2;
}
static unsigned cal_bit(const uint8_t *mask,int x,int y){
 if(x<0 || y<0 || x>=64 || y>=64)return 0;unsigned i=(unsigned)y*64+(unsigned)x;return (mask[i>>3]>>(i&7))&1u;
}
static void cal_set(uint8_t *mask,unsigned i){mask[i>>3]|=(uint8_t)(1u<<(i&7));}
static int cal_half_floor(int value){return value>=0?value/2:-(int)(((unsigned)-value+1u)/2u);}
void cal_reset(void){
 cal_bg_count=cal_noise_sum=0;cal_noise_threshold=6;
 for(unsigned i=0;i<10;i++){cal_counts[i]=0;cal_limits[i]=14;}
}
uint32_t cal_valid_mask(void){unsigned mask=0;for(unsigned i=0;i<10;i++)if(cal_counts[i]==CAL_TEMPLATES)mask|=1u<<i;return mask;}
unsigned cal_background_count(void){return cal_bg_count;}
unsigned cal_class_count(unsigned label){return label<10?cal_counts[label]:0;}
unsigned cal_class_threshold(unsigned label){return label<10?cal_limits[label]:0;}
void cal_restart_class(unsigned label){if(label<10){cal_counts[label]=0;cal_limits[label]=14;}}
int cal_capture_background(unsigned sample_index){
 if(sample_index==0)cal_reset();
 if(sample_index!=cal_bg_count || sample_index>=3)return -2;
 int offset=0;
 if(sample_index){
  for(unsigned i=0;i<512;i++)cal_hist[i]=0;
  for(unsigned i=0;i<4096;i++)cal_hist[(int)cal_gray(cal_pixel(i))-cal_bg[i]+255]++;
  unsigned sum=0;for(unsigned i=0;i<511;i++){sum+=cal_hist[i];if(sum>=2048){offset=(int)i-255;break;}}
 }
 for(unsigned i=0;i<4096;i++){
  int corrected=(int)cal_gray(cal_pixel(i))-offset;unsigned value=corrected<0?0:corrected>255?255:(unsigned)corrected;
  if(sample_index)cal_noise_sum+=cal_abs((int)value-cal_bg[i]);
  cal_bg[i]=(uint8_t)(((unsigned)cal_bg[i]*sample_index+value)/(sample_index+1));
 }
 cal_bg_count++;
 unsigned noise=cal_bg_count>1?cal_noise_sum/(4096u*(cal_bg_count-1u)):0;
 unsigned t=3*noise+4;cal_noise_threshold=t<6?6:t>20?20:t;return 0;
}
/* Reuse the histogram as a bounded union-find table; no new frame RAM.
 * Canonical image temporarily stores labels, then is overwritten normally. */
static unsigned cal_root(unsigned label){
 while(cal_hist[label]!=label){cal_hist[label]=cal_hist[cal_hist[label]];label=cal_hist[label];}return label;
}
static int cal_largest(void){
 unsigned labels=0;
 for(unsigned i=0;i<512;i++)cal_hist[i]=0;
 for(unsigned y=0;y<64;y++)for(unsigned x=0;x<64;x++){
  unsigned i=y*64+x;cal_canon[i]=0;if(!cal_bit(cal_clean,(int)x,(int)y))continue;
  unsigned adjacent[4]={x?cal_canon[i-1]:0,y && x?cal_canon[i-65]:0,y?cal_canon[i-64]:0,y && x<63?cal_canon[i-63]:0},label=0;
  for(unsigned k=0;k<4;k++)if(adjacent[k]){
   unsigned a=cal_root(adjacent[k]);if(!label)label=a;else {unsigned b=cal_root(label);label=a<b?a:b;cal_hist[a>b?a:b]=(uint16_t)label;}
  }
  if(!label){if(labels==254)return -1;label=++labels;cal_hist[label]=(uint16_t)label;}
  cal_canon[i]=(uint8_t)label;
 }
 for(unsigned i=0;i<4096;i++)if(cal_canon[i])cal_hist[256+cal_root(cal_canon[i])]++;
 unsigned best=0,count=0;
 for(unsigned i=1;i<=labels;i++)if(cal_hist[256+i]>count){best=i;count=cal_hist[256+i];}
 for(unsigned i=0;i<512;i++)cal_clean[i]=0;
 for(unsigned i=0;i<4096;i++)if(cal_canon[i] && cal_root(cal_canon[i])==best)cal_set(cal_clean,i);
 return (int)count;
}
static void cal_metrics_reset(struct cal_metrics *m){
 m->foreground_count=m->mean_rgb=0;m->threshold=cal_noise_threshold;
 m->best_distance=65535;m->margin=0;m->reason=0;
}
static int cal_extract(struct cal_metrics *m){
 cal_metrics_reset(m);if(cal_bg_count!=3){m->reason=1;return -2;}
 for(unsigned i=0;i<512;i++){cal_hist[i]=0;cal_mask[i]=0;cal_clean[i]=0;}
 for(unsigned i=0;i<4096;i++){
  int delta=(int)cal_gray(cal_pixel(i))-cal_bg[i];cal_hist[delta+255]++;
 }
 unsigned accumulated=0;int offset=0;
 for(unsigned i=0;i<511;i++){accumulated+=cal_hist[i];if(accumulated>=2048){offset=(int)i-255;break;}}
 unsigned sr=0,sg=0,sb=0;
 for(unsigned i=0;i<4096;i++){
  uint16_t p=cal_pixel(i);unsigned r=(p>>11)&31,g=(p>>5)&63,b=p&31;
  r=(r<<3)|(r>>2);g=(g<<2)|(g>>4);b=(b<<3)|(b>>2);sr+=r;sg+=g;sb+=b;
  if(cal_abs((int)((r+2*g+b)>>2)-(int)cal_bg[i]-offset)>cal_noise_threshold)cal_set(cal_mask,i);
 }
 m->mean_rgb=((sr>>12)<<16)|((sg>>12)<<8)|(sb>>12);
 unsigned count=0,minx=64,miny=64,maxx=0,maxy=0,lo=255,hi=0;
 for(unsigned y=0;y<64;y++)for(unsigned x=0;x<64;x++)if(cal_bit(cal_mask,(int)x,(int)y)){
  unsigned neighbors=0;
  for(int dy=-1;dy<=1;dy++)for(int dx=-1;dx<=1;dx++)if(dx || dy)neighbors+=cal_bit(cal_mask,(int)x+dx,(int)y+dy);
  if(neighbors>=2){unsigned i=y*64+x;cal_set(cal_clean,i);count++;
   if(x<minx)minx=x;if(x>maxx)maxx=x;if(y<miny)miny=y;if(y>maxy)maxy=y;
   unsigned value=cal_gray(cal_pixel(i));if(value<lo)lo=value;if(value>hi)hi=value;
  }
 }
 int largest=cal_largest();if(largest<0){m->reason=8;return -2;}
 count=0;minx=miny=64;maxx=maxy=0;lo=255;hi=0;
 for(unsigned i=0;i<256;i++)cal_hist[i]=0;
 for(unsigned y=0;y<64;y++)for(unsigned x=0;x<64;x++)if(cal_bit(cal_clean,(int)x,(int)y)){
  count++;if(x<minx)minx=x;if(x>maxx)maxx=x;if(y<miny)miny=y;if(y>maxy)maxy=y;
  cal_hist[cal_gray(cal_pixel(y*64+x))]++;
 }
 // Robust 5/95 percentiles prevent one glare/noise pixel rescaling the hand.
 unsigned accumulated_gray=0;
 for(unsigned i=0;i<256;i++){accumulated_gray+=cal_hist[i];if(accumulated_gray>count/20){lo=i;break;}}
 accumulated_gray=0;
 for(unsigned i=0;i<256;i++){accumulated_gray+=cal_hist[i];if(accumulated_gray>count*19/20){hi=i;break;}}
 m->foreground_count=count;
 if(count<24){m->reason=2;return -1;}
 if(count>3600 || maxx-minx+1<6 || maxy-miny+1<6){m->reason=3;return -2;}
 unsigned width=maxx-minx+1,height=maxy-miny+1,side=width>height?width:height;
 side+=(side+7)/8;
 int left=cal_half_floor((int)(minx+maxx+1)-(int)side),top=cal_half_floor((int)(miny+maxy+1)-(int)side);
 unsigned span=hi-lo;
 for(unsigned y=0;y<64;y++)for(unsigned x=0;x<64;x++){
  int sx=left+(int)(((2*x+1)*side)>>7),sy=top+(int)(((2*y+1)*side)>>7);unsigned value=0;
  if(cal_bit(cal_clean,sx,sy)){
   unsigned raw=cal_gray(cal_pixel((unsigned)sy*64+(unsigned)sx));raw=raw<lo?lo:raw>hi?hi:raw;value=span<8?160:63+(raw-lo)*192/span;
  }
  cal_canon[y*64+x]=(uint8_t)value;
 }
 for(unsigned i=0;i<64;i++)cal_hog[i]=0;
 for(unsigned y=1;y<63;y++)for(unsigned x=1;x<63;x++){
  unsigned i=y*64+x;int dx=(int)cal_canon[i+1]-cal_canon[i-1],dy=(int)cal_canon[i+64]-cal_canon[i-64];
  unsigned ax=cal_abs(dx),ay=cal_abs(dy),bin;
  if(ax>2*ay)bin=dx>=0?0:4;else if(ay>2*ax)bin=dy>=0?2:6;
  else if(dx>=0)bin=dy>=0?1:7;else bin=dy>=0?3:5;
  cal_hog[(((y>>4)*4)+(x>>4))*4+(bin&3u)]+=ax+ay;
 }
 for(unsigned cell=0;cell<16;cell++){
  unsigned sum=0;for(unsigned k=0;k<4;k++)sum+=cal_hog[cell*4+k];
  for(unsigned k=0;k<4;k++)cal_f[cell*4+k]=(uint8_t)(sum?cal_hog[cell*4+k]*255/sum:0);
 }
 for(unsigned gy=0;gy<8;gy++)for(unsigned gx=0;gx<8;gx++){
  unsigned sum=0,mask_count=0;
  for(unsigned dy=0;dy<8;dy++)for(unsigned dx=0;dx<8;dx++){
   unsigned v=cal_canon[(gy*8+dy)*64+gx*8+dx];sum+=v;mask_count+=v!=0;
  }
  unsigned i=gy*8+gx;cal_f[64+i]=(uint8_t)(sum>>6);cal_f[128+i]=(uint8_t)(mask_count*255/64);
 }
 return 0;
}
static unsigned cal_distance_view(const uint8_t *a,const uint8_t *b,unsigned mirror){
 unsigned h=0,g=0,m=0;
 for(unsigned i=0;i<64;i++){
  unsigned j=mirror?((i/16)*4+3-(i/4)%4)*4+((4-(i&3u))&3u):i;
  h+=cal_abs((int)a[j]-b[i]);
  j=mirror?(i/8)*8+7-i%8:i;
  g+=cal_abs((int)a[64+j]-b[64+i]);m+=cal_abs((int)a[128+j]-b[128+i]);
 }
 return (h+g/2+2*m)/224;
}
static unsigned cal_distance(const uint8_t *a,const uint8_t *b){
 unsigned normal=cal_distance_view(a,b,0),mirror=cal_distance_view(a,b,1);return normal<mirror?normal:mirror;
}
int cal_capture_template(unsigned label,unsigned sample_index,struct cal_metrics *m){
 cal_metrics_reset(m);
 if(label>=10 || sample_index>=CAL_TEMPLATES || cal_counts[label]!=sample_index){m->reason=5;return -2;}
 int result=cal_extract(m);if(result)return result;
 for(unsigned i=0;i<CAL_FEATURES;i++)cal_proto[label][sample_index][i]=cal_f[i];cal_counts[label]++;
 if(cal_counts[label]==CAL_TEMPLATES){
  unsigned maximum=0;
  for(unsigned i=0;i<CAL_TEMPLATES;i++)for(unsigned j=i+1;j<CAL_TEMPLATES;j++){unsigned d=cal_distance(cal_proto[label][i],cal_proto[label][j]);if(d>maximum)maximum=d;}
  unsigned limit=2*maximum+8;cal_limits[label]=(uint8_t)(limit<14?14:limit>40?40:limit);
 }
 return 0;
}
int cal_predict(struct cal_metrics *m){
 int result=cal_extract(m);if(result)return result;
 if(cal_valid_mask()!=1023){m->reason=4;return -2;}
 unsigned best=65535,second=65535,label=0;
 for(unsigned c=0;c<10;c++){
  unsigned minimum=65535;
  for(unsigned p=0;p<CAL_TEMPLATES;p++){unsigned d=cal_distance(cal_f,cal_proto[c][p]);if(d<minimum)minimum=d;}
  if(minimum<best){second=best;best=minimum;label=c;}else if(minimum<second)second=minimum;
 }
 m->best_distance=best;m->margin=second-best;
 if(best>cal_limits[label]){m->reason=6;return -2;}
 if(second-best<(best/8>2?best/8:2)){m->reason=7;return -2;}
 return (int)label;
}
