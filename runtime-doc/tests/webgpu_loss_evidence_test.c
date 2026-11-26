#include "webgpu_loss_evidence.h"
#include <assert.h>
#include <stdio.h>
int main(void){
    const char expected[]="Validation Error\n\nCaused by:\n  In wgpuDeviceCreateBuffer\n    Parent device is lost\n";
    size_t n=sizeof(expected)-1;
    assert(doc_wgpu_invalid_parent(expected,n));
    assert(!doc_wgpu_invalid_parent(NULL,n));
    for(size_t i=0;i<n;i++)assert(!doc_wgpu_invalid_parent(expected,i));
    char changed[sizeof expected];memcpy(changed,expected,sizeof expected);
    for(size_t i=0;i<n;i++){changed[i]^=1;assert(!doc_wgpu_invalid_parent(changed,n));changed[i]^=1;}
    assert(!doc_wgpu_invalid_parent(expected,n+1));
    assert(!doc_wgpu_invalid_parent("Parent device is lost",21));
    puts("DOC11_WGPU_LOSS_EVIDENCE_PASS: exact pinned provider diagnostic, all truncations and one-byte mutations rejected");
}
