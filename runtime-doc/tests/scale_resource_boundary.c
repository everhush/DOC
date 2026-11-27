/* Independent numerical/ownership checks for resource-based input admission.
 * No GPU driver, no workload-specific production policy. */
#define DOC_REACTIVE_VALUES
#include "value_primitives.h"
#include <assert.h>
static void reject(int kind,const char *s){
    jmp_buf j;failure_target=&j;
    if(!setjmp(j)){Region r;push(&r);(void)input_value(kind,s);assert(!"invalid input accepted");}
    failure_target=NULL;assert(!active&&!live_bytes);
}
int main(void){
    const char *bad[]={"9223372036854775808","-9223372036854775809","+","--1","+ 1","1x","0x10"};
    for(size_t i=0;i<sizeof(bad)/sizeof(*bad);i++)reject(I,bad[i]);
    const char *lists[]={"[1,]","[,1]","[1,,2]","[1 2]","[1]x","[9223372036854775808]","["};
    for(size_t i=0;i<sizeof(lists)/sizeof(*lists);i++)reject(L,lists[i]);
    Region r;push(&r);assert(num(input_value(I,"-9223372036854775808"))==INT64_MIN);
    assert(num(input_value(I,"+9223372036854775807"))==INT64_MAX);assert(num(input_value(I," -0 "))==0);
    V empty=input_value(L," [ ] ");assert(empty.n==0);
    V edge=input_value(L,"[-9223372036854775808,+9223372036854775807, 0]");
    assert(edge.n==3&&((const int64_t*)edge.p)[0]==INT64_MIN&&((const int64_t*)edge.p)[1]==INT64_MAX);pop(&r);assert(!live_bytes);
    size_t n=1048576;char *s=malloc(n*2+3);assert(s);s[0]='[';for(size_t i=0;i<n;i++){s[2*i+1]='1';s[2*i+2]=i+1==n?']':',';}s[2*n+1]=0;
    push(&r);V big=input_value(L,s);assert(big.n==n&&DOC_LIST_LIMIT>n);for(size_t i=0;i<n;i++)assert(((const int64_t*)big.p)[i]==1);pop(&r);free(s);assert(!live_bytes);
    /* Reject an extent above the region-derived limit before reading storage. */
    jmp_buf j;failure_target=&j;
    if(!setjmp(j)){push(&r);(void)list(NULL,DOC_LIST_LIMIT+1);assert(!"overlimit accepted");}
    failure_target=NULL;assert(!active&&!live_bytes);
    puts("DOC9_RESOURCE_BOUNDARY_PASS: exact signed parsing, malformed rejection, million-lane list, resource overflow and zero live bytes");
    return 0;
}
