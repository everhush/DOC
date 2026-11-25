/* Identity-mapped, bounded x86_64 bare-metal validation image. */
ENTRY(_start)
PHDRS {
  text PT_LOAD FLAGS(5);
  data PT_LOAD FLAGS(6);
}
SECTIONS {
  . = 1M;
  .multiboot : { KEEP(*(.multiboot)) } :text
  .text : { *(.text.boot) *(.text .text.*) } :text
  .rodata : { *(.rodata .rodata.*) } :text
  . = ALIGN(4096);
  .data : { *(.data .data.*) } :data
  .bss : { *(.bss .bss.*) *(COMMON) } :data
  ASSERT(. < 2M, "bootstrap identity map exceeded")
  /DISCARD/ : { *(.eh_frame*) *(.note*) *(.comment*) }
}
