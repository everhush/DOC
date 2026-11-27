/* Test-only timing and independent correctness oracles. Computation functions
 * and state edges above were all emitted by the admitted DOC compiler. */
#include <assert.h>
#include <time.h>
static int64_t revenue(size_t i){return 250000+(i*7919)%90000;}
static int64_t material(size_t i){return 70000+(i*3571)%30000;}
static int64_t payroll0(size_t i){return 60000+(i*1237)%25000;}
static int64_t overhead(size_t i){return 20000+(i*331)%12000;}
static int64_t financial_oracle(int64_t r,int64_t m,int64_t p,int64_t o){int64_t cost=m+p+o,total=0;for(int month=0;month<360;month++){r+=r/400+((month%12)-6)*3;cost+=cost/500+month%5;total+=(r-cost)/(100+month/12);}return total;}
static int order_i64(const void *a,const void *b){int64_t x=*(const int64_t*)a,y=*(const int64_t*)b;return (x>y)-(x<y);}
static double elapsed(struct timespec a,struct timespec b){return (b.tv_sec-a.tv_sec)*1000.0+(b.tv_nsec-a.tv_nsec)/1e6;}
static void stabilize(Epoch *e,int n,char **args){size_t t=0;assert(epoch_begin(e));int ok=batch(e,n,args,&t);if(!epoch_finish(e,ok)){fprintf(stderr,"failed batch\n");exit(2);}}
static void set_arg(char *p,size_t id,int64_t value){snprintf(p,64,"%s=%lld",states[id].name,(long long)value);}
static void set_list_arg(char *p,size_t id,int64_t value){snprintf(p,64,"%s=[%lld,0]",states[id].name,(long long)value);}
int main(int argc,char **argv){assert(argc>=2);const char *scenario=argv[1];size_t changed=argc>2?strtoull(argv[2],NULL,10):0;int dense=!strcmp(scenario,"dense-cheap"),finance=!strcmp(scenario,"financial"),sort=!strcmp(scenario,"bitonic"),cold=!strcmp(scenario,"cold");size_t units=sizeof(sources)/sizeof(sources[0]);assert(changed<=units);assert(dense||finance||sort||cold||!strcmp(scenario,"density"));size_t nd=0;for(size_t i=0;i<ns;i++)nd+=states[i].role==2;Epoch e;epoch_init(&e,states,ns);struct timespec a,b;clock_gettime(CLOCK_MONOTONIC,&a);stabilize(&e,0,NULL);clock_gettime(CLOCK_MONOTONIC,&b);double cold_ms=elapsed(a,b);size_t evals=e.evaluations;assert(evals==nd);double update_ms=0;int64_t *sort_initial=calloc(units,sizeof(int64_t));assert(sort_initial);if(sort)for(size_t i=0;i<units;i++)sort_initial[i]=num(*states[sources[i]].slot);
 char (*text)[64]=calloc(units*2,sizeof(*text));char **args=calloc(units*2,sizeof(*args));assert(text&&args);for(size_t i=0;i<2*units;i++)args[i]=text[i];
 if(dense){evals=0;clock_gettime(CLOCK_MONOTONIC,&a);for(size_t ep=0;ep<30;ep++){for(size_t i=0;i<units;i++)set_arg(text[i],sources[i],i+ep+1);stabilize(&e,units,args);evals+=e.evaluations;}clock_gettime(CLOCK_MONOTONIC,&b);update_ms=elapsed(a,b);}
 else if(!cold){size_t n=0;for(size_t i=0;i<changed;i++){if(finance){set_list_arg(text[n++],sources[i],revenue(i)+2500+i%17);set_arg(text[n++],payroll[i],payroll0(i)+400+i%11);}else set_arg(text[n++],sources[i],sort?sort_initial[i]+999999+i*104729:(100000+i+5000)*INT64_C(33554432)+3);}clock_gettime(CLOCK_MONOTONIC,&a);stabilize(&e,n,args);clock_gettime(CLOCK_MONOTONIC,&b);update_ms=elapsed(a,b);evals=e.evaluations;}
 int64_t expected=0,actual=0;if(finance){for(size_t i=0;i<units;i++)expected+=financial_oracle(revenue(i)+(i<changed?2500+i%17:0),material(i),payroll0(i)+(i<changed?400+i%11:0),overhead(i));actual=num(*states[outputs[0]].slot);assert(actual==expected);}
 else if(sort){for(size_t i=0;i<changed;i++)sort_initial[i]+=999999+i*104729;qsort(sort_initial,units,sizeof(int64_t),order_i64);for(size_t i=0;i<units;i++){assert(num(*states[outputs[i]].slot)==sort_initial[i]);actual+=num(*states[outputs[i]].slot);expected+=sort_initial[i];}}
 else {if(dense)for(size_t i=0;i<units;i++)expected+=i+30;else {size_t high=100000+1200+units+5001;unsigned char *p=malloc(high);assert(p);memset(p,1,high);p[0]=p[1]=0;for(size_t i=2;i*i<high;i++)if(p[i])for(size_t j=i*i;j<high;j+=i)p[j]=0;for(size_t i=0;i<units;i++){size_t begin=100000+i+(i<changed?5000:0);for(size_t j=begin;j<begin+1200;j++)expected+=p[j];}free(p);}actual=num(*states[outputs[0]].slot);assert(actual==expected);}
 printf("scenario=%s changed=%zu states=%zu derived=%zu cold_ms=%.9f update_ms=%.9f evaluations=%zu value=%lld launched=%zu\n",scenario,changed,ns,nd,cold_ms,update_ms,evals,(long long)actual,e.launched);epoch_free(&e);assert(!live_bytes);printf("live=0 peak=%zu allocations=%zu\n",(size_t)peak_bytes,(size_t)allocs);free(sort_initial);free(args);free(text);return 0;}
