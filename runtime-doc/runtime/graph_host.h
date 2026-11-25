#ifndef DOC_GRAPH_HOST_H
#define DOC_GRAPH_HOST_H
#include "graph_variant_abi.h"
#include "graph_generation_generated.h"
#include "graph_reader_slots.h"
#include <pthread.h>
/* Single-writer prelinked-variant coordinator. Reader callbacks see private
 * materializations and may overlap a replacement. The caller must quiesce
 * all host entry points before shutdown; variants remain linked throughout.
 * Admission is bounded by independent slots, not by ownership counts. */
typedef struct {pthread_mutex_t lock;const GraphVariant *variant;void *instance;int64_t generation;uint64_t reader_slots;} GraphHost;
typedef struct {Region owner;GraphFact *facts;size_t n;} GraphCopy;
typedef void (*GraphReader)(void *,int64_t,const GraphFact *,size_t);
static void graph_lock(GraphHost *g){if(pthread_mutex_lock(&g->lock))_Exit(1);}
static void graph_unlock(GraphHost *g){if(pthread_mutex_unlock(&g->lock))_Exit(1);}
static int graph_init(GraphHost *g,const GraphVariant *v){*g=(GraphHost){0};if(!v||pthread_mutex_init(&g->lock,NULL))return 0;g->instance=v->create(NULL,0);if(!g->instance){pthread_mutex_destroy(&g->lock);return 0;}g->variant=v;return 1;}
static void graph_destroy(GraphHost *g){if(g->reader_slots)_Exit(1);g->variant->destroy(g->instance);if(pthread_mutex_destroy(&g->lock))_Exit(1);*g=(GraphHost){0};}
static int graph_update(GraphHost *g,int64_t ticket,int argc,char **argv){graph_lock(g);int ok=ticket==g->generation&&g->variant->update(g->instance,argc,argv);graph_unlock(g);return ok;}
static int graph_copy(void *opaque,const GraphFact *facts,size_t n){
    GraphCopy *c=opaque;if(n>SIZE_MAX/sizeof(*c->facts))return 0;c->facts=calloc(n?n:1,sizeof(*c->facts));if(!c->facts)return 0;c->n=n;
    jmp_buf jump;failure_target=&jump;failure_message=NULL;if(setjmp(jump)){failure_target=NULL;return 0;}
    for(size_t i=0;i<n;i++)if(facts[i].name){c->facts[i]=facts[i];size_t z=strlen(facts[i].name)+1;char *name=alloc_in(&c->owner,z);memcpy(name,facts[i].name,z);c->facts[i].name=name;c->facts[i].value=own(&c->owner,facts[i].value);}
    failure_target=NULL;return 1;
}
static void graph_copy_free(GraphCopy *c){clear(&c->owner);free(c->facts);}
static int graph_read(GraphHost *g,int64_t ticket,GraphReader visit,void *ctx){
    if(!visit||active||failure_target)return 0;
    GraphCopy c={0};graph_lock(g);
    int slot=ticket==g->generation?graph_slot_take(&g->reader_slots):-1;
    if(slot<0){graph_unlock(g);return 0;}
    int ok=g->variant->read(g->instance,graph_copy,&c);graph_unlock(g);
    if(ok)visit(ctx,ticket,c.facts,c.n);
    graph_copy_free(&c);
    graph_lock(g);if(!graph_slot_drop(&g->reader_slots,slot))_Exit(1);graph_unlock(g);return ok;
}
typedef struct {const GraphVariant *next;void *candidate;} GraphReplacement;
static int graph_prepare(void *opaque,const GraphFact *facts,size_t n){GraphReplacement *r=opaque;r->candidate=r->next->create(facts,n);return !!r->candidate;}
static int graph_replace(GraphHost *g,int64_t ticket,const GraphVariant *next){
    if(!next)return 0;graph_lock(g);int ok=0;
    if(next!=g->variant&&truth(F_graph_admit(vb(1),vi(g->generation),vi(ticket)))){
        GraphReplacement r={next,NULL};
        /* read() rejects an unstable old graph. Candidate copies all carried
         * facts while the old snapshot is still protected; no pointer escapes. */
        if(g->variant->read(g->instance,graph_prepare,&r)){
            g->variant->destroy(g->instance);g->variant=next;g->instance=r.candidate;g->generation++;ok=1;
        }
    }
    graph_unlock(g);return ok;
}
#undef F_graph_admit
#undef F_graph_source
#undef F_graph_carry
#endif
