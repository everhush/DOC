#ifndef DOC_WEBGPU_LOSS_EVIDENCE_H
#define DOC_WEBGPU_LOSS_EVIDENCE_H
#include <stddef.h>
#include <string.h>
/* Exact bounded diagnostic emitted by the pinned v27 error sink. */
static int doc_wgpu_invalid_parent(const char *message,size_t length){
    static const char expected[]="Validation Error\n\nCaused by:\n  In wgpuDeviceCreateBuffer\n    Parent device is lost\n";
    return message&&length==sizeof(expected)-1&&!memcmp(message,expected,length);
}
#endif
