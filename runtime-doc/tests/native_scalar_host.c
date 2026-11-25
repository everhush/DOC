#include "boot.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <limits.h>
static unsigned calls;
static uint32_t last_port;
static uint8_t last_byte, result = 1;
uint8_t x86_out8(uint32_t p,uint8_t v){calls++;last_port=p;last_byte=v;return result;}
int main(void){
 uint8_t buf[2]={0}; struct doc_result_boot out={0}, before;
 assert(doc_export_boot(0,64,233,buf,2,&out));assert(buf[0]==65&&out.s_read_back==65&&out.s_emitted==1&&calls==1&&last_port==233&&last_byte==65);
 assert(doc_export_boot(1,65,233,buf,2,&out));assert(buf[1]==66&&out.s_read_back==66&&calls==2&&last_byte==66);
 before=out;
 assert(!doc_export_boot(2,66,233,buf,2,&out));assert(!memcmp(&before,&out,sizeof out)&&buf[0]==65&&buf[1]==66&&calls==2);
 assert(!doc_export_boot(-1,66,233,buf,2,&out));assert(!memcmp(&before,&out,sizeof out)&&calls==2);
 assert(!doc_export_boot(0,INT64_MAX,233,buf,2,&out));assert(!memcmp(&before,&out,sizeof out)&&calls==2);
 assert(!doc_export_boot(0,255,233,buf,2,&out));assert(!memcmp(&before,&out,sizeof out)&&calls==2);
 assert(!doc_export_boot(0,64,233,0,2,&out));assert(!memcmp(&before,&out,sizeof out)&&calls==2);
 assert(!doc_export_boot(0,64,233,buf,2,0));assert(calls==2);
 assert(!doc_export_boot(0,64,233,(uint8_t*)&out,sizeof out,&out));assert(!memcmp(&before,&out,sizeof out)&&calls==2);
 _Alignas(struct doc_result_boot) uint8_t mis[sizeof out+1];assert(!doc_export_boot(0,64,233,buf,2,(struct doc_result_boot*)(mis+1)));assert(calls==2);
 assert(!doc_export_boot(0,64,233,buf,SIZE_MAX,&out));assert(calls==2);
 result=2;assert(!doc_export_boot(0,67,233,buf,2,&out));assert(!memcmp(&before,&out,sizeof out)&&calls==3&&buf[0]==68);
 puts("native scalar ABI host checks PASS (foreign stub; irreversible effects explicitly retained)");
}
