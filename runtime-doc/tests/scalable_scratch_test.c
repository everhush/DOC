#define DOC_REACTIVE_VALUES
#define DOC_TEST_ALLOC_FAILURE
#include "value_primitives.h"
#include <assert.h>
static int once(size_t budget){
 jmp_buf j;failure_target=&j;atomic_store(&allocation_budget,budget);size_t base=atomic_load(&live_bytes);
 if(setjmp(j)){failure_target=NULL;assert(!active);assert(atomic_load(&live_bytes)==base);return 0;}
 Region parent;push(&parent);
 V result=v_recur(VL(0,7),x,v_eq(v_get(x,vi(0)),vi(20)),v_append(v_append(v_empty(),v_add(v_get(x,vi(0)),vi(1))),v_mul(v_get(x,vi(1)),vi(2))));
 assert(num(v_get(result,vi(0)))==20&&num(v_get(result,vi(1)))==7*1048576);
 Scratch scratch={0};Region work;push(&work);work.scratch=&scratch;
 void *a=alloc_in(&work,16),*b=alloc_in(&work,1024);assert(a&&b);memset(a,0,16);memset(b,0,1024);assert(atomic_load(&live_bytes)>=base+DOC_SCRATCH_BYTES+1024);reset_region(&work);assert(work.scratch->data&&work.bytes==0);pop(&work);
 pop(&parent);failure_target=NULL;assert(!active&&atomic_load(&live_bytes)==base);return 1;
}
int main(void){size_t first=0;for(size_t k=0;k<1000;k++){if(once(k)){first=k;break;}}assert(first==65);for(size_t i=0;i<1000;i++)assert(once(SIZE_MAX));printf("DOC9_SCRATCH_PASS: logical_fault_ordinals=%zu repeated_scopes=1000 peak=%zu allocations=%zu live=%zu\n",first,(size_t)peak_bytes,(size_t)allocs,(size_t)live_bytes);return 0;}
