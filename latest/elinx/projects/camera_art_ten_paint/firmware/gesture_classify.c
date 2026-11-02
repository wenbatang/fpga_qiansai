/* Fixed ROI geometric classifier: upright, separated fingers, simple background.
 * 0=confirmed sparse/no hand, -1=ambiguous/unsupported, 1..4=finger count.
 * No neural-landmark equivalence or arbitrary-background accuracy claim.
 */
#include <stdint.h>
#define GS 64
#define GN (GS*GS)
/* The first five fields retain their original layout for existing diagnostics. */
struct gesture_metrics { uint32_t area,radius,fingers,center_x,center_y,reason; };
static uint8_t gi[GN];
static uint16_t gq[GN];
static uint32_t gb[GN/32];
static int bit_at(const uint32_t *bits,int x,int y) {
 if(x<0 || y<0 || x>=GS || y>=GS)return 0;
 unsigned i=(unsigned)y*GS+(unsigned)x;return (bits[i>>5]>>(i&31))&1;
}
static int breadth(int start) {
 int n=1,head=0;gi[start]=2;gq[0]=(uint16_t)start;
 while(head<n){int pos=gq[head++],x=pos%GS,y=pos/GS;
  for(int dy=-1;dy<=1;dy++)for(int dx=-1;dx<=1;dx++) {
   int nx=x+dx,ny=y+dy;if(nx<0 || ny<0 || nx>=GS || ny>=GS)continue;
   int j=ny*GS+nx;if(gi[j]==1){gi[j]=2;gq[n++]=(uint16_t)j;}
  }
 }
 return n;
}
int gesture_classify(const uint32_t words[GN/32],struct gesture_metrics *m) {
 int total=0,best=0,second=0;
 m->area=m->radius=m->fingers=m->center_x=m->center_y=m->reason=0;
 for(int y=0;y<GS;y++)for(int x=0;x<GS;x++) {
  int n=0;
  if(bit_at(words,x,y))for(int dy=-1;dy<=1;dy++)for(int dx=-1;dx<=1;dx++)if(dx || dy)n+=bit_at(words,x+dx,y+dy);
  gi[y*GS+x]=(uint8_t)(bit_at(words,x,y) && n>=2);total+=gi[y*GS+x];
 }
 if(total<40){m->reason=1;return 0;}
 for(int i=0;i<GN;i++)if(gi[i]==1){int n=breadth(i);
  if(n>best){second=best;best=n;for(int k=0;k<GN/32;k++)gb[k]=0;for(int k=0;k<n;k++)gb[gq[k]>>5]|=1u<<(gq[k]&31);}
  else if(n>second)second=n;
 }
 m->area=(uint32_t)best;
 if(best<160 || best>2400){m->reason=2;return -1;}
 if(second>100 && second*2>best){m->reason=3;return -1;}
 int minx=GS,miny=GS,maxx=0,maxy=0;
 for(int y=0;y<GS;y++)for(int x=0;x<GS;x++){
  int yes=bit_at(gb,x,y);gi[y*GS+x]=(uint8_t)(yes?63:0);
  if(yes){if(x<minx)minx=x;if(x>maxx)maxx=x;if(y<miny)miny=y;if(y>maxy)maxy=y;}
 }
 if(minx<=0 || maxx>=GS-1 || miny<=0 || maxx-minx<13 || maxy-miny<21){m->reason=4;return -1;}
 /* City-block distance, then choose the uppermost largest inscribed palm. */
 for(int y=0;y<GS;y++)for(int x=0;x<GS;x++)if(gi[y*GS+x]) {
  int v=63;if(x==0 || y==0)v=1;else{int a=gi[y*GS+x-1]+1,b=gi[(y-1)*GS+x]+1;v=a<b?a:b;}
  gi[y*GS+x]=(uint8_t)v;
 }
 int radius=0,cx=0,cy=0;
 for(int y=GS-1;y>=0;y--)for(int x=GS-1;x>=0;x--)if(gi[y*GS+x]) {
  int v=gi[y*GS+x];if(x==GS-1 || y==GS-1)v=1;
  else {if(gi[y*GS+x+1]+1<v)v=gi[y*GS+x+1]+1;if(gi[(y+1)*GS+x]+1<v)v=gi[(y+1)*GS+x]+1;}
  gi[y*GS+x]=(uint8_t)v;if(v>=radius){radius=v;cx=x;cy=y;}
 }
 m->radius=(uint32_t)radius;m->center_x=(uint32_t)cx;m->center_y=(uint32_t)cy;
 if(radius<5 || radius>18){m->reason=5;return -1;}
 int cut2=(radius*radius*9)/4;
 for(int y=0;y<GS;y++)for(int x=0;x<GS;x++){
  int dx=x-cx,dy=y-cy;gi[y*GS+x]=(uint8_t)(bit_at(gb,x,y) && y<=cy+radius/2 && dx*dx+dy*dy>cut2);
 }
 int fingers=0;
 for(int i=0;i<GN;i++)if(gi[i]==1){int n=breadth(i),far=0,tx=cx,ty=cy;
  for(int j=0;j<n;j++){int x=gq[j]%GS,y=gq[j]/GS,dx=x-cx,dy=y-cy,d=dx*dx+dy*dy;if(d>far){far=d;tx=x;ty=y;}}
  if(n>=4 && n<=300 && ty<cy && far>=3*radius*radius){fingers++;}
  (void)tx;
 }
 m->fingers=(uint32_t)fingers;
 if(fingers>=1 && fingers<=4)return fingers;
 m->reason=6;return -1;
}
