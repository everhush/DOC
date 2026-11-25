#!/usr/bin/env python3
"""Generation-scoped cancellation and owned, protected snapshot regression."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

HARNESS = r'''
#define main generated_main
#include "generated.c"
#undef main
#include <assert.h>
static pthread_mutex_t gate=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t ready=PTHREAD_COND_INITIALIZER;
static int entered,released,slow;
static void wait_enter(void){pthread_mutex_lock(&gate);while(!entered)pthread_cond_wait(&ready,&gate);pthread_mutex_unlock(&gate);}
static void release(void){pthread_mutex_lock(&gate);released=1;pthread_cond_broadcast(&ready);pthread_mutex_unlock(&gate);}
static void pause_here(void){pthread_mutex_lock(&gate);entered=1;pthread_cond_broadcast(&ready);while(!released)pthread_cond_wait(&ready,&gate);pthread_mutex_unlock(&gate);}
static void reset_gate(void){entered=released=0;}
static V blocked_eval(void){if(slow)pause_here();return E_l0();}
static void check_list(V v,int64_t a,int64_t b,size_t n){assert(v.kind==L&&v.n==n);const int64_t *p=v.p;assert(p[0]==a&&p[1]==b);}
typedef struct {Epoch *e;int64_t generation,first,second;int pause;} Read;
static void inspect(void *raw,int64_t generation,const V *v,const unsigned char *mask,size_t n){Read *r=raw;assert(generation==r->generation&&n==r->e->n);assert(mask[0]&&mask[1]);check_list(v[0],r->first,r->second,2);check_list(v[1],r->first,r->second,3);if(r->pause){pause_here();check_list(v[0],r->first,r->second,2);check_list(v[1],r->first,r->second,3);}}
static void *reader(void *raw){Read *r=raw;assert(epoch_read(r->e,r->e->n,inspect,r));return NULL;}
static void *writer(void *raw){Epoch *e=raw;size_t target;char *a[]={"xs=[8,9]"};assert(!batch(e,1,a,&target));assert(!epoch_finish(e,1));return NULL;}
static void never(void *raw,int64_t g,const V *v,const unsigned char *m,size_t n){(void)raw;(void)g;(void)v;(void)m;(void)n;assert(0);}
int main(void){
    State copy[sizeof(states)/sizeof(states[0])];memcpy(copy,states,sizeof(states));copy[1].eval=blocked_eval;
    Epoch e;epoch_init(&e,copy,sizeof(copy)/sizeof(copy[0]));size_t target;pthread_t thread;
    assert(!epoch_read(&e,e.n,never,NULL));assert(!epoch_cancel(&e,0));
    assert(epoch_begin(&e));assert(!epoch_begin(&e));assert(batch(&e,0,NULL,&target));assert(epoch_finish(&e,1));assert(e.committed==1);
    size_t baseline=atomic_load(&live_bytes);assert(baseline>0);
    Read old={&e,1,1,2,1};assert(!pthread_create(&thread,NULL,reader,&old));wait_enter();
    assert(epoch_begin(&e));int64_t ticket=epoch_ticket(&e);char *a[]={"xs=[4,5]"};assert(batch(&e,1,a,&target));
    Read private_old={&e,1,1,2,0};assert(epoch_read(&e,e.n,inspect,&private_old));assert(epoch_finish(&e,1));assert(e.committed==2);
    Read current={&e,2,4,5,0};assert(epoch_read(&e,e.n,inspect,&current));release();assert(!pthread_join(thread,NULL));assert(atomic_load(&live_bytes)==baseline);assert(!epoch_cancel(&e,ticket));
    // Cancellation after complete private evaluation must still reject commit.
    assert(epoch_begin(&e));int64_t cancelled=epoch_ticket(&e);assert(!epoch_cancel(&e,ticket));char *b[]={"xs=[6,7]"};assert(batch(&e,1,b,&target));assert(epoch_cancel(&e,cancelled));assert(!epoch_finish(&e,1));assert(epoch_read(&e,e.n,inspect,&current));assert(atomic_load(&live_bytes)==baseline);
    // Cancel while a real compiler-generated evaluation is admitted to a frontier.
    reset_gate();slow=1;assert(epoch_begin(&e));int64_t in_flight=epoch_ticket(&e);assert(!pthread_create(&thread,NULL,writer,&e));wait_enter();assert(epoch_read(&e,e.n,inspect,&current));assert(!epoch_cancel(&e,cancelled));assert(epoch_cancel(&e,in_flight));release();assert(!pthread_join(thread,NULL));slow=0;assert(epoch_read(&e,e.n,inspect,&current));assert(atomic_load(&live_bytes)==baseline);
    // Recovery, stale ticket rejection and cutoff after rollback.
    assert(epoch_begin(&e));assert(!epoch_cancel(&e,in_flight));assert(batch(&e,1,a,&target));assert(e.evaluations==0);assert(epoch_finish(&e,1));assert(e.committed==5);
    e.attempt=INT64_MAX;assert(!epoch_begin(&e));assert(!epoch_cancel(&e,INT64_MAX));epoch_free(&e);assert(atomic_load(&live_bytes)==0);
    puts("DOC11_EPOCH_AUTHORITY_PASS: scoped snapshot survives replacement; private state hidden; cancellation during frontier and before commit; stale tokens rejected; cutoff and live=0");return 0;
}
'''


def run(args, cwd):
    result = subprocess.run([str(x) for x in args], cwd=cwd, text=True,
                            capture_output=True, timeout=120,
                            env={**os.environ, 'DOC_WORKERS':'4',
                                 'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1',
                                 'UBSAN_OPTIONS':'halt_on_error=1', 'TSAN_OPTIONS':'halt_on_error=1'})
    assert result.returncode == 0, (args[0], result.stderr)
    return result.stdout, result.stderr


def emit(compiler, source, cwd):
    out, _ = run([compiler, '--demand=code', 'input=['+','.join(map(str,source.encode()))+']'], cwd)
    assert out.startswith('code: '), out
    return out.removeprefix('code: ')


def sanitizer_flags(mode):
    return ['-fsanitize=thread'] if mode=='thread' else ['-fsanitize=address,undefined','-fno-sanitize-recover=all']


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--managed',required=True,type=Path);ap.add_argument('--reactive',required=True,type=Path);ap.add_argument('--headers',type=Path,default=Path(__file__).resolve().parent.parent/'runtime');ap.add_argument('--sanitizer',choices=('address','thread'),default='address');args=ap.parse_args()
    headers=args.headers.resolve()
    with tempfile.TemporaryDirectory() as tmp:
        cwd=Path(tmp)
        policy=(headers/'epoch_authority.doc').read_text()+'source marker:int=0\n'
        generated=emit(args.managed.resolve(),policy,cwd)
        macros=[line for line in generated.splitlines() if line.startswith('#define F_life_')]
        checked=[line for line in (headers/'epoch_policy_generated.h').read_text().splitlines() if line.startswith('#define F_life_')]
        assert len(macros)==4 and macros==checked, 'DOC authority policy drift'
        source='source xs:ints=[1,2]\n'+''.join(f'derive l{i}:ints(xs)=append(xs,{i})\n' for i in range(32))
        (cwd/'generated.c').write_text(emit(args.reactive.resolve(),source,cwd));(cwd/'harness.c').write_text(HARNESS)
        exe=cwd/'harness';run(['cc','-std=gnu11','-O1','-g','-pthread',*sanitizer_flags(args.sanitizer),'-fno-pie','-no-pie','-I',headers,cwd/'harness.c','-o',exe],cwd)
        out,err=run([exe],cwd);assert 'DOC11_EPOCH_AUTHORITY_PASS:' in out and 'DOC11_MANAGED_PARALLEL:' in err,(out,err);print(out.strip())

if __name__=='__main__': main()
