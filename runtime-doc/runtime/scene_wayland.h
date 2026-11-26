#ifndef DOC_SCENE_WAYLAND_H
#define DOC_SCENE_WAYLAND_H
/* Native Wayland xdg-shell and shared-memory presentation of validated GPU
 * readback. One display connection, three bounded buffers, no X11 fallback.
 * Frame callbacks acknowledge compositor processing, not scanout/readback. */
#include <wayland-client.h>
#include "xdg-shell-client-protocol.h"
#include <xkbcommon/xkbcommon.h>
#include <xkbcommon/xkbcommon-keysyms.h>
#include <poll.h>
#include <sys/mman.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <time.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#define WAYLAND_PIXEL_LIMIT (64u*1024u*1024u)
typedef struct {
    struct wl_buffer *buffer;unsigned char *memory;size_t size;uint32_t w,h;int busy;uint64_t *releases;
} SceneWLBuffer;
typedef struct {
    struct wl_display *display;struct wl_registry *registry;struct wl_compositor *compositor;struct wl_shm *shm;
    struct xdg_wm_base *shell;struct wl_surface *surface;struct xdg_surface *xdg;struct xdg_toplevel *top;
    struct wl_seat *seat;struct wl_keyboard *keyboard;struct xkb_context *context;struct xkb_keymap *map;struct xkb_state *state;
    struct wl_callback *frame;SceneWLBuffer slots[3];
    uint32_t compositor_id,shm_id,shell_id,seat_id,w,h,pending_w,pending_h;
    uint64_t frames,releases;int configured,closed,fault,focus,xrgb;
    unsigned char keys[256];size_t head,count;
} SceneWayland;
static uint64_t scene_wl_ms(void){struct timespec t;if(clock_gettime(CLOCK_MONOTONIC,&t))return UINT64_MAX;return (uint64_t)t.tv_sec*1000+(uint64_t)t.tv_nsec/1000000;}
static int scene_wl_dimensions(uint32_t w,uint32_t h){return w&&h&&w<=4096&&h<=4096&&(uint64_t)w*h*4<=WAYLAND_PIXEL_LIMIT;}
static void scene_wl_ping(void *ctx,struct xdg_wm_base *shell,uint32_t serial){(void)ctx;xdg_wm_base_pong(shell,serial);}
static const struct xdg_wm_base_listener scene_wl_shell_listener={.ping=scene_wl_ping};
static void scene_wl_configure(void *ctx,struct xdg_surface *surface,uint32_t serial){
    SceneWayland *w=ctx;xdg_surface_ack_configure(surface,serial);
    if(!scene_wl_dimensions(w->pending_w,w->pending_h)){w->fault=1;return;}
    w->w=w->pending_w;w->h=w->pending_h;w->configured=1;
}
static const struct xdg_surface_listener scene_wl_surface_listener={.configure=scene_wl_configure};
static void scene_wl_top_configure(void *ctx,struct xdg_toplevel *top,int32_t width,int32_t height,struct wl_array *states){
    (void)top;(void)states;SceneWayland *w=ctx;
    if(width<0||height<0){w->fault=1;return;}
    w->pending_w=width?(uint32_t)width:w->w;w->pending_h=height?(uint32_t)height:w->h;
}
static void scene_wl_top_close(void *ctx,struct xdg_toplevel *top){(void)top;((SceneWayland*)ctx)->closed=1;}
static const struct xdg_toplevel_listener scene_wl_top_listener={.configure=scene_wl_top_configure,.close=scene_wl_top_close};
static void scene_wl_keymap(void *ctx,struct wl_keyboard *keyboard,uint32_t format,int32_t fd,uint32_t size){
    (void)keyboard;SceneWayland *w=ctx;
    if(format!=WL_KEYBOARD_KEYMAP_FORMAT_XKB_V1||!size||size>1024*1024){close(fd);w->fault=1;return;}
    char *p=mmap(NULL,size,PROT_READ,MAP_PRIVATE,fd,0);close(fd);if(p==MAP_FAILED){w->fault=1;return;}
    struct xkb_keymap *map=p[size-1]==0?xkb_keymap_new_from_string(w->context,p,XKB_KEYMAP_FORMAT_TEXT_V1,XKB_KEYMAP_COMPILE_NO_FLAGS):NULL;
    munmap(p,size);if(!map){w->fault=1;return;}
    struct xkb_state *state=xkb_state_new(map);if(!state){xkb_keymap_unref(map);w->fault=1;return;}
    if(w->state)xkb_state_unref(w->state);if(w->map)xkb_keymap_unref(w->map);w->map=map;w->state=state;
}
static void scene_wl_enter(void *ctx,struct wl_keyboard *keyboard,uint32_t serial,struct wl_surface *surface,struct wl_array *keys){
    (void)keyboard;(void)serial;(void)keys;SceneWayland *w=ctx;if(surface==w->surface){w->focus=1;fprintf(stderr,"DOC11_WAYLAND_FOCUS\n");}
}
static void scene_wl_leave(void *ctx,struct wl_keyboard *keyboard,uint32_t serial,struct wl_surface *surface){
    (void)keyboard;(void)serial;(void)surface;((SceneWayland*)ctx)->focus=0;
}
static void scene_wl_key(void *ctx,struct wl_keyboard *keyboard,uint32_t serial,uint32_t time,uint32_t key,uint32_t state){
    (void)keyboard;(void)serial;(void)time;SceneWayland *w=ctx;if(!w->focus||!w->state||state!=WL_KEYBOARD_KEY_STATE_PRESSED||key>UINT32_MAX-8)return;
    xkb_keysym_t sym=xkb_state_key_get_one_sym(w->state,key+8);if(sym==XKB_KEY_Escape){w->closed=1;return;}
    uint32_t c=sym==XKB_KEY_space?'j':xkb_keysym_to_utf32(sym);if(c>='A'&&c<='Z')c+=32;if(c<32||c>=127)return;
    if(w->count==sizeof(w->keys)){w->fault=1;return;}w->keys[(w->head+w->count)%sizeof(w->keys)]=(unsigned char)c;w->count++;
}
static void scene_wl_modifiers(void *ctx,struct wl_keyboard *keyboard,uint32_t serial,uint32_t depressed,uint32_t latched,uint32_t locked,uint32_t group){
    (void)keyboard;(void)serial;SceneWayland *w=ctx;if(w->state)xkb_state_update_mask(w->state,depressed,latched,locked,0,0,group);
}
static const struct wl_keyboard_listener scene_wl_keyboard_listener={.keymap=scene_wl_keymap,.enter=scene_wl_enter,.leave=scene_wl_leave,.key=scene_wl_key,.modifiers=scene_wl_modifiers};
static void scene_wl_seat(void *ctx,struct wl_seat *seat,uint32_t capabilities){
    SceneWayland *w=ctx;
    if((capabilities&WL_SEAT_CAPABILITY_KEYBOARD)&&!w->keyboard){
        w->keyboard=wl_seat_get_keyboard(seat);
        if(!w->keyboard||wl_keyboard_add_listener(w->keyboard,&scene_wl_keyboard_listener,w))w->fault=1;
    }else if(!(capabilities&WL_SEAT_CAPABILITY_KEYBOARD)&&w->keyboard){wl_keyboard_destroy(w->keyboard);w->keyboard=NULL;w->focus=0;}
}
static const struct wl_seat_listener scene_wl_seat_listener={.capabilities=scene_wl_seat};
static void scene_wl_format(void *ctx,struct wl_shm *shm,uint32_t format){(void)shm;SceneWayland *w=ctx;if(format==WL_SHM_FORMAT_XRGB8888)w->xrgb=1;}
static const struct wl_shm_listener scene_wl_shm_listener={.format=scene_wl_format};
static void scene_wl_global(void *ctx,struct wl_registry *registry,uint32_t name,const char *interface,uint32_t version){
    SceneWayland *w=ctx;if(!version)return;
    if(!strcmp(interface,"wl_compositor")&&!w->compositor){w->compositor=wl_registry_bind(registry,name,&wl_compositor_interface,1);w->compositor_id=name;}
    else if(!strcmp(interface,"wl_shm")&&!w->shm){w->shm=wl_registry_bind(registry,name,&wl_shm_interface,1);w->shm_id=name;if(!w->shm||wl_shm_add_listener(w->shm,&scene_wl_shm_listener,w))w->fault=1;}
    else if(!strcmp(interface,"xdg_wm_base")&&!w->shell){w->shell=wl_registry_bind(registry,name,&xdg_wm_base_interface,1);w->shell_id=name;if(!w->shell||xdg_wm_base_add_listener(w->shell,&scene_wl_shell_listener,w))w->fault=1;}
    else if(!strcmp(interface,"wl_seat")&&!w->seat){w->seat=wl_registry_bind(registry,name,&wl_seat_interface,1);w->seat_id=name;if(!w->seat||wl_seat_add_listener(w->seat,&scene_wl_seat_listener,w))w->fault=1;}
}
static void scene_wl_remove(void *ctx,struct wl_registry *registry,uint32_t name){
    (void)registry;SceneWayland *w=ctx;
    if(name==w->compositor_id||name==w->shm_id||name==w->shell_id)w->fault=1;
    if(name==w->seat_id){if(w->keyboard)wl_keyboard_destroy(w->keyboard);w->keyboard=NULL;wl_seat_destroy(w->seat);w->seat=NULL;w->seat_id=0;w->focus=0;}
}
static const struct wl_registry_listener scene_wl_registry_listener={.global=scene_wl_global,.global_remove=scene_wl_remove};
/* Bounded dispatch, including write backpressure and cancellation of a
 * prepared read. No blocking roundtrip to an unresponsive compositor. */
static int scene_wl_pump(SceneWayland *w,int ms){
    if(w->fault||!w->display)return 0;
    while(wl_display_prepare_read(w->display)!=0){if(wl_display_dispatch_pending(w->display)<0||w->fault)return 0;}
    int flush=wl_display_flush(w->display);
    if(flush<0&&errno!=EAGAIN){wl_display_cancel_read(w->display);return 0;}
    struct pollfd fd={.fd=wl_display_get_fd(w->display),.events=POLLIN|(flush<0?POLLOUT:0)};
    int n=poll(&fd,1,ms);
    if(n<0&&errno==EINTR){wl_display_cancel_read(w->display);return 1;}
    if(n<0||(n>0&&(fd.revents&(POLLERR|POLLHUP|POLLNVAL)))){wl_display_cancel_read(w->display);return 0;}
    if(n>0&&(fd.revents&POLLIN)){if(wl_display_read_events(w->display)<0)return 0;}else wl_display_cancel_read(w->display);
    return wl_display_dispatch_pending(w->display)>=0&&!w->fault&&!wl_display_get_error(w->display);
}
static int scene_wl_sync_done;
static void scene_wl_sync(void *ctx,struct wl_callback *cb,uint32_t serial){(void)ctx;(void)serial;wl_callback_destroy(cb);scene_wl_sync_done=1;}
static const struct wl_callback_listener scene_wl_sync_listener={.done=scene_wl_sync};
static int scene_wl_roundtrip(SceneWayland *w){
    scene_wl_sync_done=0;struct wl_callback *cb=wl_display_sync(w->display);
    if(!cb)return 0;if(wl_callback_add_listener(cb,&scene_wl_sync_listener,w)){wl_callback_destroy(cb);return 0;}
    uint64_t start=scene_wl_ms();
    while(!scene_wl_sync_done){if(scene_wl_ms()-start>=10000||!scene_wl_pump(w,100)){if(!scene_wl_sync_done)wl_callback_destroy(cb);return 0;}}
    return !w->fault;
}
static void scene_wl_buffer_release(void *ctx,struct wl_buffer *buffer){(void)buffer;SceneWLBuffer *s=ctx;if(s->busy&&s->releases)(*s->releases)++;s->busy=0;}
static const struct wl_buffer_listener scene_wl_buffer_listener={.release=scene_wl_buffer_release};
static void scene_wl_buffer_free(SceneWLBuffer *s){
    if(s->buffer)wl_buffer_destroy(s->buffer);if(s->memory)munmap(s->memory,s->size);*s=(SceneWLBuffer){0};
}
static int scene_wl_buffer_make(SceneWayland *w,SceneWLBuffer *s,uint32_t width,uint32_t height){
    if(s->busy||!scene_wl_dimensions(width,height))return 0;
    if(s->buffer&&s->w==width&&s->h==height)return 1;
    scene_wl_buffer_free(s);size_t size=(size_t)width*height*4;
    const char *dir=getenv("XDG_RUNTIME_DIR");if(!dir||!*dir)return 0;
    char path[4096];int n=snprintf(path,sizeof(path),"%s/doc-wl-XXXXXX",dir);if(n<0||(size_t)n>=sizeof(path))return 0;
    int fd=mkstemp(path);if(fd<0)return 0;unlink(path);
    if(fcntl(fd,F_SETFD,FD_CLOEXEC)<0||ftruncate(fd,(off_t)size)){close(fd);return 0;}
    void *p=mmap(NULL,size,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);if(p==MAP_FAILED){close(fd);return 0;}
    struct wl_shm_pool *pool=wl_shm_create_pool(w->shm,fd,(int32_t)size);close(fd);
    if(!pool){munmap(p,size);return 0;}
    struct wl_buffer *buffer=wl_shm_pool_create_buffer(pool,0,(int32_t)width,(int32_t)height,(int32_t)(width*4),WL_SHM_FORMAT_XRGB8888);wl_shm_pool_destroy(pool);
    if(!buffer){munmap(p,size);return 0;}
    *s=(SceneWLBuffer){.buffer=buffer,.memory=p,.size=size,.w=width,.h=height,.releases=&w->releases};
    if(wl_buffer_add_listener(buffer,&scene_wl_buffer_listener,s)){scene_wl_buffer_free(s);return 0;}return 1;
}
static void scene_wl_frame_done(void *ctx,struct wl_callback *cb,uint32_t time){
    (void)time;SceneWayland *w=ctx;if(w->frame!=cb){w->fault=1;return;}wl_callback_destroy(cb);w->frame=NULL;w->frames++;
}
static const struct wl_callback_listener scene_wl_frame_listener={.done=scene_wl_frame_done};
static int scene_wl_open(SceneWayland *w,uint32_t width,uint32_t height){
    *w=(SceneWayland){0};if(!scene_wl_dimensions(width,height))return 0;
    w->w=w->pending_w=width;w->h=w->pending_h=height;
    w->context=xkb_context_new(XKB_CONTEXT_NO_FLAGS);w->display=wl_display_connect(NULL);
    if(!w->display||!w->context)return 0;w->registry=wl_display_get_registry(w->display);
    if(!w->registry||wl_registry_add_listener(w->registry,&scene_wl_registry_listener,w)||!scene_wl_roundtrip(w)||!w->compositor||!w->shm||!w->shell)return 0;
    w->surface=wl_compositor_create_surface(w->compositor);if(!w->surface)return 0;
    w->xdg=xdg_wm_base_get_xdg_surface(w->shell,w->surface);
    if(!w->xdg||xdg_surface_add_listener(w->xdg,&scene_wl_surface_listener,w))return 0;
    w->top=xdg_surface_get_toplevel(w->xdg);
    if(!w->top||xdg_toplevel_add_listener(w->top,&scene_wl_top_listener,w))return 0;
    xdg_toplevel_set_title(w->top,"DOC 3D scene");xdg_toplevel_set_app_id(w->top,"doc.scene");
    wl_surface_commit(w->surface);uint64_t start=scene_wl_ms();
    while(!w->configured||!w->xrgb){if(w->closed||scene_wl_ms()-start>=10000||!scene_wl_pump(w,100))return 0;}
    fprintf(stderr,"DOC11_WAYLAND_CONFIGURED: %ux%u\n",w->w,w->h);return 1;
}
static int scene_wl_present(SceneWayland *w,const unsigned char *rgba,size_t size,uint32_t width,uint32_t height,const char *title){
    if(!w->configured||!w->xrgb||w->frame||w->fault||w->closed||!rgba||!scene_wl_dimensions(width,height)||size!=(size_t)width*height*4)return 0;
    SceneWLBuffer *slot=NULL;uint64_t start=scene_wl_ms();
    while(!slot){for(size_t i=0;i<3;i++)if(!w->slots[i].busy){slot=w->slots+i;break;}if(!slot&&(w->closed||scene_wl_ms()-start>=10000||!scene_wl_pump(w,100)))return 0;}
    if(!scene_wl_buffer_make(w,slot,width,height))return 0;
    /* XRGB8888 little endian wire format, no GPU fallback or drawing here. */
    for(size_t i=0;i<size;i+=4){slot->memory[i]=rgba[i+2];slot->memory[i+1]=rgba[i+1];slot->memory[i+2]=rgba[i];slot->memory[i+3]=255;}
    w->frame=wl_surface_frame(w->surface);if(!w->frame||wl_callback_add_listener(w->frame,&scene_wl_frame_listener,w))return 0;
    xdg_toplevel_set_title(w->top,title);xdg_surface_set_window_geometry(w->xdg,0,0,(int32_t)width,(int32_t)height);
    wl_surface_attach(w->surface,slot->buffer,0,0);wl_surface_damage(w->surface,0,0,(int32_t)width,(int32_t)height);slot->busy=1;wl_surface_commit(w->surface);
    start=scene_wl_ms();while(w->frame){if(w->closed||scene_wl_ms()-start>=10000||!scene_wl_pump(w,100))return 0;}
    return !w->fault;
}
static void scene_wl_close(SceneWayland *w){
    if(w->frame)wl_callback_destroy(w->frame);
    if(w->keyboard)wl_keyboard_destroy(w->keyboard);if(w->seat)wl_seat_destroy(w->seat);
    if(w->top)xdg_toplevel_destroy(w->top);if(w->xdg)xdg_surface_destroy(w->xdg);if(w->surface)wl_surface_destroy(w->surface);
    for(size_t i=0;i<3;i++)if(w->slots[i].buffer)wl_buffer_destroy(w->slots[i].buffer);
    if(w->shell)xdg_wm_base_destroy(w->shell);if(w->shm)wl_shm_destroy(w->shm);if(w->compositor)wl_compositor_destroy(w->compositor);if(w->registry)wl_registry_destroy(w->registry);
    if(w->display)wl_display_disconnect(w->display);
    for(size_t i=0;i<3;i++)if(w->slots[i].memory)munmap(w->slots[i].memory,w->slots[i].size);
    if(w->state)xkb_state_unref(w->state);if(w->map)xkb_keymap_unref(w->map);if(w->context)xkb_context_unref(w->context);*w=(SceneWayland){0};
}
#endif
