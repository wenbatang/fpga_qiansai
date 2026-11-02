ENTRY(_start)
MEMORY { RAM (rwx) : ORIGIN = 0xf9000000, LENGTH = 32K }
SECTIONS {
 .text : { KEEP(*(.text.start)) *(.text*) } > RAM
 .rodata : { *(.rodata*) } > RAM
 .data : { *(.data*) *(.sdata*) } > RAM
 __global_pointer$ = . + 0x800;
 .bss (NOLOAD) : { . = ALIGN(4); __bss_start = .; *(.sbss*) *(.bss*) *(COMMON) . = ALIGN(4); __bss_end = .; } > RAM
 __stack_top = ORIGIN(RAM) + LENGTH(RAM);
 ASSERT(__bss_end + 2048 <= __stack_top, "Firmware does not leave 2KB stack")
}
