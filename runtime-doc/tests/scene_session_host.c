#define main doc_cli_main
#include "scene_generated.c"
#undef main
#include "scene_session.h"
#include "scene_frame.h"
#include <assert.h>
static MeshDomain domains[20];
static int project(const Epoch *e,void *ctx){
    (void)ctx;MeshFrame f;
    if(!scene_frame_copy(e,domains,640,480,&f))return 0;
    assert(f.nv&&f.ni&&f.nd);scene_frame_free(&f);return 1;
}
static int reject(const Epoch *e,void *ctx){(void)e;(void)ctx;return 0;}
int main(int argc,char **argv){
    assert(argc==3||argc==5);asset_root=argv[1];SceneSession s;
    if(argc==5)doc_output_root=argv[3];
    assert(scene_open(&s,states,sizeof(states)/sizeof(states[0]),0,project,NULL));
    assert(!scene_accepts(&s,'?')&&!scene_step(&s,'?',NULL,NULL));
    assert(!scene_step(&s,(unsigned char)argv[2][0],reject,NULL));assert(s.published==0);
    domains[0]=(MeshDomain){1,0,0};assert(!scene_step(&s,(unsigned char)argv[2][0],project,NULL));assert(s.published==0);domains[0]=(MeshDomain){0};
    if(argc==5&&!strcmp(argv[4],"restore")){uint64_t saved;assert(!scene_restore(&s,"bad.chk",project,NULL,&saved));assert(scene_restore(&s,"window.chk",project,NULL,&saved));assert(saved>0);}
    observe(&s.e,s.e.n,1,s.published);
    for(const char *p=argv[2];*p;p++){assert(scene_step(&s,(unsigned char)*p,project,NULL));observe(&s.e,s.e.n,1,s.published);if(argc==5&&!strcmp(argv[4],"save"))assert(checkpoint_audio(&s.e,"window-wav",s.published));}
    if(argc==5&&!strcmp(argv[4],"save"))assert(checkpoint_save(&s.e,s.carry,s.published,"window.chk"));
    scene_close(&s);assert(atomic_load(&live_bytes)==0);fprintf(stderr,"DOC11_SCENE_SESSION_PASS: private projection rejection and actual native recurrence replay; live=0\n");return 0;
}
