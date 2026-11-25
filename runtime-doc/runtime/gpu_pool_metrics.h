#ifndef DOC_GPU_POOL_METRICS_H
#define DOC_GPU_POOL_METRICS_H
#include <stdint.h>
/* Logical byte sizes of admitted WebGPU buffer handles. These are not
 * device-resident allocation measurements or driver-internal lifetime counts. */
typedef struct {uint64_t admitted,released,live,peak;} GPUBufferMetrics;
static int gpu_metric_admit(GPUBufferMetrics *m,uint64_t bytes){
    if(bytes>UINT64_MAX-m->admitted||bytes>UINT64_MAX-m->live)return 0;
    m->admitted+=bytes;m->live+=bytes;if(m->live>m->peak)m->peak=m->live;return 1;
}
static int gpu_metric_release(GPUBufferMetrics *m,uint64_t bytes){
    if(bytes>m->live||bytes>UINT64_MAX-m->released)return 0;
    m->released+=bytes;m->live-=bytes;return 1;
}
#endif
