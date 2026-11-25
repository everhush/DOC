#!/usr/bin/env python3
"""Independently compiled graph generations; typed carry, rollback and reader safety."""
import argparse
from pathlib import Path
import tempfile
from test_epoch_authority import emit, run, sanitizer_flags

VARIANTS = {
    'old': 'source amount:int=2\nsource xs:ints=[1,2]\nderive total:int(amount)=add(amount,1)\n',
    'new': 'source amount:int=99\nsource xs:ints=[]\nsource extra:bool=true\nderive total:int(amount)=mul(amount,2)\nderive ys:ints(xs)=append(xs,3)\n',
    'bad': 'source amount:int=0\nderive broken:int(amount)=add(amount,9223372036854775807)\n',
    'changed': 'source amount:bool=true\nsource total:int=3\nderive xs:int(total)=add(total,1)\n',
}
HARNESS = r'''
#include "graph_host.h"
#include <assert.h>
extern const GraphVariant old_variant,new_variant,bad_variant,changed_variant;
static pthread_mutex_t gate=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t ready=PTHREAD_COND_INITIALIZER;
static int entered,released;
static const GraphFact *lookup(const GraphFact *f,size_t n,const char *name){for(size_t i=0;i<n;i++)if(f[i].name&&!strcmp(f[i].name,name))return f+i;return NULL;}
static V get(const GraphFact *f,size_t n,const char *name){const GraphFact *p=lookup(f,n,name);assert(p);return p->value;}
static void old_check(void *ctx,int64_t g,const GraphFact *f,size_t n){(void)ctx;assert(g==0&&num(get(f,n,"amount"))==7&&num(get(f,n,"total"))==8);V xs=get(f,n,"xs");assert(xs.n==2&&((const int64_t*)xs.p)[0]==9);}
static void pinned(void *ctx,int64_t g,const GraphFact *f,size_t n){old_check(ctx,g,f,n);pthread_mutex_lock(&gate);entered=1;pthread_cond_broadcast(&ready);while(!released)pthread_cond_wait(&ready,&gate);pthread_mutex_unlock(&gate);old_check(ctx,g,f,n);}
static void *reader(void *p){assert(graph_read(p,0,pinned,NULL));return NULL;}
static void new_check(void *ctx,int64_t g,const GraphFact *f,size_t n){(void)ctx;assert(g==1&&num(get(f,n,"amount"))==7&&num(get(f,n,"total"))==14&&truth(get(f,n,"extra")));V xs=get(f,n,"xs"),ys=get(f,n,"ys");assert(xs.n==2&&ys.n==3&&((const int64_t*)ys.p)[0]==9&&((const int64_t*)ys.p)[2]==3);}
static void changed_check(void *ctx,int64_t g,const GraphFact *f,size_t n){(void)ctx;assert(g==2&&truth(get(f,n,"amount"))&&num(get(f,n,"total"))==3&&num(get(f,n,"xs"))==4);}
static void never(void *ctx,int64_t g,const GraphFact *f,size_t n){(void)ctx;(void)g;(void)f;(void)n;assert(0);}
int main(void){GraphHost h;assert(graph_init(&h,&old_variant));char *updates[]={"amount=7","xs=[9,2]"};assert(graph_update(&h,0,2,updates));assert(graph_read(&h,0,old_check,NULL));
    pthread_t t;assert(!pthread_create(&t,NULL,reader,&h));pthread_mutex_lock(&gate);while(!entered)pthread_cond_wait(&ready,&gate);pthread_mutex_unlock(&gate);
    assert(!graph_replace(&h,0,&bad_variant));assert(!bad_variant.live());assert(graph_read(&h,0,old_check,NULL));assert(graph_replace(&h,0,&new_variant));assert(!old_variant.live());assert(graph_read(&h,1,new_check,NULL));assert(!graph_read(&h,0,never,NULL));assert(!graph_update(&h,0,2,updates));assert(!graph_replace(&h,0,&changed_variant));
    assert(graph_replace(&h,1,&changed_variant));assert(!new_variant.live());assert(graph_read(&h,2,changed_check,NULL));
    pthread_mutex_lock(&gate);released=1;pthread_cond_broadcast(&ready);pthread_mutex_unlock(&gate);assert(!pthread_join(t,NULL));assert(!atomic_load(&live_bytes));
    assert(graph_replace(&h,2,&old_variant));assert(!changed_variant.live());char *d[]={"amount=7","--demand=amount"};assert(graph_update(&h,3,2,d));assert(!graph_replace(&h,3,&new_variant));assert(!new_variant.live());assert(graph_update(&h,3,0,NULL));assert(graph_replace(&h,3,&new_variant));
    graph_destroy(&h);assert(!old_variant.live()&&!new_variant.live()&&!bad_variant.live()&&!changed_variant.live()&&!atomic_load(&live_bytes));puts("DOC11_GRAPH_GENERATION_PASS: prelinked native variants, compatible managed source carry, changed type/role reset, failed and unstable candidates, stale tokens, stalled reader survives retirement, live=0");return 0;}
'''


def main():
    p=argparse.ArgumentParser();p.add_argument('--managed',type=Path,required=True);p.add_argument('--reactive',type=Path,required=True);p.add_argument('--headers',type=Path,default=Path(__file__).resolve().parent.parent/'runtime');p.add_argument('--sanitizer',choices=('address','thread'),default='address');a=p.parse_args();headers=a.headers.resolve()
    with tempfile.TemporaryDirectory() as tmp:
        cwd=Path(tmp);policy=(headers/'graph_generation.doc').read_text()+'source marker:int=0\n';macros=[x for x in emit(a.managed.resolve(),policy,cwd).splitlines() if x.startswith('#define F_graph_')];assert len(macros)==3 and macros==[x for x in (headers/'graph_generation_generated.h').read_text().splitlines() if x.startswith('#define F_graph_')]
        flags=['cc','-std=gnu11','-O1','-g','-pthread',*sanitizer_flags(a.sanitizer),'-fno-pie','-I',headers];objects=[]
        for name,src in VARIANTS.items():
            path=cwd/(name+'.c');path.write_text('#define main '+name+'_unused_main\n'+emit(a.reactive.resolve(),src,cwd)+'\n#undef main\n#define DOC_VARIANT_SYMBOL '+name+'_variant\n#include "graph_variant_adapter.h"\n');obj=cwd/(name+'.o');run([*flags,'-c',path,'-o',obj],cwd);objects.append(obj)
        harness=cwd/'host.c';harness.write_text(HARNESS);exe=cwd/'host';run([*flags,'-no-pie',harness,*objects,'-o',exe],cwd);out,_=run([exe],cwd);assert 'DOC11_GRAPH_GENERATION_PASS:' in out;print(out.strip())
if __name__=='__main__':main()
