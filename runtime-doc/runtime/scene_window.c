/* Link the actual Stage-2 generated game and the pinned native WebGPU
 * renderer. X11 only presents admitted GPU readback and receives OS events. */
#define main doc_cli_main
#include "scene_generated.c"
#undef main
#include "scene_session.h"
#include "scene_frame.h"
#include "mesh_render_api.h"
#include "scene_x11.h"
#include "scene_shader.h"
#include <inttypes.h>

typedef struct {
    SceneWindow window;MeshRendererNative *renderer;uint32_t width,height;
    unsigned char *current,*candidate;size_t current_n,candidate_n;int verify;char candidate_title[1024];
} SceneApp;
static int stage_frame(const Epoch *e,void *ctx){
    SceneApp *a=ctx;MeshFrame frame;free(a->candidate);a->candidate=NULL;a->candidate_n=0;
    if(!scene_report_title(e,a->candidate_title,sizeof(a->candidate_title)))return 0;
    if(!scene_frame_copy(e,scene_domains,a->width,a->height,&frame))return 0;
    size_t n=(size_t)frame.width*frame.height*4;unsigned char *p=malloc(n);
    int ok=p&&mesh_renderer_render(a->renderer,&frame,p,n);scene_frame_free(&frame);
    if(!ok){free(p);return 0;}a->candidate=p;a->candidate_n=n;return 1;
}
static uint64_t digest_rgba(const unsigned char *p,size_t n){uint64_t h=UINT64_C(0xcbf29ce484222325);for(size_t i=0;i<n;i++)h=(h^p[i])*UINT64_C(0x100000001b3);return h;}
static int publish_frame(SceneApp *a,SceneSession *s,int record){
    if(!a->candidate||a->candidate_n!=(size_t)a->width*a->height*4)return 0;
    uint64_t rgb;if(!scene_window_present(&a->window,a->candidate,a->width,a->height,a->verify,&rgb))return 0;
    free(a->current);a->current=a->candidate;a->current_n=a->candidate_n;a->candidate=NULL;a->candidate_n=0;
    fprintf(stderr,"DOC11_WINDOW_FRAME: epoch=%" PRIu64 " width=%u height=%u rgba=%016" PRIx64 " rgb=%016" PRIx64 " kind=%s\n",s->published,a->width,a->height,digest_rgba(a->current,a->current_n),rgb,record?"commit":"resize");
    if(record){XStoreName(a->window.display,a->window.window,a->candidate_title);XSync(a->window.display,False);if(scene_x11_fault)return 0;observe(&s->e,s->e.n,1,(size_t)s->published);fprintf(stderr,"DOC11_WINDOW_PRESENTED: epoch=%" PRIu64 "\n",s->published);}
    return 1;
}
static uint64_t monotonic_ms(void){struct timespec t;if(clock_gettime(CLOCK_MONOTONIC,&t))return UINT64_MAX;return (uint64_t)t.tv_sec*1000+(uint64_t)t.tv_nsec/1000000;}
static int option(const char *arg,const char *prefix,const char **dst){size_t n=strlen(prefix);if(strncmp(arg,prefix,n))return 0;if(*dst||!arg[n])return -1;*dst=arg+n;return 1;}
int main(int argc,char **argv){
    const char *assets=NULL,*output=NULL,*save=NULL,*load=NULL,*audio=NULL,*replay=NULL;int backend=2,input_only=0,verify=0;
    for(int i=1;i<argc;i++){
        const char *arg=argv[i];int r;
        if((r=option(arg,"--asset-root=",&assets))||(r=option(arg,"--output-root=",&output))||(r=option(arg,"--save=",&save))||(r=option(arg,"--load=",&load))||(r=option(arg,"--audio-dir=",&audio))||(r=option(arg,"--replay=",&replay))){if(r<0)return 1;continue;}
        if(!strcmp(arg,"--backend=cpu"))backend=0;else if(!strcmp(arg,"--backend=gpu"))backend=1;else if(!strcmp(arg,"--backend=auto"))backend=2;
        else if(!strcmp(arg,"--input-only"))input_only=1;else if(!strcmp(arg,"--verify-window"))verify=1;else return 1;
    }
    if(!assets||(replay&&(input_only||strlen(replay)>256))||((save||load||audio)&&(!output||!checkpoint_enabled())))return 1;
    asset_root=assets;doc_output_root=output;
    SceneApp a={.width=640,.height=480,.verify=verify};SceneSession s={0};int ok=0,quit=0;
    MeshBatch plan={.shader=scene_shader,.shader_len=sizeof(scene_shader)-1};memcpy(plan.domains,scene_domains,sizeof(plan.domains));
    a.renderer=mesh_renderer_open(&plan);if(!a.renderer)goto done;
    if(!scene_open(&s,states,sizeof(states)/sizeof(states[0]),backend,stage_frame,&a))goto done;
    if(replay)for(const char *p=replay;*p;p++)if(!scene_accepts(&s,(unsigned char)*p))goto done;
    if(load){uint64_t saved;if(!scene_restore(&s,load,stage_frame,&a,&saved))goto done;fprintf(stderr,"DOC11_WINDOW_RESTORED: saved_epoch=%" PRIu64 " new_epoch=0\n",saved);}
    if(!scene_window_open(&a.window,a.width,a.height)||!publish_frame(&a,&s,1))goto done;
    fprintf(stderr,"DOC11_WINDOW_READY: window=%lu\n",(unsigned long)a.window.window);
    unsigned char keys[256];size_t head=0,count=0,replay_at=0;uint64_t next=monotonic_ms();if(next==UINT64_MAX)goto done;next+=80;
    while(!quit){
        if(scene_x11_fault)goto done;
        while(XPending(a.window.display)){
            XEvent event;XNextEvent(a.window.display,&event);if(event.xany.window!=a.window.window)continue;
            if(event.type==ClientMessage&&(Atom)event.xclient.data.l[0]==a.window.close){quit=1;break;}
            if(event.type==DestroyNotify){a.window.window=0;quit=1;break;}
            if(event.type==ConfigureNotify){
                int w=event.xconfigure.width,h=event.xconfigure.height;if(w<=0||h<=0||!scene_dimensions((uint32_t)w,(uint32_t)h))goto done;
                if((uint32_t)w!=a.width||(uint32_t)h!=a.height){
                    /* Coalesce superseded configuration events before rendering. */
                    XWindowAttributes attrs;if(!XGetWindowAttributes(a.window.display,a.window.window,&attrs)||attrs.width<=0||attrs.height<=0||!scene_dimensions((uint32_t)attrs.width,(uint32_t)attrs.height))goto done;
                    if((uint32_t)attrs.width!=a.width||(uint32_t)attrs.height!=a.height){a.width=(uint32_t)attrs.width;a.height=(uint32_t)attrs.height;if(!stage_frame(&s.e,&a)||!publish_frame(&a,&s,0))goto done;fprintf(stderr,"DOC11_WINDOW_RESIZE: %ux%u\n",a.width,a.height);}
                }
            }else if(event.type==Expose&&event.xexpose.count==0){
                if(a.current&&a.current_n==(size_t)a.width*a.height*4&&!scene_window_present(&a.window,a.current,a.width,a.height,0,NULL))goto done;
            }else if(event.type==KeyPress){
                char raw[16];KeySym sym;int n=XLookupString(&event.xkey,raw,sizeof(raw),&sym,NULL);if(sym==XK_Escape){quit=1;break;}if(replay)continue;
                unsigned char key=sym==XK_space?'j':n==1?(unsigned char)raw[0]:0;if(key>='A'&&key<='Z')key=(unsigned char)(key-'A'+'a');
                if(scene_accepts(&s,key)){if(count==sizeof(keys))goto done;keys[(head+count)%sizeof(keys)]=key;count++;fprintf(stderr,"DOC11_WINDOW_INPUT: key=%c\n",key);}
            }
        }
        if(quit)break;
        if(replay&&!replay[replay_at]){quit=1;break;}
        uint64_t now=monotonic_ms();if(now==UINT64_MAX)goto done;
        if((input_only&&count)||(!input_only&&now>=next)){
            unsigned char key='.';if(replay)key=(unsigned char)replay[replay_at++];else if(count){key=keys[head];head=(head+1)%sizeof(keys);count--;}
            if(!scene_step(&s,key,stage_frame,&a)||!publish_frame(&a,&s,1))goto done;
            if(audio&&!checkpoint_audio(&s.e,audio,s.published))goto done;
            now=monotonic_ms();if(now==UINT64_MAX)goto done;next=now+80;continue;
        }
        struct pollfd fd={.fd=ConnectionNumber(a.window.display),.events=POLLIN};int delay=input_only?-1:(int)(next-now);int n=poll(&fd,1,delay);if(n<0&&errno!=EINTR)goto done;if(n>0&&(fd.revents&(POLLERR|POLLHUP|POLLNVAL)))goto done;
    }
    if(replay&&replay[replay_at])goto done;
    if(save&&!checkpoint_save(&s.e,s.carry,s.published,save))goto done;
    ok=1;
done:
    if(!ok)fprintf(stderr,"DOC11_WINDOW_REJECT: no unvalidated candidate presentation\n");
    scene_window_close(&a.window);if(a.renderer&&!mesh_renderer_close(a.renderer))ok=0;
    free(a.current);free(a.candidate);scene_close(&s);
    if(atomic_load(&live_bytes))ok=0;
    if(ok)fprintf(stderr,"DOC11_WINDOW_PASS: committed game session and native window closed; live=0\n");return ok?0:1;
}
