#define main doc_generated_main
#include "generated.c"
#undef main
#include <assert.h>
#include <time.h>
#ifndef DOC_SCALE_COMPLEX
#define DOC_SCALE_COMPLEX 0
#endif
static uint64_t stamp(void){struct timespec t;assert(!clock_gettime(CLOCK_MONOTONIC,&t));return (uint64_t)t.tv_sec*1000000000u+(uint64_t)t.tv_nsec;}
static int64_t item_at(size_t i,size_t epoch){return DOC_SCALE_COMPLEX?(int64_t)((i+epoch)%9)-4:(int64_t)(i+epoch);}
static int64_t oracle(int64_t x,int64_t bias){if(!DOC_SCALE_COMPLEX)return x+bias;int64_t v=bias;for(int j=0;j<5;j++)v=v*x+bias;return v;}
int main(int argc,char **argv){assert(argc==4);size_t n=(size_t)strtoul(argv[2],NULL,10),epochs=(size_t)strtoul(argv[3],NULL,10);assert(n<=4096&&epochs>1&&epochs<=128);gpu_mode=!strcmp(argv[1],"gpu")?1:!strcmp(argv[1],"auto")?2:0;assert(gpu_mode||!strcmp(argv[1],"cpu"));Epoch e;epoch_init(&e,states,sizeof(states)/sizeof(states[0]));uint64_t open=0;if(gpu_mode){uint64_t t=stamp();assert(gpu_open(e.n));open=stamp()-t;}printf("open_ns=%llu lanes=%zu epochs=%zu complex=%d\n",(unsigned long long)open,n,epochs,DOC_SCALE_COMPLEX);char *input=malloc(32*n+32);assert(input);char bias_arg[64];char *args[]={"--demand=ys",input,bias_arg};
for(size_t i=0;i<epochs;i++){size_t pos=(size_t)snprintf(input,32*n+32,"xs=[");for(size_t k=0;k<n;k++)pos+=(size_t)snprintf(input+pos,32*n+32-pos,"%s%lld",k?",":"",(long long)item_at(k,i));snprintf(input+pos,32*n+32-pos,"]");int64_t bias=(int64_t)(i%7)-3;snprintf(bias_arg,sizeof(bias_arg),"bias=%lld",(long long)bias);size_t target;uint64_t begin=stamp();assert(epoch_begin(&e));assert(batch(&e,3,args,&target));assert(epoch_finish(&e,1));uint64_t elapsed=stamp()-begin;V result=*e.states[target].slot;assert(result.kind==L&&result.n==n);int64_t total=0;for(size_t k=0;k<n;k++){int64_t got=((const int64_t*)result.p)[k];assert(got==oracle(item_at(k,i),bias));total+=got;}printf("epoch=%zu wall_ns=%llu evals=%zu checksum=%lld\n",i,(unsigned long long)elapsed,e.evaluations,(long long)total);}
free(input);epoch_free(&e);gpu_close();assert(!live_bytes);printf("live=0 peak=%zu allocations=%zu\n",(size_t)peak_bytes,(size_t)allocs);doc_process_metrics();return 0;}
