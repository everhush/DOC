/* Independent boot test oracle only. The memory and output algorithm is DOC. */
#include "boot.h"
static uint8_t memory[2];
static struct doc_result_boot result;
static __attribute__((noreturn)) void exit_test(uint32_t code) {
    __asm__ volatile("outl %0,%1"::"a"(code),"Nd"((uint16_t)0xf4):"memory");
    for (;;) __asm__ volatile("cli; hlt");
}
void boot_verify(void) {
    if (!doc_export_boot(0,64,233,memory,2,&result) ||
        memory[0]!=65 || result.s_read_back!=65 || !result.s_emitted)
        exit_test(0x11);
    if (!doc_export_boot(1,65,233,memory,2,&result) ||
        memory[1]!=66 || result.s_read_back!=66 || !result.s_emitted)
        exit_test(0x12);
    if (doc_export_boot(2,66,233,memory,2,&result) ||
        memory[0]!=65 || memory[1]!=66 || result.s_read_back!=66)
        exit_test(0x13);
    exit_test(0x10);
}
