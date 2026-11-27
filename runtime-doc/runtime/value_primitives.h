#ifndef DOC_VALUE_PRIMITIVES_H
#define DOC_VALUE_PRIMITIVES_H
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
/* Provisional C platform/value substrate. No parser of DOC or operation
 * bytecode. Each generated expression invokes a direct primitive. Arenas
 * have a single owner; borrowed values never outlive their arena. */
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <ctype.h>
#include <limits.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
#ifdef DOC_REACTIVE_VALUES
#include <setjmp.h>
#include <stdatomic.h>
#endif
/* Compiler executables have a separately bounded workspace for token triples
 * and type inference; never define this for compiled application code. */
#define DOC_INPUT_LIMIT 65536u
#define DOC_FAMILY_LIMIT DOC_LIST_LIMIT
#ifdef DOC_COMPILER_WORKSPACE
#define LIMIT 131072u
#define DOC_CAUSAL_LIMIT 262144u
#else
#define LIMIT DOC_INPUT_LIMIT
#define DOC_CAUSAL_LIMIT DOC_INPUT_LIMIT
#endif
#define REGION_LIMIT (64u*1024u*1024u)
/* Application lists and families share the actual region byte budget.
 * Compiler workspace and text/input-stream limits remain distinct. */
#ifdef DOC_COMPILER_WORKSPACE
#define DOC_LIST_LIMIT LIMIT
#define DOC_LIST_INPUT_LIMIT DOC_INPUT_LIMIT
#else
#define DOC_LIST_LIMIT ((REGION_LIMIT-sizeof(Block))/sizeof(int64_t))
#define DOC_LIST_INPUT_LIMIT DOC_LIST_LIMIT
#endif
typedef struct Block {struct Block *next; max_align_t alignment; unsigned char data[];} Block;
typedef struct Scratch {unsigned char *data;size_t used,charge;} Scratch;
typedef struct Region {Block *head; size_t bytes; struct Region *parent; Scratch *scratch;} Region;
#ifdef DOC_REACTIVE_VALUES
static _Thread_local Region *active;
static _Thread_local jmp_buf *failure_target;
static _Thread_local const char *failure_message;
static _Atomic size_t live_bytes, peak_bytes, allocs;
#ifdef DOC_TEST_ALLOC_FAILURE
/* Test-only, process-wide atomic admission budget; never enabled in release. */
static _Atomic size_t allocation_budget=SIZE_MAX;
static int admit_test_allocation(void){size_t left=atomic_load(&allocation_budget);while(left!=SIZE_MAX){if(!left)return 0;if(atomic_compare_exchange_weak(&allocation_budget,&left,left-1))break;}return 1;}
#else
static int admit_test_allocation(void){return 1;}
#endif
static void account(size_t z){size_t total=atomic_fetch_add(&live_bytes,z)+z,peak=atomic_load(&peak_bytes);while(peak<total&&!atomic_compare_exchange_weak(&peak_bytes,&peak,total)){}atomic_fetch_add(&allocs,1);}
#else
static Region *active;
static size_t live_bytes, peak_bytes, allocs;
static int admit_test_allocation(void){return 1;}
static void account(size_t z){live_bytes+=z;if(live_bytes>peak_bytes)peak_bytes=live_bytes;allocs++;}
#endif
/* Small scratch slabs are owned by a single causal region. Heap accounting
 * records every actual reservation/free exactly, not logical bump allocations.
 * The retained 512-byte slab is bounded and released on every scope exit. */
#define DOC_SCRATCH_BYTES 512u
static void reset_region(Region *r){while(r->head){Block *b=r->head;r->head=b->next;free(b);}if(r->bytes)live_bytes-=r->bytes;r->bytes=0;if(r->scratch)r->scratch->used=r->scratch->charge=0;}
static void clear(Region *r){reset_region(r);if(r->scratch&&r->scratch->data){free(r->scratch->data);r->scratch->data=NULL;live_bytes-=DOC_SCRATCH_BYTES;}}
static void cleanup(void){while(active){Region *r=active;active=r->parent;clear(r);}}
static _Noreturn void fail(const char *message){cleanup();
#ifdef DOC_REACTIVE_VALUES
    if(failure_target){failure_message=message;longjmp(*failure_target,1);}
#endif
    fprintf(stderr,"DOC: %s\n",message);exit(1);
}
static void push(Region *r){*r=(Region){.parent=active};active=r;}
static void pop(Region *r){if(active!=r)fail("region stack");active=r->parent;clear(r);}
static void *alloc_in(Region *r,size_t n){if(!n)return NULL;if(!r||n>REGION_LIMIT-sizeof(Block)||r->bytes>REGION_LIMIT-sizeof(Block)-n||(r->scratch&&r->scratch->charge>REGION_LIMIT-sizeof(Block)-n-r->bytes))fail("region capacity");size_t z=sizeof(Block)+n;if(!admit_test_allocation())fail("injected allocation failure");
    if(r->scratch&&z<=DOC_SCRATCH_BYTES){Scratch *s=r->scratch;size_t align=_Alignof(max_align_t),off=(s->used+align-1)/align*align;
        if(off<=DOC_SCRATCH_BYTES&&z<=DOC_SCRATCH_BYTES-off){if(!s->data){s->data=malloc(DOC_SCRATCH_BYTES);if(!s->data)fail("allocation failure");account(DOC_SCRATCH_BYTES);}s->used=off+z;s->charge+=z;return s->data+off+sizeof(Block);}}
    Block *b=malloc(z);if(!b)fail("allocation failure");b->next=r->head;r->head=b;r->bytes+=z;account(z);return b->data;}
enum {I=0,B=1,N=2,L=3,M=4,T=5};
typedef struct {int kind;int64_t x;size_t n;const void *p;} V;
static V vi(int64_t x){return (V){.kind=I,.x=x};}
static V vb(int x){return (V){.kind=B,.x=!!x};}
static V vv(int k,size_t n,const void *p){return (V){.kind=k,.n=n,.p=p};}
static V need(V a,int k){if(a.kind!=k)fail("value kind");return a;}
static int64_t num(V a){return need(a,I).x;}
static int truth(V a){return need(a,B).x!=0;}
static size_t count(size_t n){if(n>LIMIT)fail("value capacity");return n;}
static size_t list_count(size_t n){if(n>DOC_LIST_LIMIT)fail("list capacity");return n;}
static size_t bytes(V a){return a.kind==L?list_count(a.n)*sizeof(int64_t):a.kind==T||a.kind==N?a.n:0;}
static V own(Region *r,V a){size_t z=bytes(a);if(z){void *p=alloc_in(r,z);memcpy(p,a.p,z);a.p=p;}else a.p=NULL;return a;}
static V list(const int64_t *p,size_t n){return own(active,vv(L,list_count(n),p));}
static int utf8(const unsigned char *p,size_t n){for(size_t i=0;i<n;){unsigned c=p[i++];if(c<128)continue;unsigned k=c>=0xc2&&c<=0xdf?1:c>=0xe0&&c<=0xef?2:c>=0xf0&&c<=0xf4?3:0;if(!k||k>n-i)return 0;unsigned lo=c==0xe0?0xa0:c==0xf0?0x90:0x80,hi=c==0xed?0x9f:c==0xf4?0x8f:0xbf;if(p[i]<lo||p[i]>hi)return 0;while(k--){if((p[i++]&0xc0)!=0x80)return 0;}}return 1;}
static V txt(const char *p,size_t n){count(n);if(!utf8((const unsigned char*)p,n))fail("UTF-8");return vv(T,n,p);}
#define TXT(s) txt((s),sizeof(s)-1)
static V nat(const char *p,size_t n){count(n);if(!n)fail("empty natural");for(size_t i=0;i<n;i++)if(p[i]<'0'||p[i]>'9')fail("natural literal");while(n>1&&*p=='0'){p++;n--;}return vv(N,n,p);}
#define NAT(s) nat((s),sizeof(s)-1)
#define VL(...) list(((int64_t[]){0,##__VA_ARGS__})+1,sizeof((int64_t[]){0,##__VA_ARGS__})/sizeof(int64_t)-1)
static V v_empty(void){return vv(L,0,NULL);}
static V v_none(void){return vv(M,0,NULL);}
static V v_some(V a){return (V){.kind=M,.x=num(a),.n=1};}
static int equal(V a,V b){if(a.kind!=b.kind||a.n!=b.n)return 0;if(a.kind==L||a.kind==N||a.kind==T)return !a.n||!memcmp(a.p,b.p,bytes(a));return (a.kind==M&&!a.n)||a.x==b.x;}
static int order(V a,V b){if(a.kind!=b.kind)fail("order type");if(a.kind==I)return (a.x>b.x)-(a.x<b.x);if(a.kind!=N)fail("order kind");if(a.n!=b.n)return a.n>b.n?1:-1;return memcmp(a.p,b.p,a.n);}
static V v_eq(V a,V b){if(a.kind!=b.kind)fail("equality kind");return vb(equal(a,b));}
static V v_lt(V a,V b){return vb(order(a,b)<0);}
static V v_le(V a,V b){return vb(order(a,b)<=0);}
#define v_if(c,a,b) (truth(c)?(a):(b))
static V nfinish(char *p,size_t n){return nat(p,n);}
static V nadd(V a,V b){const unsigned char *x=a.p,*y=b.p;size_t n=a.n>b.n?a.n:b.n,w=n<LIMIT?n+1:n;char *p=alloc_in(active,w);unsigned carry=0;for(size_t k=0;k<w;k++){unsigned d=carry+(k<a.n?x[a.n-1-k]-48:0)+(k<b.n?y[b.n-1-k]-48:0);p[w-1-k]=48+d%10;carry=d/10;}if(carry)fail("natural capacity");return nfinish(p,w);}
static V nsub(V a,V b){if(order(a,b)<0)fail("natural underflow");const unsigned char *x=a.p,*y=b.p;char *p=alloc_in(active,a.n);int borrow=0;for(size_t k=0;k<a.n;k++){int d=x[a.n-1-k]-48-borrow-(k<b.n?y[b.n-1-k]-48:0);borrow=d<0;p[a.n-1-k]=48+d+(borrow?10:0);}return nfinish(p,a.n);}
static V nmul(V a,V b){if((a.n==1&&*(const char*)a.p=='0')||(b.n==1&&*(const char*)b.p=='0'))return NAT("0");size_t n=count(a.n+b.n);if(a.n>16777216u/b.n)fail("natural work capacity");const unsigned char *x=a.p,*y=b.p;unsigned char *p=alloc_in(active,n);memset(p,0,n);for(size_t i=0;i<a.n;i++){unsigned c=0;for(size_t j=0;j<b.n;j++){size_t k=n-1-i-j;unsigned d=p[k]+(x[a.n-1-i]-48)*(y[b.n-1-j]-48)+c;p[k]=d%10;c=d/10;}p[n-1-i-b.n]=c;}for(size_t i=0;i<n;i++)p[i]+=48;return nfinish((char*)p,n);}
static V v_add(V a,V b){if(a.kind==N&&b.kind==N)return nadd(a,b);int64_t z;if(__builtin_add_overflow(num(a),num(b),&z))fail("integer overflow");return vi(z);}
static V v_sub(V a,V b){if(a.kind==N&&b.kind==N)return nsub(a,b);int64_t z;if(__builtin_sub_overflow(num(a),num(b),&z))fail("integer overflow");return vi(z);}
static V v_mul(V a,V b){if(a.kind==N&&b.kind==N)return nmul(a,b);int64_t z;if(__builtin_mul_overflow(num(a),num(b),&z))fail("integer overflow");return vi(z);}
static int64_t divisor(V a,V b){int64_t x=num(a),y=num(b);if(!y||(x==INT64_MIN&&y==-1))fail("integer division");return y;}
static V v_quot(V a,V b){return vi(num(a)/divisor(a,b));}
static V v_rem(V a,V b){return vi(num(a)%divisor(a,b));}
static V bits(uint64_t x){return vi(x<=INT64_MAX?(int64_t)x:-1-(int64_t)(UINT64_MAX-x));}
static V v_bit_and(V a,V b){return bits((uint64_t)num(a)&(uint64_t)num(b));}
static V v_bit_or(V a,V b){return bits((uint64_t)num(a)|(uint64_t)num(b));}
static V v_bit_xor(V a,V b){return bits((uint64_t)num(a)^(uint64_t)num(b));}
static V v_bit_not(V a){return bits(~(uint64_t)num(a));}
static unsigned shift(V b){int64_t k=num(b);if(k<0||k>=64)fail("shift range");return (unsigned)k;}
static V v_shift_left(V a,V b){return bits((uint64_t)num(a)<<shift(b));}
static V v_shift_right(V a,V b){return bits((uint64_t)num(a)>>shift(b));}
static V v_len(V a){if(a.kind!=L&&a.kind!=T)fail("len kind");return vi((int64_t)a.n);}
static size_t index_of(V a,V b){need(a,L);int64_t i=num(b);if(i<0||(uint64_t)i>=a.n)fail("index");return (size_t)i;}
static V v_get(V a,V b){return vi(((const int64_t*)a.p)[index_of(a,b)]);}
static V v_try_get(V a,V b){need(a,L);int64_t i=num(b);return i<0||(uint64_t)i>=a.n?v_none():v_some(vi(((const int64_t*)a.p)[i]));}
static V v_unwrap_or(V a,V b){need(a,M);need(b,I);return a.n?vi(a.x):b;}
static V v_slice(V a,V b,V c){need(a,L);int64_t s=num(b),n=num(c);if(s<0||n<0||(uint64_t)s>a.n||(uint64_t)n>a.n-(size_t)s)fail("slice range");return vv(L,(size_t)n,n?(const int64_t*)a.p+s:NULL);}
static V v_tail(V a){need(a,L);return a.n?vv(L,a.n-1,a.n>1?(const int64_t*)a.p+1:NULL):a;}
static V v_append(V a,V b){need(a,L);size_t n=list_count(a.n+1);int64_t *p=alloc_in(active,n*sizeof(*p));if(a.n)memcpy(p,a.p,a.n*sizeof(*p));p[a.n]=num(b);return vv(L,n,p);}
static V v_remove_at(V a,V b){size_t i=index_of(a,b),n=a.n-1;if(!n)return v_empty();int64_t *p=alloc_in(active,n*sizeof(*p));if(i)memcpy(p,a.p,i*sizeof(*p));if(i<n)memcpy(p+i,(const int64_t*)a.p+i+1,(n-i)*sizeof(*p));return vv(L,n,p);}
static V v_replace_at(V a,V b,V c){size_t i=index_of(a,b);int64_t *p=alloc_in(active,a.n*sizeof(*p));memcpy(p,a.p,a.n*sizeof(*p));p[i]=num(c);return vv(L,a.n,p);}
static V v_concat(V a,V b){need(a,T);need(b,T);size_t n=count(a.n+b.n);char *p=alloc_in(active,n);if(a.n)memcpy(p,a.p,a.n);if(b.n)memcpy(p+a.n,b.p,b.n);return vv(T,n,p);}
static V v_starts_with(V a,V b){need(a,T);need(b,T);return vb(a.n>=b.n&&(!b.n||!memcmp(a.p,b.p,b.n)));}
static V v_utf8_bytes(V a){need(a,T);int64_t *p=alloc_in(active,a.n*sizeof(*p));for(size_t i=0;i<a.n;i++)p[i]=((const unsigned char*)a.p)[i];return vv(L,a.n,p);}
static V v_utf8_text(V a){need(a,L);char *p=alloc_in(active,a.n);for(size_t i=0;i<a.n;i++){int64_t x=((const int64_t*)a.p)[i];if(x<0||x>255)fail("byte range");p[i]=(char)x;}return txt(p,a.n);}
/* Generated causal expressions use private alternating carry owners, not
 * references into a region that is being reset. No refcount or collector. */
#define v_recur(seed,binder,pred,step) ({ Region *parent=active; V start=(seed); Region a,b,tmp;push(&a);push(&b);push(&tmp);Scratch as={0},bs={0},ts={0};a.scratch=&as;b.scratch=&bs;tmp.scratch=&ts;Region *old=&a,*next=&b;V binder=own(old,start);size_t rounds=0;for(;;){if(truth(pred)){reset_region(&tmp);break;}if(rounds++>=DOC_CAUSAL_LIMIT)fail("causal step capacity");V result=(step);if(result.kind!=binder.kind)fail("causal type");V copy=own(next,result);reset_region(&tmp);reset_region(old);Region *swap=old;old=next;next=swap;binder=copy;}V out=own(parent,binder);pop(&tmp);pop(&b);pop(&a);out;})
#define v_map_ints(seed,binder,expr) ({ V src=need((seed),L);if(src.n>DOC_FAMILY_LIMIT)fail("family lane capacity");int64_t *dst=alloc_in(active,src.n*sizeof(*dst));Region tmp;push(&tmp);for(size_t i=0;i<src.n;i++){V binder=vi(((const int64_t*)src.p)[i]);dst[i]=num(expr);clear(&tmp);}pop(&tmp);vv(L,src.n,dst);})
static const char *skip(const char *s){while(isspace((unsigned char)*s))s++;return s;}
static int64_t parse_i(const char **s){
    const char *p=skip(*s);int negative=*p=='-';if(*p=='-'||*p=='+')p++;
    if(*p<'0'||*p>'9')fail("integer literal");
    uint64_t limit=negative?UINT64_C(9223372036854775808):UINT64_C(9223372036854775807),v=0;
    do{unsigned d=(unsigned)(*p++-'0');if(v>limit/10||(v==limit/10&&d>limit%10))fail("integer literal");v=v*10+d;}while(*p>='0'&&*p<='9');
    *s=skip(p);if(!negative)return (int64_t)v;
    return v==UINT64_C(9223372036854775808)?INT64_MIN:-(int64_t)v;
}
static V input_value(int k,const char *s){s=skip(s);size_t n=strlen(s);while(n&&isspace((unsigned char)s[n-1]))n--;if(k==T){if(n>DOC_INPUT_LIMIT+2u)fail("text input capacity");if(n<2||s[0]!='"'||s[n-1]!='"')fail("quoted text source");for(size_t i=1;i+1<n;i++)if(s[i]==10||s[i]==13||s[i]==34||s[i]==92)fail("text literal control");return txt(s+1,n-2);}if(k==N){if(n>DOC_INPUT_LIMIT)fail("natural input capacity");return nat(s,n);}if(k==B){if(n==4&&!memcmp(s,"true",4))return vb(1);if(n==5&&!memcmp(s,"false",5))return vb(0);fail("bool literal");}if(k==I){int64_t x=parse_i(&s);if(*s)fail("integer trailing input");return vi(x);}if(k==M){if(n==4&&!memcmp(s,"none",4))return v_none();if(n<7||memcmp(s,"some(",5))fail("maybe literal");s+=5;int64_t x=parse_i(&s);if(*s!=')'||*skip(s+1))fail("maybe literal");return v_some(vi(x));}if(k!=L||*s++!='[')fail("list literal");size_t capacity=0;s=skip(s);if(*s!=']'){capacity=1;for(const char *q=s;*q&&*q!=']';q++)if(*q==','){if(capacity==DOC_LIST_INPUT_LIMIT)fail("list capacity");capacity++;}}int64_t *p=alloc_in(active,capacity*sizeof(*p));size_t z=0;if(*s!=']'){for(;;){if(z==capacity)fail("list capacity");p[z++]=parse_i(&s);if(*s!=',')break;s++;}}if(*s!=']'||*skip(s+1))fail("list literal");return vv(L,z,p);}
/* Explicit startup-only read, using the host-granted root directory.
 * Every child component is descriptor-relative and no-follow. */
static const char *asset_root=".";
static int source_role(int role){return role==1||role==5;}
static int asset_fd(const char *path){size_t n=strlen(path);if(!n||n>256)return -1;int dir=open(asset_root,O_RDONLY|O_DIRECTORY|O_CLOEXEC);if(dir<0)return -1;const char *p=path;for(;;){const char *slash=strchr(p,'/');size_t k=slash?(size_t)(slash-p):strlen(p);char name[257];int ok=k&&k<=256&&!(k==1&&p[0]=='.')&&!(k==2&&p[0]=='.'&&p[1]=='.');for(size_t i=0;ok&&i<k;i++){unsigned char c=p[i];ok=(c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_'||c=='-'||c=='.';}if(!ok){close(dir);return -1;}memcpy(name,p,k);name[k]=0;int fd=openat(dir,name,O_RDONLY|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK|(slash?O_DIRECTORY:0));close(dir);if(fd<0||!slash)return fd;dir=fd;p=slash+1;}}
#define ASSET_LIMIT 1048576u
static V doc_asset(int kind,const char *path){char *buf=alloc_in(active,ASSET_LIMIT+2);int fd=asset_fd(path);if(fd<0)fail("startup asset authority");struct stat st;if(fstat(fd,&st)||!S_ISREG(st.st_mode)||st.st_size<0||(uintmax_t)st.st_size>ASSET_LIMIT){close(fd);fail("startup asset capacity or type");}size_t n=0;while(n<=ASSET_LIMIT){ssize_t z=read(fd,buf+n,ASSET_LIMIT+1-n);if(z<0&&errno==EINTR)continue;if(z<0){close(fd);fail("startup asset read");}if(!z)break;n+=(size_t)z;}close(fd);if(n>ASSET_LIMIT||!utf8((const unsigned char*)buf,n))fail("startup asset bytes");buf[n]=0;if(kind==T){while(n&&(buf[n-1]==10||buf[n-1]==13))n--;for(size_t i=0;i<n;i++)if(buf[i]==10||buf[i]==13||buf[i]==34||buf[i]==92||buf[i]==35)fail("startup text literal");return txt(buf,n);}if(memchr(buf,0,n))fail("startup asset embedded zero");return input_value(kind,buf);}
static void print(V a){if(a.kind==I)printf("%lld",(long long)a.x);else if(a.kind==B)fputs(a.x?"true":"false",stdout);else if(a.kind==N||a.kind==T){if(a.n)fwrite(a.p,1,a.n,stdout);}else if(a.kind==M){if(a.n)printf("some(%lld)",(long long)a.x);else fputs("none",stdout);}else if(a.kind==L){putchar('[');for(size_t i=0;i<a.n;i++){if(i)putchar(',');printf("%lld",(long long)((const int64_t*)a.p)[i]);}putchar(']');}else fail("print kind");}
typedef struct {const char *name;int kind,role;V *slot;V (*eval)(void);const size_t *deps;size_t ndeps;} State;
#ifndef DOC_REACTIVE_VALUES
/* Explicit byte-input transport for compiled compiler tools. It bypasses
 * the OS argv-size limit, not language admission or the bounded value model.
 * The source must be an ordinary ints fact named input; no hidden file read. */
static V stdin_bytes(void){int64_t *p=alloc_in(active,DOC_INPUT_LIMIT*sizeof(*p));size_t n=0;for(;;){int c=fgetc(stdin);if(c==EOF){if(ferror(stdin))fail("input stream read");break;}if(n==DOC_INPUT_LIMIT)fail("input stream capacity");p[n++]=c;}return vv(L,n,p);}
static int run_graph(const State *states,size_t n,int argc,char **argv){
    Region retained;push(&retained);unsigned char *required=alloc_in(active,n),*supplied=alloc_in(active,n);if(n){memset(required,0,n);memset(supplied,0,n);}size_t target=n;int has_target=0;int start=1;if(argc>1&&!strncmp(argv[1],"--asset-root=",13)){asset_root=argv[1]+13;start++;}
    for(size_t i=0;i<n;i++)if(states[i].role==5){Region tmp;push(&tmp);V v=states[i].eval();if(v.kind!=states[i].kind)fail("asset kind");*states[i].slot=own(&retained,v);pop(&tmp);}
    for(int a=start;a<argc;a++){const char *arg=argv[a];if(!strncmp(arg,"--demand=",9)){if(has_target)fail("duplicate demand");has_target=1;for(size_t i=0;i<n;i++)if(states[i].name&&!strcmp(states[i].name,arg+9)){target=i;break;}if(target==n)fail("unknown demand");continue;}if(!strcmp(arg,"--input-stdin")){size_t i=0;for(;i<n;i++)if(states[i].name&&!strcmp(states[i].name,"input"))break;if(i==n||states[i].role!=1||states[i].kind!=L||supplied[i])fail("invalid input stream source");Region tmp;push(&tmp);*states[i].slot=own(&retained,stdin_bytes());pop(&tmp);supplied[i]=1;continue;}if(!strcmp(arg,"--backend=cpu"))continue;if(!strncmp(arg,"--backend=",10))fail("unsupported backend");const char *eq=strchr(arg,'=');if(!eq)fail("source argument");size_t i=0;for(;i<n;i++)if(states[i].name&&strlen(states[i].name)==(size_t)(eq-arg)&&!memcmp(states[i].name,arg,(size_t)(eq-arg)))break;if(i==n||!source_role(states[i].role)||supplied[i])fail("invalid source assignment");Region tmp;push(&tmp);*states[i].slot=own(&retained,input_value(states[i].kind,eq+1));pop(&tmp);supplied[i]=1;}
    if(has_target)required[target]=1;else if(n)memset(required,1,n);
    for(size_t i=n;i--;)if(required[i])for(size_t j=0;j<states[i].ndeps;j++){size_t d=states[i].deps[j];if(d>=i||!states[d].name)fail("dependency metadata");required[d]=1;}
    for(size_t i=0;i<n;i++)if(states[i].name&&states[i].role!=5&&(required[i]||states[i].role==1)&&!supplied[i]){Region tmp;push(&tmp);V v=states[i].eval();if(v.kind!=states[i].kind)fail("result type");*states[i].slot=own(&retained,v);pop(&tmp);}
    for(size_t i=0;i<n;i++)if(states[i].name&&(!has_target||i==target)){printf("%s: ",states[i].name);print(*states[i].slot);putchar('\n');}
    pop(&retained);if(live_bytes)fail("region leak");if(getenv("DOC_REGION_METRICS"))fprintf(stderr,"DOC11_REGIONS: live=%zu peak=%zu allocations=%zu\n",live_bytes,peak_bytes,allocs);return 0;
}
#endif
#endif
