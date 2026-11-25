/* Adverse interleaving at a real WebGPU queue submission boundary.
 * This test builds the unmodified compiler-generated mixed graph and enables
 * a test-only callback; no application-level scheduling policy is introduced. */
#define DOC_GPU_TEST_SUBMIT_HOOK
#define main generated_main
#include "generated.c"
#undef main
#include <assert.h>
static pthread_mutex_t gate=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t ready=PTHREAD_COND_INITIALIZER;
static int entered,released;
static int hold_submission(Epoch *e){
    (void)e;pthread_mutex_lock(&gate);entered=1;pthread_cond_broadcast(&ready);
    while(!released)pthread_cond_wait(&ready,&gate);pthread_mutex_unlock(&gate);return 1;
}
static int abandon_submission(Epoch *e){(void)e;return 0;}
static int destroy_submission(Epoch *e){
    (void)e;wgpuDeviceDestroy(gpu_device);gpu_wait(&gpu_device_lost,0);
    assert(!gpu_healthy());return 0;
}
typedef struct {Epoch *e;int64_t generation,x;size_t list_n;int64_t first,second;} Expected;
static void inspect(void *raw,int64_t generation,const V *v,const unsigned char *mask,size_t n){
    Expected *p=raw;assert(generation==p->generation&&n==p->e->n);
    char name[32];int z=snprintf(name,sizeof(name),"g%lld",(long long)p->x);assert(z>0&&(size_t)z<sizeof(name));
    size_t x=find_state(p->e,"x",1),g=find_state(p->e,name,(size_t)z),c=find_state(p->e,"c0",2);
    assert(x<n&&g<n&&c<n&&mask[x]&&mask[g]&&mask[c]);
    assert(v[x].kind==I&&num(v[x])==p->x&&v[g].kind==B&&truth(v[g]));
    assert(v[c].kind==L&&v[c].n==p->list_n);
    const int64_t *list=v[c].p;assert(list[0]==p->first&&list[1]==p->second&&list[p->list_n-1]==0);
}
static void read_expected(Expected *p){assert(epoch_read(p->e,p->e->n,inspect,p));}
static void *cancelled_writer(void *raw){
    Epoch *e=raw;size_t target;char *updates[]={"x=3","xs=[4]"};
    assert(!batch(e,2,updates,&target));assert(!epoch_finish(e,1));return NULL;
}
int main(void){
    Epoch e;size_t target;epoch_init(&e,states,sizeof(states)/sizeof(states[0]));
    gpu_mode=2;assert(gpu_open(e.n));assert(epoch_begin(&e));assert(batch(&e,0,NULL,&target));assert(epoch_finish(&e,1));
    assert(e.committed==1&&gpu_dispatches>0);size_t dispatches=gpu_dispatches,baseline=atomic_load(&live_bytes);assert(baseline>0);
    Expected old={&e,1,2,3,1,2};read_expected(&old);
    /* Hold host acknowledgement after a genuine submit; the device may
       already have finished, but its completion has not been consumed. */
    gpu_test_after_submit=hold_submission;assert(epoch_begin(&e));int64_t ticket=epoch_ticket(&e);
    pthread_t writer;assert(!pthread_create(&writer,NULL,cancelled_writer,&e));
    pthread_mutex_lock(&gate);while(!entered)pthread_cond_wait(&ready,&gate);pthread_mutex_unlock(&gate);
    read_expected(&old);assert(epoch_cancel(&e,ticket));
    pthread_mutex_lock(&gate);released=1;pthread_cond_broadcast(&ready);pthread_mutex_unlock(&gate);
    assert(!pthread_join(writer,NULL));gpu_test_after_submit=NULL;
    assert(gpu_healthy()&&gpu_dispatches>dispatches&&e.committed==1&&!epoch_cancel(&e,ticket));
    read_expected(&old);assert(atomic_load(&live_bytes)==baseline);
    /* Cancellation is not device failure: a later epoch reuses the pool and
       publishes the new mixed values only after actual GPU completion. */
    char *retry[]={"x=3","xs=[4]"};assert(epoch_begin(&e));assert(batch(&e,2,retry,&target));assert(epoch_finish(&e,1));
    Expected current={&e,3,3,2,4,0};read_expected(&current);baseline=atomic_load(&live_bytes);
    /* Abandon a real submission without a successful map. Its queue must
       acknowledge completion before host resource retirement and pool reuse. */
    gpu_test_after_submit=abandon_submission;char *next[]={"x=4","xs=[8]"};assert(epoch_begin(&e));
    assert(!batch(&e,2,next,&target));assert(!epoch_finish(&e,1));gpu_test_after_submit=NULL;
    assert(gpu_healthy()&&e.committed==3);read_expected(&current);assert(atomic_load(&live_bytes)==baseline);
    assert(epoch_begin(&e));assert(batch(&e,2,next,&target));assert(epoch_finish(&e,1));
    Expected newer={&e,5,4,2,8,0};read_expected(&newer);baseline=atomic_load(&live_bytes);
    /* A subsequent actual submission loses its device before readback admission. */
    gpu_test_after_submit=destroy_submission;char *lost[]={"x=5","xs=[9]"};assert(epoch_begin(&e));
    assert(!batch(&e,2,lost,&target));assert(!epoch_finish(&e,1));gpu_test_after_submit=NULL;
    assert(!gpu_healthy()&&atomic_load(&gpu_device_lost)&&e.committed==5);
    read_expected(&newer);assert(atomic_load(&live_bytes)==baseline);
    gpu_close();gpu_mode=0;epoch_free(&e);assert(atomic_load(&live_bytes)==0);
    puts("DOC11_GPU_EPOCH_AUTHORITY_PASS: real submitted mixed frontier cancellation, protected old snapshot, rollback, pool reuse, abandoned submission queue completion, submitted device loss, retirement and live=0");
    return 0;
}
