#ifndef DOC_GRAPH_VARIANT_ABI_H
#define DOC_GRAPH_VARIANT_ABI_H
/* Private native linkage ABI: a graph variant has one coordinator and one
 * instance at a time. No runtime parser or loading untrusted native code. */
#ifndef DOC_REACTIVE_VALUES
#define DOC_REACTIVE_VALUES
#endif
#include "value_primitives.h"
typedef struct {const char *name;int kind,role;V value;} GraphFact;
typedef int (*GraphVisit)(void *,const GraphFact *,size_t);
typedef struct {
    void *(*create)(const GraphFact *,size_t);
    void (*destroy)(void *);
    int (*update)(void *,int,char **);
    int (*read)(void *,GraphVisit,void *);
    size_t (*live)(void);
    /* Writer-quiescent diagnostics, never a reader ownership mechanism. */
    uint64_t (*device_live)(void);
    size_t (*dispatches)(void);
} GraphVariant;
#endif
