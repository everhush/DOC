/* Host-only oracle for the original native_regions.doc effect chain. */
#include "regions.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdatomic.h>
#include <limits.h>
int main(void){
 uint8_t device[4]={0};_Atomic(uint32_t) counter[4]={0};
 struct doc_result_regions out={0},saved;
 assert(doc_export_regions(1,42,2,device,4,counter,4,&out));
 assert(device[1]==42&&counter[1]==2&&out.s_previous==0&&out.s_total==2&&out.s_read_back==42&&out.s_ordered);
 assert(doc_export_regions(1,255,3,device,4,counter,4,&out));
 assert(device[1]==255&&counter[1]==5&&out.s_previous==2&&out.s_total==5);
 saved=out;
 assert(!doc_export_regions(-1,1,1,device,4,counter,4,&out));
 assert(!doc_export_regions(1,256,1,device,4,counter,4,&out));
 assert(!doc_export_regions(1,1,1,counter,4,counter,4,&out));
 assert(!doc_export_regions(1,1,1,device,4,(char*)counter+1,1,&out));
 assert(!doc_export_regions(1,1,1,&out,sizeof(out),counter,4,&out));
 assert(!doc_export_regions(1,1,1,device,4,counter,SIZE_MAX,&out));
 assert(!doc_export_regions(1,1,1,device,4,counter,4,NULL));
 assert(!memcmp(&saved,&out,sizeof(out))&&device[1]==255&&counter[1]==5);
 /* External stores are irreversible, but failed results are not published. */
 assert(!doc_export_regions(1,7,-1,device,4,counter,4,&out));
 assert(device[1]==7&&counter[1]==5&&!memcmp(&saved,&out,sizeof(out)));
 atomic_store(&counter[1],UINT32_MAX);
 assert(doc_export_regions(1,8,1,device,4,counter,4,&out));
 assert(out.s_previous==UINT32_MAX&&out.s_total==0&&counter[1]==0);
 puts("DOC11_NATIVE_REGIONS_HOST_PASS: checked alignment/disjointness/bounds, seq_cst fence and wrapping u32 atomic addition, irreversible effects explicit");
}
