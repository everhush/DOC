#ifndef DOC_GRAPH_READER_SLOTS_H
#define DOC_GRAPH_READER_SLOTS_H
#include <stdint.h>
/* Independent physical reader reservations, protected by the graph mutex.
 * Not reference counts: each callback owns a private immutable copy. */
#ifndef DOC_GRAPH_READER_SLOTS
#define DOC_GRAPH_READER_SLOTS 8
#endif
#if DOC_GRAPH_READER_SLOTS < 1 || DOC_GRAPH_READER_SLOTS > 64
#error invalid graph reader capacity
#endif
static int graph_slot_take(uint64_t *slots){
    for(unsigned i=0;i<DOC_GRAPH_READER_SLOTS;i++){
        uint64_t bit=UINT64_C(1)<<i;
        if(!(*slots&bit)){*slots|=bit;return (int)i;}
    }
    return -1;
}
static int graph_slot_drop(uint64_t *slots,int slot){
    if(slot<0||slot>=DOC_GRAPH_READER_SLOTS)return 0;
    uint64_t bit=UINT64_C(1)<<(unsigned)slot;
    if(!(*slots&bit))return 0;
    *slots&=~bit;return 1;
}
#endif
