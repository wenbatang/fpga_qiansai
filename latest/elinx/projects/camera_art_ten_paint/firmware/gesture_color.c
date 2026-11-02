/* RGB565 ROI segmentation for SC431HAI diagnostics.
 * These three explicit profiles are engineering hypotheses, not a trained
 * skin model or automatic white balance. No arbitrary-background claim.
 * profile 0: original red-dominant predicate, retained as a comparison.
 * profile 1: allow moderate green bias (G <= 4R/3).
 * profile 2: allow stronger green bias (G <= 8R/5).
 * The latter profiles still require red/green above blue and chroma >=20,
 * so neutral grey and saturated green alone cannot form a hand mask.
 */
#include <stdint.h>
unsigned gesture_skin565(uint16_t pixel,unsigned profile) {
 unsigned r=((pixel>>11)&31u),g=((pixel>>5)&63u),b=pixel&31u;
 r=(r<<3)|(r>>2);g=(g<<2)|(g>>4);b=(b<<3)|(b>>2);
 unsigned maximum=r>g?(r>b?r:b):(g>b?g:b);
 unsigned minimum=r<g?(r<b?r:b):(g<b?g:b);
 if(profile==1u || profile==2u) {
  if(r<40u || g<25u || b<10u || r<b+12u || g<b+4u || maximum-minimum<20u)return 0;
  if(profile==1u)return 4u*r>=3u*g && 2u*g<=3u*r+16u;
  return 8u*r>=5u*g;
 }
 /* Unknown profiles use the original strict mode. */
 return r>=40u && g>=20u && b>=10u && r>g && r>b && r>=g+9u && maximum-minimum>15u;
}
