/* Multiboot 1 entry: minimal platform bootstrap, no DOC computation. */
.section .multiboot,"a"
.align 4
.long 0x1badb002, 0, -(0x1badb002)
.section .text.boot,"ax"
.code32
.global _start
_start:
    cli
    cld
    mov $stack_top, %esp
    /* Identity-map first 2 MiB: PML4 -> PDPT -> 2 MiB page. */
    mov $pdpt, %eax
    or $3, %eax
    mov %eax, pml4
    mov $pd, %eax
    or $3, %eax
    mov %eax, pdpt
    movl $0x83, pd
    mov %cr4, %eax
    or $0x20, %eax
    mov %eax, %cr4
    mov $pml4, %eax
    mov %eax, %cr3
    mov $0xc0000080, %ecx
    rdmsr
    or $0x100, %eax
    wrmsr
    lgdt gdt_pointer
    mov %cr0, %eax
    or $0x80000001, %eax
    mov %eax, %cr0
    ljmp $8, $long_entry
.code64
long_entry:
    mov $16, %ax
    mov %ax, %ds
    mov %ax, %es
    mov %ax, %ss
    mov $stack_top, %rsp
    xor %ebp, %ebp
    call boot_verify
1:  cli
    hlt
    jmp 1b
/* Generic target I/O ABI: no application or device policy. */
.global x86_out8
.type x86_out8,@function
x86_out8:
    mov %edi, %edx
    mov %esi, %eax
    outb %al, %dx
    mov $1, %eax
    ret
.size x86_out8,.-x86_out8
.align 8
gdt:
    .quad 0
    .quad 0x00af9a000000ffff
    .quad 0x00cf92000000ffff
gdt_pointer:
    .word 23
    .long gdt
.section .bss,"aw",@nobits
.align 4096
pml4: .skip 4096
pdpt: .skip 4096
pd: .skip 4096
.align 16
stack: .skip 32768
stack_top:
.section .note.GNU-stack,"",@progbits
