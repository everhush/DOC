#define _GNU_SOURCE
#include "reactive_values.h"
#include <assert.h>
static void doc_mark(size_t id,unsigned char *dirty){(void)id;(void)dirty;}
static void doc_demand(unsigned char *need){(void)need;}
static void doc_block(const unsigned char *dirty,unsigned char *blocked){(void)dirty;(void)blocked;}
static size_t doc_select(const unsigned char *dirty,const unsigned char *need,const unsigned char *blocked,size_t *queue){(void)dirty;(void)need;(void)blocked;(void)queue;return 0;}
static size_t linear(const State *s,size_t n,const char *q,size_t z){for(size_t i=0;i<n;i++)if(s[i].name&&strlen(s[i].name)==z&&!memcmp(s[i].name,q,z))return i;return n;}
static void test(size_t n){State *s=calloc(n?n:1,sizeof(*s));char (*names)[32]=calloc(n?n:1,sizeof(*names));assert(s&&names);for(size_t i=0;i<n;i++){snprintf(names[i],sizeof(names[i]),"%s_%zu",i%3?"state":"other",i);if(i%19)s[i].name=names[i];if(i%31==0)s[i].name="duplicate";}
 Epoch e;assert(epoch_try_init(&e,s,n));assert((e.name_index!=NULL)==(n>=DOC_NAME_INDEX_MIN));size_t step=n>2000?13:1;for(size_t i=0;i<n;i+=step){char q[64];snprintf(q,sizeof(q),"%s=ignored",names[i]);size_t z=strlen(names[i]);assert(find_state(&e,q,z)==linear(s,n,q,z));assert(find_state(&e,q,z-1)==linear(s,n,q,z-1));assert(find_state(&e,q,z+1)==n);}assert(find_state(&e,"duplicate=anything",9)==linear(s,n,"duplicate",9));assert(find_state(&e,"duplicate\0junk",14)==n);assert(find_state(&e,"missing",7)==n);assert(find_state(&e,"",0)==n);epoch_free(&e);assert(!live_bytes);free(s);free(names);}
int main(void){size_t sizes[]={0,1,255,256,257,1024,24575};for(size_t i=0;i<sizeof(sizes)/sizeof(*sizes);i++)test(sizes[i]);for(int i=0;i<64;i++)test(257);printf("DOC9_NAME_INDEX_PASS: 7 size classes, 64 independent index lifetimes, exact length/prefix/duplicate/hole handling, live=%zu\n",(size_t)live_bytes);return 0;}
