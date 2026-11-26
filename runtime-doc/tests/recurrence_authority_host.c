#define main generated_main
#include "generated.c"
#undef main
#include "recurrence_policy_generated.h"
#include <assert.h>
static void expect(Epoch *e,size_t a,size_t b,size_t sum,int64_t va,int64_t vb_){assert(!e->in_flight&&e->have[a]&&e->have[b]&&e->have[sum]);assert(num(*e->states[a].slot)==va&&num(*e->states[b].slot)==vb_&&num(*e->states[sum].slot)==va+vb_);}
static void reject(Epoch *e,const size_t *carry,const V *defaults,const Fact *facts,size_t nf,uint64_t ep,size_t a,size_t b,size_t sum){int64_t committed=e->committed;size_t bytes=atomic_load(&live_bytes);assert(epoch_begin(e));assert(!recurrence_successor_candidate(e,carry,defaults,facts,nf,ep));assert(!epoch_finish(e,1));assert(e->committed==committed&&atomic_load(&live_bytes)==bytes);expect(e,a,b,sum,1,2);}
int main(void){
    for(int mask=0;mask<64;mask++){int a=mask&1,b=!!(mask&2),c=!!(mask&4),d=!!(mask&8),f=!!(mask&16),g=!!(mask&32);
        assert(truth(F_rec_fact(vb(a),vb(b),vb(c),vb(d),vb(f),vb(g)))==(a&&b&&c&&d&&f&&g));
        assert(truth(F_rec_carry(vb(a),vb(b),vb(c),vb(d)))==(a&&b&&c&&d));
        assert(truth(F_rec_prepare(vb(a),vb(b),vb(c),vb(d)))==(a&&b&&(c?!d:d)));
        assert(num(F_rec_pick(vb(a),vb(b)))==(a?(b?-1:1):(b?2:0)));
        assert(num(F_rec_stop(vb(a),vb(b),vb(c)))==(a?(b?1:(c?-1:0)):(c?1:0)));
    }
    Epoch e;Region defaults_owner={0};size_t n=sizeof(states)/sizeof(states[0]);epoch_init(&e,states,n);
    size_t *carry=zalloc(n,sizeof(*carry));V *defaults=zalloc(n,sizeof(*defaults));assert(carry&&defaults);for(size_t i=0;i<n;i++)carry[i]=n;
    size_t a=find_state(&e,"a",1),b=find_state(&e,"b",1),sum=find_state(&e,"sum",3),done=find_state(&e,"done",4);assert(a<n&&b<n&&sum<n&&done<n);
    assert(!recurrence_initial_candidate(&e,&defaults_owner,defaults,NULL));assert(!recurrence_successor_candidate(&e,carry,defaults,NULL,0,1));
    assert(epoch_begin(&e));assert(recurrence_initial_candidate(&e,&defaults_owner,defaults,NULL));assert(!recurrence_initial_candidate(&e,&defaults_owner,defaults,NULL));assert(!epoch_finish(&e,1));assert(!e.committed);
    clear(&defaults_owner);memset(defaults,0,n*sizeof(*defaults));assert(epoch_begin(&e));assert(recurrence_initial_candidate(&e,&defaults_owner,defaults,NULL));assert(epoch_finish(&e,1));expect(&e,a,b,sum,1,2);
    size_t baseline=atomic_load(&live_bytes);int64_t stable=e.committed;
    assert(epoch_begin(&e));assert(!recurrence_initial_candidate(&e,&defaults_owner,defaults,NULL));assert(!epoch_finish(&e,1));assert(e.committed==stable&&atomic_load(&live_bytes)==baseline);
    carry[a]=n+1;reject(&e,carry,defaults,NULL,0,1,a,b,sum);carry[a]=done;reject(&e,carry,defaults,NULL,0,1,a,b,sum);carry[a]=n;
    carry[sum]=a;reject(&e,carry,defaults,NULL,0,1,a,b,sum);carry[sum]=n;
    Fact invalid[]={ {1,n+1,vi(9)}, {1,sum,vi(9)}, {1,a,vb(1)} };
    for(size_t i=0;i<sizeof(invalid)/sizeof(invalid[0]);i++)reject(&e,carry,defaults,invalid+i,1,1,a,b,sum);
    Fact duplicate[]={{1,a,vi(7)},{1,a,vi(8)}};reject(&e,carry,defaults,duplicate,2,1,a,b,sum);
    carry[a]=b;reject(&e,carry,defaults,duplicate,1,1,a,b,sum);carry[a]=n;
    reject(&e,carry,defaults,NULL,1,1,a,b,sum);reject(&e,carry,defaults,NULL,0,0,a,b,sum);
    Fact update={1,a,vi(9)};assert(epoch_begin(&e));assert(recurrence_successor_candidate(&e,carry,defaults,&update,1,1));assert(!recurrence_successor_candidate(&e,carry,defaults,&update,1,1));assert(!epoch_finish(&e,1));expect(&e,a,b,sum,1,2);assert(e.committed==stable&&atomic_load(&live_bytes)==baseline);
    carry[a]=b;carry[b]=a;assert(epoch_begin(&e));assert(recurrence_successor_candidate(&e,carry,defaults,NULL,0,1));assert(epoch_finish(&e,1));expect(&e,a,b,sum,2,1);
    carry[a]=n;carry[b]=n;assert(epoch_begin(&e));assert(recurrence_successor_candidate(&e,carry,defaults,&update,1,1));assert(epoch_finish(&e,1));expect(&e,a,b,sum,9,2);
    epoch_free(&e);clear(&defaults_owner);free(carry);free(defaults);assert(!atomic_load(&live_bytes));puts("DOC11_RECURRENCE_AUTHORITY_PASS: generated DOC policies, invalid direct host carry/fact, incomplete and repeated candidates cannot publish, simultaneous carries and recovery, live=0");return 0;
}
