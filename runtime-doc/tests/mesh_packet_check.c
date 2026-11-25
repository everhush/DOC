#include "mesh_packet.h"
int main(void){MeshBatch b;if(!mesh_load(stdin,&b))return 1;printf("%u %zu\n",b.n,b.pixel_bytes);mesh_free(&b);return 0;}
