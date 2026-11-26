/* Actual separately compiled, explicitly GPU-backed graph replacement. */
#include "graph_host.h"
#include <assert.h>
extern const GraphVariant old_variant,new_variant;
static pthread_mutex_t gate=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t ready=PTHREAD_COND_INITIALIZER;
static int entered,released;
static int64_t value(const GraphFact *f,size_t n,const char *name){for(size_t i=0;i<n;i++)if(f[i].name&&!strcmp(f[i].name,name))return num(f[i].value);assert(0);return 0;}
static void check_old(void *ctx,int64_t g,const GraphFact *f,size_t n){(void)ctx;assert(g==0&&value(f,n,"amount")==7&&value(f,n,"total")==8);}
static void check_new(void *ctx,int64_t g,const GraphFact *f,size_t n){(void)ctx;assert(g==1&&value(f,n,"amount")==7&&value(f,n,"total")==14&&value(f,n,"combined")==18);}
static void check_reopened(void *ctx,int64_t g,const GraphFact *f,size_t n){(void)ctx;assert(g==2&&value(f,n,"amount")==9&&value(f,n,"total")==10);}
static void pinned(void *ctx,int64_t g,const GraphFact *f,size_t n){check_old(ctx,g,f,n);pthread_mutex_lock(&gate);entered=1;pthread_cond_broadcast(&ready);while(!released)pthread_cond_wait(&ready,&gate);pthread_mutex_unlock(&gate);check_old(ctx,g,f,n);}
static void *reader(void *ctx){assert(graph_read(ctx,0,pinned,NULL));return NULL;}
static void never(void *ctx,int64_t g,const GraphFact *f,size_t n){(void)ctx;(void)g;(void)f;(void)n;assert(0);}
int main(void){
    GraphHost h;assert(graph_init(&h,&old_variant));char *updates[]={"amount=7"};assert(graph_update(&h,0,1,updates));
    assert(old_variant.dispatches()==2&&old_variant.device_live()>0);assert(graph_read(&h,0,check_old,NULL));
    pthread_t t;assert(!pthread_create(&t,NULL,reader,&h));pthread_mutex_lock(&gate);while(!entered)pthread_cond_wait(&ready,&gate);pthread_mutex_unlock(&gate);
    assert(!setenv("DOC_GPU_TEST_FAIL_DISPATCH","1",1));assert(!graph_replace(&h,0,&new_variant));assert(!unsetenv("DOC_GPU_TEST_FAIL_DISPATCH"));
    assert(!new_variant.live()&&!new_variant.device_live()&&new_variant.dispatches()==1);assert(old_variant.device_live()>0);assert(graph_read(&h,0,check_old,NULL));
    assert(graph_replace(&h,0,&new_variant));assert(!old_variant.live()&&!old_variant.device_live());assert(new_variant.dispatches()==2&&new_variant.device_live()>0);assert(!graph_read(&h,0,never,NULL));assert(!graph_update(&h,0,1,updates));assert(!graph_replace(&h,0,&old_variant));assert(graph_read(&h,1,check_new,NULL));
    pthread_mutex_lock(&gate);released=1;pthread_cond_broadcast(&ready);pthread_mutex_unlock(&gate);assert(!pthread_join(t,NULL));assert(!h.reader_slots&&!atomic_load(&live_bytes));
    char *cpu[]={"--backend=cpu"};assert(!graph_update(&h,1,1,cpu));char *next[]={"amount=9"};assert(graph_update(&h,1,1,next));
    assert(graph_replace(&h,1,&old_variant));assert(!new_variant.live()&&!new_variant.device_live());assert(old_variant.dispatches()==1&&old_variant.device_live()>0);assert(graph_read(&h,2,check_reopened,NULL));
    graph_destroy(&h);assert(!old_variant.live()&&!new_variant.live()&&!old_variant.device_live()&&!new_variant.device_live()&&!atomic_load(&live_bytes));
    puts("DOC11_GPU_GRAPH_GENERATION_PASS: actual GPU candidate rollback, successful topology change, stale tickets, pinned reader survives device retirement, source carry, device reopen, zero live bytes");return 0;
}
