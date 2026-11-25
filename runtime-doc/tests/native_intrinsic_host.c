#include <assert.h>
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include "intrinsics.h"
#include "external.h"
static unsigned calls;
int32_t target_transform(int64_t x,uint8_t enabled){calls++;return enabled?(int32_t)(-17-(x%100)):42;}
static void check(uint64_t x){int64_t input;memcpy(&input,&x,8);struct doc_result_intrinsics o;assert(doc_export_intrinsics(input,&o));unsigned bits=0,lead=0,tail=0;for(unsigned i=0;i<64;i++)bits+=(x>>i)&1;while(lead<64&&!((x>>(63-lead))&1))lead++;while(tail<64&&!((x>>tail)&1))tail++;assert(o.s_bits==bits&&o.s_lead==lead&&o.s_tail==tail);}
int main(void){check(0);check(UINT64_MAX);for(unsigned i=0;i<64;i++)check(UINT64_C(1)<<i);uint64_t x=0x123456789abcdef0ULL;for(int i=0;i<4096;i++){x^=x<<13;x^=x>>7;x^=x<<17;check(x);}struct doc_result_external e={0},old;assert(doc_export_external(7,1,&e)&&e.s_transformed==-24&&calls==1);assert(doc_export_external(7,0,&e)&&e.s_transformed==42&&calls==2);old=e;assert(!doc_export_external(7,2,&e)&&!memcmp(&old,&e,sizeof(e))&&calls==2);assert(!doc_export_external(7,1,0)&&calls==2);puts("DOC11_NATIVE_INTRINSICS_HOST_PASS: 4162 signed bit-pattern cases and external ABI admission");}
