#ifndef DOC_EPOCH_AUTHORITY_H
#define DOC_EPOCH_AUTHORITY_H
#include "epoch_policy_generated.h"
#include "graph_reader_slots.h"
/* Single-writer host boundary. All external snapshot/cancel calls must finish
 * before epoch_free. A snapshot callback borrows its private copy for the
 * duration of the call only; no runtime-owned pointers may escape. */
static void epoch_lock(Epoch *e){if(pthread_mutex_lock(&e->authority))_Exit(1);}
static void epoch_unlock(Epoch *e){if(pthread_mutex_unlock(&e->authority))_Exit(1);}
static int64_t epoch_ticket(Epoch *e){epoch_lock(e);int64_t t=e->in_flight?e->attempt:0;epoch_unlock(e);return t;}
static int epoch_cancel(Epoch *e,int64_t ticket){epoch_lock(e);int ok=truth(F_life_cancel(vb(e->in_flight),vi(e->attempt),vi(ticket)));if(ok)atomic_store(&e->cancelled,1);epoch_unlock(e);return ok;}
static int epoch_cancelled(const Epoch *e){return atomic_load(&e->cancelled);}
static int store_value(Region *owner,V *out,V v);
typedef void (*EpochReader)(void *,int64_t,const V *,const unsigned char *,size_t);
static int epoch_read(Epoch *e,size_t target,EpochReader visit,void *ctx){
    if(!visit||target>e->n||active||failure_target)return 0;
    epoch_lock(e);
    int slot=graph_slot_take(&e->reader_slots);
    if(slot<0){epoch_unlock(e);return 0;}
    Region owner={0};V *values=zalloc(e->n,sizeof(*values));unsigned char *ready=zalloc(e->n,1);int ok=values&&ready;int64_t generation=e->committed;
    for(size_t i=0;i<e->n&&ok;i++)if(target==e->n||target==i){
        const State *s=e->states+i;
        if(!s->name){if(target==i)ok=0;continue;}
        unsigned char have=e->in_flight?e->saved_have[i]:e->have[i],dirty=e->in_flight?e->saved_dirty[i]:e->dirty[i];
        if(!truth(F_life_visible(vb(have),vb(dirty)))){ok=0;break;}
        V v=e->in_flight?e->cell[i].previous:*s->slot;
        ok=store_value(&owner,values+i,v);if(ok)ready[i]=1;
    }
    epoch_unlock(e);
    if(ok)visit(ctx,generation,values,ready,e->n);
    clear(&owner);free(values);free(ready);
    epoch_lock(e);if(!graph_slot_drop(&e->reader_slots,slot))_Exit(1);epoch_unlock(e);return ok;
}
#endif
