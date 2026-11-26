/* Native Wayland sibling of the X11 adapter, using the exact same generated
 * game, checked scene session, typed frame projection and WebGPU renderer. */
#define main doc_cli_main
#include "scene_generated.c"
#undef main
#include "scene_session.h"
#include "scene_frame.h"
#include "mesh_render_api.h"
#include "scene_wayland.h"
#include "scene_shader.h"
typedef struct {SceneWayland window;MeshRendererNative *renderer;uint32_t w,h;unsigned char *pixels;size_t n;char title[1024];} WaylandApp;
static int stage_frame(const Epoch *e,void *opaque){
    WaylandApp *a=opaque;MeshFrame f;free(a->pixels);a->pixels=NULL;a->n=0;
    if(!scene_report_title(e,a->title,sizeof(a->title))||!scene_frame_copy(e,scene_domains,a->w,a->h,&f))return 0;
    size_t n=(size_t)f.width*f.height*4;unsigned char *p=malloc(n);
    int ok=p&&mesh_renderer_render(a->renderer,&f,p,n);scene_frame_free(&f);
    if(!ok){free(p);return 0;}a->pixels=p;a->n=n;return 1;
}
static int present(WaylandApp *a,SceneSession *s,int record){
    if(!scene_wl_present(&a->window,a->pixels,a->n,a->w,a->h,a->title))return 0;
    uint64_t h=UINT64_C(0xcbf29ce484222325);for(size_t i=0;i<a->n;i++)h=(h^a->pixels[i])*UINT64_C(0x100000001b3);
    fprintf(stderr,"DOC11_WAYLAND_FRAME: epoch=%" PRIu64 " width=%u height=%u rgba=%016" PRIx64 " callback=%" PRIu64 " kind=%s\n",s->published,a->w,a->h,h,a->window.frames,record?"commit":"resize");
    if(record){observe(&s->e,s->e.n,1,(size_t)s->published);fprintf(stderr,"DOC11_WAYLAND_PRESENTED: epoch=%" PRIu64 "\n",s->published);}return 1;
}
static int opt(const char *arg,const char *prefix,const char **dst){size_t n=strlen(prefix);if(strncmp(arg,prefix,n))return 0;if(*dst||!arg[n])return -1;*dst=arg+n;return 1;}
int main(int argc,char **argv){
    const char *assets=NULL,*output=NULL,*save=NULL,*load=NULL,*audio=NULL,*replay=NULL;int backend=2,input_only=0;
    for(int i=1;i<argc;i++){const char *arg=argv[i];int r;
        if((r=opt(arg,"--asset-root=",&assets))||(r=opt(arg,"--output-root=",&output))||(r=opt(arg,"--save=",&save))||(r=opt(arg,"--load=",&load))||(r=opt(arg,"--audio-dir=",&audio))||(r=opt(arg,"--replay=",&replay))){if(r<0)return 1;continue;}
        if(!strcmp(arg,"--backend=cpu"))backend=0;else if(!strcmp(arg,"--backend=gpu"))backend=1;else if(!strcmp(arg,"--backend=auto"))backend=2;
        else if(!strcmp(arg,"--input-only"))input_only=1;else return 1;
    }
    if(!assets||(replay&&(input_only||strlen(replay)>256))||((save||load||audio)&&!output))return 1;
    asset_root=assets;doc_output_root=output;if((save||load||audio)&&!checkpoint_enabled())return 1;
    WaylandApp a={0};SceneSession s={0};int ok=0;size_t at=0;
    if(!scene_wl_open(&a.window,640,480))goto done;a.w=a.window.w;a.h=a.window.h;
    MeshBatch plan={.shader=scene_shader,.shader_len=sizeof(scene_shader)-1};memcpy(plan.domains,scene_domains,sizeof(plan.domains));
    a.renderer=mesh_renderer_open(&plan);if(!a.renderer||!scene_open(&s,states,sizeof(states)/sizeof(states[0]),backend,stage_frame,&a))goto done;
    if(replay)for(const char *p=replay;*p;p++)if(!scene_accepts(&s,(unsigned char)*p))goto done;
    if(load){uint64_t saved;if(!scene_restore(&s,load,stage_frame,&a,&saved))goto done;fprintf(stderr,"DOC11_WAYLAND_RESTORED: saved_epoch=%" PRIu64 "\n",saved);}
    if(!present(&a,&s,1))goto done;fprintf(stderr,"DOC11_WAYLAND_READY\n");
    uint64_t next=scene_wl_ms()+80;
    while(!a.window.closed){
        if(!scene_wl_pump(&a.window,0))goto done;
        if(a.window.closed)break;
        if(a.window.w!=a.w||a.window.h!=a.h){
            a.w=a.window.w;a.h=a.window.h;if(!stage_frame(&s.e,&a)||!present(&a,&s,0))goto done;continue;
        }
        if(replay&&!replay[at])break;
        unsigned char key=0;while(a.window.count){unsigned char c=a.window.keys[a.window.head];a.window.head=(a.window.head+1)%sizeof(a.window.keys);a.window.count--;if(!replay&&scene_accepts(&s,c)){key=c;fprintf(stderr,"DOC11_WAYLAND_INPUT: key=%c\n",key);break;}}
        uint64_t now=scene_wl_ms();if(now==UINT64_MAX)goto done;
        if((input_only&&key)||(!input_only&&(key||now>=next))){
            if(replay)key=(unsigned char)replay[at++];else if(!key)key='.';
            if(!scene_step(&s,key,stage_frame,&a)||!present(&a,&s,1))goto done;
            if(audio&&!checkpoint_audio(&s.e,audio,s.published))goto done;
            next=scene_wl_ms()+80;
        }else if(!scene_wl_pump(&a.window,input_only?100:(int)(next-now)))goto done;
    }
    if(replay&&replay[at])goto done;
    if(save&&!checkpoint_save(&s.e,s.carry,s.published,save))goto done;
    ok=1;
done:
    if(!ok)fprintf(stderr,"DOC11_WAYLAND_REJECT: no unvalidated candidate presentation\n");
    scene_wl_close(&a.window);if(a.renderer&&!mesh_renderer_close(a.renderer))ok=0;
    free(a.pixels);scene_close(&s);if(atomic_load(&live_bytes))ok=0;
    if(ok)fprintf(stderr,"DOC11_WAYLAND_PASS: native compositor frame callbacks; live=0\n");return ok?0:1;
}
