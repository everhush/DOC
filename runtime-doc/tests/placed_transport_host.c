#include "value_primitives.h"
#include "placed_transport.h"
#include <assert.h>
static void reject(Placed *p,int64_t epoch,size_t state,size_t definition,int kind,PlaceReceipt *r,unsigned char *wire,size_t n,V *out){PlaceReceipt old=*r;V v=*out;assert(place_admit(p,epoch,state,definition,kind,r,wire,n,out)==-1);assert(r->seen==old.seen&&r->kind==old.kind&&r->value==old.value&&v.kind==out->kind&&v.x==out->x);}
int main(void){
    Placed p;assert(placed_init(&p,8));assert(placed_join(&p)==0);assert(placed_join(&p)==1);assert(placed_join(&p)==2);
    assert(p.roles[0].resource==0&&p.roles[3].resource==0&&p.roles[5].resource==2);
    unsigned char packet[PLACE_WIRE_BYTES],bad[PLACE_WIRE_BYTES];PlaceReceipt r={0};V out=vi(0);
    assert(place_frame(&p,7,0,2,vi(INT64_MIN),packet));assert(place_admit(&p,7,0,2,I,&r,packet,sizeof packet,&out)==0&&num(out)==INT64_MIN);
    assert(placed_transfer(&p,7,0,2,vi(INT64_MIN),&r,&out)==1);
    assert(placed_transfer(&p,7,0,2,vi(INT64_MAX),&r,&out)==-1&&num(out)==INT64_MIN);
    for(size_t i=0;i<sizeof packet;i++){memcpy(bad,packet,sizeof bad);bad[i]^=1;reject(&p,7,0,2,I,&r,bad,sizeof bad,&out);reject(&p,7,0,2,I,&r,packet,i,&out);}
    for(size_t i=1;i<=9;i++){memcpy(bad,packet,sizeof bad);place_put(bad+8*i,place_get(bad+8*i)^1);place_put(bad+88,place_checksum(bad));reject(&p,7,0,2,I,&r,bad,sizeof bad,&out);}
    reject(&p,8,0,2,I,&r,packet,sizeof packet,&out);reject(&p,7,1,2,I,&r,packet,sizeof packet,&out);reject(&p,7,0,1,I,&r,packet,sizeof packet,&out);
    int res=p.roles[5].resource;int64_t gen=p.roles[5].generation;assert(placed_remove(&p,res));assert(!placed_current(&p,5,res,gen));reject(&p,7,0,2,I,&r,packet,sizeof packet,&out);assert(placed_join(&p)==res);assert(!placed_current(&p,5,res,gen));
    for(int64_t k=1;k<=4096;k++){r=(PlaceReceipt){0};assert(placed_transfer(&p,k,0,2,vi(k),&r,&out)==0&&num(out)==k);assert(placed_transfer(&p,k,0,2,vi(k),&r,&out)==1);}
    r=(PlaceReceipt){0};assert(placed_transfer(&p,9,1,3,vb(1),&r,&out)==0&&truth(out));
    int dead=p.roles[5].resource;assert(!shutdown(p.resources[dead].rx,SHUT_RDWR));r=(PlaceReceipt){0};assert(placed_transfer(&p,99,0,2,vi(4),&r,&out)==-1);assert(p.resources[dead].failed&&!placed_current(&p,5,dead,p.roles[5].generation));assert(placed_remove(&p,dead));assert(placed_join(&p)==dead);
    for(int i=0;i<PLACE_MAX_RESOURCES;i++)if(p.resources[i].active)assert(placed_remove(&p,i));assert(!place_frame(&p,1,0,2,vi(0),packet));assert(placed_join(&p)==0);
    for(int i=1;i<PLACE_MAX_RESOURCES;i++)assert(placed_join(&p)==i);assert(placed_join(&p)==-1);
    p.roles[1].generation=INT64_MAX;int old=p.roles[1].resource;assert(!placed_remove(&p,old));assert(p.resources[old].active&&p.roles[1].resource==old);placed_free(&p);assert(!live_bytes);
    printf("DOC11_PLACED_TRANSPORT_PASS: %llu actual TCP frames sent; stale/wrong roles, conflicts, all byte mutations/truncations, join/drain/rejoin, broken endpoint and generation exhaustion\n",(unsigned long long)p.sent);return 0;
}
