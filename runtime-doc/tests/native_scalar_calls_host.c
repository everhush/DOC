/* Actual generated objects call the declared native ABI directly.
 * acquire/release are the frozen fixture's deliberately supplied ABI oracle;
 * socket/close are genuine local POSIX operations (no external connection). */
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/socket.h>
#include "conditional.h"
#include "socket.h"

static unsigned acquisitions,releases;
static int32_t owned;
int32_t acquire(int32_t argument) { acquisitions++;if(argument<0)return -1;owned=argument;return argument; }
int32_t release(int32_t handle) { releases++;assert(handle==owned);return 0; }

int main(void) {
    struct doc_result_conditional c={0};
    assert(doc_export_conditional(7,1,&c));
    assert(c.s_acquired==7&&c.s_acquired_ok&&c.s_released==0&&acquisitions==1&&releases==1);
    assert(doc_export_conditional(-1,1,&c));
    assert(c.s_acquired==-1&&!c.s_acquired_ok&&c.s_released==-1&&acquisitions==2&&releases==1);
    assert(doc_export_conditional(INT64_MAX,0,&c));
    assert(c.s_acquired==-1&&!c.s_acquired_ok&&c.s_released==-1&&acquisitions==2&&releases==1);
    assert(!doc_export_conditional(INT64_MAX,1,&c));
    assert(c.s_acquired==-1&&c.s_released==-1&&acquisitions==2&&releases==1);
    assert(!doc_export_conditional(7,2,&c)&&acquisitions==2&&releases==1);
    struct doc_result_socket sock={0};
    for(int i=0;i<128;i++){
        assert(doc_export_socket(AF_UNIX,SOCK_STREAM,0,&sock));
        assert(sock.s_fd>=0&&sock.s_closed==0&&sock.s_success);
        errno=0;assert(fcntl((int)sock.s_fd,F_GETFD)==-1&&errno==EBADF);
    }
    assert(doc_export_socket(-1,SOCK_STREAM,0,&sock));
    assert(sock.s_fd==-1&&sock.s_closed==-1&&!sock.s_success);
    assert(!doc_export_socket(INT64_MAX,SOCK_STREAM,0,&sock));
    assert(sock.s_fd==-1&&sock.s_closed==-1&&!sock.s_success);
    puts("DOC11_NATIVE_SCALAR_CALLS_HOST_PASS: conditional signed ABI and 128 real local socket/close pairs, checked narrowing and no descriptor retention");
    return 0;
}
