#ifndef DOC_CHECKPOINT_IO_H
#define DOC_CHECKPOINT_IO_H
/* Narrow Linux filesystem boundary. No source, graph or gameplay parsing. */
#include <math.h>
#include "effects_policy_generated.h"
#define CHECKPOINT_LIMIT (8u*1024u*1024u)
static const char *doc_output_root=NULL;
#ifdef DOC_SOURCE_SHA256
static int output_parent(const char *path,char name[257]){
    if(!doc_output_root||!path||!*path||strlen(path)>256)return -1;
    int dir=open(doc_output_root,O_RDONLY|O_DIRECTORY|O_CLOEXEC);
    if(dir<0)return -1;
    const char *p=path;
    for(;;){const char *slash=strchr(p,'/');size_t n=slash?(size_t)(slash-p):strlen(p);
        int ok=n&&!(n==1&&p[0]=='.')&&!(n==2&&p[0]=='.'&&p[1]=='.');
        for(size_t i=0;ok&&i<n;i++){unsigned char c=p[i];ok=(c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_'||c=='-'||c=='.';}
        if(!ok){close(dir);return -1;}memcpy(name,p,n);name[n]=0;if(!slash)return dir;
        int fd=openat(dir,name,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);close(dir);if(fd<0)return -1;dir=fd;p=slash+1;
    }
}
static int output_regular(int dir,const char *name){struct stat st;if(!fstatat(dir,name,&st,AT_SYMLINK_NOFOLLOW))return S_ISREG(st.st_mode);return errno==ENOENT;}
static int output_atomic(const char *path,const unsigned char *bytes,size_t n){
    char name[257],tmp[80];int dir=output_parent(path,name);if(dir<0)return 0;
    int fd=-1,ok=0;if(n>CHECKPOINT_LIMIT||!output_regular(dir,name))goto done;
    /* O_EXCL prevents following or overwriting any existing temporary path. */
    for(unsigned k=0;k<128;k++){snprintf(tmp,sizeof(tmp),".doc-tmp-%ld-%u",(long)getpid(),k);fd=openat(dir,tmp,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);if(fd>=0)break;if(errno!=EEXIST)goto done;}
    if(fd<0)goto done;size_t at=0;
    while(at<n){ssize_t z=write(fd,bytes+at,n-at);if(z<0&&errno==EINTR)continue;if(z<=0)goto remove;at+=(size_t)z;}
    if(fsync(fd))goto remove;int rc=close(fd);fd=-1;if(rc||!output_regular(dir,name)||renameat(dir,tmp,dir,name))goto remove;
    /* renameat is the publication point. A failed directory fsync means
     * crash durability is unconfirmed; it cannot undo publication. */
    ok=1;if(fsync(dir))fprintf(stderr,"DOC: output published; directory durability unconfirmed\n");goto done;
remove:if(fd>=0)close(fd);unlinkat(dir,tmp,0);
done:close(dir);return ok;
}
static unsigned char *output_read(const char *path,size_t *n){
    char name[257];int dir=output_parent(path,name);if(dir<0)return NULL;
    int fd=openat(dir,name,O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC);close(dir);if(fd<0)return NULL;
    struct stat st;unsigned char *buf=NULL;*n=0;if(fstat(fd,&st)||!S_ISREG(st.st_mode)||st.st_size<0||(uintmax_t)st.st_size>CHECKPOINT_LIMIT)goto fail;
    buf=malloc(CHECKPOINT_LIMIT+1u);if(!buf)goto fail;
    while(*n<=CHECKPOINT_LIMIT){ssize_t z=read(fd,buf+*n,CHECKPOINT_LIMIT+1u-*n);if(z<0&&errno==EINTR)continue;if(z<0)goto fail;if(!z)break;*n+=(size_t)z;}
    close(fd);if(*n>CHECKPOINT_LIMIT){free(buf);return NULL;}return buf;
fail:close(fd);free(buf);return NULL;
}
static void put_le(unsigned char *p,uint64_t v,size_t n){for(size_t i=0;i<n;i++){p[i]=(unsigned char)v;v>>=8;}}
static uint64_t get_le(const unsigned char *p,size_t n){uint64_t v=0;while(n)v=(v<<8)|p[--n];return v;}
static uint64_t checkpoint_checksum(const unsigned char *p,size_t n){uint64_t h=UINT64_C(0xcbf29ce484222325);for(size_t i=0;i<n;i++)h=(h^p[i])*UINT64_C(0x100000001b3);return h;}
static int checkpoint_take(const unsigned char *buf,size_t end,size_t *at,size_t n,const unsigned char **p){if(*at>end||n>end-*at)return 0;*p=buf+*at;*at+=n;return 1;}
static int checkpoint_put(unsigned char *buf,size_t *at,const void *p,size_t n){if(*at>CHECKPOINT_LIMIT||n>CHECKPOINT_LIMIT-*at)return 0;if(n)memcpy(buf+*at,p,n);*at+=n;return 1;}
static int checkpoint_put64(unsigned char *buf,size_t *at,uint64_t n){unsigned char p[8];put_le(p,n,8);return checkpoint_put(buf,at,p,8);}
/* A native checkpoint is versioned separately from the frozen Rust debug-IR
 * format. Exact bundled-source SHA and ordered carry authority are required. */
static int checkpoint_enabled(void){return sizeof(DOC_SOURCE_SHA256)==65;}
static const char checkpoint_schema[]=DOC_SOURCE_SHA256;
static int64_t checkpoint_signed(uint64_t v){return v<=INT64_MAX?(int64_t)v:-1-(int64_t)(UINT64_MAX-v);}
static int checkpoint_value_put(unsigned char *buf,size_t *at,V v){
    if(v.kind==I||v.kind==B||v.kind==M){if(!checkpoint_put64(buf,at,v.kind==M?v.n:1))return 0;return !v.n&&v.kind==M?1:checkpoint_put64(buf,at,(uint64_t)v.x);}
    if(v.kind!=N&&v.kind!=T&&v.kind!=L)return 0;if(v.n>LIMIT||!checkpoint_put64(buf,at,v.n))return 0;
    if(v.kind==L){const int64_t *p=v.p;for(size_t k=0;k<v.n;k++)if(!checkpoint_put64(buf,at,(uint64_t)p[k]))return 0;return 1;}
    return checkpoint_put(buf,at,v.p,v.n);
}
static int checkpoint_save_record(const Epoch *e,const size_t *carry,uint64_t ep,const char *path,uint64_t *receipt){
    if(!checkpoint_enabled()||e->in_flight)return 0;unsigned char *buf=malloc(CHECKPOINT_LIMIT);if(!buf)return 0;size_t at=0,n=0;int ok=0;
    for(size_t i=0;i<e->n;i++)if(source_role(e->states[i].role))n++;
    if(!checkpoint_put(buf,&at,"DOC11CP1",8)||!checkpoint_put(buf,&at,checkpoint_schema,64)||!checkpoint_put64(buf,&at,ep)||!checkpoint_put64(buf,&at,n))goto done;
    for(size_t i=0;i<e->n;i++)if(source_role(e->states[i].role)){
        if(!e->have[i]||e->dirty[i]||!checkpoint_put64(buf,&at,i)||!checkpoint_put64(buf,&at,e->states[i].kind)||!checkpoint_put64(buf,&at,carry[i])||!checkpoint_value_put(buf,&at,*e->states[i].slot))goto done;
    }
    uint64_t checksum=checkpoint_checksum(buf,at);if(!checkpoint_put64(buf,&at,checksum))goto done;ok=output_atomic(path,buf,at);if(ok&&receipt)*receipt=checksum;
done:free(buf);return ok;
}
static int checkpoint_save(const Epoch *e,const size_t *carry,uint64_t ep,const char *path){return checkpoint_save_record(e,carry,ep,path,NULL);}
static int checkpoint_value_read(const unsigned char *buf,size_t end,size_t *at,int kind,Region *owner,V *out){
    const unsigned char *p;if(!checkpoint_take(buf,end,at,8,&p))return 0;uint64_t n=get_le(p,8);if(n>LIMIT)return 0;
    if(kind==I||kind==B||kind==M){if(kind==M&&n==0){*out=v_none();return 1;}if(n!=1||!checkpoint_take(buf,end,at,8,&p))return 0;uint64_t x=get_le(p,8);if(kind==B&&x>1)return 0;*out=kind==I?vi(checkpoint_signed(x)):kind==B?vb((int)x):v_some(vi(checkpoint_signed(x)));return 1;}
    if(kind==L){if(!checkpoint_take(buf,end,at,(size_t)n*8,&p))return 0;int64_t *listbuf=malloc((size_t)n*sizeof(int64_t)+(n==0));if(!listbuf)return 0;for(size_t i=0;i<n;i++)listbuf[i]=checkpoint_signed(get_le(p+i*8,8));int ok=store_value(owner,out,vv(L,(size_t)n,listbuf));free(listbuf);return ok;}
    if(kind!=N&&kind!=T)return 0;if(!checkpoint_take(buf,end,at,(size_t)n,&p))return 0;
    if(kind==T&&!utf8(p,(size_t)n))return 0;
    if(kind==N){if(!n||(n>1&&*p=='0'))return 0;for(size_t i=0;i<n;i++)if(p[i]<'0'||p[i]>'9')return 0;}
    return store_value(owner,out,vv(kind,(size_t)n,p));
}
static int checkpoint_load_record(const Epoch *e,const size_t *carry,const char *path,Region *owner,V *values,uint64_t *saved,const uint64_t *receipt){
    if(!checkpoint_enabled())return 0;size_t n=0,at=0,expected=0;unsigned char *buf=output_read(path,&n);if(!buf)return 0;int ok=0;const unsigned char *p;
    if(n<96||memcmp(buf,"DOC11CP1",8)||memcmp(buf+8,checkpoint_schema,64)||checkpoint_checksum(buf,n-8)!=get_le(buf+n-8,8))goto done;
    if(receipt&&*receipt!=get_le(buf+n-8,8))goto done;
    *saved=get_le(buf+72,8);for(size_t i=0;i<e->n;i++)if(source_role(e->states[i].role))expected++;
    if(get_le(buf+80,8)!=expected)goto done;at=88;
    for(size_t i=0;i<e->n;i++)if(source_role(e->states[i].role)){
        if(!checkpoint_take(buf,n-8,&at,24,&p)||get_le(p,8)!=i||get_le(p+8,8)>INT_MAX||get_le(p+16,8)>INT64_MAX)goto done;
        if(!truth(F_effect_checkpoint_fact(vi(e->states[i].role),vi((int64_t)get_le(p+8,8)),vi(e->states[i].kind),vi((int64_t)get_le(p+16,8)),vi((int64_t)carry[i]))))goto done;
        if(!checkpoint_value_read(buf,n-8,&at,e->states[i].kind,owner,values+i))goto done;
    }
    ok=at==n-8;
done:free(buf);return ok;
}
static int checkpoint_load(const Epoch *e,const size_t *carry,const char *path,Region *owner,V *values,uint64_t *saved){return checkpoint_load_record(e,carry,path,owner,values,saved,NULL);}
/* WAV is a host audio effect, not DOC computation; cue and trigger are
 * evaluated by the unchanged DOC graph. Only committed successors call it. */
static int checkpoint_audio(const Epoch *e,const char *dir,uint64_t ep){
    size_t h=find_state(e,"audio_hz",8),m=find_state(e,"audio_ms",8);if(h==e->n||m==e->n||!e->have[h]||!e->have[m]||e->dirty[h]||e->dirty[m])return 0;
    V hz=*e->states[h].slot,ms=*e->states[m].slot;if(hz.kind!=I||ms.kind!=I||!truth(F_effect_audio_admit(hz,ms)))return 0;if(truth(F_effect_audio_empty(hz,ms)))return 1;
    size_t samples=(size_t)44100*ms.x/1000,n=44+samples*2;unsigned char *buf=malloc(n);if(!buf)return 0;
    memcpy(buf,"RIFF",4);put_le(buf+4,n-8,4);memcpy(buf+8,"WAVEfmt ",8);put_le(buf+16,16,4);put_le(buf+20,1,2);put_le(buf+22,1,2);put_le(buf+24,44100,4);put_le(buf+28,88200,4);put_le(buf+32,2,2);put_le(buf+34,16,2);memcpy(buf+36,"data",4);put_le(buf+40,samples*2,4);
    for(size_t k=0;k<samples;k++){double radians=6.283185307179586476925286766559*(double)hz.x*(double)k/44100.0;int16_t value=(int16_t)round(sin(radians)*7200.0);put_le(buf+44+k*2,(uint16_t)value,2);}
    char path[257];int z=snprintf(path,sizeof(path),"%s/cue_%llu.wav",dir,(unsigned long long)ep);int ok=z>0&&(size_t)z<sizeof(path)&&output_atomic(path,buf,n);free(buf);if(ok)fprintf(stderr,"DOC11_AUDIO_WAV: epoch=%llu path=%s\n",(unsigned long long)ep,path);return ok;
}
#else
static int checkpoint_enabled(void){return 0;}
static int checkpoint_save(const Epoch *e,const size_t *c,uint64_t ep,const char *p){(void)e;(void)c;(void)ep;(void)p;return 0;}
static int checkpoint_load(const Epoch *e,const size_t *c,const char *p,Region *r,V *v,uint64_t *s){(void)e;(void)c;(void)p;(void)r;(void)v;(void)s;return 0;}
static int checkpoint_audio(const Epoch *e,const char *d,uint64_t ep){(void)e;(void)d;(void)ep;return 0;}
#endif
#endif
