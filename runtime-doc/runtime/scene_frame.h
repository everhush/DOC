#ifndef DOC_SCENE_FRAME_H
#define DOC_SCENE_FRAME_H
#include "mesh_packet.h"
/* Copy a complete typed candidate into owned native render buffers. This is
 * only the same integer ABI admission as mesh_load, not a scene evaluator. */
static void scene_frame_free(MeshFrame *f){free(f->vertices);free(f->indices);free(f->draws);*f=(MeshFrame){0};}
static int scene_list(const Epoch *e,const char *name,V *out){return scene_value(e,name,out)&&out->kind==L&&out->n&&out->p;}
static int scene_i32(int64_t x,MeshDomain d,int32_t *out){if(x<INT32_MIN||x>INT32_MAX||!mesh_bound(d,(int32_t)x))return 0;*out=(int32_t)x;return 1;}
static int scene_frame_copy(const Epoch *e,const MeshDomain domains[20],uint32_t w,uint32_t h,MeshFrame *f){
    *f=(MeshFrame){0};V vertices,indices,draws,clear;
    if(!w||!h||w>4096||h>4096||(uint64_t)w*h*4>MESH_BYTES)return 0;
    if(!scene_list(e,"render_vertices",&vertices)||!scene_list(e,"render_indices",&indices)||!scene_list(e,"render_draws",&draws)||!scene_list(e,"render_clear",&clear))return 0;
    if(vertices.n%12||vertices.n/12>65536||indices.n%3||indices.n>196608||draws.n%10||draws.n/10>128||clear.n!=4)return 0;
    for(size_t i=0;i<20;i++)if(domains[i].set>1||(domains[i].set?domains[i].lo>domains[i].hi:domains[i].lo||domains[i].hi))return 0;
    f->width=w;f->height=h;f->nv=(uint32_t)(vertices.n/12);f->ni=(uint32_t)indices.n;f->nd=(uint32_t)(draws.n/10);
    const int64_t *v=vertices.p,*in=indices.p,*d=draws.p,*c=clear.p;
    for(size_t i=0;i<4;i++){if(c[i]<0||c[i]>255)goto fail;f->clear[i]=(unsigned char)c[i];}
    f->vertices=calloc(f->nv,sizeof(*f->vertices));f->indices=calloc(f->ni,sizeof(*f->indices));f->draws=calloc(f->nd,sizeof(*f->draws));if(!f->vertices||!f->indices||!f->draws)goto fail;
    for(size_t i=0;i<f->nv;i++)for(size_t j=0;j<12;j++)if(!scene_i32(v[i*12+j],domains[j],&f->vertices[i][j]))goto fail;
    for(size_t i=0;i<f->ni;i++){if(in[i]<0||(uint64_t)in[i]>=f->nv)goto fail;f->indices[i]=(uint32_t)in[i];}
    for(size_t i=0;i<f->nd;i++){
        const int64_t *row=d+10*i;MeshDraw *r=f->draws+i;
        if(row[0]<0||(uint64_t)row[0]>f->ni||row[1]<=0||(uint64_t)row[1]>f->ni-(uint32_t)row[0]||row[1]%3)goto fail;
        r->first=(uint32_t)row[0];r->count=(uint32_t)row[1];
        for(size_t j=0;j<8;j++)if(!scene_i32(row[j+2],domains[12+j],&r->params[j]))goto fail;
    }
    return 1;
fail:scene_frame_free(f);return 0;
}
#endif
