#include "scope.h"
#include "stream.h"
#include "repeat_scope.h"
#include "multi_carry.h"
#include <assert.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static int identity,acquired,released,depth,max_depth;
static int32_t stack[4],last_release;
int32_t acquire(int32_t argument){
    acquired++;
    if(argument<0)return -1;
    int32_t h=identity?argument:100+acquired;
    assert(depth<4);stack[depth++]=h;if(depth>max_depth)max_depth=depth;
    return h;
}
void release_handle(int32_t h){assert(depth>0&&stack[depth-1]==h);depth--;released++;last_release=h;}
static void reset(int mode){assert(!depth);identity=mode;acquired=released=max_depth=0;last_release=-1;}
static void check_scope(void){
    struct doc_result_scope out,save;memset(&out,0xa5,sizeof out);save=out;
    reset(0);assert(doc_export_scope(7,1,1,&out));assert(out.s_first==101&&out.s_second==102&&out.s_quotient==102);assert(acquired==2&&released==2&&!depth&&max_depth==2&&last_release==101);
    reset(0);assert(doc_export_scope(7,0,1,&out));assert(out.s_first==99&&out.s_second==101);assert(acquired==1&&released==1&&!depth&&max_depth==1&&last_release==101);
    save=out;reset(0);assert(!doc_export_scope(7,1,0,&out));assert(!memcmp(&out,&save,sizeof out)&&acquired==2&&released==2&&!depth&&last_release==101);
    reset(0);assert(doc_export_scope(-1,1,1,&out));assert(out.s_first==-1&&out.s_second==-1&&acquired==2&&!released&&!depth);
    save=out;reset(0);assert(!doc_export_scope(INT64_MAX,1,1,&out));assert(!memcmp(&out,&save,sizeof out)&&!acquired&&!released);
    assert(!doc_export_scope(7,2,1,&out)&&!acquired);assert(!doc_export_scope(7,1,1,NULL)&&!acquired);
}
static void check_repeat(void){
    struct doc_result_repeat_scope out,save;memset(&out,0xa5,sizeof out);
    reset(1);assert(doc_export_repeat_scope(0,3,-1,&out));assert(out.s_step==2&&out.s_next==3&&out.s_owned==2&&out.s_halt);assert(acquired==3&&released==3&&!depth&&max_depth==1);
    save=out;reset(1);assert(!doc_export_repeat_scope(0,3,2,&out));assert(!memcmp(&out,&save,sizeof out)&&acquired==2&&released==2&&!depth&&max_depth==1);
    reset(1);assert(!doc_export_repeat_scope(0,65537,-1,&out));assert(!memcmp(&out,&save,sizeof out)&&acquired==65536&&released==65536&&!depth&&max_depth==1);
    struct doc_result_multi_carry multi;assert(doc_export_multi_carry(11,22,0,2,&multi));assert(multi.s_left==22&&multi.s_right==11&&multi.s_next==2&&multi.s_halt);
}
static void check_stream(void){
    int input[2],output[2];assert(!pipe(input)&&!pipe(output));assert(write(input[1],"abcde",5)==5);assert(!close(input[1]));uint8_t bytes[8]={0};struct doc_result_stream out,save;
    memset(&out,0xa5,sizeof out);assert(doc_export_stream(input[0],output[1],2,1,10,-1,bytes,sizeof bytes,&out));assert(out.s_total==15&&out.s_next_total==15&&out.s_received==0&&out.s_sent==0&&out.s_complete&&out.s_stopped);
    assert(!close(output[1]));char copied[8]={0};assert(read(output[0],copied,sizeof copied)==5&&!memcmp(copied,"abcde",5));assert(read(output[0],copied,sizeof copied)==0);assert(!close(input[0])&&!close(output[0]));
    save=out;assert(!doc_export_stream(-1,-1,2,7,0,-1,bytes,sizeof bytes,&out));assert(!memcmp(&out,&save,sizeof out));
    assert(!doc_export_stream(-1,-1,1,0,0,-1,&out,sizeof out,&out));assert(!memcmp(&out,&save,sizeof out));
}
int main(void){check_scope();check_repeat();check_stream();puts("DOC11_NATIVE_LIFECYCLE_PASS: scoped LIFO and guard/error cleanup, per-epoch release, 65536-step exhaustion, simultaneous carries, real pipe stream and atomic failure output");return 0;}
