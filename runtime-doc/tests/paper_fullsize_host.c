#define _GNU_SOURCE
#include <stddef.h>
#include <stdint.h>
static _Thread_local size_t paper_test_id;
#include "reactive_values.h"
#include <time.h>
#include <assert.h>
extern int64_t prime_leaf(int64_t,uint64_t,uint64_t);
extern int64_t financial_leaf(int64_t,int64_t,int64_t,int64_t);
extern void seed_sort(int64_t*,size_t);
enum {P_SOURCE,P_ID,P_PRIME,P_ADD,P_FIN,P_MIN,P_MAX,P_EXPENSIVE};
#define MAX 25000
static V values[MAX];static State nodes[MAX];static int op[MAX];static int64_t initial[MAX];static size_t deps[MAX][4];static char names[MAX][20];static size_t users_offsets[MAX+1],*users,ns,nd;static uint64_t start_prime=100000,interval=1200;
static V eval_test(void){size_t i=paper_test_id,*d=deps[i];switch(op[i]){case P_SOURCE:return vi(initial[i]);case P_ID:return values[d[0]];case P_PRIME:return vi(prime_leaf(num(values[d[0]]),start_prime,interval));case P_ADD:return v_add(values[d[0]],values[d[1]]);case P_EXPENSIVE:{int64_t z=num(values[d[0]]);for(size_t k=0;k<2000000;k++)z=(z*48271+1)%2147483647;return vi(z);}case P_FIN:return vi(financial_leaf(num(values[d[0]]),num(values[d[1]]),num(values[d[2]]),num(values[d[3]])));case P_MIN:return num(values[d[0]])<=num(values[d[1]])?values[d[0]]:values[d[1]];case P_MAX:return num(values[d[0]])>=num(values[d[1]])?values[d[0]]:values[d[1]];default:abort();}}
static size_t add_node(int operation,int64_t seed,size_t n,size_t a,size_t b,size_t c,size_t d){assert(ns<MAX);size_t i=ns++;op[i]=operation;initial[i]=seed;snprintf(names[i],sizeof(names[i]),"s%zu",i);deps[i][0]=a;deps[i][1]=b;deps[i][2]=c;deps[i][3]=d;nodes[i]=(State){names[i],I,operation==P_SOURCE?1:2,&values[i],eval_test,deps[i],n};if(operation!=P_SOURCE)nd++;return i;}
static void prepare_users(void){for(size_t i=0;i<ns;i++)for(size_t j=0;j<nodes[i].ndeps;j++){assert(deps[i][j]<i);users_offsets[deps[i][j]+1]++;}for(size_t i=1;i<=ns;i++)users_offsets[i]+=users_offsets[i-1];users=calloc(users_offsets[ns],sizeof(size_t));assert(users);size_t *cursor=malloc(ns*sizeof(size_t));memcpy(cursor,users_offsets,ns*sizeof(size_t));for(size_t i=0;i<ns;i++)for(size_t j=0;j<nodes[i].ndeps;j++)users[cursor[deps[i][j]]++]=i;free(cursor);}
/* Test-only equivalent CSR policy. Follows the same direct successor, reverse
 * demand, forward active-ancestor and full ready-frontier rules as emitted C.
 * This does NOT benchmark compiler-generated unrolled edge code at full size. */
static void doc_mark(size_t id,unsigned char *dirty){for(size_t i=users_offsets[id];i<users_offsets[id+1];i++)dirty[users[i]]=1;}
static void doc_demand(unsigned char *need){for(size_t i=ns;i-->0;)if(need[i])for(size_t j=0;j<nodes[i].ndeps;j++)need[deps[i][j]]=1;}
static void doc_block(const unsigned char *dirty,unsigned char *blocked){for(size_t i=0;i<ns;i++)for(size_t j=0;j<nodes[i].ndeps;j++){size_t p=deps[i][j];if(dirty[p]||blocked[p]){blocked[i]=1;break;}}}
static size_t doc_select(const unsigned char *dirty,const unsigned char *need,const unsigned char *blocked,size_t *queue){size_t n=0;for(size_t i=0;i<ns;i++)if(nodes[i].role==2&&dirty[i]&&need[i]&&!blocked[i])queue[n++]=i;return n;}
static size_t reduce(size_t *cur,size_t n){while(n>1){size_t k=0;for(size_t i=0;i<n;i+=2)cur[k++]=i+1==n?cur[i]:add_node(P_ADD,0,2,cur[i],cur[i+1],0,0);n=k;}return cur[0];}
static size_t sources[4096],payroll[4096],cur[4096],outs[512],root,units;
static int64_t sort_initial[512];
static int64_t revenue(size_t i){return 250000+(i*7919)%90000;}
static int64_t material(size_t i){return 70000+(i*3571)%30000;}
static int64_t payroll0(size_t i){return 60000+(i*1237)%25000;}
static int64_t overhead(size_t i){return 20000+(i*331)%12000;}
static int64_t financial_oracle(int64_t r,int64_t m,int64_t p,int64_t o){int64_t cost=m+p+o,total=0;for(int month=0;month<360;month++){r+=r/400+((month%12)-6)*3;cost+=cost/500+month%5;total+=(r-cost)/(100+month/12);}return total;}
static int order_i64(const void *a,const void *b){int64_t x=*(const int64_t*)a,y=*(const int64_t*)b;return (x>y)-(x<y);}
static double elapsed(struct timespec a,struct timespec b){return (b.tv_sec-a.tv_sec)*1000.0+(b.tv_nsec-a.tv_nsec)/1e6;}
static void stabilize(Epoch *e,int n,char **args){size_t t=0;assert(epoch_begin(e));int ok=batch(e,n,args,&t);if(!epoch_finish(e,ok)){fprintf(stderr,"failed batch\n");exit(2);}}
static void set_arg(char *p,size_t id,int64_t value){snprintf(p,64,"%s=%lld",names[id],(long long)value);}
int main(int argc,char **argv){assert(argc>=2);const char *scenario=argv[1];size_t changed=argc>2?strtoull(argv[2],NULL,10):0;int dense=!strcmp(scenario,"dense-cheap"),finance=!strcmp(scenario,"financial"),sort=!strcmp(scenario,"bitonic"),parallel=!strcmp(scenario,"parallel"),cold=!strcmp(scenario,"cold"),cutoff=!strcmp(scenario,"cutoff");
 if(cutoff){units=2;sources[0]=add_node(P_SOURCE,2,0,0,0,0,0);sources[1]=add_node(P_SOURCE,3,0,0,0,0,0);size_t sum=add_node(P_ADD,0,2,sources[0],sources[1],0,0);root=add_node(P_EXPENSIVE,0,1,sum,0,0,0);assert(ns==4&&nd==2);}
 else if(finance){units=4096;for(size_t i=0;i<units;i++){size_t a=add_node(P_SOURCE,revenue(i),0,0,0,0,0),b=add_node(P_SOURCE,material(i),0,0,0,0,0),c=add_node(P_SOURCE,payroll0(i),0,0,0,0,0),d=add_node(P_SOURCE,overhead(i),0,0,0,0,0);sources[i]=a;payroll[i]=c;cur[i]=add_node(P_FIN,0,4,a,b,c,d);}root=reduce(cur,units);assert(ns==24575&&nd==8191);}
 else if(sort){units=512;seed_sort(sort_initial,units);for(size_t i=0;i<units;i++)cur[i]=sources[i]=add_node(P_SOURCE,sort_initial[i],0,0,0,0,0);for(size_t k=2;k<=units;k*=2)for(size_t j=k/2;j;j/=2){size_t next[512];memcpy(next,cur,units*sizeof(size_t));for(size_t i=0;i<units;i++){size_t p=i^j;if(p<=i)continue;size_t lo=add_node(P_MIN,0,2,cur[i],cur[p],0,0),hi=add_node(P_MAX,0,2,cur[i],cur[p],0,0);next[i]=i&k?hi:lo;next[p]=i&k?lo:hi;}memcpy(cur,next,units*sizeof(size_t));}memcpy(outs,cur,sizeof(outs));assert(ns==23552&&nd==23040);}
 else {units=dense?4096:parallel?40:2048;if(parallel){start_prime=500000;interval=25000;}for(size_t i=0;i<units;i++){sources[i]=add_node(P_SOURCE,i,0,0,0,0,0);cur[i]=add_node(dense?P_ID:P_PRIME,0,1,sources[i],0,0,0);}root=reduce(cur,units);assert(ns==3*units-1&&nd==2*units-1);}
 assert(changed<=units);prepare_users();Epoch e;epoch_init(&e,nodes,ns);struct timespec a,b;clock_gettime(CLOCK_MONOTONIC,&a);stabilize(&e,0,NULL);clock_gettime(CLOCK_MONOTONIC,&b);double cold_ms=elapsed(a,b);size_t evals=e.evaluations;double update_ms=0;
 char (*text)[64]=calloc(units*2,sizeof(*text));char **args=calloc(units*2,sizeof(*args));assert(text&&args);for(size_t i=0;i<2*units;i++)args[i]=text[i];
 if(cutoff){set_arg(text[0],sources[0],4);set_arg(text[1],sources[1],1);clock_gettime(CLOCK_MONOTONIC,&a);stabilize(&e,2,args);clock_gettime(CLOCK_MONOTONIC,&b);update_ms=elapsed(a,b);evals=e.evaluations;assert(evals==1);}
 else if(dense){evals=0;clock_gettime(CLOCK_MONOTONIC,&a);for(size_t ep=0;ep<30;ep++){for(size_t i=0;i<units;i++)set_arg(text[i],sources[i],i+ep+1);stabilize(&e,units,args);evals+=e.evaluations;}clock_gettime(CLOCK_MONOTONIC,&b);update_ms=elapsed(a,b);}
 else if(!cold&&!parallel){size_t n=0;for(size_t i=0;i<changed;i++){if(finance){set_arg(text[n++],sources[i],revenue(i)+2500+i%17);set_arg(text[n++],payroll[i],payroll0(i)+400+i%11);}else set_arg(text[n++],sources[i],sort?sort_initial[i]+999999+i*104729:i+5000);}clock_gettime(CLOCK_MONOTONIC,&a);stabilize(&e,n,args);clock_gettime(CLOCK_MONOTONIC,&b);update_ms=elapsed(a,b);evals=e.evaluations;}
 /* Independent full numerical oracle, outside timed intervals. */
 int64_t expected=0,actual=0;if(cutoff){expected=5;for(int i=0;i<2000000;i++)expected=(expected*48271+1)%2147483647;actual=num(values[root]);assert(actual==expected);}
 else if(finance){for(size_t i=0;i<units;i++)expected+=financial_oracle(revenue(i)+(i<changed?2500+i%17:0),material(i),payroll0(i)+(i<changed?400+i%11:0),overhead(i));actual=num(values[root]);assert(actual==expected);}
 else if(sort){for(size_t i=0;i<changed;i++)sort_initial[i]+=999999+i*104729;qsort(sort_initial,units,sizeof(int64_t),order_i64);for(size_t i=0;i<units;i++){assert(num(values[outs[i]])==sort_initial[i]);actual+=num(values[outs[i]]);expected+=sort_initial[i];}}
 else {if(dense)for(size_t i=0;i<units;i++)expected+=i+30;else {size_t high=start_prime+interval+units+5001;unsigned char *p=malloc(high);memset(p,1,high);p[0]=p[1]=0;for(size_t i=2;i*i<high;i++)if(p[i])for(size_t j=i*i;j<high;j+=i)p[j]=0;for(size_t i=0;i<units;i++){size_t begin=start_prime+i+(i<changed?5000:0);for(size_t j=begin;j<begin+interval;j++)expected+=p[j];}free(p);}actual=num(values[root]);assert(actual==expected);}
 printf("scenario=%s changed=%zu states=%zu derived=%zu cold_ms=%.9f update_ms=%.9f evaluations=%zu value=%lld launched=%zu\n",scenario,changed,ns,nd,cold_ms,update_ms,evals,(long long)actual,e.launched);epoch_free(&e);assert(!live_bytes);free(users);free(args);free(text);return 0;
}
