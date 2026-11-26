#ifndef DOC_PLACED_EPOCH_H
#define DOC_PLACED_EPOCH_H
#include "placed_transport.h"
/* Explicit, single-writer host profile; normal CPU/GPU builds do not include
 * this adapter. The graph and evaluation functions are DOC-generated.
 * Receivers own decoded scalar copies, never pointers into a sender arena. */
typedef struct PlacedExecution {
    Placed transport;
    const State *states;size_t n;
    Epoch *owner;
    PlaceReceipt *receipts;V *original;
    unsigned char *lost,*closure;
    int64_t epoch_floor,durable_epoch;uint64_t durable_checksum;
} PlacedExecution;
static void placed_profile_free(PlacedExecution *p){
    if(p->owner)_Exit(1);
    if(!p->transport.roles&&!p->n)return;
    placed_free(&p->transport);free(p->receipts);free(p->original);free(p->lost);free(p->closure);*p=(PlacedExecution){0};
}
static int placed_profile_init(PlacedExecution *p,const State *states,size_t n){
    *p=(PlacedExecution){0};
    if(!placed_init(&p->transport,n))return 0;
    p->states=states;p->n=n;
    for(size_t i=0;i<n;i++)if(states[i].name&&((states[i].role!=1&&states[i].role!=2)||(states[i].kind!=I&&states[i].kind!=B))){placed_profile_free(p);return 0;}
    p->receipts=zalloc(n,sizeof(*p->receipts));p->original=zalloc(n,sizeof(*p->original));p->lost=zalloc(n,1);p->closure=zalloc(n,1);
    if(!p->receipts||!p->original||!p->lost||!p->closure){placed_profile_free(p);return 0;}return 1;
}
static int placed_profile_healthy(const PlacedExecution *p){
    int any=0;for(int i=0;i<PLACE_MAX_RESOURCES;i++)if(p->transport.resources[i].active){if(p->transport.resources[i].failed)return 0;any=1;}return any;
}
static int placed_attach(Epoch *e,PlacedExecution *p){
    if(!p->transport.roles||e->placed||p->owner||e->in_flight||e->attempt||e->committed||gpu_mode||e->states!=p->states||e->n!=p->n||!placed_profile_healthy(p))return 0;
    e->placed=p;p->owner=e;e->attempt=p->epoch_floor;return 1;
}
static int placed_detach(Epoch *e){
    if(!e->placed||e->in_flight||e->reader_slots)return 0;
    PlacedExecution *p=e->placed;p->epoch_floor=e->attempt;p->owner=NULL;e->placed=NULL;return 1;
}
static int placed_profile_join(PlacedExecution *p){
    if(p->owner&&p->owner->in_flight)return -1;
    for(int i=0;i<PLACE_MAX_RESOURCES;i++)if(p->transport.resources[i].active&&p->transport.resources[i].failed)return -1;
    return placed_join(&p->transport);
}
/* Quiescent invalidation precedes closing endpoints. A fail-stop loss
 * records the lost derived value roles; source authority is separate.
 * A committed source generation must have an acknowledged durable record. */
static void placed_loss_closure(PlacedExecution *p){
    memcpy(p->closure,p->lost,p->n);
    for(size_t i=0;i<p->n;i++)if(p->closure[i])doc_mark(i,p->closure);
}
static int placed_profile_remove(PlacedExecution *p,int resource,int fail_stop){
    if(!p->transport.roles||resource<0||resource>=PLACE_MAX_RESOURCES||!p->transport.resources[resource].active)return 0;
    Epoch *e=p->owner;int ok=0;if(e)epoch_lock(e);
    if(e&&e->in_flight)goto done;
    if(p->transport.resources[resource].failed&&!fail_stop)goto done;
    if(fail_stop&&e&&e->committed&&p->durable_epoch!=e->committed)goto done;
    memset(p->closure,0,p->n);
    if(fail_stop)for(size_t i=0;i<p->n;i++)if(p->states[i].role==2&&p->transport.roles[2*i].resource==resource)p->closure[i]=1;
    if(!placed_remove(&p->transport,resource))goto done;
    for(size_t i=0;i<p->n;i++)if(p->closure[i])p->lost[i]=1;
    if(fail_stop&&e){
        /* Lost materializations really cease to exist. Already admitted
         * readers own private copies; new readers see unavailable slots.
         * The single coordinator reconstructs from surviving source facts. */
        placed_loss_closure(p);
        for(size_t i=0;i<e->n;i++){
            if(p->lost[i]){Cell *c=e->cell+i;clear(&c->stable);clear(&c->next);clear(&c->candidate);*e->states[i].slot=(V){0};c->previous=c->result=(V){0};e->have[i]=0;}
            if(p->closure[i])e->dirty[i]=1;
        }
    }
    ok=1;
done:if(e)epoch_unlock(e);return ok;
}
static int placed_prepare_epoch(Epoch *e,int argc,char **argv){
    PlacedExecution *p=e->placed;if(gpu_mode||!placed_profile_healthy(p))return 0;
    int loss=0;for(size_t i=0;i<e->n;i++)loss|=p->lost[i];
    for(int i=0;i<argc;i++)if(!strncmp(argv[i],"--backend=",10)||(loss&&!strncmp(argv[i],"--demand=",9)))return 0;
    /* Full repair of a lost derived cache, including its transitive user
     * region. The compiler emits direct successor relations in doc_mark.
     * A lost slot remains unavailable until a new stabilization commits. */
    if(loss){
        placed_loss_closure(p);
        for(size_t i=0;i<e->n;i++){if(p->lost[i])e->have[i]=0;if(p->closure[i])e->dirty[i]=1;}
    }return 1;
}
static void placed_finish_epoch(Epoch *e,int success){
    PlacedExecution *p=e->placed;p->epoch_floor=e->attempt;
    if(success)memset(p->lost,0,p->n);
}
static int placed_evaluate(Epoch *e,size_t id){
    if(id>=e->n)return 0;
    PlacedExecution *p=e->placed;const State *s=e->states+id;size_t role=2*id+1;
    if(s->role!=2||!s->name)return 0;
    PlaceRole token=p->transport.roles[role];if(!placed_current(&p->transport,role,token.resource,token.generation))return 0;
    memset(p->receipts,0,e->n*sizeof(*p->receipts));int ok=1;
    for(size_t i=0;i<s->ndeps&&ok;i++){
        size_t dep=s->deps[i];if(dep>=id||!e->have[dep]||e->dirty[dep]||epoch_cancelled(e)){ok=0;break;}
        V old=*e->states[dep].slot,copy;PlaceReceipt *receipt=p->receipts+dep;
        if(old.kind!=e->states[dep].kind){ok=0;break;}
        int rc=placed_transfer(&p->transport,e->attempt,dep,id,old,receipt,&copy);
        if(rc<0){ok=0;break;}
        if(!rc){p->original[dep]=old;*e->states[dep].slot=copy;}
    }
    /* The generated evaluator actually reads the decoded premise copies.
     * No parallel worker runs in this bounded profile. Snapshot readers
     * select Cell.previous throughout the open attempt, never these slots. */
    if(ok)ok=evaluate(e,id,NULL);
    for(size_t i=0;i<s->ndeps;i++){size_t dep=s->deps[i];if(dep<e->n&&p->receipts[dep].seen){*e->states[dep].slot=p->original[dep];p->receipts[dep]=(PlaceReceipt){0};p->original[dep]=(V){0};}}
    return ok&&!epoch_cancelled(e)&&placed_current(&p->transport,role,token.resource,token.generation);
}
static int placed_execute(Epoch *e,size_t tasks){
    if(gpu_mode||!placed_profile_healthy(e->placed))return 0;
    for(size_t k=0;k<tasks;k++)if(!placed_evaluate(e,e->queue[k]))return 0;
    return 1;
}
#endif
