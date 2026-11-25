#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
/* Test-only injection: track each allocation in the packet decoder and
 * fail one specified allocation. The production decoder is unchanged. */
static size_t attempts, fail_at, live;
static void *owned[2 + 32 * 3];
static void *checked_calloc(size_t n,size_t size){
    ++attempts;
    if(attempts==fail_at)return NULL;
    void *p=calloc(n,size);
    if(p){assert(live<sizeof(owned)/sizeof(*owned));owned[live++]=p;}
    return p;
}
static void checked_free(void *p){
    if(!p)return;
    size_t i=0;while(i<live&&owned[i]!=p)++i;
    assert(i<live);owned[i]=owned[--live];free(p);
}
#define calloc checked_calloc
#define free checked_free
#include "mesh_packet.h"
#undef calloc
#undef free
int main(int argc,char **argv){
    if(argc==2){char *end=NULL;unsigned long n=strtoul(argv[1],&end,10);if(!n||*end||n>sizeof(owned)/sizeof(*owned))return 2;fail_at=(size_t)n;}
    else if(argc!=1)return 2;
    MeshBatch b;
    if(!mesh_load(stdin,&b)){
        assert(!live&&!b.shader&&!b.frames&&!b.n&&!b.pixel_bytes&&!b.shader_len);
        mesh_free(&b);assert(!live);
        return fail_at&&attempts<fail_at?2:1;
    }
    assert(!fail_at);
    printf("%u %zu\n",b.n,b.pixel_bytes);
    mesh_free(&b);mesh_free(&b);assert(!live);
    return 0;
}
