#ifndef DOC_WEBGPU_RETIREMENT_H
#define DOC_WEBGPU_RETIREMENT_H
#include <webgpu/wgpu.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
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
static void doc_wgpu_destroy_and_retire(WGPUInstance instance,WGPUDevice device,WGPUQueue queue,_Atomic int *lost){
    doc_wgpu_retire_queue(instance,device,queue,1);
    /* wgpu-native v27 routes invalid-device errors through its error sink.
     * After real destruction and queue drain, use a valid minimal descriptor
     * to elicit that real device-lost callback if it has not already arrived.
     * Never set the loss flag ourselves, never map or use the probe buffer. */
    if(!atomic_load(lost)){
        WGPUBuffer probe=wgpuDeviceCreateBuffer(device,&(WGPUBufferDescriptor){.size=4,.usage=WGPUBufferUsage_CopyDst});
        if(probe)wgpuBufferRelease(probe);
    }
    doc_wgpu_wait_retirement(instance,device,lost,0,"device loss");
    fprintf(stderr,"DOC11_WGPU_DESTROY_CONFIRMED: actual loss callback after queue retirement\n");
}
#endif
