/* Stage-0 native platform and transaction support. No DOC parser or interpreter. */
typedef struct { doc_value value[DOC_N]; unsigned char dirty[DOC_N]; } doc_state;
typedef struct { const doc_state *state; const size_t *ids; size_t start,end; doc_value *results; unsigned char *ok; int outer_parallel; } doc_job;
static int doc_fail(const char *msg) { fprintf(stderr,"DOC_AOT: %s\n",msg); return 0; }
static void doc_state_drop(doc_state *s){for(size_t i=0;i<DOC_N;i++)doc_drop(&s->value[i]);}
static int doc_state_copy(doc_state *s,const doc_value *values){
    memset(s,0,sizeof(*s));
    for(size_t i=0;i<DOC_N;i++)if(!doc_clone(values[i],&s->value[i])){doc_state_drop(s);return doc_fail("value allocation failed");}
    return 1;
}
static doc_state doc_startup;
static int doc_startup_ready;
static int doc_reset(doc_state *s){
    if(!doc_state_copy(s,doc_startup_ready?doc_startup.value:doc_initial))return 0;
    for(size_t i=0;i<DOC_N;i++)s->dirty[i]=!doc_source[i];return 1;
}
static int doc_assign(doc_state *s,size_t id,doc_value value){
    if(!doc_equal(s->value[id],value)){
        doc_value next;if(!doc_clone(value,&next))return doc_fail("value allocation failed");
        doc_drop(&s->value[id]);s->value[id]=next;doc_mark(id,s->dirty);
    }return 1;
}
static void *doc_work(void *ptr) {
    doc_job *j=ptr;
    int previous=doc_outer_parallel;doc_outer_parallel=j->outer_parallel;
    for(size_t k=j->start;k<j->end;k++){
        size_t id=j->ids[k];
        j->ok[k]=(unsigned char)doc_functions[id](j->state->value,&j->results[k]);
    }
    doc_outer_parallel=previous;
    return NULL;
}
/* Host capacity, not source-language scheduling. The generated graph/family
 * limits bound count to 4096, so grain bounds temporary worker metadata to
 * at most 128 slots; there is no separate arbitrary participant ceiling. */
static size_t doc_worker_count(size_t count,size_t hardware,size_t request){
    if(count<64)return 1;
    if(!hardware)hardware=1;
    if(!request||request>hardware)request=hardware;
    size_t grain=count/32;
    return request>grain?grain:request;
}
static size_t doc_hardware_workers(void){
    cpu_set_t mask;
    if(sched_getaffinity(0,sizeof(mask),&mask)==0){
        int n=CPU_COUNT(&mask);return n>0?(size_t)n:1;
    }
    // Linux can expose affinity masks larger than cpu_set_t. Allocate only
    // platform mask metadata and retry when the kernel says the mask is small.
    if(errno!=EINVAL)return 1;
    for(size_t bits=2u*CPU_SETSIZE;bits<=SIZE_MAX/2;bits*=2){
        cpu_set_t *large=CPU_ALLOC(bits);
        if(!large)return 1;
        size_t bytes=CPU_ALLOC_SIZE(bits);
        int rc=sched_getaffinity(0,bytes,large),error=errno;
        int n=rc==0?CPU_COUNT_S(bytes,large):0;
        CPU_FREE(large);
        if(rc==0)return n>0?(size_t)n:1;
        if(error!=EINVAL)return 1;
    }
    return 1;
}
static size_t doc_workers(size_t count) {
    if(count<64)return 1;
    size_t hardware=doc_hardware_workers(),request=hardware;
    const char *raw=getenv("DOC_WORKERS");
    if(raw && *raw){char *end=NULL;errno=0;unsigned long long x=strtoull(raw,&end,10);
        if(!errno && *end=='\0' && *raw!='-' && x>0 && x<hardware)request=(size_t)x;}
    return doc_worker_count(count,hardware,request);
}
static int doc_stabilize(doc_state *s,size_t target) {
    unsigned char needed[DOC_N]; size_t ids[DOC_N]; doc_value result[DOC_N]; unsigned char ok[DOC_N];
    if(target<DOC_N)doc_need(target,needed);else memset(needed,1,sizeof(needed));
    size_t evaluations=0;
    /* Static independent levels; candidates read one immutable valuation. */
    for(size_t level=0;level<DOC_LEVELS;level++){
        size_t count=0;
        for(size_t k=doc_offsets[level];k<doc_offsets[level+1];k++){
            size_t id=doc_ids[k]; if(needed[id]&&s->dirty[id])ids[count++]=id;
        }
        if(!count)continue;
        size_t workers=doc_workers(count);
        doc_job jobs[workers]; pthread_t threads[workers]; size_t started=0;
        for(size_t w=0;w<workers;w++)
            jobs[w]=(doc_job){s,ids,w*count/workers,(w+1)*count/workers,result,ok,workers>1};
        for(size_t w=1;w<workers;w++){
            if(pthread_create(&threads[started],NULL,doc_work,&jobs[w])!=0)break;
            started++;
        }
        doc_work(&jobs[0]);
        for(size_t w=started+1;w<workers;w++)doc_work(&jobs[w]);
        for(size_t w=0;w<started;w++)if(pthread_join(threads[w],NULL)!=0)abort();
        if(started)fprintf(stderr,"DOC_AOT_PARALLEL_FRONTIER: workers=%zu candidates=%zu\n",started+1,count);
        for(size_t k=0;k<count;k++)if(!ok[k]){
            fprintf(stderr,"DOC_AOT: checked expression/resource failure at %s; no candidate publication\n",doc_names[ids[k]]);
            for(size_t j=0;j<count;j++)if(ok[j])doc_drop(&result[j]);
            return 0;
        }
        for(size_t k=0;k<count;k++){
            size_t id=ids[k];int changed=!doc_equal(s->value[id],result[k]);
            doc_drop(&s->value[id]);s->value[id]=result[k];s->dirty[id]=0;
            if(changed)doc_mark(id,s->dirty);
        }
        evaluations+=count;
    }
    fprintf(stderr,"DOC_AOT_EVALUATIONS: %zu\n",evaluations);
    return 1;
}
static size_t doc_lookup(const char *name,size_t len) {
    for(size_t i=0;i<DOC_N;i++)if(strlen(doc_names[i])==len&&!memcmp(doc_names[i],name,len))return i;
    return DOC_N;
}
static int doc_i64(const char *raw,int64_t *out) {
    while(isspace((unsigned char)*raw))raw++;
    const char *p=raw;if(*p=='-'||*p=='+')p++;
    if(*p<'0'||*p>'9')return 0;
    while(*p>='0'&&*p<='9')p++;
    while(isspace((unsigned char)*p))p++;
    if(*p)return 0;
    char *end; errno=0; intmax_t x=strtoimax(raw,&end,10);
    if(errno==ERANGE||x<INT64_MIN||x>INT64_MAX)return 0;
    *out=(int64_t)x;return 1;
}
static int doc_parse(size_t id,const char *raw,doc_value *out){
    unsigned char kind=doc_kind[id];doc_value v={.kind=kind};
    while(isspace((unsigned char)*raw))raw++;
    size_t len=strlen(raw);while(len&&isspace((unsigned char)raw[len-1]))len--;
    if(kind==DOC_INT){if(!doc_i64(raw,&v.scalar))return 0;}
    else if(kind==DOC_BOOL){
        if(len==4&&!memcmp(raw,"true",4))v.scalar=1;
        else if(len!=5||memcmp(raw,"false",5))return 0;
    }else if(kind==DOC_MAYBE){
        if(len==4&&!memcmp(raw,"none",4)){}
        else if(len>=7&&!memcmp(raw,"some(",5)&&raw[len-1]==')'){
            size_t n=len-6;char *body=malloc(n+1);if(!body)return 0;
            memcpy(body,raw+5,n);body[n]=0;int ok=doc_i64(body,&v.scalar);free(body);
            if(!ok)return 0;v.len=1;
        }else return 0;
    }else if(kind==DOC_NAT||kind==DOC_TEXT){
        const unsigned char *p=(const unsigned char*)raw;
        if(kind==DOC_NAT){
            if(!len)return 0;
            for(size_t i=0;i<len;i++)if(p[i]<'0'||p[i]>'9')return 0;
            while(len>1&&*p=='0'){p++;len--;}
        }else{
            if(len<2||p[0]!='"'||p[len-1]!='"')return 0;
            p++;len-=2;
            for(size_t i=0;i<len;i++)if(p[i]=='"'||p[i]=='\\'||p[i]=='\r'||p[i]=='\n')return 0;
            if(!doc_utf8(p,len))return 0;
        }
        if(len>DOC_LIST_LIMIT)return 0;
        if(len){unsigned char *copy=malloc(len);if(!copy)return 0;memcpy(copy,p,len);v.bytes=copy;}
        v.len=len;
    }else if(kind==DOC_LIST){
        if(len<2||raw[0]!='['||raw[len-1]!=']')return 0;
        const char *p=raw+1,*end=raw+len-1;
        while(p<end&&isspace((unsigned char)*p))p++;
        if(p!=end){
            size_t count=1;
            for(const char *q=p;q<end;q++)if(*q==','){if(++count>DOC_LIST_LIMIT)return 0;}
            int64_t *data=malloc(count*sizeof(*data));if(!data)return 0;
            for(size_t i=0;i<count;i++){
                while(p<end&&isspace((unsigned char)*p))p++;
                const char *digits=p;if(p<end&&(*p=='-'||*p=='+'))p++;
                if(p==end||*p<'0'||*p>'9'){free(data);return 0;}
                while(p<end&&*p>='0'&&*p<='9')p++;
                errno=0;char *after=NULL;intmax_t x=strtoimax(digits,&after,10);
                if(errno==ERANGE||after!=p||x<INT64_MIN||x>INT64_MAX){free(data);return 0;}
                data[i]=(int64_t)x;
                while(p<end&&isspace((unsigned char)*p))p++;
                if(i+1<count){if(p==end||*p++!=','){free(data);return 0;}}
                else if(p!=end){free(data);return 0;}
            }
            v.len=count;v.data=data;
        }
    }else return 0;
    *out=v;return 1;
}
/* Startup read boundary: root chosen by the operator, path components
 * compiled from checked effect declarations. No symlink traversal or
 * path-based check/open race. More restrictive than reference symlinks. */
#define DOC_ASSET_BYTES (1024u*1024u)
static int doc_asset_open(int root,const char *path){
    char component[257];int dir=dup(root);if(dir<0)return -1;
    const char *p=path;
    for(;;){
        const char *slash=strchr(p,'/');size_t n=slash?(size_t)(slash-p):strlen(p);
        if(!n||n>256||(n==1&&p[0]=='.')||(n==2&&p[0]=='.'&&p[1]=='.')){close(dir);return -1;}
        memcpy(component,p,n);component[n]=0;
        int flags=O_RDONLY|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK;
        if(slash)flags|=O_DIRECTORY;
        int fd=openat(dir,component,flags);close(dir);
        if(fd<0||!slash)return fd;
        dir=fd;p=slash+1;
    }
}
static int doc_read_asset(int root,size_t id,doc_value *out){
    int fd=doc_asset_open(root,doc_asset_paths[id]);if(fd<0)return 0;
    struct stat st;if(fstat(fd,&st)||!S_ISREG(st.st_mode)||st.st_size<0||(uintmax_t)st.st_size>DOC_ASSET_BYTES){close(fd);return 0;}
    /* Allocate bounded input plus quotes and terminator, then free after parse. */
    char *buf=malloc(DOC_ASSET_BYTES+4);if(!buf){close(fd);return 0;}
    size_t n=0;int ok=1;
    while(n<=DOC_ASSET_BYTES){
        ssize_t got=read(fd,buf+1+n,DOC_ASSET_BYTES+1-n);
        if(got<0&&errno==EINTR)continue;
        if(got<0){ok=0;break;}
        if(!got)break;n+=(size_t)got;
    }
    close(fd);
    if(!ok||n>DOC_ASSET_BYTES||memchr(buf+1,0,n)||!doc_utf8((unsigned char*)buf+1,n)){free(buf);return 0;}
    if(doc_kind[id]==DOC_TEXT){
        while(n&&(buf[n]=='\n'||buf[n]=='\r'))n--;
        /* Same simple-literal boundary as the current reference frontend. */
        if(memchr(buf+1,'#',n)){free(buf);return 0;}
        buf[0]='"';buf[n+1]='"';buf[n+2]=0;ok=doc_parse(id,buf,out);
    }else{buf[n+1]=0;ok=doc_parse(id,buf+1,out);}
    free(buf);return ok;
}
static int doc_load_assets(const char *root){
    int any=0;for(size_t i=0;i<DOC_N;i++)if(doc_asset_paths[i])any=1;
    if(!any)return 1;
    int fd=open(root,O_RDONLY|O_DIRECTORY|O_CLOEXEC);if(fd<0)return doc_fail("asset root unavailable");
    if(!doc_state_copy(&doc_startup,doc_initial)){close(fd);return 0;}
    for(size_t i=0;i<DOC_N;i++)if(doc_asset_paths[i]){
        doc_value v;
        if(!doc_read_asset(fd,i,&v)){
            fprintf(stderr,"DOC_AOT: invalid startup asset for %s; no publication\n",doc_names[i]);
            close(fd);doc_state_drop(&doc_startup);return 0;
        }
        doc_drop(&doc_startup.value[i]);doc_startup.value[i]=v;
        fprintf(stderr,"DOC_AOT_ASSET_READ: %s\n",doc_names[i]);
    }
    close(fd);doc_startup_ready=1;return 1;
}
static int doc_assignment(doc_state *s,unsigned char *seen,const char *arg) {
    const char *eq=strchr(arg,'=');
    if(!eq)return doc_fail("expected source=value");
    size_t id=doc_lookup(arg,(size_t)(eq-arg));doc_value value;
    if(id==DOC_N||!doc_source[id]||seen[id]||!doc_parse(id,eq+1,&value))
        return doc_fail("unknown, duplicate, derived or mistyped source assignment");
    seen[id]=1;int ok=doc_assign(s,id,value);doc_drop(&value);return ok;
}
static void doc_print(const doc_state *s,size_t target) {
    for(size_t i=0;i<DOC_N;i++)if(target==DOC_N||target==i){
        doc_value v=s->value[i];printf("%s: ",doc_names[i]);
        if(v.kind==DOC_BOOL)printf("%s",v.scalar?"true":"false");
        else if(v.kind==DOC_INT)printf("%" PRId64,v.scalar);
        else if(v.kind==DOC_MAYBE){if(v.len)printf("some(%" PRId64 ")",v.scalar);else printf("none");}
        else if(v.kind==DOC_TEXT||v.kind==DOC_NAT){if(v.len)fwrite(v.bytes,1,v.len,stdout);}
        else {putchar('[');for(size_t j=0;j<v.len;j++)printf("%s%" PRId64,j?",":"",v.data[j]);putchar(']');}
        putchar('\n');
    }
}
static int doc_u64(const char *s,uint64_t *n) {
    if(!*s)return 0;for(const char *p=s;*p;p++)if(*p<'0'||*p>'9')return 0;
    errno=0;char *end;uintmax_t x=strtoumax(s,&end,10);
    if(errno==ERANGE||*end||x>UINT64_MAX)return 0;
    *n=(uint64_t)x;return 1;
}
typedef struct {uint64_t epoch;size_t id;doc_value value;} doc_fact;
static void doc_facts_drop(doc_fact *facts,size_t n){for(size_t i=0;i<n;i++)doc_drop(&facts[i].value);free(facts);}
static int doc_recurrence(int argc,char **argv,int at) {
    size_t carry[DOC_N],halt=DOC_N;uint64_t cap;
    for(size_t i=0;i<DOC_N;i++)carry[i]=DOC_N;
    if(!strncmp(argv[at],"--through=",10)){
        if(!doc_u64(argv[at++]+10,&cap))return doc_fail("invalid recurrence cap");
    }else{
        const char *name=argv[at++]+8;halt=doc_lookup(name,strlen(name));
        if(halt==DOC_N||doc_kind[halt]!=DOC_BOOL||at==argc||strncmp(argv[at],"--max-epochs=",13)||
           !doc_u64(argv[at++]+13,&cap))return doc_fail("invalid halt predicate/cap");
    }
    doc_fact *facts=calloc((size_t)(argc-at)+1,sizeof(*facts));size_t nf=0;
    if(!facts)return doc_fail("fact allocation failed");
    for(;at<argc;at++){
        const char *arg=argv[at];
        if(!strncmp(arg,"--fact=",7)){
            const char *colon=strchr(arg+7,':'),*eq=colon?strchr(colon+1,'='):NULL;
            if(!colon||!eq||colon-(arg+7)>20)goto invalid;
            char number[21];size_t len=(size_t)(colon-(arg+7));memcpy(number,arg+7,len);number[len]=0;
            uint64_t epoch;size_t id=doc_lookup(colon+1,(size_t)(eq-colon-1));doc_value value;
            if(!doc_u64(number,&epoch)||!epoch||epoch>cap||id==DOC_N||!doc_source[id]||
               !doc_parse(id,eq+1,&value))goto invalid;
            for(size_t i=0;i<nf;i++)if(facts[i].epoch==epoch&&facts[i].id==id){doc_drop(&value);goto invalid;}
            facts[nf++]=(doc_fact){epoch,id,value};
        }else{
            const char *eq=strchr(arg,'=');if(!eq)goto invalid;
            size_t source=doc_lookup(arg,(size_t)(eq-arg)),prev=doc_lookup(eq+1,strlen(eq+1));
            if(source==DOC_N||prev==DOC_N||!doc_source[source]||carry[source]!=DOC_N||
               doc_kind[source]!=doc_kind[prev])goto invalid;
            carry[source]=prev;
        }
    }
    for(size_t i=0;i<nf;i++)if(carry[facts[i].id]!=DOC_N)goto invalid;
    doc_state stable;if(!doc_reset(&stable)){doc_facts_drop(facts,nf);return 0;}
    if(!doc_stabilize(&stable,DOC_N)){doc_state_drop(&stable);doc_facts_drop(facts,nf);return 0;}
    for(uint64_t epoch=0;;epoch++){
        printf("epoch: %" PRIu64 "\n",epoch);doc_print(&stable,DOC_N);fflush(stdout);
        if(halt!=DOC_N&&stable.value[halt].scalar){printf("DOC_RECURRENCE_HALT: %" PRIu64 "\n",epoch);doc_state_drop(&stable);doc_facts_drop(facts,nf);return 1;}
        if(epoch==cap){doc_state_drop(&stable);doc_facts_drop(facts,nf);return halt==DOC_N?1:doc_fail("recurrence halt cap exhausted");}
        doc_state candidate;if(!doc_reset(&candidate)){doc_state_drop(&stable);doc_facts_drop(facts,nf);return 0;}
        int ok=1;
        for(size_t i=0;i<DOC_N&&ok;i++)if(carry[i]!=DOC_N)ok=doc_assign(&candidate,i,stable.value[carry[i]]);
        for(size_t i=0;i<nf&&ok;i++)if(facts[i].epoch==epoch+1)ok=doc_assign(&candidate,facts[i].id,facts[i].value);
        if(!ok||!doc_stabilize(&candidate,DOC_N)){doc_state_drop(&candidate);doc_state_drop(&stable);doc_facts_drop(facts,nf);return 0;}
        doc_state_drop(&stable);stable=candidate;doc_memory_report("commit");
    }
invalid:
    doc_facts_drop(facts,nf);return doc_fail("invalid recurrence carry/fact authority");
}
#ifdef DOC_GAME_HOST
static int doc_game_main(int argc,char **argv,int at,const char *root);
#endif
static int doc_main(int argc,char **argv) {
    int at=1;const char *asset_root=".";
    if(at<argc&&!strncmp(argv[at],"--asset-root=",13)){asset_root=argv[at++]+13;}
    if(at<argc&&!strncmp(argv[at],"--backend=",10)){
        if(strcmp(argv[at++],"--backend=cpu")){doc_fail("DOC_AOT_UNSUPPORTED: native GPU not implemented; no CPU fallback");return 1;}
    }
    if(!doc_load_assets(asset_root))return 1;
#ifdef DOC_GAME_HOST
    return doc_game_main(argc,argv,at,asset_root);
#endif
    if(at<argc&&(!strncmp(argv[at],"--through=",10)||!strncmp(argv[at],"--until=",8)))
        return doc_recurrence(argc,argv,at)?0:1;
    int repeated=0;for(int i=at;i<argc;i++)if(!strcmp(argv[i],"--next"))repeated=1;
    doc_state stable;if(!doc_reset(&stable))return 1;uint64_t epoch=0;
    for(;;){
        doc_state candidate;if(!doc_state_copy(&candidate,stable.value)){doc_state_drop(&stable);return 1;}
        memcpy(candidate.dirty,stable.dirty,DOC_N);unsigned char seen[DOC_N]={0};size_t target=DOC_N;
        if(at<argc&&!strncmp(argv[at],"--demand=",9)){
            const char *name=argv[at++]+9;target=doc_lookup(name,strlen(name));
            if(target==DOC_N){doc_fail("unknown demand");doc_state_drop(&candidate);doc_state_drop(&stable);return 1;}
        }
        for(;at<argc&&strcmp(argv[at],"--next");at++)
            if(!doc_assignment(&candidate,seen,argv[at])){doc_state_drop(&candidate);doc_state_drop(&stable);return 1;}
        if(!doc_stabilize(&candidate,target)){doc_state_drop(&candidate);doc_state_drop(&stable);return 1;}
        doc_state_drop(&stable);stable=candidate;doc_memory_report("commit");
        if(repeated)printf("epoch: %" PRIu64 "\n",epoch++);
        doc_print(&stable,target);fflush(stdout);
        if(at==argc){doc_state_drop(&stable);return 0;}
        at++;
    }
}

int main(int argc,char **argv){
    const char *trace=getenv("DOC_AOT_MEMORY_TRACE");
    doc_trace_memory=trace&&strcmp(trace,"1")==0;
    const char *fail=getenv("DOC_AOT_FAIL_ALLOC_AT");
    if(fail){
        uint64_t index;
        if(!doc_u64(fail,&index)||!index||index>SIZE_MAX){doc_fail("invalid allocation injection");return 1;}
        doc_fail_at=(size_t)index;
    }
    int result=doc_main(argc,argv);
    if(doc_startup_ready){doc_state_drop(&doc_startup);doc_startup_ready=0;}
    doc_memory_report("exit");
    if(atomic_load(&doc_live)!=0){doc_fail("owned allocation leak");return 1;}
    return result;
}
