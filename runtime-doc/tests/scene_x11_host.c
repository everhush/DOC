#define _POSIX_C_SOURCE 200809L
#include "scene_x11.h"
#include <assert.h>
#include <stdio.h>
int main(void){
    SceneWindow w;assert(scene_window_open(&w,128,96));unsigned char pixels[128*96*4];
    for(size_t i=0;i<128*96;i++){pixels[4*i]=(unsigned char)i;pixels[4*i+1]=(unsigned char)(i>>4);pixels[4*i+2]=(unsigned char)(i>>8);pixels[4*i+3]=255;}
    uint64_t before,after;assert(scene_window_present(&w,pixels,128,96,1,&before));
    XResizeWindow(w.display,w.window,96,72);XSync(w.display,False);assert(scene_window_present(&w,pixels,96,72,1,&after)&&before!=after);
    assert(!scene_window_present(&w,pixels,4097,1,1,NULL));scene_window_close(&w);puts("DOC11_X11_PRESENT_PASS: actual Xvfb RGB readback, resize, bounds and cleanup (platform test only)");return 0;
}
