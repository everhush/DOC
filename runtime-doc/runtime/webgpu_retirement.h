#ifndef DOC_WEBGPU_RETIREMENT_H
#define DOC_WEBGPU_RETIREMENT_H
#include <webgpu/wgpu.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include "webgpu_loss_evidence.h"
/* Native C ABI transport for the checksum-pinned wgpu-native v27.0.4.1.
 * The queue callback must complete before submitted resources can be freed
 * or reused. A device-lost callback alone is NOT a retirement certificate.
 * Timeout/failure is process fail-stop; no stale data is published. */
static void doc_wgpu_completed(WGPUQueueWorkDoneStatus status,WGPUStringView message,void *ctx,void *unused){
    (void)message;(void)unused;
    atomic_store((_Atomic int*)ctx,status==WGPUQueueWorkDoneStatus_Success?1:-1);
}
static void doc_wgpu_wait_retirement(WGPUInstance instance,WGPUDevice device,_Atomic int *done,int poll,const char *phase){
    struct timespec start,now,delay={0,1000000};
    if(clock_gettime(CLOCK_MONOTONIC,&start))_Exit(1);
    while(!atomic_load(done)){
        if(clock_gettime(CLOCK_MONOTONIC,&now)||now.tv_sec-start.tv_sec>=30){
            fprintf(stderr,"DOC11_WGPU_RETIRE_TIMEOUT: phase=%s; fail-stop without publication\n",phase);_Exit(1);
        }
        if(poll)wgpuDevicePoll(device,0,NULL);
        if(!atomic_load(done))wgpuInstanceProcessEvents(instance);
        if(!atomic_load(done))nanosleep(&delay,NULL);
    }
}
static void doc_wgpu_retire_queue(WGPUInstance instance,WGPUDevice device,WGPUQueue queue,int destroy){
    _Atomic int done=0;
    if(!instance||!device||!queue)_Exit(1);
    wgpuQueueOnSubmittedWorkDone(queue,(WGPUQueueWorkDoneCallbackInfo){.mode=WGPUCallbackMode_AllowSpontaneous,.callback=doc_wgpu_completed,.userdata1=&done});
    /* Register first: destroy invalidates future operations but permits
     * already-submitted queue work to drain. */
    if(destroy)wgpuDeviceDestroy(device);
    doc_wgpu_wait_retirement(instance,device,&done,1,"queue");
    if(atomic_load(&done)!=1){fprintf(stderr,"DOC11_WGPU_RETIRE_FAILED: queue status; fail-stop\n");_Exit(1);}
    fprintf(stderr,"DOC11_WGPU_QUEUE_RETIRED: destroy=%d\n",destroy);
}
/* v27 reports invalid-parent device creation as a scoped validation error,
 * rather than always delivering a device-lost callback. Accept only the
 * exact provider diagnostic for our minimal valid post-destroy probe.
 * An unrelated validation failure, timeout or successful probe is fatal. */
typedef struct {_Atomic int done;int proof;} DocWgpuLossProbe;
static void doc_wgpu_loss_probe(WGPUPopErrorScopeStatus status,WGPUErrorType type,WGPUStringView message,void *ctx,void *unused){
    (void)unused;DocWgpuLossProbe *p=ctx;
    size_t n=message.data?(message.length==WGPU_STRLEN?strlen(message.data):message.length):0;
    p->proof=status==WGPUPopErrorScopeStatus_Success&&type==WGPUErrorType_Validation&&doc_wgpu_invalid_parent(message.data,n);
    if(p->proof)fprintf(stderr,"DOC11_WGPU_LOSS_PROBE: status=success type=validation\n%.*s",(int)n,message.data);
    else fprintf(stderr,"DOC11_WGPU_LOSS_PROBE_OTHER: status=%u type=%u message=%.*s\n",(unsigned)status,(unsigned)type,(int)(n>4096?4096:n),message.data?message.data:"");
    atomic_store(&p->done,1);
}
static void doc_wgpu_destroy_and_retire(WGPUInstance instance,WGPUDevice device,WGPUQueue queue,_Atomic int *lost,_Atomic int *fault){
    doc_wgpu_retire_queue(instance,device,queue,1);
    if(!atomic_load(lost)){
        DocWgpuLossProbe proof={0};
        wgpuDevicePushErrorScope(device,WGPUErrorFilter_Validation);
        WGPUBuffer probe=wgpuDeviceCreateBuffer(device,&(WGPUBufferDescriptor){.size=4,.usage=WGPUBufferUsage_CopyDst});
        wgpuDevicePopErrorScope(device,(WGPUPopErrorScopeCallbackInfo){.mode=WGPUCallbackMode_AllowSpontaneous,.callback=doc_wgpu_loss_probe,.userdata1=&proof});
        doc_wgpu_wait_retirement(instance,device,&proof.done,0,"device invalidation probe");
        if(probe)wgpuBufferRelease(probe);
        if(!proof.proof&&!atomic_load(lost)){
            fprintf(stderr,"DOC11_WGPU_DESTROY_UNVERIFIED: provider did not confirm invalidation; fail-stop\n");_Exit(1);
        }
        /* A validated invalid-device result changes our own admission state.
         * It is not a fabricated WebGPU device-lost callback. */
        if(proof.proof){atomic_store(fault,1);atomic_store(lost,1);}
    }
    fprintf(stderr,"DOC11_WGPU_DESTROY_CONFIRMED: provider invalidation after queue retirement\n");
}
#endif
