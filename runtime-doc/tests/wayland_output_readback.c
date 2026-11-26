/* Test-only X11 readback of the NESTED compositor's output. The game itself
 * is a native Wayland client with no direct X11 linkage. No pixels synthesized:
 * read each displayed pixel and reconstruct the XRGB8888 opaque alpha. */
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <stdint.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
static int shift(unsigned long mask,unsigned *s){if(!mask)return 0;*s=0;while(!(mask&1)){mask>>=1;(*s)++;}return mask==255;}
int main(int argc,char **argv){
    if(argc!=2)return 1;errno=0;char *end;unsigned long id=strtoul(argv[1],&end,10);if(errno||!*argv[1]||*end||!id)return 1;
    Display *d=XOpenDisplay(NULL);if(!d)return 1;
    Window w=(Window)id;XWindowAttributes a;int ok=0;XImage *img=NULL;
    if(!XGetWindowAttributes(d,w,&a)||a.width!=640||a.height!=480||a.map_state!=IsViewable||a.visual->class!=TrueColor)goto done;
    unsigned r,g,b;if(!shift(a.visual->red_mask,&r)||!shift(a.visual->green_mask,&g)||!shift(a.visual->blue_mask,&b))goto done;
    img=XGetImage(d,w,0,0,640,480,AllPlanes,ZPixmap);if(!img)goto done;
    uint64_t digest=UINT64_C(0xcbf29ce484222325);
    for(int y=0;y<480;y++)for(int x=0;x<640;x++){
        unsigned long p=XGetPixel(img,x,y);
        unsigned char rgba[4]={(unsigned char)(p>>r),(unsigned char)(p>>g),(unsigned char)(p>>b),255};
        for(int k=0;k<4;k++)digest=(digest^rgba[k])*UINT64_C(0x100000001b3);
    }
    printf("%016" PRIx64 "\n",digest);ok=1;
done:if(img)XDestroyImage(img);XCloseDisplay(d);return ok?0:1;
}
