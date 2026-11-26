#ifndef DOC_PLACED_TRANSPORT_H
#define DOC_PLACED_TRANSPORT_H
/* Bounded one-process TCP loopback profile. This is platform framing and
 * resource ownership, not a distributed consensus or remote code loader. */
#include <sys/socket.h>
#include <netinet/in.h>
#include <sys/time.h>
#include "placed_policy_generated.h"
#define PLACE_MAX_RESOURCES 8
#define PLACE_WIRE_BYTES 96
#define PLACE_MAGIC UINT64_C(0x444f433131504c31)
typedef struct {int tx,rx,active,failed;} PlaceEndpoint;
typedef struct {int resource;int64_t generation;} PlaceRole;
typedef struct {int seen;int kind;int64_t value;} PlaceReceipt;
typedef struct {size_t roles_n;PlaceRole *roles;PlaceEndpoint resources[PLACE_MAX_RESOURCES];uint64_t sent,received;} Placed;
static void place_endpoint_close(PlaceEndpoint *p){if(p->tx>=0)close(p->tx);if(p->rx>=0)close(p->rx);*p=(PlaceEndpoint){-1,-1,0,0};}
static int place_socket_timeout(int fd){struct timeval t={2,0};return !setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&t,sizeof t)&&!setsockopt(fd,SOL_SOCKET,SO_SNDTIMEO,&t,sizeof t);}
static int place_endpoint_open(PlaceEndpoint *p){
    int listener=-1,tx=-1,rx=-1,ok=0;struct sockaddr_in addr={.sin_family=AF_INET,.sin_addr={htonl(INADDR_LOOPBACK)}},local,peer;socklen_t z=sizeof addr;
    listener=socket(AF_INET,SOCK_STREAM|SOCK_CLOEXEC,0);
    if(listener<0||!place_socket_timeout(listener)||bind(listener,(struct sockaddr*)&addr,sizeof addr)||listen(listener,1)||getsockname(listener,(struct sockaddr*)&addr,&z))goto done;
    tx=socket(AF_INET,SOCK_STREAM|SOCK_CLOEXEC,0);if(tx<0||!place_socket_timeout(tx)||connect(tx,(struct sockaddr*)&addr,sizeof addr))goto done;
    z=sizeof peer;rx=accept4(listener,(struct sockaddr*)&peer,&z,SOCK_CLOEXEC);if(rx<0||!place_socket_timeout(rx))goto done;
    z=sizeof local;if(getsockname(tx,(struct sockaddr*)&local,&z)||peer.sin_family!=AF_INET||peer.sin_addr.s_addr!=htonl(INADDR_LOOPBACK)||peer.sin_port!=local.sin_port)goto done;
    *p=(PlaceEndpoint){tx,rx,1,0};ok=1;
done:if(listener>=0)close(listener);if(!ok){if(tx>=0)close(tx);if(rx>=0)close(rx);}return ok;
}
static int placed_init(Placed *p,size_t states){
    *p=(Placed){0};for(size_t i=0;i<PLACE_MAX_RESOURCES;i++)p->resources[i]=(PlaceEndpoint){-1,-1,0,0};
    if(!states||states>65536)return 0;p->roles_n=2*states;p->roles=calloc(p->roles_n,sizeof(*p->roles));if(!p->roles){p->roles_n=0;return 0;}
    for(size_t i=0;i<p->roles_n;i++)p->roles[i].resource=-1;return 1;
}
static void placed_free(Placed *p){for(size_t i=0;i<PLACE_MAX_RESOURCES;i++)place_endpoint_close(p->resources+i);free(p->roles);p->roles=NULL;p->roles_n=0;}
/* Single coordinator, quiescent endpoints. Preflight generation exhaustion
 * for every role before changing any authority. */
static int placed_rebalance(Placed *p){
    int live[PLACE_MAX_RESOURCES],n=0;for(int i=0;i<PLACE_MAX_RESOURCES;i++)if(p->resources[i].active)live[n++]=i;
    for(int pass=0;pass<2;pass++)for(size_t i=0;i<p->roles_n;i++){
        int64_t slot=num(F_placed_slot(vi((int64_t)i),vi(n)));int dest=slot<0?-1:live[slot];PlaceRole *r=p->roles+i;
        int64_t g=num(F_placed_advance(vi(r->resource),vi(dest),vi(r->generation)));if(g<0)return 0;
        if(pass){r->resource=dest;r->generation=g;}
    }return 1;
}
static int placed_join(Placed *p){if(!p->roles)return -1;for(int i=0;i<PLACE_MAX_RESOURCES;i++)if(!p->resources[i].active){if(!place_endpoint_open(p->resources+i))return -1;if(!placed_rebalance(p)){place_endpoint_close(p->resources+i);return -1;}return i;}return -1;}
static int placed_remove(Placed *p,int i){if(i<0||i>=PLACE_MAX_RESOURCES||!p->resources[i].active)return 0;p->resources[i].active=0;if(!placed_rebalance(p)){p->resources[i].active=1;return 0;}place_endpoint_close(p->resources+i);return 1;}
static int placed_current(const Placed *p,size_t role,int resource,int64_t gen){if(role>=p->roles_n||resource<0||resource>=PLACE_MAX_RESOURCES||(!p->resources[resource].active||p->resources[resource].failed))return 0;PlaceRole r=p->roles[role];return truth(F_placed_token(vi((int64_t)role),vi(r.resource),vi(r.generation),vi((int64_t)role),vi(resource),vi(gen)));}
static void place_put(unsigned char *p,uint64_t x){for(int i=0;i<8;i++){p[i]=(unsigned char)x;x>>=8;}}
static uint64_t place_get(const unsigned char *p){uint64_t x=0;for(int i=7;i>=0;i--)x=(x<<8)|p[i];return x;}
static uint64_t place_checksum(const unsigned char *p){uint64_t h=UINT64_C(0xcbf29ce484222325);for(size_t i=0;i<PLACE_WIRE_BYTES-8;i++)h=(h^p[i])*UINT64_C(0x100000001b3);return h;}
static int place_frame(const Placed *p,int64_t epoch,size_t state,size_t definition,V v,unsigned char out[PLACE_WIRE_BYTES]){
    if(!out||epoch<=0||state>=p->roles_n/2||definition>=p->roles_n/2||(v.kind!=I&&v.kind!=B)||(v.kind==B&&v.x!=0&&v.x!=1))return 0;
    size_t sender=state*2,receiver=definition*2+1;PlaceRole a=p->roles[sender],b=p->roles[receiver];
    if(!placed_current(p,sender,a.resource,a.generation)||!placed_current(p,receiver,b.resource,b.generation))return 0;
    uint64_t fields[]={PLACE_MAGIC,(uint64_t)epoch,state,sender,(uint64_t)a.resource,(uint64_t)a.generation,receiver,(uint64_t)b.resource,(uint64_t)b.generation,(uint64_t)v.kind,(uint64_t)v.x};
    for(size_t i=0;i<11;i++)place_put(out+i*8,fields[i]);place_put(out+88,place_checksum(out));return 1;
}
/* Reject before mutating receipt or output. 0 = first, 1 = identical
 * duplicate, -1 = stale/wrong-role/conflict/invalid framing. */
static int place_admit(const Placed *p,int64_t epoch,size_t state,size_t definition,int kind,PlaceReceipt *receipt,const unsigned char *in,size_t n,V *out){
    if(!in||n!=PLACE_WIRE_BYTES||!receipt||!out||epoch<=0||state>=p->roles_n/2||definition>=p->roles_n/2||(kind!=I&&kind!=B)||place_get(in)!=PLACE_MAGIC||place_get(in+88)!=place_checksum(in))return -1;
    uint64_t f[11];for(size_t i=0;i<11;i++)f[i]=place_get(in+i*8);for(size_t i=1;i<10;i++)if(f[i]>INT64_MAX)return -1;
    size_t sender=state*2,receiver=definition*2+1;PlaceRole a=p->roles[sender],b=p->roles[receiver];
    if(!truth(F_placed_epoch(vi(epoch),vi((int64_t)f[1])))||f[2]!=state||f[9]!=(uint64_t)kind||(kind==B&&f[10]>1)||f[4]>=PLACE_MAX_RESOURCES||f[7]>=PLACE_MAX_RESOURCES||!p->resources[f[4]].active||!p->resources[f[7]].active||p->resources[f[4]].failed||p->resources[f[7]].failed)return -1;
    if(!truth(F_placed_token(vi((int64_t)sender),vi(a.resource),vi(a.generation),vi((int64_t)f[3]),vi((int64_t)f[4]),vi((int64_t)f[5])))||!truth(F_placed_token(vi((int64_t)receiver),vi(b.resource),vi(b.generation),vi((int64_t)f[6]),vi((int64_t)f[7]),vi((int64_t)f[8]))))return -1;
    int64_t value=f[10]<=INT64_MAX?(int64_t)f[10]:-1-(int64_t)(UINT64_MAX-f[10]);int rc=(int)num(F_placed_receipt(vb(receipt->seen),vi(receipt->kind),vi(receipt->value),vi(kind),vi(value)));if(rc<0)return -1;
    *receipt=(PlaceReceipt){1,kind,value};*out=kind==I?vi(value):vb((int)value);return rc;
}
static int place_io(int fd,unsigned char *p,size_t n,int send_data){size_t at=0;while(at<n){ssize_t z=send_data?send(fd,p+at,n-at,MSG_NOSIGNAL):recv(fd,p+at,n-at,0);if(z<0&&errno==EINTR)continue;if(z<=0)return 0;at+=(size_t)z;}return 1;}
static int placed_transfer(Placed *p,int64_t epoch,size_t state,size_t definition,V v,PlaceReceipt *receipt,V *out){
    unsigned char wire[PLACE_WIRE_BYTES],received[PLACE_WIRE_BYTES];if(!place_frame(p,epoch,state,definition,v,wire))return -1;int id=p->roles[definition*2+1].resource;PlaceEndpoint *r=p->resources+id;
    if(p->sent==UINT64_MAX||p->received==UINT64_MAX)return -1;
    if(!place_io(r->tx,wire,sizeof wire,1)){r->failed=1;return -1;}p->sent++;if(!place_io(r->rx,received,sizeof received,0)){r->failed=1;return -1;}p->received++;
    return place_admit(p,epoch,state,definition,v.kind,receipt,received,sizeof received,out);
}
#endif
