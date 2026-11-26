/* Include after one DOC-generated reactive C translation unit. The linker
 * supplies a unique DOC_VARIANT_SYMBOL for this separately compiled graph. */
#ifndef DOC_VARIANT_SYMBOL
#error missing graph variant symbol
#endif
#include "graph_variant_abi.h"
#include "graph_generation_generated.h"
#ifndef DOC_VARIANT_BACKEND
#define DOC_VARIANT_BACKEND 0
#endif
#if DOC_VARIANT_BACKEND < 0 || DOC_VARIANT_BACKEND > 1
#error graph variant requires an explicit CPU (0) or GPU (1) backend
#endif
#if DOC_VARIANT_BACKEND && !defined(DOC_ENABLE_GPU)
#error GPU variant requires generated shader and native device adapter
#endif
static _Atomic int variant_active;
static void variant_clear_slots(void){for(size_t i=0;i<sizeof(states)/sizeof(states[0]);i++)if(states[i].name)*states[i].slot=(V){0};}
static void *variant_create(const GraphFact *old,size_t count){
    int expected=0;if(!atomic_compare_exchange_strong(&variant_active,&expected,1))return NULL;
    Epoch *e=calloc(1,sizeof(*e));if(!e){atomic_store(&variant_active,0);return NULL;}
    variant_clear_slots();if(!epoch_try_init(e,states,sizeof(states)/sizeof(states[0]))){free(e);atomic_store(&variant_active,0);return NULL;}
    gpu_mode=DOC_VARIANT_BACKEND;
    if((gpu_mode&&!gpu_open(e->n))||!epoch_begin(e)){gpu_close();gpu_mode=0;epoch_free(e);free(e);atomic_store(&variant_active,0);return NULL;}
    int ok=1;size_t target;
    for(size_t i=0;i<e->n&&ok;i++){const State *s=e->states+i;if(!s->name)continue;
        for(size_t j=0;j<count;j++)if(old[j].name&&truth(F_graph_carry(vi(old[j].role),vi(s->role),vi(old[j].kind),vi(s->kind),vb(!strcmp(old[j].name,s->name))))){
            Cell *c=e->cell+i;ok=store_value(&c->candidate,&c->result,old[j].value);if(ok)publish_private(e,i);break;
        }
    }
    if(ok)ok=batch(e,0,NULL,&target);
    if(!epoch_finish(e,ok)){gpu_close();gpu_mode=0;epoch_free(e);variant_clear_slots();free(e);atomic_store(&variant_active,0);return NULL;}
    return e;
}
static void variant_destroy(void *opaque){Epoch *e=opaque;gpu_close();gpu_mode=0;epoch_free(e);variant_clear_slots();free(e);atomic_store(&variant_active,0);}
static int variant_update(void *opaque,int argc,char **argv){Epoch *e=opaque;size_t target;for(int i=0;i<argc;i++)if(!strncmp(argv[i],"--backend=",10))return 0;if(!epoch_begin(e))return 0;return epoch_finish(e,batch(e,argc,argv,&target));}
typedef struct {const Epoch *e;GraphVisit visit;void *ctx;int ok;} VariantRead;
static void variant_visit(void *opaque,int64_t generation,const V *v,const unsigned char *mask,size_t n){
    (void)generation;VariantRead *r=opaque;GraphFact *facts=zalloc(n,sizeof(*facts));if(!facts)return;
    for(size_t i=0;i<n;i++)if(mask[i])facts[i]=(GraphFact){r->e->states[i].name,r->e->states[i].kind,r->e->states[i].role,v[i]};
    r->ok=r->visit(r->ctx,facts,n);free(facts);
}
static int variant_read(void *opaque,GraphVisit visit,void *ctx){Epoch *e=opaque;VariantRead r={e,visit,ctx,0};return epoch_read(e,e->n,variant_visit,&r)&&r.ok;}
static size_t variant_live(void){return atomic_load(&live_bytes);}
static uint64_t variant_device_live(void){
#ifdef DOC_ENABLE_GPU
    return gpu_pool_metrics.live;
#else
    return 0;
#endif
}
static size_t variant_dispatches(void){
#ifdef DOC_ENABLE_GPU
    return gpu_dispatches;
#else
    return 0;
#endif
}
const GraphVariant DOC_VARIANT_SYMBOL={variant_create,variant_destroy,variant_update,variant_read,variant_live,variant_device_live,variant_dispatches};
#undef F_graph_admit
#undef F_graph_source
#undef F_graph_carry
