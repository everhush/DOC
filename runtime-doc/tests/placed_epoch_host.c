/* Native generated graph, explicit host placement (not DOC source hints). */
#define DOC_ENABLE_PLACED
#define main generated_main
#include "generated.c"
#undef main
#include <assert.h>
static V oracle[sizeof(states)/sizeof(states[0])];
static size_t n=sizeof(states)/sizeof(states[0]);
static pthread_mutex_t gate=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t ready=PTHREAD_COND_INITIALIZER;
static int pause_eval,entered,released;
static V hold_x(void){if(pause_eval){pthread_mutex_lock(&gate);entered=1;pthread_cond_broadcast(&ready);while(!released)pthread_cond_wait(&ready,&gate);pthread_mutex_unlock(&gate);}return E_x();}
static void *cancelled_writer(void *opaque){Epoch *e=opaque;size_t target;char *updates[]={"a=8"};assert(!batch(e,1,updates,&target));assert(!epoch_finish(e,1));return NULL;}
static void snapshot(void *ctx,int64_t generation,const V *v,const unsigned char *mask,size_t count){
    int capture=*(int*)ctx;assert(generation>0&&count==n);
    for(size_t i=0;i<n;i++)if(states[i].name){assert(mask[i]);if(capture)oracle[i]=v[i];else assert(equal(oracle[i],v[i]));}
}
static void pinned_snapshot(void *ctx,int64_t generation,const V *v,const unsigned char *mask,size_t count){
    int capture=0;snapshot(&capture,generation,v,mask,count);
    pthread_mutex_lock(&gate);entered=1;pthread_cond_broadcast(&ready);while(!released)pthread_cond_wait(&ready,&gate);pthread_mutex_unlock(&gate);
    snapshot(&capture,generation,v,mask,count);(void)ctx;
}
static void *pinned_reader(void *opaque){Epoch *e=opaque;assert(epoch_read(e,e->n,pinned_snapshot,NULL));return NULL;}
static void verify(Epoch *e,int capture){assert(epoch_read(e,e->n,snapshot,&capture));}
static void reset_slots(void){for(size_t i=0;i<n;i++)if(states[i].name)*states[i].slot=(V){0};}
int main(int argc,char **argv){
    assert(argc==2);doc_output_root=argv[1];Epoch e;size_t target;
    char *updates[]={"a=7","b=-2"};
    epoch_init(&e,states,n);assert(epoch_begin(&e));assert(batch(&e,2,updates,&target));assert(epoch_finish(&e,1));verify(&e,1);epoch_free(&e);reset_slots();
    State copy[sizeof(states)/sizeof(states[0])];memcpy(copy,states,sizeof copy);size_t x_index=n;for(size_t i=0;i<n;i++)if(states[i].name&&!strcmp(states[i].name,"x"))x_index=i;assert(x_index<n);copy[x_index].eval=hold_x;
    PlacedExecution p;assert(placed_profile_init(&p,copy,n));assert(placed_profile_join(&p)==0);assert(placed_profile_join(&p)==1);assert(placed_profile_join(&p)==2);
    epoch_init(&e,copy,n);assert(placed_attach(&e,&p));assert(epoch_begin(&e));assert(placed_profile_join(&p)==-1);assert(!placed_profile_remove(&p,0,0));assert(batch(&e,2,updates,&target));assert(epoch_finish(&e,1));verify(&e,0);assert(p.transport.sent&&p.transport.sent==p.transport.received);
    size_t a=find_state(&e,"a",1),x=find_state(&e,"x",1),end=find_state(&e,"end",3);assert(a<n&&x<n&&end<n&&num(*states[end].slot)==45);
    assert(!placed_profile_remove(&p,0,1)); /* no durable acknowledgement yet */
    /* Pause the real generated evaluator after TCP premise copies have
       been installed. Readers still see the old publication; cancellation
       invalidates the entire attempt even when evaluation succeeds. */
    int64_t old_generation=e.committed;pause_eval=1;assert(epoch_begin(&e));int64_t ticket=epoch_ticket(&e);pthread_t writer;assert(!pthread_create(&writer,NULL,cancelled_writer,&e));
    pthread_mutex_lock(&gate);while(!entered)pthread_cond_wait(&ready,&gate);pthread_mutex_unlock(&gate);
    verify(&e,0);assert(epoch_cancel(&e,ticket));pthread_mutex_lock(&gate);released=1;pthread_cond_broadcast(&ready);pthread_mutex_unlock(&gate);
    assert(!pthread_join(writer,NULL));pause_eval=0;assert(e.committed==old_generation&&!epoch_cancel(&e,ticket));verify(&e,0);
    unsigned char stale[PLACE_WIRE_BYTES];assert(place_frame(&p.transport,e.committed,a,x,*states[a].slot,stale));
    int64_t saved=e.committed;uint64_t sent=p.transport.sent;
    assert(placed_profile_join(&p)==3);assert(placed_profile_remove(&p,1,0));verify(&e,0);assert(epoch_begin(&e));assert(batch(&e,0,NULL,&target));assert(epoch_finish(&e,1));assert(!e.evaluations&&p.transport.sent==sent);verify(&e,0);
    PlaceReceipt receipt={0};V got=vi(0);assert(place_admit(&p.transport,e.committed,a,x,I,&receipt,stale,sizeof stale,&got)==-1&&!receipt.seen);
    assert(e.committed>saved);assert(placed_authority_save(&e,"authority.cp"));int64_t durable=e.committed;
    /* A real broken TCP endpoint poisons an attempted source update. No
       publication despite the caller requesting success. */
    int dead=p.transport.roles[2*x+1].resource;assert(!shutdown(p.transport.resources[dead].rx,SHUT_RDWR));
    char *bad[]={"a=8"};assert(epoch_begin(&e));assert(!batch(&e,1,bad,&target));assert(!epoch_finish(&e,1));assert(e.committed==durable);verify(&e,0);
    assert(p.transport.resources[dead].failed);assert(!placed_profile_remove(&p,dead,0));
    /* Fail-stop invalidation and affected-region reconstruction. At least
       one other resource survives. Full repair is required while loss is pending. */
    entered=released=0;pthread_t reader;assert(!pthread_create(&reader,NULL,pinned_reader,&e));
    pthread_mutex_lock(&gate);while(!entered)pthread_cond_wait(&ready,&gate);pthread_mutex_unlock(&gate);
    assert(placed_profile_remove(&p,dead,1));assert(placed_profile_join(&p)>=0);
    size_t lost=0;for(size_t i=0;i<n;i++)if(p.lost[i]){lost++;assert(!e.have[i]&&e.dirty[i]&&states[i].slot->x==0);}
    assert(lost);int capture=0;assert(!epoch_read(&e,e.n,snapshot,&capture));assert(placed_observe(&e,e.n,snapshot,&capture));verify(&e,0);assert(e.evaluations>0);
    pthread_mutex_lock(&gate);released=1;pthread_cond_broadcast(&ready);pthread_mutex_unlock(&gate);assert(!pthread_join(reader,NULL));assert(placed_authority_save(&e,"authority.cp"));durable=e.committed;
    /* Lose all physical resources and all in-memory materializations.
       Reconstruct using the on-disk authoritative source facts, not a
       retained derived state or a host-authored application evaluator. */
    assert(placed_detach(&e));epoch_free(&e);reset_slots();
    for(int i=0;i<PLACE_MAX_RESOURCES;i++)if(p.transport.resources[i].active)assert(placed_profile_remove(&p,i,1));
    assert(placed_profile_join(&p)==0);assert(placed_profile_join(&p)==1);
    epoch_init(&e,copy,n);assert(placed_attach(&e,&p));sent=p.transport.sent;
    size_t bytes_n=0;unsigned char *bytes=output_read("authority.cp",&bytes_n);assert(bytes&&bytes_n>96);bytes[bytes_n-1]^=1;assert(output_atomic("broken.cp",bytes,bytes_n));free(bytes);
    assert(!placed_authority_restore(&e,"broken.cp")&&!e.in_flight&&!e.committed&&p.transport.sent==sent);
    /* Another well-formed record for the same epoch is not the one the
     * surviving authority acknowledged. A valid checksum alone is insufficient. */
    bytes=output_read("authority.cp",&bytes_n);assert(bytes&&bytes_n>128);put_le(bytes+120,999,8);put_le(bytes+bytes_n-8,checkpoint_checksum(bytes,bytes_n-8),8);assert(output_atomic("other.cp",bytes,bytes_n));free(bytes);
    assert(!placed_authority_restore(&e,"other.cp")&&!e.in_flight&&!e.committed&&p.transport.sent==sent);
    assert(placed_authority_restore(&e,"authority.cp"));assert(e.committed>durable&&p.transport.sent>sent);verify(&e,0);
    assert(!placed_authority_restore(&e,"authority.cp"));assert(placed_detach(&e));epoch_free(&e);reset_slots();int descriptors[PLACE_MAX_RESOURCES*2],count=0;for(int i=0;i<PLACE_MAX_RESOURCES;i++)if(p.transport.resources[i].active){descriptors[count++]=p.transport.resources[i].tx;descriptors[count++]=p.transport.resources[i].rx;}
    placed_profile_free(&p);placed_profile_free(&p);for(int i=0;i<count;i++){errno=0;assert(fcntl(descriptors[i],F_GETFD)==-1&&errno==EBADF);}assert(!atomic_load(&live_bytes));
    puts("DOC11_PLACED_EPOCH_PASS: generated graph consumes TCP premises, oracle parity, protected reader/cancellation, quiescent join/drain and cutoff, broken transport rollback, role invalidation, actual eviction, observation-triggered affected-region and durable full-loss reconstruction, corrupt and unacknowledged checkpoint rejection and closed endpoints; live=0");return 0;
}
