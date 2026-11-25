/* Immutable typed values. Only owned list buffers may be dropped.
 * Generated expressions borrow inputs and local arena allocations; clone
 * the final value before arena destruction. Workers never mutate inputs. */
enum { DOC_INT, DOC_BOOL, DOC_LIST, DOC_MAYBE, DOC_TEXT, DOC_NAT };
#define DOC_LIST_LIMIT 65536u
#define DOC_ARENA_LIMIT (16u*1024u*1024u)
typedef struct { unsigned char kind; int64_t scalar; size_t len; const int64_t *data; const unsigned char *bytes; } doc_value;
typedef struct doc_block {struct doc_block *next;int64_t data[];} doc_block;
typedef struct {doc_block *head;size_t bytes;} doc_arena;
static void doc_arena_clear(doc_arena *a){
    while(a->head){doc_block *b=a->head;a->head=b->next;free(b);}a->bytes=0;
}
static int64_t *doc_alloc(doc_arena *a,size_t n){
    if(!n||n>DOC_LIST_LIMIT)return NULL;
    size_t bytes=sizeof(doc_block)+n*sizeof(int64_t);
    if(bytes>DOC_ARENA_LIMIT-a->bytes)return NULL;
    doc_block *b=malloc(bytes);if(!b)return NULL;
    b->next=a->head;a->head=b;a->bytes+=bytes;return b->data;
}
static void doc_drop(doc_value *v){
    if(v->kind==DOC_LIST)free((void*)v->data);
    if(v->kind==DOC_TEXT||v->kind==DOC_NAT)free((void*)v->bytes);
    *v=(doc_value){0};
}
static int doc_clone(doc_value v,doc_value *out){
    if(v.kind==DOC_LIST){
        if(v.len>DOC_LIST_LIMIT)return 0;
        if(v.len){
            int64_t *p=malloc(v.len*sizeof(*p));if(!p)return 0;
            memcpy(p,v.data,v.len*sizeof(*p));v.data=p;
        }else v.data=NULL;
    }
    if(v.kind==DOC_TEXT||v.kind==DOC_NAT){
        if(v.len>DOC_LIST_LIMIT)return 0;
        if(v.len){unsigned char *p=malloc(v.len);if(!p)return 0;memcpy(p,v.bytes,v.len);v.bytes=p;}
        else v.bytes=NULL;
    }
    *out=v;return 1;
}
static int doc_equal(doc_value a,doc_value b){
    if(a.kind!=b.kind)return 0;
    if(a.kind==DOC_LIST)return a.len==b.len&&(!a.len||!memcmp(a.data,b.data,a.len*sizeof(int64_t)));
    if(a.kind==DOC_TEXT||a.kind==DOC_NAT)return a.len==b.len&&(!a.len||!memcmp(a.bytes,b.bytes,a.len));
    if(a.kind==DOC_MAYBE)return a.len==b.len&&(!a.len||a.scalar==b.scalar);
    return a.scalar==b.scalar;
}
static int doc_index(doc_value a,doc_value b){return b.scalar>=0&&(uint64_t)b.scalar<a.len;}
static doc_value doc_try_get(doc_value a,doc_value b){
    if(doc_index(a,b))return (doc_value){.kind=DOC_MAYBE,.len=1,.scalar=a.data[(size_t)b.scalar]};
    return (doc_value){.kind=DOC_MAYBE};
}
static int doc_get(doc_arena *arena,doc_value a,doc_value b,doc_value *out){
    (void)arena;if(!doc_index(a,b))return 0;
    *out=(doc_value){.kind=DOC_INT,.scalar=a.data[(size_t)b.scalar]};return 1;
}
static int doc_append(doc_arena *arena,doc_value a,doc_value b,doc_value *out){
    if(a.len>=DOC_LIST_LIMIT)return 0;
    int64_t *p=doc_alloc(arena,a.len+1);if(!p)return 0;
    if(a.len)memcpy(p,a.data,a.len*sizeof(*p));p[a.len]=b.scalar;
    *out=(doc_value){.kind=DOC_LIST,.len=a.len+1,.data=p};return 1;
}
static int doc_remove(doc_arena *arena,doc_value a,doc_value b,doc_value *out){
    if(!doc_index(a,b))return 0;
    if(a.len==1){*out=(doc_value){.kind=DOC_LIST};return 1;}
    int64_t *p=doc_alloc(arena,a.len-1);if(!p)return 0;
    size_t i=(size_t)b.scalar;
    if(i)memcpy(p,a.data,i*sizeof(*p));
    if(i+1<a.len)memcpy(p+i,a.data+i+1,(a.len-i-1)*sizeof(*p));
    *out=(doc_value){.kind=DOC_LIST,.len=a.len-1,.data=p};return 1;
}
static int doc_replace(doc_arena *arena,doc_value a,doc_value b,doc_value c,doc_value *out){
    if(!doc_index(a,b))return 0;
    int64_t *p=doc_alloc(arena,a.len);if(!p)return 0;
    memcpy(p,a.data,a.len*sizeof(*p));p[(size_t)b.scalar]=c.scalar;
    *out=(doc_value){.kind=DOC_LIST,.len=a.len,.data=p};return 1;
}
/* Borrow an immutable checked subrange for this expression only. The
 * existing result clone barrier owns the published result, including slices
 * of arena temporaries. Empty slices never form a pointer into null storage. */
static int doc_slice(doc_arena *arena,doc_value a,doc_value start,doc_value count,doc_value *out){
    (void)arena;
    if(a.kind!=DOC_LIST||start.kind!=DOC_INT||count.kind!=DOC_INT||
       start.scalar<0||count.scalar<0)return 0;
    uint64_t s=(uint64_t)start.scalar,n=(uint64_t)count.scalar;
    if(s>a.len||n>a.len-s)return 0;
    *out=(doc_value){.kind=DOC_LIST,.len=(size_t)n,.data=n?a.data+(size_t)s:NULL};
    return 1;
}
static doc_value doc_tail(doc_value a){
    return a.len>1?(doc_value){.kind=DOC_LIST,.len=a.len-1,.data=a.data+1}:(doc_value){.kind=DOC_LIST};
}

/* Byte values use the same uniquely owned copies and temporary arena protocol.
 * Decimal naturals are canonical, with checked underflow and resource limits. */
static unsigned char *doc_bytes_alloc(doc_arena *a,size_t n){
    if(!n||n>DOC_LIST_LIMIT)return NULL;
    return (unsigned char*)doc_alloc(a,(n+sizeof(int64_t)-1)/sizeof(int64_t));
}
static int doc_order(doc_value a,doc_value b){
    if(a.kind==DOC_NAT){
        if(a.len!=b.len)return a.len<b.len?-1:1;
        return a.len?memcmp(a.bytes,b.bytes,a.len):0;
    }
    return (a.scalar>b.scalar)-(a.scalar<b.scalar);
}
static int doc_prefix(doc_value a,doc_value b){
    return a.len>=b.len&&(!b.len||!memcmp(a.bytes,b.bytes,b.len));
}
static int doc_concat(doc_arena *a,doc_value x,doc_value y,doc_value *out){
    size_t n=x.len+y.len;
    if(!n){*out=(doc_value){.kind=DOC_TEXT};return 1;}
    unsigned char *p=doc_bytes_alloc(a,n);if(!p)return 0;
    if(x.len)memcpy(p,x.bytes,x.len);if(y.len)memcpy(p+x.len,y.bytes,y.len);
    *out=(doc_value){.kind=DOC_TEXT,.len=n,.bytes=p};return 1;
}
static void doc_nat_finish(unsigned char *p,size_t n,doc_value *out){
    while(n>1&&*p=='0'){p++;n--;}
    *out=(doc_value){.kind=DOC_NAT,.len=n,.bytes=p};
}
static int doc_nat_add(doc_arena *a,doc_value x,doc_value y,doc_value *out){
    size_t n=(x.len>y.len?x.len:y.len)+1;
    /* A max-length addition can still fit; compute without a leading carry slot. */
    size_t width=n>DOC_LIST_LIMIT?n-1:n;
    unsigned char *p=doc_bytes_alloc(a,width);if(!p)return 0;
    unsigned carry=0;
    for(size_t i=0;i<width;i++){
        unsigned z=carry+(i<x.len?x.bytes[x.len-1-i]-'0':0)+(i<y.len?y.bytes[y.len-1-i]-'0':0);
        p[width-1-i]=(unsigned char)('0'+z%10);carry=z/10;
    }
    if(carry)return 0;
    doc_nat_finish(p,width,out);return 1;
}
static int doc_nat_sub(doc_arena *a,doc_value x,doc_value y,doc_value *out){
    if(doc_order(x,y)<0)return 0;
    unsigned char *p=doc_bytes_alloc(a,x.len);if(!p)return 0;
    int borrow=0;
    for(size_t i=0;i<x.len;i++){
        int z=x.bytes[x.len-1-i]-'0'-borrow-(i<y.len?y.bytes[y.len-1-i]-'0':0);
        borrow=z<0;if(borrow)z+=10;p[x.len-1-i]=(unsigned char)('0'+z);
    }
    if(borrow)return 0;
    doc_nat_finish(p,x.len,out);return 1;
}
static int doc_nat_mul(doc_arena *a,doc_value x,doc_value y,doc_value *out){
    if((x.len==1&&x.bytes[0]=='0')||(y.len==1&&y.bytes[0]=='0')){
        *out=(doc_value){.kind=DOC_NAT,.len=1,.bytes=(const unsigned char*)"0"};return 1;
    }
    if(!x.len||!y.len||x.len+y.len>DOC_LIST_LIMIT||x.len>16777216u/y.len)return 0;
    size_t n=x.len+y.len;unsigned char *p=doc_bytes_alloc(a,n);if(!p)return 0;
    memset(p,0,n);
    for(size_t i=0;i<x.len;i++){
        unsigned carry=0;
        for(size_t j=0;j<y.len;j++){
            size_t k=n-1-i-j;
            unsigned z=p[k]+(unsigned)(x.bytes[x.len-1-i]-'0')*(unsigned)(y.bytes[y.len-1-j]-'0')+carry;
            p[k]=(unsigned char)(z%10);carry=z/10;
        }
        p[n-1-i-y.len]=(unsigned char)carry;
    }
    for(size_t i=0;i<n;i++)p[i]+='0';
    doc_nat_finish(p,n,out);return 1;
}
/* Strict UTF-8 validation at external text boundaries. */
static int doc_utf8(const unsigned char *p,size_t n){
    size_t i=0;
    while(i<n){
        unsigned c=p[i++];if(c<128)continue;
        unsigned count,min=0x80,max=0xbf;
        if(c>=0xc2&&c<=0xdf)count=1;
        else if(c>=0xe0&&c<=0xef){count=2;if(c==0xe0)min=0xa0;if(c==0xed)max=0x9f;}
        else if(c>=0xf0&&c<=0xf4){count=3;if(c==0xf0)min=0x90;if(c==0xf4)max=0x8f;}
        else return 0;
        if(count>n-i||p[i]<min||p[i]>max)return 0;
        i++;
        for(unsigned j=1;j<count;j++,i++)if(p[i]<0x80||p[i]>0xbf)return 0;
    }
    return 1;
}

/* Exact 64-bit word operations: no C signed overflow or implementation
 * defined unsigned-to-signed conversion, no shift outside word width. */
static int doc_utf8_bytes(doc_arena *a,doc_value v,doc_value *out){
    if(v.kind!=DOC_TEXT||v.len>DOC_LIST_LIMIT)return 0;
    if(!v.len){*out=(doc_value){.kind=DOC_LIST};return 1;}
    int64_t *p=doc_alloc(a,v.len);if(!p)return 0;
    for(size_t i=0;i<v.len;i++)p[i]=v.bytes[i];
    *out=(doc_value){.kind=DOC_LIST,.len=v.len,.data=p};return 1;
}
static int doc_utf8_text(doc_arena *a,doc_value v,doc_value *out){
    if(v.kind!=DOC_LIST||v.len>DOC_LIST_LIMIT)return 0;
    if(!v.len){*out=(doc_value){.kind=DOC_TEXT};return 1;}
    unsigned char *p=doc_bytes_alloc(a,v.len);if(!p)return 0;
    for(size_t i=0;i<v.len;i++){if(v.data[i]<0||v.data[i]>255)return 0;p[i]=(unsigned char)v.data[i];}
    if(!doc_utf8(p,v.len))return 0;
    *out=(doc_value){.kind=DOC_TEXT,.len=v.len,.bytes=p};return 1;
}
