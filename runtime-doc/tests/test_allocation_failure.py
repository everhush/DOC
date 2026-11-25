#!/usr/bin/env python3
"""Native allocation failure and stalled-reader lifetime tests, no reference counts."""
import argparse
from pathlib import Path
import tempfile
from test_epoch_authority import emit, run, sanitizer_flags

HARNESS = r'''
#define DOC_TEST_ALLOC_FAILURE
#define main generated_main
#include "generated.c"
#undef main
#include <assert.h>
static pthread_mutex_t gate=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t ready=PTHREAD_COND_INITIALIZER;
static unsigned entered,released;
typedef struct {Epoch *e; int64_t value,generation;int stall;} Read;
static void inspect(void *raw,int64_t generation,const V *v,const unsigned char *mask,size_t n){
    Read *r=raw;assert(generation==r->generation&&n==r->e->n);
    for(size_t i=0;i<n;i++){assert(mask[i]);assert(v[i].kind==L&&v[i].n==(i?3:2));const int64_t *p=v[i].p;assert(p[0]==r->value&&p[1]==2);if(i)assert(p[2]==(int64_t)i-1);}
    if(r->stall){pthread_mutex_lock(&gate);entered++;pthread_cond_broadcast(&ready);while(!released)pthread_cond_wait(&ready,&gate);pthread_mutex_unlock(&gate);for(size_t i=0;i<n;i++)assert(((const int64_t*)v[i].p)[0]==r->value);}
}
static void *read_old(void *raw){Read *r=raw;assert(epoch_read(r->e,r->e->n,inspect,r));return NULL;}
static int update(Epoch *e,int value){char arg[64];snprintf(arg,sizeof(arg),"xs=[%d,2]",value);char *args[]={arg};size_t t;assert(epoch_begin(e));return epoch_finish(e,batch(e,1,args,&t));}
int main(void){
    Epoch e;epoch_init(&e,states,sizeof(states)/sizeof(states[0]));size_t t;assert(epoch_begin(&e));assert(epoch_finish(&e,batch(&e,0,NULL,&t)));size_t baseline=atomic_load(&live_bytes);
    // Measure all allocation sites on a successful update, then reject at each
    // possible allocation ordinal under the same source and actual worker path.
    size_t before=atomic_load(&allocs);assert(update(&e,7));size_t count=atomic_load(&allocs)-before;assert(count>32);assert(update(&e,1));assert(atomic_load(&live_bytes)==baseline);
    for(size_t k=0;k<count;k++){int64_t g=e.committed;atomic_store(&allocation_budget,k);assert(!update(&e,7));atomic_store(&allocation_budget,SIZE_MAX);Read old={&e,1,g,0};assert(epoch_read(&e,e.n,inspect,&old));assert(atomic_load(&live_bytes)==baseline);}
    Read old={&e,1,e.committed,0};
    // Reject every partially copied reader snapshot; no callback or retained
    // allocation on failure. Then prove two independent stalled readers survive.
    for(size_t k=0;k<e.n;k++){atomic_store(&allocation_budget,k);assert(!epoch_read(&e,e.n,inspect,&old));atomic_store(&allocation_budget,SIZE_MAX);assert(atomic_load(&live_bytes)==baseline);}
    pthread_t a,b;old.stall=1;assert(!pthread_create(&a,NULL,read_old,&old));assert(!pthread_create(&b,NULL,read_old,&old));pthread_mutex_lock(&gate);while(entered<2)pthread_cond_wait(&ready,&gate);pthread_mutex_unlock(&gate);
    size_t protected_bytes=atomic_load(&live_bytes);assert(protected_bytes>baseline);
    for(int i=0;i<128;i++){assert(update(&e,10+i));assert(atomic_load(&live_bytes)==protected_bytes);Read now={&e,10+i,e.committed,0};assert(epoch_read(&e,e.n,inspect,&now));assert(atomic_load(&live_bytes)==protected_bytes);}
    pthread_mutex_lock(&gate);released=1;pthread_cond_broadcast(&ready);pthread_mutex_unlock(&gate);assert(!pthread_join(a,NULL));assert(!pthread_join(b,NULL));assert(atomic_load(&live_bytes)==baseline);
    epoch_free(&e);assert(atomic_load(&live_bytes)==0);printf("DOC11_ALLOCATION_FAILURE_PASS: %zu update fault ordinals, %zu snapshot fault ordinals, 128 replacements with two stalled readers, baseline=%zu protected=%zu peak=%zu live=0\n",count,sizeof(states)/sizeof(states[0]),baseline,protected_bytes,(size_t)peak_bytes);return 0;
}
'''


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--reactive',required=True,type=Path);ap.add_argument('--headers',type=Path,default=Path(__file__).resolve().parent.parent/'runtime');ap.add_argument('--sanitizer',choices=('address','thread'),default='address');a=ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        cwd=Path(tmp);source='source xs:ints=[1,2]\n'+''.join(f'derive l{i}:ints(xs)=append(xs,{i})\n' for i in range(32))
        (cwd/'generated.c').write_text(emit(a.reactive.resolve(),source,cwd));(cwd/'harness.c').write_text(HARNESS)
        exe=cwd/'harness';run(['cc','-std=gnu11','-O1','-g','-pthread',*sanitizer_flags(a.sanitizer),'-fno-pie','-no-pie','-I',a.headers.resolve(),cwd/'harness.c','-o',exe],cwd)
        out,err=run([exe],cwd);assert 'DOC11_ALLOCATION_FAILURE_PASS:' in out and 'DOC11_MANAGED_PARALLEL:' in err,(out,err);print(out.strip())
if __name__=='__main__':main()
