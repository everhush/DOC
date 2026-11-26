#ifndef DOC_GPU_VALUES_H
#define DOC_GPU_VALUES_H
/* WebGPU C ABI substrate. Typed eligibility, bounds and shader operations
 * are emitted by the DOC compiler; no CPU interpreter or shader substitute. */
#ifdef DOC_ENABLE_GPU
#include <webgpu/wgpu.h>
#include <time.h>
#include <stdatomic.h>
#include "gpu_generated.h"
#include "gpu_pool_metrics.h"
#include "webgpu_retirement.h"
static WGPUInstance gpu_instance;
static WGPUAdapter gpu_adapter;
static WGPUDevice gpu_device;
static WGPUQueue gpu_queue;
static WGPUComputePipeline gpu_pipeline;
static WGPUBindGroupLayout gpu_layout;
static WGPULimits gpu_limits;
/* Device-owned pool: prior map completion and unmap precede reuse. */
static WGPUBuffer gpu_cached_input,gpu_cached_selection,gpu_cached_output,gpu_cached_staging;
static size_t gpu_cached_states,gpu_capacity;
static GPUBufferMetrics gpu_pool_metrics;
static void gpu_pool_admit(uint64_t n){if(!gpu_metric_admit(&gpu_pool_metrics,n))_Exit(1);}
static void gpu_pool_release(uint64_t n){if(!gpu_metric_release(&gpu_pool_metrics,n))_Exit(1);}
static void gpu_pool_log(const char *event){
    GPUBufferMetrics *m=&gpu_pool_metrics;
    fprintf(stderr,"DOC11_GPU_POOL_METRICS: event=%s admitted=%llu released=%llu live=%llu peak=%llu\n",event,(unsigned long long)m->admitted,(unsigned long long)m->released,(unsigned long long)m->live,(unsigned long long)m->peak);
}
static _Atomic int gpu_fault, gpu_device_lost;
static int gpu_submission_retired;
static int gpu_healthy(void){return !atomic_load(&gpu_fault);}
static size_t gpu_dispatches;
static uint64_t gpu_wall_ns(void){struct timespec t;if(clock_gettime(CLOCK_MONOTONIC,&t))return 0;return (uint64_t)t.tv_sec*UINT64_C(1000000000)+(uint64_t)t.tv_nsec;}
static int gpu_mode; /* 0 CPU, 1 explicit GPU, 2 automatic */
static void gpu_error(WGPUDevice const *d,WGPUErrorType t,WGPUStringView m,void *a,void *b){(void)d;(void)t;(void)a;(void)b;atomic_store(&gpu_fault,1);fprintf(stderr,"DOC11_GPU_ERROR: %.*s\n",(int)(m.data?(m.length==WGPU_STRLEN?strlen(m.data):m.length):0),m.data?m.data:"");}
static void gpu_lost(WGPUDevice const *d,WGPUDeviceLostReason t,WGPUStringView m,void *a,void *b){(void)d;(void)m;(void)a;(void)b;atomic_store(&gpu_fault,1);atomic_store(&gpu_device_lost,1);fprintf(stderr,"DOC11_GPU_LOST_CALLBACK: reason=%u\n",(unsigned)t);}
typedef struct {_Atomic int done;WGPUAdapter adapter;WGPUDevice device;} GPURequest;
static void got_adapter(WGPURequestAdapterStatus status,WGPUAdapter a,WGPUStringView m,void *ctx,void *b){(void)m;(void)b;GPURequest *r=ctx;if(status==WGPURequestAdapterStatus_Success)r->adapter=a;atomic_store(&r->done,1);}
static void got_device(WGPURequestDeviceStatus status,WGPUDevice d,WGPUStringView m,void *ctx,void *b){(void)m;(void)b;GPURequest *r=ctx;if(status==WGPURequestDeviceStatus_Success)r->device=d;atomic_store(&r->done,1);}
static void gpu_wait(_Atomic int *done,int poll_device){struct timespec interval={0,1000000},start,now;if(clock_gettime(CLOCK_MONOTONIC,&start))_Exit(1);while(!atomic_load(done)){if(clock_gettime(CLOCK_MONOTONIC,&now))_Exit(1);if(now.tv_sec-start.tv_sec>=30){fprintf(stderr,"DOC11_GPU_TIMEOUT: callback did not complete\n");_Exit(1);}if(poll_device)wgpuDevicePoll(gpu_device,0,NULL);wgpuInstanceProcessEvents(gpu_instance);nanosleep(&interval,NULL);}}
static void gpu_buffers_close(void){
    if(gpu_cached_staging)wgpuBufferRelease(gpu_cached_staging);
    if(gpu_cached_output)wgpuBufferRelease(gpu_cached_output);
    if(gpu_cached_selection)wgpuBufferRelease(gpu_cached_selection);
    if(gpu_cached_input)wgpuBufferRelease(gpu_cached_input);
    gpu_pool_release((uint64_t)gpu_cached_states*4+(uint64_t)gpu_capacity*20);
    gpu_cached_input=gpu_cached_selection=gpu_cached_output=gpu_cached_staging=NULL;
    gpu_cached_states=gpu_capacity=0;
    if(gpu_pool_metrics.admitted)gpu_pool_log("closed");
}
static void gpu_close(void){gpu_buffers_close();if(gpu_layout)wgpuBindGroupLayoutRelease(gpu_layout);if(gpu_pipeline)wgpuComputePipelineRelease(gpu_pipeline);if(gpu_queue)wgpuQueueRelease(gpu_queue);if(gpu_device)wgpuDeviceRelease(gpu_device);if(gpu_adapter)wgpuAdapterRelease(gpu_adapter);if(gpu_instance)wgpuInstanceRelease(gpu_instance);gpu_layout=NULL;gpu_pipeline=NULL;gpu_queue=NULL;gpu_device=NULL;gpu_adapter=NULL;gpu_instance=NULL;}
static int gpu_open(size_t n){uint64_t begin=gpu_wall_ns();if(n!=sizeof(doc_gpu_bound)/sizeof(doc_gpu_bound[0]))return 0;gpu_instance=wgpuCreateInstance(NULL);if(!gpu_instance)return 0;GPURequest req={0};WGPURequestAdapterOptions opts={.featureLevel=WGPUFeatureLevel_Core,.powerPreference=WGPUPowerPreference_HighPerformance};wgpuInstanceRequestAdapter(gpu_instance,&opts,(WGPURequestAdapterCallbackInfo){.mode=WGPUCallbackMode_AllowSpontaneous,.callback=got_adapter,.userdata1=&req});gpu_wait(&req.done,0);gpu_adapter=req.adapter;if(!gpu_adapter)return 0;WGPUAdapterInfo info={0};if(wgpuAdapterGetInfo(gpu_adapter,&info)!=WGPUStatus_Success)return 0;int physical=info.adapterType==WGPUAdapterType_DiscreteGPU||info.adapterType==WGPUAdapterType_IntegratedGPU;fprintf(stderr,"DOC11_GPU_ADAPTER: type=%u backend=%u physical=%d description=%.*s\n",(unsigned)info.adapterType,(unsigned)info.backendType,physical,(int)info.description.length,info.description.data);wgpuAdapterInfoFreeMembers(info);if(!physical&&(getenv("DOC_REQUIRE_PHYSICAL_GPU")||!getenv("DOC_GPU_ALLOW_SOFTWARE")||strcmp(getenv("DOC_GPU_ALLOW_SOFTWARE"),"1")))return 0;
    atomic_store(&req.done,0);WGPUDeviceDescriptor desc={.deviceLostCallbackInfo={.mode=WGPUCallbackMode_AllowSpontaneous,.callback=gpu_lost},.uncapturedErrorCallbackInfo={.callback=gpu_error}};wgpuAdapterRequestDevice(gpu_adapter,&desc,(WGPURequestDeviceCallbackInfo){.mode=WGPUCallbackMode_AllowSpontaneous,.callback=got_device,.userdata1=&req});gpu_wait(&req.done,0);gpu_device=req.device;if(!gpu_device)return 0;gpu_queue=wgpuDeviceGetQueue(gpu_device);if(!gpu_queue||wgpuDeviceGetLimits(gpu_device,&gpu_limits)!=WGPUStatus_Success)return 0;if(gpu_limits.maxStorageBuffersPerShaderStage<3||gpu_limits.maxComputeInvocationsPerWorkgroup<64||gpu_limits.maxComputeWorkgroupSizeX<64)return 0;
    WGPUShaderSourceWGSL source={.chain={.sType=WGPUSType_ShaderSourceWGSL},.code={doc_wgsl,WGPU_STRLEN}};WGPUShaderModule module=wgpuDeviceCreateShaderModule(gpu_device,&(WGPUShaderModuleDescriptor){.nextInChain=&source.chain});if(!module)return 0;gpu_pipeline=wgpuDeviceCreateComputePipeline(gpu_device,&(WGPUComputePipelineDescriptor){.compute={.module=module,.entryPoint={"main",WGPU_STRLEN}}});wgpuShaderModuleRelease(module);if(!gpu_pipeline)return 0;gpu_layout=wgpuComputePipelineGetBindGroupLayout(gpu_pipeline,0);int ok=gpu_layout&&!atomic_load(&gpu_fault);if(ok){uint64_t end=gpu_wall_ns();fprintf(stderr,"DOC11_GPU_OPEN_TIMING: wall_ns=%llu\n",(unsigned long long)(begin&&end>=begin?end-begin:0));}return ok;}
static int gpu_eligible(Epoch *e,size_t id){int64_t bound=doc_gpu_bound[id];if(bound<0)return 0;const State *s=e->states+id;for(size_t j=0;j<s->ndeps;j++){size_t dep=s->deps[j];if(!e->have[dep]||e->dirty[dep])return 0;V v=*e->states[dep].slot;if(v.kind!=I&&v.kind!=B)return 0;if(v.x< -bound||v.x>bound||v.x<INT32_MIN||v.x>INT32_MAX)return 0;if(v.kind==B&&(v.x<0||v.x>1))return 0;}return 1;}
static void gpu_mapped(WGPUMapAsyncStatus status,WGPUStringView m,void *ctx,void *b){(void)m;(void)b;atomic_store((_Atomic int*)ctx,status==WGPUMapAsyncStatus_Success?1:-1);}
/* The pinned native provider delivers lost errors via actual operation
 * failure. An error callback is not itself proof of queue retirement.
 * An explicit destroy registers completion before invalidating the device. */
static void gpu_destroy_verified(void){
    doc_wgpu_destroy_and_retire(gpu_instance,gpu_device,gpu_queue,&gpu_device_lost);
    gpu_submission_retired=1;
}
static void gpu_retire_failed_submission(void){
    if(!gpu_submission_retired){
        doc_wgpu_retire_queue(gpu_instance,gpu_device,gpu_queue,0);
        gpu_submission_retired=1;
    }
    fprintf(stderr,"DOC11_GPU_RETIRED: outcome=%s\n",atomic_load(&gpu_device_lost)?"device-lost":"queue-complete");
}
#ifdef DOC_GPU_TEST_SUBMIT_HOOK
/* Only present in the separately built adverse-interleaving test executable. */
static int (*gpu_test_after_submit)(Epoch *);
#endif
static WGPUBuffer gpu_buffer(uint64_t size,WGPUBufferUsage usage){return wgpuDeviceCreateBuffer(gpu_device,&(WGPUBufferDescriptor){.size=size,.usage=usage});}
static int gpu_reserve(size_t states,size_t count){
    if(!gpu_cached_input){
        WGPUBuffer candidate=gpu_buffer((uint64_t)states*4,WGPUBufferUsage_Storage|WGPUBufferUsage_CopyDst);
        if(!candidate||!gpu_healthy()){if(candidate)wgpuBufferRelease(candidate);return 0;}
        gpu_pool_admit((uint64_t)states*4);gpu_cached_input=candidate;gpu_cached_states=states;
    }
    if(gpu_cached_states!=states)return 0;
    if(gpu_capacity>=count){
        fprintf(stderr,"DOC11_GPU_BUFFER_POOL: action=reused capacity=%zu lanes=%zu\n",gpu_capacity,count);
        gpu_pool_log("reused");return 1;
    }
    WGPUBuffer selection=gpu_buffer((uint64_t)count*4,WGPUBufferUsage_Storage|WGPUBufferUsage_CopyDst);
    WGPUBuffer output=gpu_buffer((uint64_t)count*8,WGPUBufferUsage_Storage|WGPUBufferUsage_CopySrc|WGPUBufferUsage_CopyDst);
    WGPUBuffer staging=gpu_buffer((uint64_t)count*8,WGPUBufferUsage_MapRead|WGPUBufferUsage_CopyDst);
    if(!selection||!output||!staging||!gpu_healthy()){
        if(staging)wgpuBufferRelease(staging);
        if(output)wgpuBufferRelease(output);
        if(selection)wgpuBufferRelease(selection);
        return 0;
    }
    /* Count the overlap of admitted old and new handles before retiring
     * the previous capacity. A prior successful map or failed-submit
     * retirement acknowledgement precedes any reuse or growth. */
    gpu_pool_admit((uint64_t)count*20);
    if(gpu_cached_staging)wgpuBufferRelease(gpu_cached_staging);
    if(gpu_cached_output)wgpuBufferRelease(gpu_cached_output);
    if(gpu_cached_selection)wgpuBufferRelease(gpu_cached_selection);
    const char *action=gpu_capacity?"grown":"created";gpu_pool_release((uint64_t)gpu_capacity*20);
    gpu_cached_selection=selection;gpu_cached_output=output;gpu_cached_staging=staging;gpu_capacity=count;
    fprintf(stderr,"DOC11_GPU_BUFFER_POOL: action=%s capacity=%zu lanes=%zu\n",action,gpu_capacity,count);
    gpu_pool_log(action);return 1;
}
static int gpu_execute(Epoch *e,const size_t *ids,size_t count){uint64_t begin=gpu_wall_ns();const char *phase="preflight";int ok=0,mapped=0,submitted=0;uint32_t *in=NULL,*queue=NULL;WGPUBuffer input=NULL,selection=NULL,output=NULL,staging=NULL;WGPUBindGroup group=NULL;WGPUCommandEncoder encoder=NULL;WGPUComputePassEncoder pass=NULL;WGPUCommandBuffer command=NULL;if(!count)return 1;if(!gpu_device||atomic_load(&gpu_fault)||e->n>UINT32_MAX||count>e->n||count>UINT32_MAX)return 0;uint64_t in_bytes=(uint64_t)e->n*4,selection_bytes=(uint64_t)count*4,out_bytes=(uint64_t)count*8;if(in_bytes>gpu_limits.maxStorageBufferBindingSize||out_bytes>gpu_limits.maxStorageBufferBindingSize||in_bytes>gpu_limits.maxBufferSize||out_bytes>gpu_limits.maxBufferSize||(count+63)/64>gpu_limits.maxComputeWorkgroupsPerDimension)return 0;phase="host staging";in=calloc(e->n,sizeof(*in));queue=calloc(count,sizeof(*queue));if(!in||!queue)goto done;for(size_t i=0;i<count;i++){size_t id=ids[i];if(id>=e->n||!gpu_eligible(e,id)){fprintf(stderr,"DOC11_GPU_REJECT: invalid selection index=%zu id=%zu\n",i,id);goto done;}queue[i]=(uint32_t)id;const State *s=e->states+id;for(size_t j=0;j<s->ndeps;j++){size_t p=s->deps[j];in[p]=(uint32_t)(int32_t)e->states[p].slot->x;}}
    phase="buffer reserve";if(!gpu_reserve(e->n,count))goto done;input=gpu_cached_input;selection=gpu_cached_selection;output=gpu_cached_output;staging=gpu_cached_staging;
    phase="bind/encode";WGPUBindGroupEntry entries[]={{.binding=0,.buffer=input,.size=in_bytes},{.binding=1,.buffer=selection,.size=selection_bytes},{.binding=2,.buffer=output,.size=out_bytes}};group=wgpuDeviceCreateBindGroup(gpu_device,&(WGPUBindGroupDescriptor){.layout=gpu_layout,.entryCount=3,.entries=entries});encoder=wgpuDeviceCreateCommandEncoder(gpu_device,NULL);if(!group||!encoder||atomic_load(&gpu_fault))goto done;/* A previous dispatch marker must never validate missing new output. */wgpuCommandEncoderClearBuffer(encoder,output,0,out_bytes);if(!gpu_healthy())goto done;pass=wgpuCommandEncoderBeginComputePass(encoder,NULL);if(!pass)goto done;wgpuComputePassEncoderSetPipeline(pass,gpu_pipeline);wgpuComputePassEncoderSetBindGroup(pass,0,group,0,NULL);wgpuComputePassEncoderDispatchWorkgroups(pass,(uint32_t)((count+63)/64),1,1);wgpuComputePassEncoderEnd(pass);wgpuComputePassEncoderRelease(pass);pass=NULL;wgpuCommandEncoderCopyBufferToBuffer(encoder,output,0,staging,0,out_bytes);command=wgpuCommandEncoderFinish(encoder,NULL);if(!command||atomic_load(&gpu_fault))goto done;
    phase="submit/map";wgpuQueueWriteBuffer(gpu_queue,input,0,in,(size_t)in_bytes);wgpuQueueWriteBuffer(gpu_queue,selection,0,queue,(size_t)selection_bytes);gpu_submission_retired=0;wgpuQueueSubmit(gpu_queue,1,&command);submitted=1;
#ifdef DOC_GPU_TEST_SUBMIT_HOOK
    if(gpu_test_after_submit&&!gpu_test_after_submit(e))goto done;
#endif
    if(atomic_load(&gpu_device_lost))goto done;_Atomic int map=0;wgpuBufferMapAsync(staging,WGPUMapMode_Read,0,(size_t)out_bytes,(WGPUBufferMapCallbackInfo){.mode=WGPUCallbackMode_AllowSpontaneous,.callback=gpu_mapped,.userdata1=&map});gpu_wait(&map,1);if(atomic_load(&map)!=1)goto done;mapped=1;if(!gpu_healthy())goto done;phase="readback";const uint32_t *result=wgpuBufferGetConstMappedRange(staging,0,(size_t)out_bytes);if(!result)goto done;size_t invalid=0;for(size_t i=0;i<count;i++){size_t id=ids[i];uint32_t word=result[2*i];if(result[2*i+1]!=UINT32_C(0xd0c11a5e)||(e->states[id].kind==B&&word>1)){if(invalid<16)fprintf(stderr,"DOC11_GPU_REJECT: readback index=%zu id=%zu value=%08x marker=%08x\n",i,id,word,result[2*i+1]);invalid++;}}if(invalid){fprintf(stderr,"DOC11_GPU_REJECT: invalid_readback_lanes=%zu total=%zu\n",invalid,count);goto done;}for(size_t i=0;i<count;i++){size_t id=ids[i];uint32_t word=result[2*i];int64_t x=word<=INT32_MAX?(int64_t)word:(int64_t)word-4294967296LL;e->cell[id].result=e->states[id].kind==B?vb((int)x):vi(x);}gpu_dispatches++;fprintf(stderr,"DOC11_GPU_DISPATCH: lanes=%zu workgroups=%zu\n",count,(count+63)/64);uint64_t end=gpu_wall_ns();fprintf(stderr,"DOC11_GPU_DISPATCH_TIMING: dispatch=%zu wall_ns=%llu upload_bytes=%llu readback_bytes=%llu capacity=%zu\n",gpu_dispatches,(unsigned long long)(begin&&end>=begin?end-begin:0),(unsigned long long)(in_bytes+selection_bytes),(unsigned long long)out_bytes,gpu_capacity);const char *inject=getenv("DOC_GPU_TEST_FAIL_DISPATCH");if(inject){char *end;errno=0;unsigned long long at=strtoull(inject,&end,10);if(!errno&&*inject&&!*end&&at==gpu_dispatches){fprintf(stderr,"DOC11_GPU_INJECTED_FAILURE: dispatch=%zu\n",gpu_dispatches);goto done;}}ok=1;
done:if(!ok)fprintf(stderr,"DOC11_GPU_REJECT: phase=%s lanes=%zu device_fault=%d\n",phase,count,atomic_load(&gpu_fault));if(mapped)wgpuBufferUnmap(staging);else if(submitted)gpu_retire_failed_submission();if(command)wgpuCommandBufferRelease(command);if(pass)wgpuComputePassEncoderRelease(pass);if(encoder)wgpuCommandEncoderRelease(encoder);if(group)wgpuBindGroupRelease(group);free(in);free(queue);return ok&&!atomic_load(&gpu_fault);}
#else
static int gpu_mode;
static int gpu_healthy(void){return 1;}
static void gpu_close(void){}
static int gpu_open(size_t n){(void)n;return 0;}
static int gpu_eligible(Epoch *e,size_t id){(void)e;(void)id;return 0;}
static int gpu_execute(Epoch *e,const size_t *ids,size_t count){(void)e;(void)ids;return !count;}
#endif
#endif
