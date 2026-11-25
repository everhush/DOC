// Linux Goose dynamic C ABI transport smoke for the future Dawn-backed
// native WebGPU provider. NO GPU/DOC language evaluation happens in C.
// The production bridge MUST add true webgpu.h request/dispatch/fence paths
// before this test can count toward issue #17 W2 or GPU conformance.
#include <stdint.h>
#include <stddef.h>
#include <limits.h>
#include <string.h>
typedef struct { int32_t opcode, operand; } doc_gpu_inst;
typedef struct { int32_t offset, length, input_offset, kind; } doc_gpu_stage;
_Static_assert(sizeof(doc_gpu_inst)==8, "DOC GPU v1 instruction ABI changed");
_Static_assert(sizeof(doc_gpu_stage)==16, "DOC GPU v1 stage ABI changed");
_Static_assert(offsetof(doc_gpu_stage,kind)==12, "DOC GPU stage layout changed");
int32_t doc_gpu_probe_abi_version(void){return 1;}
// Opaque transport copy only. A failed validation performs NO writes.
// Goose owns both arrays; this C code cannot retain borrowed pointers.
int32_t doc_gpu_probe_copy(const int32_t *input, int32_t *output, int32_t count) {
    if(!input || !output || count<0 || count>1024) return -1;
    if(count>INT32_MAX/(int32_t)sizeof(int32_t)) return -1;
    if(count!=0) memmove(output,input,(size_t)count*sizeof(int32_t));
    return count;
}
