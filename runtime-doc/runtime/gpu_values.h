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
/* A grid-stride shader covers every admitted lane. Derive dispatch extent
 * from the actual workload and negotiated device limit; no application hint,
 * benchmark cap, device model or fixed total worker count. */
static size_t gpu_groups(size_t count){size_t groups=count/64+(count%64!=0);return groups<gpu_limits.maxComputeWorkgroupsPerDimension?groups:gpu_limits.maxComputeWorkgroupsPerDimension;}
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
static void gpu_wait(_Atomic int *done,int poll_device){struct timespec interval={0,50000},start,now;if(clock_gettime(CLOCK_MONOTONIC,&start))_Exit(1);while(!atomic_load(done)){if(clock_gettime(CLOCK_MONOTONIC,&now))_Exit(1);if(now.tv_sec-start.tv_sec>=30){fprintf(stderr,"DOC11_GPU_TIMEOUT: callback did not complete\n");_Exit(1);}if(poll_device)wgpuDevicePoll(gpu_device,0,NULL);wgpuInstanceProcessEvents(gpu_instance);if(!atomic_load(done)){nanosleep(&interval,NULL);if(interval.tv_nsec<1000000){interval.tv_nsec*=2;if(interval.tv_nsec>1000000)interval.tv_nsec=1000000;}}}}
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
static void gpu_close(void){if(!gpu_submission_retired&&gpu_queue&&gpu_device){doc_wgpu_retire_queue(gpu_instance,gpu_device,gpu_queue,0);gpu_submission_retired=1;}gpu_buffers_close();if(gpu_layout)wgpuBindGroupLayoutRelease(gpu_layout);if(gpu_pipeline)wgpuComputePipelineRelease(gpu_pipeline);if(gpu_queue)wgpuQueueRelease(gpu_queue);if(gpu_device)wgpuDeviceRelease(gpu_device);if(gpu_adapter)wgpuAdapterRelease(gpu_adapter);if(gpu_instance)wgpuInstanceRelease(gpu_instance);gpu_layout=NULL;gpu_pipeline=NULL;gpu_queue=NULL;gpu_device=NULL;gpu_adapter=NULL;gpu_instance=NULL;}
static int gpu_open(size_t n){uint64_t begin=gpu_wall_ns();if(gpu_instance||gpu_device||gpu_queue||gpu_pool_metrics.live||n!=sizeof(doc_gpu_bound)/sizeof(doc_gpu_bound[0])||n!=sizeof(doc_gpu_family)/sizeof(doc_gpu_family[0]))return 0;gpu_pool_metrics=(GPUBufferMetrics){0};gpu_dispatches=0;gpu_submission_retired=1;atomic_store(&gpu_fault,0);atomic_store(&gpu_device_lost,0);gpu_instance=wgpuCreateInstance(NULL);if(!gpu_instance)return 0;GPURequest req={0};WGPURequestAdapterOptions opts={.featureLevel=WGPUFeatureLevel_Core,.powerPreference=WGPUPowerPreference_HighPerformance};wgpuInstanceRequestAdapter(gpu_instance,&opts,(WGPURequestAdapterCallbackInfo){.mode=WGPUCallbackMode_AllowSpontaneous,.callback=got_adapter,.userdata1=&req});gpu_wait(&req.done,0);gpu_adapter=req.adapter;if(!gpu_adapter)return 0;WGPUAdapterInfo info={0};if(wgpuAdapterGetInfo(gpu_adapter,&info)!=WGPUStatus_Success)return 0;int physical=info.adapterType==WGPUAdapterType_DiscreteGPU||info.adapterType==WGPUAdapterType_IntegratedGPU;fprintf(stderr,"DOC11_GPU_ADAPTER: type=%u backend=%u physical=%d description=%.*s\n",(unsigned)info.adapterType,(unsigned)info.backendType,physical,(int)info.description.length,info.description.data);wgpuAdapterInfoFreeMembers(info);if(!physical&&(getenv("DOC_REQUIRE_PHYSICAL_GPU")||!getenv("DOC_GPU_ALLOW_SOFTWARE")||strcmp(getenv("DOC_GPU_ALLOW_SOFTWARE"),"1")))return 0;
    atomic_store(&req.done,0);WGPUDeviceDescriptor desc={.deviceLostCallbackInfo={.mode=WGPUCallbackMode_AllowSpontaneous,.callback=gpu_lost},.uncapturedErrorCallbackInfo={.callback=gpu_error}};wgpuAdapterRequestDevice(gpu_adapter,&desc,(WGPURequestDeviceCallbackInfo){.mode=WGPUCallbackMode_AllowSpontaneous,.callback=got_device,.userdata1=&req});gpu_wait(&req.done,0);gpu_device=req.device;if(!gpu_device)return 0;gpu_queue=wgpuDeviceGetQueue(gpu_device);if(!gpu_queue||wgpuDeviceGetLimits(gpu_device,&gpu_limits)!=WGPUStatus_Success)return 0;if(gpu_limits.maxStorageBuffersPerShaderStage<3||gpu_limits.maxComputeInvocationsPerWorkgroup<64||gpu_limits.maxComputeWorkgroupSizeX<64)return 0;
    fprintf(stderr,"DOC9_LIMITS: wg_invocations=%u wg_x=%u groups=%u storage=%llu buffer=%llu\n",gpu_limits.maxComputeInvocationsPerWorkgroup,gpu_limits.maxComputeWorkgroupSizeX,gpu_limits.maxComputeWorkgroupsPerDimension,(unsigned long long)gpu_limits.maxStorageBufferBindingSize,(unsigned long long)gpu_limits.maxBufferSize);WGPUShaderSourceWGSL source={.chain={.sType=WGPUSType_ShaderSourceWGSL},.code={doc_wgsl,WGPU_STRLEN}};WGPUShaderModule module=wgpuDeviceCreateShaderModule(gpu_device,&(WGPUShaderModuleDescriptor){.nextInChain=&source.chain});if(!module)return 0;gpu_pipeline=wgpuDeviceCreateComputePipeline(gpu_device,&(WGPUComputePipelineDescriptor){.compute={.module=module,.entryPoint={"main",WGPU_STRLEN}}});wgpuShaderModuleRelease(module);if(!gpu_pipeline)return 0;gpu_layout=wgpuComputePipelineGetBindGroupLayout(gpu_pipeline,0);int ok=gpu_layout&&!atomic_load(&gpu_fault);if(ok){uint64_t end=gpu_wall_ns();fprintf(stderr,"DOC11_GPU_OPEN_TIMING: wall_ns=%llu\n",(unsigned long long)(begin&&end>=begin?end-begin:0));}return ok;}
static int gpu_value_fits(int64_t x,int64_t bound){return x>=-bound&&x<=bound&&x>=INT32_MIN&&x<=INT32_MAX;}
/* All family inputs remain immutable through the frontier. Admission uses
 * actual list extent and the compiler-emitted lexical family source. */
static int gpu_eligible(Epoch *e,size_t id){
    if(id>=e->n||id>=sizeof(doc_gpu_family)/sizeof(doc_gpu_family[0]))return 0;
    int64_t bound=doc_gpu_bound[id];int32_t family=doc_gpu_family[id];
    if(bound<0||family< -1||(family>=0&&(size_t)family>=e->n))return 0;
    const State *s=e->states+id;int found=0;
    if(family>=0?s->kind!=L:(s->kind!=I&&s->kind!=B))return 0;
    for(size_t j=0;j<s->ndeps;j++){
        size_t dep=s->deps[j];if(dep>=e->n||!e->have[dep]||e->dirty[dep])return 0;
        V v=*e->states[dep].slot;
        if(family>=0&&dep==(size_t)family){
            if(v.kind!=L||v.n>DOC_FAMILY_LIMIT||(v.n&&!v.p)||e->n>UINT32_MAX-v.n)return 0;
            uint64_t bytes=((uint64_t)e->n+v.n)*4,out=(uint64_t)v.n*8;
            if(bytes>gpu_limits.maxStorageBufferBindingSize||out>gpu_limits.maxStorageBufferBindingSize||bytes>gpu_limits.maxBufferSize||out>gpu_limits.maxBufferSize||(v.n&&!gpu_groups(v.n)))return 0;
            const int64_t *xs=v.p;for(size_t i=0;i<v.n;i++)if(!gpu_value_fits(xs[i],bound))return 0;found=1;
        }else if((v.kind!=I&&v.kind!=B)||!gpu_value_fits(v.x,bound)||(v.kind==B&&(v.x<0||v.x>1)))return 0;
    }
    return family<0||found;
}
static size_t gpu_lane_count(Epoch *e,size_t id){int32_t f=doc_gpu_family[id];return f<0?1:e->states[f].slot->n;}
static void gpu_mapped(WGPUMapAsyncStatus status,WGPUStringView m,void *ctx,void *b){(void)m;(void)b;atomic_store((_Atomic int*)ctx,status==WGPUMapAsyncStatus_Success?1:-1);}
/* The pinned native provider delivers lost errors via actual operation
 * failure. An error callback is not itself proof of queue retirement.
 * An explicit destroy registers completion before invalidating the device. */
static void gpu_destroy_verified(void){
    doc_wgpu_destroy_and_retire(gpu_instance,gpu_device,gpu_queue,&gpu_device_lost,&gpu_fault);
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
    int grow_input=states>gpu_cached_states,grow_lanes=count>gpu_capacity;
    if(!grow_input&&!grow_lanes){
        fprintf(stderr,"DOC11_GPU_BUFFER_POOL: action=reused capacity=%zu lanes=%zu\n",gpu_capacity,count);
        gpu_pool_log("reused");return 1;
    }
    WGPUBuffer input=NULL,selection=NULL,output=NULL,staging=NULL;
    if(grow_input)input=gpu_buffer((uint64_t)states*4,WGPUBufferUsage_Storage|WGPUBufferUsage_CopyDst);
    if(grow_lanes){
        selection=gpu_buffer((uint64_t)count*4,WGPUBufferUsage_Storage|WGPUBufferUsage_CopyDst);
        output=gpu_buffer((uint64_t)count*8,WGPUBufferUsage_Storage|WGPUBufferUsage_CopySrc|WGPUBufferUsage_CopyDst);
        staging=gpu_buffer((uint64_t)count*8,WGPUBufferUsage_MapRead|WGPUBufferUsage_CopyDst);
    }
    if((grow_input&&!input)||(grow_lanes&&(!selection||!output||!staging))||!gpu_healthy()){
        if(input)wgpuBufferRelease(input);if(selection)wgpuBufferRelease(selection);
        if(output)wgpuBufferRelease(output);if(staging)wgpuBufferRelease(staging);return 0;
    }
    /* Admit new capacity before releasing old; both input and output may
     * grow, and all previous submissions are retired before this call. */
    const char *action=gpu_capacity?"grown":"created";
    gpu_pool_admit((grow_input?(uint64_t)states*4:0)+(grow_lanes?(uint64_t)count*20:0));
    if(grow_input){if(gpu_cached_input)wgpuBufferRelease(gpu_cached_input);
        gpu_pool_release((uint64_t)gpu_cached_states*4);gpu_cached_input=input;gpu_cached_states=states;}
    if(grow_lanes){
        if(gpu_cached_staging)wgpuBufferRelease(gpu_cached_staging);if(gpu_cached_output)wgpuBufferRelease(gpu_cached_output);if(gpu_cached_selection)wgpuBufferRelease(gpu_cached_selection);
        gpu_pool_release((uint64_t)gpu_capacity*20);
        gpu_cached_selection=selection;gpu_cached_output=output;gpu_cached_staging=staging;gpu_capacity=count;
    }
    fprintf(stderr,"DOC11_GPU_BUFFER_POOL: action=%s capacity=%zu lanes=%zu\n",action,gpu_capacity,count);
    gpu_pool_log(action);return 1;
}
static int store_value(Region *,V *,V);
static int gpu_dispatch(Epoch *e,const size_t *ids,size_t count,size_t family){int family_mode=family<e->n;int64_t *family_values=NULL;uint64_t begin=gpu_wall_ns();const char *phase="preflight";int ok=0,mapped=0,submitted=0;uint32_t *in=NULL,*queue=NULL;WGPUBuffer input=NULL,selection=NULL,output=NULL,staging=NULL;WGPUBindGroup group=NULL;WGPUCommandEncoder encoder=NULL;WGPUComputePassEncoder pass=NULL;WGPUCommandBuffer command=NULL;if(!count)return 1;if(!gpu_device||atomic_load(&gpu_fault)||e->n>UINT32_MAX||(!family_mode&&count>e->n)||count>UINT32_MAX||(family_mode&&count>UINT32_MAX-e->n))return 0;size_t input_words=e->n+(family_mode?count:0);uint64_t in_bytes=(uint64_t)input_words*4,selection_bytes=(uint64_t)(family_mode?1:count)*4,out_bytes=(uint64_t)count*8;if(in_bytes>gpu_limits.maxStorageBufferBindingSize||out_bytes>gpu_limits.maxStorageBufferBindingSize||in_bytes>gpu_limits.maxBufferSize||out_bytes>gpu_limits.maxBufferSize||!gpu_groups(count))return 0;phase="host staging";in=calloc(input_words,sizeof(*in));queue=calloc(family_mode?1:count,sizeof(*queue));if(!in||!queue)goto done;
    if(family_mode){
        if(!gpu_eligible(e,family)||doc_gpu_family[family]<0||count!=gpu_lane_count(e,family))goto done;
        size_t dep=(size_t)doc_gpu_family[family];const int64_t *xs=e->states[dep].slot->p;
        queue[0]=(uint32_t)family;for(size_t i=0;i<count;i++)in[e->n+i]=(uint32_t)(int32_t)xs[i];
        const State *s=e->states+family;for(size_t j=0;j<s->ndeps;j++){size_t p=s->deps[j];if(p!=dep)in[p]=(uint32_t)(int32_t)e->states[p].slot->x;}
        family_values=malloc(count*sizeof(*family_values));if(!family_values)goto done;
    }else for(size_t i=0;i<count;i++){size_t id=ids[i];if(id>=e->n||!gpu_eligible(e,id)||doc_gpu_family[id]>=0){fprintf(stderr,"DOC11_GPU_REJECT: invalid selection index=%zu id=%zu\n",i,id);goto done;}queue[i]=(uint32_t)id;const State *s=e->states+id;for(size_t j=0;j<s->ndeps;j++){size_t p=s->deps[j];in[p]=(uint32_t)(int32_t)e->states[p].slot->x;}}
    phase="buffer reserve";if(!gpu_reserve(input_words,count))goto done;input=gpu_cached_input;selection=gpu_cached_selection;output=gpu_cached_output;staging=gpu_cached_staging;
    phase="bind/encode";WGPUBindGroupEntry entries[]={{.binding=0,.buffer=input,.size=in_bytes},{.binding=1,.buffer=selection,.size=selection_bytes},{.binding=2,.buffer=output,.size=out_bytes}};group=wgpuDeviceCreateBindGroup(gpu_device,&(WGPUBindGroupDescriptor){.layout=gpu_layout,.entryCount=3,.entries=entries});encoder=wgpuDeviceCreateCommandEncoder(gpu_device,NULL);if(!group||!encoder||atomic_load(&gpu_fault))goto done;/* A previous dispatch marker must never validate missing new output. */wgpuCommandEncoderClearBuffer(encoder,output,0,out_bytes);if(!gpu_healthy())goto done;pass=wgpuCommandEncoderBeginComputePass(encoder,NULL);if(!pass)goto done;wgpuComputePassEncoderSetPipeline(pass,gpu_pipeline);wgpuComputePassEncoderSetBindGroup(pass,0,group,0,NULL);wgpuComputePassEncoderDispatchWorkgroups(pass,(uint32_t)(gpu_groups(count)),1,1);wgpuComputePassEncoderEnd(pass);wgpuComputePassEncoderRelease(pass);pass=NULL;wgpuCommandEncoderCopyBufferToBuffer(encoder,output,0,staging,0,out_bytes);command=wgpuCommandEncoderFinish(encoder,NULL);if(!command||atomic_load(&gpu_fault))goto done;
    phase="submit/map";wgpuQueueWriteBuffer(gpu_queue,input,0,in,(size_t)in_bytes);wgpuQueueWriteBuffer(gpu_queue,selection,0,queue,(size_t)selection_bytes);gpu_submission_retired=0;wgpuQueueSubmit(gpu_queue,1,&command);submitted=1;
#ifdef DOC_GPU_TEST_SUBMIT_HOOK
    if(gpu_test_after_submit&&!gpu_test_after_submit(e))goto done;
#endif
    if(atomic_load(&gpu_device_lost))goto done;_Atomic int map=0;wgpuBufferMapAsync(staging,WGPUMapMode_Read,0,(size_t)out_bytes,(WGPUBufferMapCallbackInfo){.mode=WGPUCallbackMode_AllowSpontaneous,.callback=gpu_mapped,.userdata1=&map});gpu_wait(&map,1);if(atomic_load(&map)!=1)goto done;mapped=1;if(!gpu_healthy())goto done;phase="readback";const uint32_t *result=wgpuBufferGetConstMappedRange(staging,0,(size_t)out_bytes);if(!result)goto done;size_t invalid=0;for(size_t i=0;i<count;i++){size_t id=family_mode?family:ids[i];uint32_t word=result[2*i];if(result[2*i+1]!=UINT32_C(0xd0c11a5e)||(e->states[id].kind==B&&word>1)){if(invalid<16)fprintf(stderr,"DOC11_GPU_REJECT: readback index=%zu id=%zu value=%08x marker=%08x\n",i,id,word,result[2*i+1]);invalid++;}}if(invalid){fprintf(stderr,"DOC11_GPU_REJECT: invalid_readback_lanes=%zu total=%zu\n",invalid,count);goto done;}for(size_t i=0;i<count;i++){size_t id=family_mode?family:ids[i];uint32_t word=result[2*i];int64_t x=word<=INT32_MAX?(int64_t)word:(int64_t)word-4294967296LL;if(family_mode)family_values[i]=x;else e->cell[id].result=e->states[id].kind==B?vb((int)x):vi(x);}
    if(family_mode&&!store_value(&e->cell[family].candidate,&e->cell[family].result,vv(L,count,family_values)))goto done;
    if(family_mode)fprintf(stderr,"DOC11_GPU_FAMILY: state=%zu lanes=%zu\n",family,count);
    gpu_dispatches++;fprintf(stderr,"DOC11_GPU_DISPATCH: lanes=%zu workgroups=%zu\n",count,gpu_groups(count));uint64_t end=gpu_wall_ns();fprintf(stderr,"DOC11_GPU_DISPATCH_TIMING: dispatch=%zu wall_ns=%llu upload_bytes=%llu readback_bytes=%llu capacity=%zu\n",gpu_dispatches,(unsigned long long)(begin&&end>=begin?end-begin:0),(unsigned long long)(in_bytes+selection_bytes),(unsigned long long)out_bytes,gpu_capacity);const char *inject=getenv("DOC_GPU_TEST_FAIL_DISPATCH");if(inject){char *end;errno=0;unsigned long long at=strtoull(inject,&end,10);if(!errno&&*inject&&!*end&&at==gpu_dispatches){fprintf(stderr,"DOC11_GPU_INJECTED_FAILURE: dispatch=%zu\n",gpu_dispatches);goto done;}}ok=1;
done:if(!ok)fprintf(stderr,"DOC11_GPU_REJECT: phase=%s lanes=%zu device_fault=%d\n",phase,count,atomic_load(&gpu_fault));if(mapped){wgpuBufferUnmap(staging);gpu_submission_retired=1;}else if(submitted)gpu_retire_failed_submission();if(command)wgpuCommandBufferRelease(command);if(pass)wgpuComputePassEncoderRelease(pass);if(encoder)wgpuCommandEncoderRelease(encoder);if(group)wgpuBindGroupRelease(group);free(family_values);free(in);free(queue);return ok&&!atomic_load(&gpu_fault);}
/* Each list is dispatched as a separate lexical family. No list is copied
 * into a published cell before all selected states finish successfully. */
static int gpu_execute(Epoch *e,const size_t *ids,size_t count){
    if(!count)return 1;
    size_t *scalars=malloc(count*sizeof(*scalars));if(!scalars)return 0;size_t n=0;int ok=1;
    for(size_t i=0;i<count;i++){size_t id=ids[i];if(!gpu_eligible(e,id)){ok=0;break;}if(doc_gpu_family[id]<0)scalars[n++]=id;}
    if(ok&&n)ok=gpu_dispatch(e,scalars,n,e->n);
    for(size_t i=0;ok&&i<count;i++){
        size_t id=ids[i];if(atomic_load(&e->cancelled)){ok=0;break;}if(doc_gpu_family[id]<0)continue;
        size_t lanes=gpu_lane_count(e,id);
        if(lanes)ok=gpu_dispatch(e,NULL,lanes,id);else e->cell[id].result=vv(L,0,NULL);
    }
    free(scalars);return ok;
}
#else
static int gpu_mode;
static int gpu_healthy(void){return 1;}
static void gpu_close(void){}
static int gpu_open(size_t n){(void)n;return 0;}
static int gpu_eligible(Epoch *e,size_t id){(void)e;(void)id;return 0;}
static size_t gpu_lane_count(Epoch *e,size_t id){(void)e;(void)id;return 0;}
static int gpu_execute(Epoch *e,const size_t *ids,size_t count){(void)e;(void)ids;return !count;}
#endif
#endif
