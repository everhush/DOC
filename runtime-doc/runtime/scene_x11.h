#ifndef DOC_SCENE_X11_H
#define DOC_SCENE_X11_H
/* Linux X11 presentation only. GPU pixels have already been produced and
 * validated by the native renderer; this adapter never generates geometry. */
#include <X11/Xlib.h>
/* Xutil exposes an unrelated opaque Region typedef. */
#define Region X11Region
#include <X11/Xutil.h>
#undef Region
#include <X11/keysym.h>
#include <poll.h>
#include <time.h>
#include <errno.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#define SCENE_PIXEL_LIMIT (64u*1024u*1024u)
typedef struct {Display *display;Window window;GC gc;Atom close;Visual *visual;int depth;unsigned rs,gs,bs;} SceneWindow;
static int scene_x11_fault;
static int scene_x11_error(Display *d,XErrorEvent *event){(void)d;(void)event;scene_x11_fault=1;return 0;}
static int scene_channel(unsigned long mask,unsigned *shift){if(!mask)return 0;unsigned n=0;while(!(mask&1)){mask>>=1;n++;}if(mask!=255||n>24)return 0;*shift=n;return 1;}
static int scene_dimensions(uint32_t w,uint32_t h){return w&&h&&w<=4096&&h<=4096&&(uint64_t)w*h*4<=SCENE_PIXEL_LIMIT;}
static void scene_window_close(SceneWindow *w){if(w->display){if(w->gc)XFreeGC(w->display,w->gc);if(w->window)XDestroyWindow(w->display,w->window);XSync(w->display,False);XCloseDisplay(w->display);}*w=(SceneWindow){0};}
static int scene_window_open(SceneWindow *w,uint32_t width,uint32_t height){
    *w=(SceneWindow){0};if(!scene_dimensions(width,height))return 0;
    w->display=XOpenDisplay(NULL);if(!w->display)return 0;scene_x11_fault=0;XSetErrorHandler(scene_x11_error);
    int screen=DefaultScreen(w->display);w->visual=DefaultVisual(w->display,screen);w->depth=DefaultDepth(w->display,screen);
    Visual *v=w->visual;if(v->class!=TrueColor||!scene_channel(v->red_mask,&w->rs)||!scene_channel(v->green_mask,&w->gs)||!scene_channel(v->blue_mask,&w->bs)||(v->red_mask&v->green_mask)||(v->red_mask&v->blue_mask)||(v->green_mask&v->blue_mask))goto fail;
    w->window=XCreateSimpleWindow(w->display,RootWindow(w->display,screen),0,0,width,height,0,0,BlackPixel(w->display,screen));
    if(!w->window)goto fail;w->gc=XCreateGC(w->display,w->window,0,NULL);if(!w->gc)goto fail;
    XSelectInput(w->display,w->window,ExposureMask|StructureNotifyMask|KeyPressMask);
    w->close=XInternAtom(w->display,"WM_DELETE_WINDOW",False);XSetWMProtocols(w->display,w->window,&w->close,1);
    XStoreName(w->display,w->window,"DOC 3D scene");XMapRaised(w->display,w->window);XSync(w->display,False);
    for(int i=0;i<250&&!scene_x11_fault;i++){
        XWindowAttributes a;if(XGetWindowAttributes(w->display,w->window,&a)&&a.map_state==IsViewable)return 1;
        struct timespec pause={0,20000000};nanosleep(&pause,NULL);
    }
fail:scene_window_close(w);return 0;
}
static unsigned long scene_rgb(const SceneWindow *w,const unsigned char *p){return (unsigned long)p[0]<<w->rs|(unsigned long)p[1]<<w->gs|(unsigned long)p[2]<<w->bs;}
static int scene_window_present(SceneWindow *w,const unsigned char *rgba,uint32_t width,uint32_t height,int verify,uint64_t *digest){
    if(!w->display||scene_x11_fault||!rgba||!scene_dimensions(width,height))return 0;
    XImage *image=XCreateImage(w->display,w->visual,(unsigned)w->depth,ZPixmap,0,NULL,width,height,32,0);
    if(!image)return 0;
    if(image->bytes_per_line<=0||(size_t)image->bytes_per_line>SCENE_PIXEL_LIMIT/height){XDestroyImage(image);return 0;}
    image->data=calloc((size_t)image->bytes_per_line,height);if(!image->data){XDestroyImage(image);return 0;}
    uint64_t h=UINT64_C(0xcbf29ce484222325);
    for(uint32_t y=0;y<height;y++)for(uint32_t x=0;x<width;x++){const unsigned char *p=rgba+4*((size_t)y*width+x);XPutPixel(image,x,y,scene_rgb(w,p));for(int k=0;k<3;k++)h=(h^p[k])*UINT64_C(0x100000001b3);}
    XPutImage(w->display,w->window,w->gc,image,0,0,0,0,width,height);XDestroyImage(image);XSync(w->display,False);
    if(scene_x11_fault)return 0;
    if(verify){
        XWindowAttributes a;if(!XGetWindowAttributes(w->display,w->window,&a)||a.width!=(int)width||a.height!=(int)height||a.map_state!=IsViewable)return 0;
        XImage *actual=XGetImage(w->display,w->window,0,0,width,height,AllPlanes,ZPixmap);if(!actual)return 0;
        int ok=1;unsigned long mask=w->visual->red_mask|w->visual->green_mask|w->visual->blue_mask;
        for(uint32_t y=0;y<height&&ok;y++)for(uint32_t x=0;x<width;x++)if((XGetPixel(actual,x,y)&mask)!=scene_rgb(w,rgba+4*((size_t)y*width+x))){ok=0;break;}
        XDestroyImage(actual);if(!ok||scene_x11_fault)return 0;
    }
    if(digest)*digest=h;return 1;
}
#endif
