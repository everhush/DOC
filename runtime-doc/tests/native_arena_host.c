/* Independent host oracle: the allocation calculation is generated from DOC. */
#include "arena.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
#include <stdint.h>
int main(void){
 unsigned char storage[16]={0};struct doc_result_arena out={0};
 assert(doc_export_arena(0,3,4,7,storage,16,&out));
 assert(out.s_capacity==16&&out.s_start==0&&out.s_last==2&&out.s_next==3&&storage[2]==7);
 assert(doc_export_arena(3,3,4,9,storage,16,&out));
 assert(out.s_start==4&&out.s_next==7&&storage[6]==9);
 struct doc_result_arena old=out;unsigned char saved[16];memcpy(saved,storage,16);
 const int64_t invalid[][4]={{INT64_MAX,3,4,7},{0,0,4,7},{0,3,3,7},{0,3,4,256},{14,3,4,7},{-1,3,4,7},{0,3,0,7}};
 for(size_t i=0;i<sizeof(invalid)/sizeof(invalid[0]);i++){
   const int64_t *a=invalid[i];
   assert(!doc_export_arena(a[0],a[1],a[2],a[3],storage,16,&out));
   assert(!memcmp(&old,&out,sizeof(out))&&!memcmp(saved,storage,16));
 }
 puts("DOC11_NATIVE_ARENA_HOST_PASS: original DOC allocation policy, capacity, alignment, zero/overflow/exhaustion and marker rejection");
}
