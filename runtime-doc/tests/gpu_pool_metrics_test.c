#include "gpu_pool_metrics.h"
#include <assert.h>
#include <stdio.h>
int main(void){
    GPUBufferMetrics m={0};assert(gpu_metric_admit(&m,400));
    uint64_t old=0,peak=400;
    for(uint64_t i=1;i<=4096;i++){
        uint64_t now=i*20;
        assert(gpu_metric_admit(&m,now));peak=400+old+now;
        assert(m.peak==peak);assert(gpu_metric_release(&m,old));
        assert(m.live==400+now&&m.admitted-m.released==m.live);old=now;
    }
    assert(!gpu_metric_release(&m,m.live+1));assert(m.live==400+old);
    assert(gpu_metric_release(&m,400+old));assert(!m.live&&m.admitted==m.released);
    GPUBufferMetrics high={0};assert(gpu_metric_admit(&high,UINT64_MAX));
    assert(!gpu_metric_admit(&high,1)&&high.admitted==UINT64_MAX&&high.live==UINT64_MAX);
    assert(gpu_metric_release(&high,UINT64_MAX));assert(!gpu_metric_admit(&high,1));
    assert(!high.live&&high.admitted==high.released);
    puts("DOC11_GPU_POOL_METRICS_PASS: 4096 growth/retirement transitions, overlap peak, underflow/overflow rejection and zero live logical bytes");
    return 0;
}
