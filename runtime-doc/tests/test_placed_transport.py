#!/usr/bin/env python3
"""Actual DOC-generated placed-role policy and TCP transport regression."""
import argparse
from pathlib import Path
import tempfile
from test_epoch_authority import emit,run
def main():
    p=argparse.ArgumentParser();p.add_argument('--managed',required=True,type=Path);p.add_argument('--headers',type=Path,default=Path(__file__).resolve().parent.parent/'runtime');a=p.parse_args();headers=a.headers.resolve()
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);source=(headers/'placed_policy.doc').read_text()+'source marker:int=0\n'
        actual=[l for l in emit(a.managed.resolve(),source,root).splitlines() if l.startswith('#define F_placed_')]
        expected=[l for l in (headers/'placed_policy_generated.h').read_text().splitlines() if l.startswith('#define F_placed_')]
        assert len(actual)==5 and actual==expected,'DOC placed policy drift'
        exe=root/'transport'
        run(['cc','-std=gnu11','-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie','-I',headers,Path(__file__).resolve().parent/'placed_transport_host.c','-o',exe],root)
        out,_=run([exe],root);assert 'DOC11_PLACED_TRANSPORT_PASS:' in out;print(out.strip())
if __name__=='__main__':main()
