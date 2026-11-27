#!/usr/bin/env python3
"""Regenerate actual DOC placement policy and verify native policy decisions."""
import argparse
from pathlib import Path
import tempfile
from test_epoch_authority import emit,run
HARNESS=r'''
#include "value_primitives.h"
#include "placement_policy_generated.h"
#include <assert.h>
int main(void){
    size_t cases=0;
    for(int64_t t=0;t<=4096;t++)for(int64_t hw=1;hw<=256;hw++){
        int64_t expected=t<32?1:(hw<t/16?hw:t/16);
        assert(num(F_place_workers(vi(t),vi(hw)))==expected);
        assert(truth(F_place_parallel(vi(t)))==(t>=32));cases++;
    }
    for(int64_t mode=0;mode<3;mode++)for(int64_t g=0;g<=256;g++)for(int64_t c=0;c<=256;c++){
        int64_t expected=mode==1?(c?-1:1):mode==2?(g>=64):0;
        assert(num(F_place_device(vi(mode),vi(g),vi(c)))==expected);cases++;
    }
    for(int64_t t=1;t<=128;t++)for(int64_t hw=1;hw<=32;hw++)for(int64_t limited=0;limited<2;limited++){
        int64_t grain=t<32?1:(hw<t/16?hw:t/16);
        assert(num(F_place_cost_workers(vi(t),vi(hw),vi(100),vb(limited)))==(limited?grain:1));cases++;
        assert(num(F_place_cost_workers(vi(t),vi(hw),vi(50000),vb(limited)))==(t<hw?t:hw));cases++;
        assert(num(F_place_cost_workers(vi(t),vi(hw),vi(49999),vb(limited)))==((limited||t*49999>=200000)?grain:1));cases++;
    }
    assert(!live_bytes);
    printf("DOC11_PLACEMENT_POLICY_PASS: %zu native decisions; no workload names or hints\n",cases);
    return 0;
}
'''
def main():
    p=argparse.ArgumentParser();p.add_argument('--managed',required=True,type=Path);p.add_argument('--headers',type=Path,default=Path(__file__).resolve().parent.parent/'runtime');a=p.parse_args();headers=a.headers.resolve()
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        source=(headers/'placement_policy.doc').read_text()+'source marker:int=0\n'
        actual=[l for l in emit(a.managed.resolve(),source,root).splitlines() if l.startswith('#define F_place_')]
        expected=[l for l in (headers/'placement_policy_generated.h').read_text().splitlines() if l.startswith('#define F_place_')]
        assert len(actual)==4 and actual==expected,'DOC placement policy drift'
        (root/'test.c').write_text(HARNESS);exe=root/'test'
        run(['cc','-std=gnu11','-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie','-I',headers,root/'test.c','-o',exe],root)
        out,_=run([exe],root);assert 'DOC11_PLACEMENT_POLICY_PASS:' in out;print(out.strip())
if __name__=='__main__':main()
