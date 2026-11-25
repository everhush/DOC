#ifndef DOC_MESH_PACKET_H
#define DOC_MESH_PACKET_H
/* Checked transport boundary for DOC-generated shader bytes and typed scene
 * facts. No expression evaluation. A complete batch is admitted before GPU use. */
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define MESH_BYTES (64u*1024u*1024u)
typedef struct {uint32_t set;int32_t lo,hi;} MeshDomain;
typedef struct {uint32_t first,count;int32_t params[8];} MeshDraw;
typedef struct {uint32_t width,height,nv,ni,nd;unsigned char clear[4];int32_t (*vertices)[12];uint32_t *indices;MeshDraw *draws;} MeshFrame;
typedef struct {char *shader;uint32_t shader_len,n;MeshDomain domains[20];MeshFrame *frames;size_t pixel_bytes;} MeshBatch;
static void mesh_free(MeshBatch *m){if(m->frames)for(size_t i=0;i<m->n;i++){free(m->frames[i].vertices);free(m->frames[i].indices);free(m->frames[i].draws);}free(m->frames);free(m->shader);*m=(MeshBatch){0};}
static int mesh_read(FILE *f,void *p,size_t n,size_t *budget){if(n>*budget||fread(p,1,n,f)!=n)return 0;*budget-=n;return 1;}
static int mesh_u32(FILE *f,uint32_t *v,size_t *budget){unsigned char b[4];if(!mesh_read(f,b,4,budget))return 0;*v=(uint32_t)b[0]|(uint32_t)b[1]<<8|(uint32_t)b[2]<<16|(uint32_t)b[3]<<24;return 1;}
static int mesh_i32(FILE *f,int32_t *v,size_t *budget){uint32_t u;if(!mesh_u32(f,&u,budget))return 0;*v=u<=INT32_MAX?(int32_t)u:(int32_t)((int64_t)u-4294967296LL);return 1;}
static int mesh_bound(MeshDomain d,int32_t v){return !d.set||(v>=d.lo&&v<=d.hi);}
static int mesh_frame(FILE *in,MeshBatch *m,MeshFrame *f,size_t *budget){
    if(!mesh_u32(in,&f->width,budget)||!mesh_u32(in,&f->height,budget)||!mesh_u32(in,&f->nv,budget)||!mesh_u32(in,&f->ni,budget)||!mesh_u32(in,&f->nd,budget)||!mesh_read(in,f->clear,4,budget))return 0;
    if(!f->width||f->width>4096||!f->height||f->height>4096||!f->nv||f->nv>65536||!f->ni||f->ni>196608||f->ni%3||!f->nd||f->nd>128)return 0;
    size_t pixels=(size_t)f->width*f->height*4,bytes=(size_t)f->nv*48+(size_t)f->ni*4+(size_t)f->nd*40;
    if(pixels>MESH_BYTES-m->pixel_bytes||bytes>*budget)return 0;
    m->pixel_bytes+=pixels;f->vertices=calloc(f->nv,sizeof(*f->vertices));f->indices=calloc(f->ni,sizeof(*f->indices));f->draws=calloc(f->nd,sizeof(*f->draws));if(!f->vertices||!f->indices||!f->draws)return 0;
    for(size_t i=0;i<f->nv;i++)for(size_t j=0;j<12;j++)if(!mesh_i32(in,&f->vertices[i][j],budget)||!mesh_bound(m->domains[j],f->vertices[i][j]))return 0;
    for(size_t i=0;i<f->ni;i++)if(!mesh_u32(in,&f->indices[i],budget)||f->indices[i]>=f->nv)return 0;
    for(size_t i=0;i<f->nd;i++){MeshDraw *d=f->draws+i;if(!mesh_u32(in,&d->first,budget)||!mesh_u32(in,&d->count,budget)||d->first>f->ni||!d->count||d->count%3||d->count>f->ni-d->first)return 0;for(size_t j=0;j<8;j++)if(!mesh_i32(in,&d->params[j],budget)||!mesh_bound(m->domains[12+j],d->params[j]))return 0;}
    return 1;
}
static int mesh_load(FILE *in,MeshBatch *m){
    *m=(MeshBatch){0};size_t budget=MESH_BYTES;char magic[8];
    if(!mesh_read(in,magic,8,&budget)||memcmp(magic,"DOCMSH01",8)||!mesh_u32(in,&m->shader_len,&budget)||!mesh_u32(in,&m->n,&budget)||!m->shader_len||m->shader_len>65536||!m->n||m->n>32)goto fail;
    for(size_t j=0;j<20;j++){MeshDomain *d=m->domains+j;if(!mesh_u32(in,&d->set,&budget)||!mesh_i32(in,&d->lo,&budget)||!mesh_i32(in,&d->hi,&budget)||d->set>1||(d->set?d->lo>d->hi:d->lo||d->hi))goto fail;}
    m->shader=calloc((size_t)m->shader_len+1,1);m->frames=calloc(m->n,sizeof(*m->frames));if(!m->shader||!m->frames||!mesh_read(in,m->shader,m->shader_len,&budget))goto fail;
    for(size_t i=0;i<m->shader_len;i++){unsigned char c=m->shader[i];if(c!=9&&c!=10&&c!=13&&(c<32||c>126))goto fail;}
    for(size_t i=0;i<m->n;i++)if(!mesh_frame(in,m,m->frames+i,&budget))goto fail;
    if(fgetc(in)!=EOF||ferror(in))goto fail;
    return 1;
fail:mesh_free(m);return 0;
}
#endif
