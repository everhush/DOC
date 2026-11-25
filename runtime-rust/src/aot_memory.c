/* Native allocation instrumentation. Aggregate counters measure bytes, never
 * references to individual values, and never decide lifetime or reclamation.
 * Ownership and phase completion decide all frees. */
#include <stdatomic.h>
typedef union {max_align_t alignment;size_t bytes;} doc_alloc_header;
static _Atomic size_t doc_live,doc_peak,doc_allocated,doc_freed,doc_calls;
static size_t doc_fail_at;
static int doc_trace_memory;
static void *doc_malloc(size_t n){
    size_t call=atomic_fetch_add_explicit(&doc_calls,1,memory_order_relaxed)+1;
    if((doc_fail_at&&call==doc_fail_at)||n>SIZE_MAX-sizeof(doc_alloc_header))return NULL;
    doc_alloc_header *p=malloc(sizeof(*p)+n);if(!p)return NULL;p->bytes=n;
    atomic_fetch_add_explicit(&doc_allocated,n,memory_order_relaxed);
    size_t live=atomic_fetch_add_explicit(&doc_live,n,memory_order_relaxed)+n;
    size_t old=atomic_load_explicit(&doc_peak,memory_order_relaxed);
    while(old<live&&!atomic_compare_exchange_weak_explicit(&doc_peak,&old,live,memory_order_relaxed,memory_order_relaxed)){}
    return p+1;
}
static void *doc_calloc(size_t n,size_t w){
    if(w&&n>SIZE_MAX/w)return NULL;
    void *p=doc_malloc(n*w);if(p)memset(p,0,n*w);return p;
}
static void doc_free(void *v){
    if(!v)return;
    doc_alloc_header *p=(doc_alloc_header*)v-1;
    atomic_fetch_sub_explicit(&doc_live,p->bytes,memory_order_relaxed);
    atomic_fetch_add_explicit(&doc_freed,p->bytes,memory_order_relaxed);
    free(p);
}
static void doc_memory_report(const char *phase){
    if(doc_trace_memory)fprintf(stderr,"DOC_AOT_MEMORY: phase=%s live=%zu peak=%zu allocated=%zu freed=%zu calls=%zu\n",phase,
        atomic_load(&doc_live),atomic_load(&doc_peak),atomic_load(&doc_allocated),atomic_load(&doc_freed),atomic_load(&doc_calls));
}
#define malloc doc_malloc
#define calloc doc_calloc
#define free doc_free
