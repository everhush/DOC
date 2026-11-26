#ifndef DOC_MESH_RENDER_API_H
#define DOC_MESH_RENDER_API_H
#include "mesh_packet.h"
/* Opaque, uniquely owned native WebGPU device. No DOC values are retained. */
typedef struct MeshRendererNative MeshRendererNative;
MeshRendererNative *mesh_renderer_open(const MeshBatch *plan);
int mesh_renderer_render(MeshRendererNative *renderer,const MeshFrame *frame,unsigned char *pixels,size_t size);
int mesh_renderer_close(MeshRendererNative *renderer);
#endif
