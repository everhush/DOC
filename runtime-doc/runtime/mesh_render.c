#define _POSIX_C_SOURCE 200809L
#include "mesh_packet.h"
#include <webgpu/wgpu.h>
#include <stdatomic.h>
#include <time.h>
/* Linux x86-64 platform adapter. All mesh and shader facts are supplied
 * by the admitted DOC compiler/frame transport, not evaluated here. */
#if !defined(__BYTE_ORDER__) || __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error unsupported native mesh byte order
#endif

typedef struct {
    WGPUInstance instance;WGPUAdapter adapter;WGPUDevice device;WGPUQueue queue;
    WGPUBindGroupLayout layout;WGPURenderPipeline pipeline;WGPULimits limits;
    _Atomic int fault,lost;
} MeshDevice;
typedef struct {_Atomic int done;WGPUAdapter adapter;WGPUDevice device;} Request;
static void got_adapter(WGPURequestAdapterStatus s,WGPUAdapter a,WGPUStringView msg,void *ctx,void *unused){(void)msg;(void)unused;Request *r=ctx;if(s==WGPURequestAdapterStatus_Success)r->adapter=a;atomic_store(&r->done,1);}
static void got_device(WGPURequestDeviceStatus s,WGPUDevice d,WGPUStringView msg,void *ctx,void *unused){(void)unused;Request *r=ctx;if(s==WGPURequestDeviceStatus_Success)r->device=d;else {size_t n=msg.data?(msg.length==WGPU_STRLEN?strlen(msg.data):msg.length):0;fprintf(stderr,"DOC11_MESH_DEVICE_REQUEST: status=%u message=%.*s\n",(unsigned)s,(int)(n>4096?4096:n),msg.data?msg.data:"");}atomic_store(&r->done,1);}
static void device_error(WGPUDevice const *d,WGPUErrorType t,WGPUStringView msg,void *ctx,void *unused){(void)d;(void)t;(void)unused;MeshDevice *g=ctx;atomic_store(&g->fault,1);size_t n=msg.data?(msg.length==WGPU_STRLEN?strlen(msg.data):msg.length):0;fprintf(stderr,"DOC11_MESH_DEVICE_ERROR: %.*s\n",(int)(n>4096?4096:n),msg.data?msg.data:"");}
static void device_lost(WGPUDevice const *d,WGPUDeviceLostReason t,WGPUStringView msg,void *ctx,void *unused){(void)d;(void)t;(void)msg;(void)unused;MeshDevice *g=ctx;atomic_store(&g->fault,1);atomic_store(&g->lost,1);}
static void mapped(WGPUMapAsyncStatus s,WGPUStringView msg,void *ctx,void *unused){(void)msg;(void)unused;atomic_store((_Atomic int*)ctx,s==WGPUMapAsyncStatus_Success?1:-1);}
static int healthy(MeshDevice *g){return !atomic_load(&g->fault);}
static void wait_callback(MeshDevice *g,_Atomic int *done,int poll){struct timespec start,now,pause={0,1000000};if(clock_gettime(CLOCK_MONOTONIC,&start))_Exit(1);while(!atomic_load(done)){if(clock_gettime(CLOCK_MONOTONIC,&now)||now.tv_sec-start.tv_sec>=30){fprintf(stderr,"DOC11_MESH_TIMEOUT: callback not completed; no pixel publication\n");_Exit(1);}if(poll)wgpuDevicePoll(g->device,0,NULL);wgpuInstanceProcessEvents(g->instance);nanosleep(&pause,NULL);}}
static void device_close(MeshDevice *g){if(g->pipeline)wgpuRenderPipelineRelease(g->pipeline);if(g->layout)wgpuBindGroupLayoutRelease(g->layout);if(g->queue)wgpuQueueRelease(g->queue);if(g->device)wgpuDeviceRelease(g->device);if(g->adapter)wgpuAdapterRelease(g->adapter);if(g->instance)wgpuInstanceRelease(g->instance);}
static int device_open(MeshDevice *g,const MeshBatch *b){
    atomic_init(&g->fault,0);atomic_init(&g->lost,0);g->instance=wgpuCreateInstance(NULL);if(!g->instance)return 0;
    Request req={0};WGPURequestAdapterOptions opts={.featureLevel=WGPUFeatureLevel_Core,.powerPreference=WGPUPowerPreference_HighPerformance};
    wgpuInstanceRequestAdapter(g->instance,&opts,(WGPURequestAdapterCallbackInfo){.mode=WGPUCallbackMode_AllowSpontaneous,.callback=got_adapter,.userdata1=&req});wait_callback(g,&req.done,0);g->adapter=req.adapter;if(!g->adapter)return 0;
    WGPUAdapterInfo info={0};if(wgpuAdapterGetInfo(g->adapter,&info)!=WGPUStatus_Success)return 0;
    int physical=info.adapterType==WGPUAdapterType_DiscreteGPU||info.adapterType==WGPUAdapterType_IntegratedGPU;size_t n=info.description.data?info.description.length:0;if(n==WGPU_STRLEN)n=strlen(info.description.data);fprintf(stderr,"DOC11_MESH_ADAPTER: physical=%d backend=%u description=%.*s\n",physical,(unsigned)info.backendType,(int)(n>4096?4096:n),info.description.data?info.description.data:"");wgpuAdapterInfoFreeMembers(info);
    const char *allow=getenv("DOC_GPU_ALLOW_SOFTWARE");if(!physical&&(getenv("DOC_REQUIRE_PHYSICAL_GPU")||!allow||strcmp(allow,"1"))){fprintf(stderr,"DOC11_MESH_REJECT: adapter admission\n");return 0;}
    atomic_store(&req.done,0);WGPUDeviceDescriptor desc={.deviceLostCallbackInfo={.mode=WGPUCallbackMode_AllowSpontaneous,.callback=device_lost,.userdata1=g},.uncapturedErrorCallbackInfo={.callback=device_error,.userdata1=g}};
    wgpuAdapterRequestDevice(g->adapter,&desc,(WGPURequestDeviceCallbackInfo){.mode=WGPUCallbackMode_AllowSpontaneous,.callback=got_device,.userdata1=&req});wait_callback(g,&req.done,0);g->device=req.device;if(!g->device){fprintf(stderr,"DOC11_MESH_REJECT: device request\n");return 0;}
    g->queue=wgpuDeviceGetQueue(g->device);if(!g->queue||wgpuDeviceGetLimits(g->device,&g->limits)!=WGPUStatus_Success){fprintf(stderr,"DOC11_MESH_REJECT: queue/limits query\n");return 0;}fprintf(stderr,"DOC11_MESH_LIMITS: attributes=%u vertex_buffers=%u stride=%u uniform_bytes=%llu uniforms=%u groups=%u colors=%u\n",(unsigned)g->limits.maxVertexAttributes,(unsigned)g->limits.maxVertexBuffers,(unsigned)g->limits.maxVertexBufferArrayStride,(unsigned long long)g->limits.maxUniformBufferBindingSize,(unsigned)g->limits.maxUniformBuffersPerShaderStage,(unsigned)g->limits.maxBindGroups,(unsigned)g->limits.maxColorAttachments);if(g->limits.maxVertexAttributes<3||g->limits.maxVertexBuffers<1||g->limits.maxVertexBufferArrayStride<48||g->limits.maxUniformBufferBindingSize<32||g->limits.maxUniformBuffersPerShaderStage<1||g->limits.maxBindGroups<1||g->limits.maxColorAttachments<1){fprintf(stderr,"DOC11_MESH_REJECT: required device limits\n");return 0;}
    WGPUShaderSourceWGSL src={.chain={.sType=WGPUSType_ShaderSourceWGSL},.code={b->shader,b->shader_len}};
    WGPUShaderModule module=wgpuDeviceCreateShaderModule(g->device,&(WGPUShaderModuleDescriptor){.nextInChain=&src.chain});if(!module){fprintf(stderr,"DOC11_MESH_REJECT: shader module\n");return 0;}
    WGPUBindGroupLayoutEntry entry={.binding=0,.visibility=WGPUShaderStage_Vertex|WGPUShaderStage_Fragment,.buffer={.type=WGPUBufferBindingType_Uniform,.minBindingSize=32}};
    g->layout=wgpuDeviceCreateBindGroupLayout(g->device,&(WGPUBindGroupLayoutDescriptor){.entryCount=1,.entries=&entry});
    WGPUPipelineLayout pl=g->layout?wgpuDeviceCreatePipelineLayout(g->device,&(WGPUPipelineLayoutDescriptor){.bindGroupLayoutCount=1,.bindGroupLayouts=&g->layout}):NULL;
    if(pl&&healthy(g)){
        WGPUVertexAttribute attrs[]={{.format=WGPUVertexFormat_Sint32x4,.offset=0,.shaderLocation=0},{.format=WGPUVertexFormat_Sint32x4,.offset=16,.shaderLocation=1},{.format=WGPUVertexFormat_Sint32x4,.offset=32,.shaderLocation=2}};
        WGPUVertexBufferLayout vl={.stepMode=WGPUVertexStepMode_Vertex,.arrayStride=48,.attributeCount=3,.attributes=attrs};
        WGPUColorTargetState color={.format=WGPUTextureFormat_RGBA8Unorm,.writeMask=WGPUColorWriteMask_All};
        WGPUFragmentState fragment={.module=module,.entryPoint={"fs_main",WGPU_STRLEN},.targetCount=1,.targets=&color};
        WGPUStencilFaceState stencil={.compare=WGPUCompareFunction_Always,.failOp=WGPUStencilOperation_Keep,.depthFailOp=WGPUStencilOperation_Keep,.passOp=WGPUStencilOperation_Keep};
        WGPUDepthStencilState depth={.format=WGPUTextureFormat_Depth32Float,.depthWriteEnabled=WGPUOptionalBool_True,.depthCompare=WGPUCompareFunction_Less,.stencilFront=stencil,.stencilBack=stencil,.stencilReadMask=UINT32_MAX,.stencilWriteMask=UINT32_MAX};
        g->pipeline=wgpuDeviceCreateRenderPipeline(g->device,&(WGPURenderPipelineDescriptor){.layout=pl,.vertex={.module=module,.entryPoint={"vs_main",WGPU_STRLEN},.bufferCount=1,.buffers=&vl},.primitive={.topology=WGPUPrimitiveTopology_TriangleList,.frontFace=WGPUFrontFace_CCW,.cullMode=WGPUCullMode_None},.depthStencil=&depth,.multisample={.count=1,.mask=UINT32_MAX},.fragment=&fragment});
    }
    if(pl)wgpuPipelineLayoutRelease(pl);wgpuShaderModuleRelease(module);wgpuDevicePoll(g->device,0,NULL);wgpuInstanceProcessEvents(g->instance);int ok=g->pipeline&&healthy(g);if(!ok)fprintf(stderr,"DOC11_MESH_REJECT: pipeline layout=%d pipeline=%d fault=%d\n",g->layout!=NULL,g->pipeline!=NULL,atomic_load(&g->fault));else fprintf(stderr,"DOC11_MESH_PIPELINE_READY\n");return ok;
}
static WGPUBuffer buffer(MeshDevice *g,uint64_t n,WGPUBufferUsage usage){return wgpuDeviceCreateBuffer(g->device,&(WGPUBufferDescriptor){.size=n,.usage=usage});}
static WGPUTexture texture(MeshDevice *g,WGPUExtent3D size,WGPUTextureFormat format,WGPUTextureUsage usage){return wgpuDeviceCreateTexture(g->device,&(WGPUTextureDescriptor){.size=size,.format=format,.usage=usage,.dimension=WGPUTextureDimension_2D,.mipLevelCount=1,.sampleCount=1});}
static int render(MeshDevice *g,const MeshFrame *f,unsigned char *out){
    if(!healthy(g)||f->width>g->limits.maxTextureDimension2D||f->height>g->limits.maxTextureDimension2D){fprintf(stderr,"DOC11_MESH_REJECT: frame size or device fault\n");return 0;}
    uint64_t vn=(uint64_t)f->nv*48,in=(uint64_t)f->ni*4,row=((uint64_t)f->width*4+255)&~255ULL,readn=row*f->height;
    if(vn>g->limits.maxBufferSize||in>g->limits.maxBufferSize||readn>g->limits.maxBufferSize){fprintf(stderr,"DOC11_MESH_REJECT: buffer limits\n");return 0;}
    WGPUBuffer vb=NULL,ib=NULL,read=NULL,uniforms[128]={0};WGPUBindGroup groups[128]={0};WGPUTexture color=NULL,depth=NULL;WGPUTextureView cv=NULL,dv=NULL;WGPUCommandEncoder encoder=NULL;WGPURenderPassEncoder pass=NULL;WGPUCommandBuffer commands=NULL;int ok=0,is_mapped=0;const char *phase="frame buffers";
    vb=buffer(g,vn,WGPUBufferUsage_Vertex|WGPUBufferUsage_CopyDst);ib=buffer(g,in,WGPUBufferUsage_Index|WGPUBufferUsage_CopyDst);read=buffer(g,readn,WGPUBufferUsage_MapRead|WGPUBufferUsage_CopyDst);if(!vb||!ib||!read||!healthy(g))goto done;
    wgpuQueueWriteBuffer(g->queue,vb,0,f->vertices,(size_t)vn);wgpuQueueWriteBuffer(g->queue,ib,0,f->indices,(size_t)in);
    phase="uniform bindings";for(size_t i=0;i<f->nd;i++){uniforms[i]=buffer(g,32,WGPUBufferUsage_Uniform|WGPUBufferUsage_CopyDst);if(!uniforms[i]||!healthy(g))goto done;wgpuQueueWriteBuffer(g->queue,uniforms[i],0,f->draws[i].params,32);WGPUBindGroupEntry entry={.binding=0,.buffer=uniforms[i],.size=32};groups[i]=wgpuDeviceCreateBindGroup(g->device,&(WGPUBindGroupDescriptor){.layout=g->layout,.entryCount=1,.entries=&entry});if(!groups[i]||!healthy(g))goto done;}
    phase="textures/views";WGPUExtent3D size={.width=f->width,.height=f->height,.depthOrArrayLayers=1};color=texture(g,size,WGPUTextureFormat_RGBA8Unorm,WGPUTextureUsage_RenderAttachment|WGPUTextureUsage_CopySrc);depth=texture(g,size,WGPUTextureFormat_Depth32Float,WGPUTextureUsage_RenderAttachment);if(!color||!depth||!healthy(g))goto done;
    cv=wgpuTextureCreateView(color,NULL);dv=wgpuTextureCreateView(depth,NULL);encoder=wgpuDeviceCreateCommandEncoder(g->device,NULL);if(!cv||!dv||!encoder||!healthy(g))goto done;
    WGPURenderPassColorAttachment ca={.view=cv,.depthSlice=WGPU_DEPTH_SLICE_UNDEFINED,.loadOp=WGPULoadOp_Clear,.storeOp=WGPUStoreOp_Store,.clearValue={f->clear[0]/255.0,f->clear[1]/255.0,f->clear[2]/255.0,f->clear[3]/255.0}};
    WGPURenderPassDepthStencilAttachment da={.view=dv,.depthLoadOp=WGPULoadOp_Clear,.depthStoreOp=WGPUStoreOp_Store,.depthClearValue=1.0f,.stencilReadOnly=1};
    phase="render pass";pass=wgpuCommandEncoderBeginRenderPass(encoder,&(WGPURenderPassDescriptor){.colorAttachmentCount=1,.colorAttachments=&ca,.depthStencilAttachment=&da});if(!pass||!healthy(g))goto done;
    wgpuRenderPassEncoderSetPipeline(pass,g->pipeline);wgpuRenderPassEncoderSetVertexBuffer(pass,0,vb,0,vn);wgpuRenderPassEncoderSetIndexBuffer(pass,ib,WGPUIndexFormat_Uint32,0,in);
    for(size_t i=0;i<f->nd;i++){wgpuRenderPassEncoderSetBindGroup(pass,0,groups[i],0,NULL);wgpuRenderPassEncoderDrawIndexed(pass,f->draws[i].count,1,f->draws[i].first,0,0);}
    wgpuRenderPassEncoderEnd(pass);wgpuRenderPassEncoderRelease(pass);pass=NULL;
    phase="copy/finish";WGPUTexelCopyTextureInfo source={.texture=color,.aspect=WGPUTextureAspect_All};WGPUTexelCopyBufferInfo dest={.buffer=read,.layout={.bytesPerRow=(uint32_t)row,.rowsPerImage=f->height}};
    wgpuCommandEncoderCopyTextureToBuffer(encoder,&source,&dest,&size);commands=wgpuCommandEncoderFinish(encoder,NULL);if(!commands||!healthy(g))goto done;
    phase="submit/map";wgpuQueueSubmit(g->queue,1,&commands);_Atomic int map=0;wgpuBufferMapAsync(read,WGPUMapMode_Read,0,(size_t)readn,(WGPUBufferMapCallbackInfo){.mode=WGPUCallbackMode_AllowSpontaneous,.callback=mapped,.userdata1=&map});wait_callback(g,&map,1);if(atomic_load(&map)!=1)goto done;is_mapped=1;if(!healthy(g))goto done;
    phase="mapped pixels";const unsigned char *pixels=wgpuBufferGetConstMappedRange(read,0,(size_t)readn);if(!pixels)goto done;
    for(size_t y=0;y<f->height;y++)memcpy(out+y*f->width*4,pixels+y*row,(size_t)f->width*4);
    ok=1;
done:
    wgpuDevicePoll(g->device,0,NULL);wgpuInstanceProcessEvents(g->instance);if(!ok||!healthy(g))fprintf(stderr,"DOC11_MESH_REJECT: phase=%s fault=%d vertices=%u indices=%u draws=%u\n",phase,atomic_load(&g->fault),(unsigned)f->nv,(unsigned)f->ni,(unsigned)f->nd);
    if(is_mapped)wgpuBufferUnmap(read);
    if(commands)wgpuCommandBufferRelease(commands);
    if(pass)wgpuRenderPassEncoderRelease(pass);
    if(encoder)wgpuCommandEncoderRelease(encoder);
    if(cv)wgpuTextureViewRelease(cv);
    if(dv)wgpuTextureViewRelease(dv);
    if(color)wgpuTextureRelease(color);
    if(depth)wgpuTextureRelease(depth);
    for(size_t i=0;i<f->nd;i++){if(groups[i])wgpuBindGroupRelease(groups[i]);if(uniforms[i])wgpuBufferRelease(uniforms[i]);}
    if(vb)wgpuBufferRelease(vb);
    if(ib)wgpuBufferRelease(ib);
    if(read)wgpuBufferRelease(read);
    return ok&&healthy(g);
}
int main(int argc,char **argv){
    int destroy=argc==2&&!strcmp(argv[1],"--test-device-loss");if(argc!=1&&!destroy)return 1;
    MeshBatch batch;if(!mesh_load(stdin,&batch)){fprintf(stderr,"DOC11_MESH_REJECT: invalid packet\n");return 1;}
    unsigned char *pixels=malloc(batch.pixel_bytes);MeshDevice g={0};int ok=pixels&&device_open(&g,&batch);size_t at=0;
    for(size_t i=0;ok&&i<batch.n;i++){ok=render(&g,batch.frames+i,pixels+at);if(!ok)fprintf(stderr,"DOC11_MESH_REJECT: frame=%zu\n",i);at+=(size_t)batch.frames[i].width*batch.frames[i].height*4;if(ok&&destroy){wgpuDeviceDestroy(g.device);wait_callback(&g,&g.lost,0);ok=0;fprintf(stderr,"DOC11_MESH_DEVICE_LOSS: no pixel publication\n");}}
    ok=ok&&healthy(&g)&&at==batch.pixel_bytes;device_close(&g);
    if(ok){ok=fwrite(pixels,1,at,stdout)==at&&fflush(stdout)==0;if(ok)fprintf(stderr,"DOC11_MESH_RENDER: frames=%u bytes=%zu\n",batch.n,at);}
    free(pixels);mesh_free(&batch);return ok?0:1;
}
