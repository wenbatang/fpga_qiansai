/* Ti60 V4 SC431HAI + Sapphire control, freestanding RV32 firmware.
 * I2C is open drain: 1 releases a wire, 0 pulls it low; never drive high.
 * Sensor analog/PLL values come from demo10 V7, not guessed 720p values.
 */
#include <stdint.h>
#include "camera_mode.h"
#include "weights_catalog.h"
#define CTRL_BASE 0xf8100000u
#define REG(offset) (*(volatile uint32_t *)(uintptr_t)(CTRL_BASE+(offset)))
#define PLIC(offset) (*(volatile uint32_t *)(uintptr_t)(0xf8c00000u+(offset)))
#define SENSOR_ADDR 0x30u
static volatile uint32_t events, irq_count;
static uint32_t lines=3;
static void delay_ticks(uint32_t n) {
 uint32_t start=REG(0x48); while((uint32_t)(REG(0x48)-start)<n) {}
}
static void wires(uint32_t mask) { lines=mask;REG(0x40)=mask;delay_ticks(500); }
static int clock_high(void) {
 uint32_t start=REG(0x48);REG(0x40)=lines|2;
 while(!(REG(0x44)&2))if((uint32_t)(REG(0x48)-start)>1000000)return -1;
 lines|=2;delay_ticks(500);return 0;
}
static int i2c_start(void) {
 wires(1);if(clock_high())return -1;
 if(!(REG(0x44)&1))return -1;
 wires(2);wires(0);return 0;
}
static void i2c_stop(void) { wires(0);(void)clock_high();wires(3); }
static int send_byte(uint32_t data) {
 for(int bit=7;bit>=0;--bit) {
  wires((data>>bit)&1);if(clock_high())return -1;wires(lines&1);
 }
 wires(1);if(clock_high())return -1;
 int nack=REG(0x44)&1;wires(1);return nack ? -1:0;
}
static int receive_byte(uint8_t *value) {
 uint32_t data=0;
 for(int bit=0;bit<8;++bit) {
  wires(1);if(clock_high())return -1;data=(data<<1)|(REG(0x44)&1);wires(1);
 }
 /* NACK the single final read byte, then STOP. */
 wires(1);if(clock_high())return -1;wires(1);*value=(uint8_t)data;return 0;
}
static int sensor_write(uint16_t address,uint8_t data) {
 int bad=i2c_start() || send_byte(SENSOR_ADDR<<1) || send_byte(address>>8) ||
   send_byte(address&255) || send_byte(data);
 i2c_stop();return bad ? -1:0;
}
static int sensor_read(uint16_t address,uint8_t *data) {
 int bad=i2c_start() || send_byte(SENSOR_ADDR<<1) || send_byte(address>>8) ||
  send_byte(address&255) || i2c_start() || send_byte((SENSOR_ADDR<<1)|1) || receive_byte(data);
 i2c_stop();return bad ? -1:0;
}
static void fail(uint32_t reason) {
 REG(0x60)=0x80000000u|reason;
 REG(0x04)=4; /* capture off, sensor held reset, overlay retained */
 REG(0x40)=3;
 for(;;) {}
}
static void load_style(uint32_t style) {
 if(style>=10)style=0;
 REG(0x2c)=style;REG(0x30)=2;
 const volatile uint8_t *p=(const volatile uint8_t *)(uintptr_t)(CTRL_BASE+0x4000u+style*736u);
 for(uint32_t layer=0;layer<10;++layer) {
  uint32_t nw=weight_count[layer],nc=channel_count[layer];
  for(uint32_t i=0;i<nw;i+=4){REG(0x50)=(layer<<12)|i;REG(0x54)=*(const volatile uint32_t *)(p+i);}
  p+=nw;
  for(uint32_t c=0;c<nc;++c){REG(0x50)=(layer<<12)|0x400u|c;REG(0x54)=*(const volatile uint32_t *)(p+4*c);}
  p+=4*nc;
  for(uint32_t c=0;c<nc;++c){REG(0x50)=(layer<<12)|0x800u|c;REG(0x54)=p[c];}
  p+=(nc+3u)&~3u;
 }
 if(REG(0x58)!=216)fail(0x20);
 REG(0x30)=4;
}
void __attribute__((interrupt("machine"),aligned(4))) machine_trap(void) {
 uint32_t cause;__asm__ volatile("csrr %0,mcause":"=r"(cause));
 if(cause!=0x8000000bu)fail(0x40);
 uint32_t claim=PLIC(0x200004);
 if(claim==16) {
  uint32_t pending=REG(0x0c);events|=pending;REG(0x0c)=pending;++irq_count;
 }
 if(claim)PLIC(0x200004)=claim;
}
#include "gesture_runtime.c"
int main(void) {
 uint8_t hi,lo;
 uint32_t misa;__asm__ volatile("csrr %0,misa":"=r"(misa));
 if(!(misa&(1u<<12)))fail(0x70); /* Existing Sapphire IP advertises RV32M. */
 volatile int32_t math_a=-7,math_b=9;
 if(math_a*math_b!=-63 || (math_a*math_b)/math_b!=math_a)fail(0x70);
 if(REG(0)!=0x53565931u)fail(1);
 REG(0x60)=1;REG(0x04)=4;REG(0x40)=3;delay_ticks(1000000);
 REG(0x04)=6;delay_ticks(1000000); /* Release V7 active-high module RESET, >=4ms */
 if(sensor_read(0x3107,&hi)||sensor_read(0x3108,&lo))fail(2);
 if(hi!=0xcd || lo!=0x6b)fail(3);
 REG(0x60)=2;
 for(uint32_t i=0;i<CAMERA_MODE_COUNT;++i)
  if(sensor_write(camera_mode[i].address,camera_mode[i].value))fail(4);
 const uint16_t check_addr[4]={0x3208,0x3209,0x320a,0x320b};
 const uint8_t check_value[4]={0x07,0x80,0x04,0x38};
 for(uint32_t i=0;i<4;++i)
  if(sensor_read(check_addr[i],&hi)||hi!=check_value[i])fail(5);
 /* V7's final exposure can exceed this mode's frame length. The linear
  * datasheet limit is 2*VTS-11 HALF-lines; read the actual VTS rather than
  * guessing a frame rate or changing the manufacturer's clock settings. */
 if(sensor_read(0x320e,&hi)||sensor_read(0x320f,&lo))fail(7);
 uint32_t vts=((uint32_t)hi<<8)|lo;
 if(vts<1080)fail(8);
 uint8_t e0,e1,e2;
 if(sensor_read(0x3e00,&e0)||sensor_read(0x3e01,&e1)||sensor_read(0x3e02,&e2))fail(7);
 uint32_t exposure=((uint32_t)(e0&15)<<12)|((uint32_t)e1<<4)|(e2>>4);
 uint32_t maximum=2*vts-11;
 if(exposure>maximum || exposure<4) {
  exposure=exposure<4 ? 4:maximum;
  if(sensor_write(0x3e00,(e0&0xf0)|(exposure>>12)) ||
     sensor_write(0x3e01,(exposure>>4)&255) ||
     sensor_write(0x3e02,((exposure&15)<<4)|(e2&15)))fail(9);
 }
 load_style(0);
 PLIC(16*4)=1;PLIC(0x2000)=1u<<16;PLIC(0x200000)=0;
 REG(0x0c)=15;REG(0x10)=15;
 __asm__ volatile("csrs mie,%0"::"r"(0x800));
 __asm__ volatile("csrs mstatus,%0"::"r"(8));
 REG(0x04)=7;
 if(sensor_write(0x0100,1))fail(6);
 REG(0x60)=3;
 for(;;) {
  /* IRQ completion is acknowledged in the handler. Source selection and
   * accelerator START stay under software control; no auto-FSM posing as CPU.
   */
  uint32_t status=REG(0x08);
  if(!(status&1)) {
   uint32_t requested=REG(0x28)&63;
   if((REG(0x2c)&63)!=requested || !(status&8))load_style(requested);
   if(REG(0x08)&4)REG(0x30)=1;
  }
  /* Launch eligible video work first, then service gesture/watchdogs even
   * when capture temporarily has no source. No idle-dependent timer stall. */
  gesture_poll();
 }
}
