/* Specialized dependency families. No bytecode or runtime expression interpreter.
 * One output slot per lane; all joins complete before owned list publication.
 * Use the same hardware/grain worker policy as ordinary native frontiers.
 */
#define DOC_FAMILY_LIMIT 4096u
static size_t doc_workers(size_t count);
static _Thread_local int doc_outer_parallel;
typedef int (*doc_lane_fn)(const doc_value*,int64_t,int64_t*);
typedef struct {const doc_value *v;const int64_t *in;int64_t *out;doc_lane_fn fn;size_t start,end;int ok;} doc_family_job;
static void *doc_family_work(void *p){
    doc_family_job *j=p;j->ok=1;
    for(size_t i=j->start;i<j->end;i++)if(!j->fn(j->v,j->in[i],&j->out[i])){j->ok=0;break;}
    return NULL;
}
static int doc_map_ints(const doc_value *v,doc_value xs,doc_lane_fn fn,doc_value *out){
    if(xs.kind!=DOC_LIST||xs.len>DOC_FAMILY_LIMIT)return 0;
    if(!xs.len){*out=(doc_value){.kind=DOC_LIST};return 1;}
    int64_t *values=malloc(xs.len*sizeof(*values));if(!values)return 0;
    size_t workers=doc_outer_parallel?1:doc_workers(xs.len);
    doc_family_job jobs[workers];pthread_t threads[workers];size_t started=0;
    for(size_t w=0;w<workers;w++)jobs[w]=(doc_family_job){v,xs.data,values,fn,w*xs.len/workers,(w+1)*xs.len/workers,0};
    for(size_t w=1;w<workers;w++){
        if(pthread_create(&threads[started],NULL,doc_family_work,&jobs[w]))break;
        started++;
    }
    doc_family_work(&jobs[0]);
    for(size_t w=started+1;w<workers;w++)doc_family_work(&jobs[w]);
    for(size_t w=0;w<started;w++)if(pthread_join(threads[w],NULL))abort();
    for(size_t w=0;w<workers;w++)if(!jobs[w].ok){free(values);return 0;}
    fprintf(stderr,"DOC_AOT_FAMILY: lanes=%zu workers=%zu\n",xs.len,started+1);
    *out=(doc_value){.kind=DOC_LIST,.len=xs.len,.data=values};return 1;
}
