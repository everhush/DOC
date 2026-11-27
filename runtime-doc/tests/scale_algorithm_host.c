/* Same emitted DOC map functions and checked source/epoch path for both CPU
 * and physical GPU. Host controls packed-pair stages for the sorting/reduction
 * profiles; those are not integrated whole-program GPU sort/reduce claims. */
#define main doc_generated_main
#include "generated.c"
#undef main
#include <assert.h>
#include <time.h>
static uint64_t stamp(void){struct timespec t;assert(!clock_gettime(CLOCK_MONOTONIC,&t));return (uint64_t)t.tv_sec*1000000000u+t.tv_nsec;}
static int cmp(const void *a,const void *b){int64_t x=*(const int64_t*)a,y=*(const int64_t*)b;return(x>y)-(x<y);}
static uint64_t stage(Epoch *e,int64_t *in,size_t n,int64_t bias,int64_t *out,char *text,size_t stage_id){size_t pos=snprintf(text,32*n+32,"xs=[");for(size_t i=0;i<n;i++)pos+=snprintf(text+pos,32*n+32-pos,"%s%lld",i?",":"",(long long)in[i]);snprintf(text+pos,32*n+32-pos,"]");char arg[64];snprintf(arg,sizeof(arg),"bias=%lld",(long long)bias);char *args[]={"--demand=ys",text,arg};size_t target;uint64_t t=stamp();assert(epoch_begin(e));assert(batch(e,3,args,&target));assert(epoch_finish(e,1));uint64_t wall=stamp()-t;V v=*e->states[target].slot;assert(v.kind==L&&v.n==n);memcpy(out,v.p,n*sizeof(*out));printf("stage=%zu lanes=%zu epoch_ns=%llu evaluations=%zu\n",stage_id,n,(unsigned long long)wall,e->evaluations);return wall;}
int main(int argc,char **argv){assert(argc==4);size_t n=strtoul(argv[2],NULL,10),rounds=strtoul(argv[3],NULL,10);assert(n&&n<=DOC_FAMILY_LIMIT&&!(n&(n-1))&&rounds>0&&rounds<=16);gpu_mode=!strcmp(argv[1],"gpu")?1:!strcmp(argv[1],"auto")?2:0;assert(gpu_mode||!strcmp(argv[1],"cpu"));Epoch e;epoch_init(&e,states,sizeof(states)/sizeof(states[0]));uint64_t open=0;if(gpu_mode){uint64_t t=stamp();assert(gpu_open(e.n));open=stamp()-t;}
 int64_t *x=malloc(n*sizeof(*x)),*y=malloc(n*sizeof(*y)),*packed=malloc(n*sizeof(*packed)),*expected=malloc(n*sizeof(*expected));char *text=malloc(n*32+32);assert(x&&y&&packed&&expected&&text);
 printf("open_ns=%llu n=%zu rounds=%zu algorithm=%d\n",(unsigned long long)open,n,rounds,DOC_ALGORITHM);
 size_t seq=0;
 for(size_t r=0;r<rounds;r++){uint64_t start=stamp(),sum=0;int64_t checksum=0;
 if(DOC_ALGORITHM==0){int64_t bias=13849+(int64_t)r;for(size_t i=0;i<n;i++)x[i]=(i+r)%32760;sum+=stage(&e,x,n,bias,y,text,seq++);for(size_t i=0;i<n;i++){int64_t v=x[i];for(int j=0;j<32;j++)v=(v*25173+bias)%65521;assert(v==y[i]);checksum+=v;}}
 else if(DOC_ALGORITHM==1){uint32_t seed=(uint32_t)(2026+r);for(size_t i=0;i<n;i++){seed=seed*1664525u+1013904223u;x[i]=expected[i]=(seed>>16)&32767;}
 for(size_t k=2;k<=n;k*=2){for(size_t j=k/2;j;j/=2){for(size_t i=0;i<n;i++){size_t p=i^j;int want_min=((i&j)==0)==((i&k)==0);packed[i]=x[i]*32768+x[p]+(want_min?0:1073741824);}sum+=stage(&e,packed,n,(int64_t)seq,y,text,seq);seq++;int64_t *tmp=x;x=y;y=tmp;}}
 qsort(expected,n,sizeof(*expected),cmp);for(size_t i=0;i<n;i++){assert(x[i]==expected[i]);checksum+=x[i];}}
 else {for(size_t i=0;i<n;i++)x[i]=(i+r)&1;for(size_t m=n;m>1;m/=2){for(size_t i=0;i<m/2;i++){assert(x[2*i]<=32767&&x[2*i+1]<=32767);packed[i]=x[2*i]*32768+x[2*i+1];}sum+=stage(&e,packed,m/2,(int64_t)seq,y,text,seq);seq++;int64_t *tmp=x;x=y;y=tmp;}assert(x[0]==(int64_t)n/2);checksum=x[0];}
 printf("round=%zu epoch_sum_ns=%llu algorithm_ns=%llu checksum=%lld\n",r,(unsigned long long)sum,(unsigned long long)(stamp()-start),(long long)checksum);}
 free(x);free(y);free(packed);free(expected);free(text);epoch_free(&e);gpu_close();assert(!live_bytes);puts("live=0");doc_process_metrics();return 0;}
