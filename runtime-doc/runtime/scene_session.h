#ifndef DOC_SCENE_SESSION_H
#define DOC_SCENE_SESSION_H
/* Native input/session ABI for a generated DOC scene. Metadata comes from
 * committed DOC text values; this host has no movement, physics, collision,
 * score, entity, lighting or dependency policy. One coordinator per process. */
typedef int (*SceneValidate)(const Epoch *,void *);
typedef struct {
    Epoch e;Region default_owner;V *defaults;size_t *carry,action;
    unsigned char admitted[128];int64_t actions[128];
    uint64_t published;int initialized;
} SceneSession;
static int scene_value(const Epoch *e,const char *name,V *out){
    size_t i=find_state(e,name,strlen(name));
    if(i==e->n||!e->have[i]||e->dirty[i])return 0;
    *out=*e->states[i].slot;return 1;
}
static int scene_carry_map(SceneSession *s,V spec){
    if(spec.kind!=T||!spec.n||spec.n>4096)return 0;
    const char *p=spec.p,*end=p+spec.n;
    while(p<end){
        const char *comma=memchr(p,',',(size_t)(end-p));if(!comma)comma=end;
        const char *colon=memchr(p,':',(size_t)(comma-p));if(!colon||colon==p||colon+1==comma)return 0;
        size_t i=find_state(&s->e,p,(size_t)(colon-p)),j=find_state(&s->e,colon+1,(size_t)(comma-colon-1));
        if(i==s->action||!recurrence_carry_admitted(i<s->e.n&&source_role(s->e.states[i].role),j<s->e.n,i<s->e.n&&j<s->e.n&&s->e.states[i].kind==s->e.states[j].kind,i<s->e.n&&s->carry[i]==s->e.n))return 0;
        s->carry[i]=j;if(comma==end)break;p=comma+1;if(p==end)return 0;
    }
    return 1;
}
static int scene_action_map(SceneSession *s,V spec){
    if(spec.kind!=T||!spec.n||spec.n>4096)return 0;
    const char *p=spec.p,*end=p+spec.n;
    while(p<end){
        const char *comma=memchr(p,',',(size_t)(end-p));if(!comma)comma=end;
        if(comma-p<3||p[1]!=':')return 0;unsigned char key=(unsigned char)p[0];
        if(key<32||key>=127||s->admitted[key])return 0;
        size_t n=(size_t)(comma-p-2);char tmp[32];if(!n||n>=sizeof(tmp))return 0;
        for(size_t k=0;k<n;k++)if((p[k+2]<'0'||p[k+2]>'9')&&!(k==0&&p[k+2]=='-'))return 0;
        memcpy(tmp,p+2,n);tmp[n]=0;char *tail;errno=0;long long v=strtoll(tmp,&tail,10);
        if(errno||tail!=tmp+n)return 0;s->actions[key]=(int64_t)v;s->admitted[key]=1;
        if(comma==end)break;p=comma+1;if(p==end)return 0;
    }
    return s->admitted[(unsigned char)'.'];
}
static void scene_close(SceneSession *s){
    if(s->initialized){if(s->e.in_flight)epoch_finish(&s->e,0);epoch_free(&s->e);gpu_close();gpu_mode=0;}
    clear(&s->default_owner);free(s->defaults);free(s->carry);*s=(SceneSession){0};
}
static int scene_open(SceneSession *s,const State *states,size_t n,int backend,SceneValidate validate,void *ctx){
    *s=(SceneSession){0};if(backend<0||backend>2)return 0;
    epoch_init(&s->e,states,n);s->initialized=1;s->action=find_state(&s->e,"action",6);
    s->carry=zalloc(n,sizeof(*s->carry));s->defaults=zalloc(n,sizeof(*s->defaults));
    if(!s->carry||!s->defaults||s->action==n||states[s->action].kind!=I||!source_role(states[s->action].role))goto fail;
    for(size_t i=0;i<n;i++)s->carry[i]=n;
    gpu_mode=backend;if(gpu_mode&&!gpu_open(n)){gpu_close();if(backend==1||getenv("DOC_REQUIRE_PHYSICAL_GPU"))goto fail;gpu_mode=0;}
    if(!epoch_begin(&s->e))goto fail;
    V carries,actions;
    int ok=recurrence_initial_candidate(&s->e,&s->default_owner,s->defaults,NULL)&&scene_value(&s->e,"render_carries",&carries)&&scene_value(&s->e,"render_actions",&actions)&&scene_carry_map(s,carries)&&scene_action_map(s,actions)&&(!validate||validate(&s->e,ctx));
    if(!epoch_finish(&s->e,ok))goto fail;return 1;
fail:scene_close(s);return 0;
}
/* Restore only the admitted source authority, never derived materialization.
 * The caller has not presented the initial frame yet. */
static int scene_restore(SceneSession *s,const char *path,SceneValidate validate,void *ctx,uint64_t *saved){
    if(!s->initialized||s->published||!checkpoint_enabled())return 0;
    Region owner={0};V *values=zalloc(s->e.n,sizeof(*values));int ok=values&&checkpoint_load(&s->e,s->carry,path,&owner,values,saved);
    if(ok)ok=epoch_begin(&s->e);
    if(ok){
        for(size_t i=0;i<s->e.n&&ok;i++)if(source_role(s->e.states[i].role)){
            Cell *c=s->e.cell+i;ok=store_value(&c->candidate,&c->result,values[i]);if(ok)publish_private(&s->e,i);
        }
        size_t target;if(ok)ok=batch(&s->e,0,NULL,&target)&&(!validate||validate(&s->e,ctx));
        ok=epoch_finish(&s->e,ok);
    }
    clear(&owner);free(values);return ok;
}
static int scene_accepts(const SceneSession *s,unsigned char key){return key<128&&s->admitted[key];}
static int scene_step(SceneSession *s,unsigned char key,SceneValidate validate,void *ctx){
    if(!s->initialized||!scene_accepts(s,key)||s->published==UINT64_MAX||!epoch_begin(&s->e))return 0;
    Fact fact={s->published+1,s->action,vi(s->actions[key])};
    int ok=recurrence_successor_candidate(&s->e,s->carry,s->defaults,&fact,1,fact.epoch)&&(!validate||validate(&s->e,ctx));
    if(!epoch_finish(&s->e,ok))return 0;s->published++;return 1;
}
#endif
