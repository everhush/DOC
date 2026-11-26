#!/usr/bin/env python3
"""Actual C-toolchain failure/provenance and atomic output regression."""
import argparse,json,os,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'compiler'))
from doc_build import build_bundled,compile_c

def main():
    p=argparse.ArgumentParser();p.add_argument('--compiler',type=Path,required=True);a=p.parse_args()
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);exe=root/'app';src=root/'program.c';report=root/'compile.json'
        program=b'source x:int=7\nderive y:int(x)=add(x,1)\n'
        kwargs=dict(emit_c=src,compile_evidence=report)
        code=build_bundled([a.compiler.resolve()],program,exe,ROOT/'runtime',stream=True,**kwargs)
        assert src.read_bytes()==code==Path(str(report)+'.candidate.c').read_bytes()
        assert subprocess.check_output([exe])==b'x: 7\ny: 8\n'
        log=json.loads(report.read_text());assert not log['timed_out'] and log['returncode']==0
        saved=exe.read_bytes()
        try:build_bundled([a.compiler.resolve()],program,exe,ROOT/'runtime',stream=True,cc='/bin/false',**kwargs)
        except ValueError as e:assert 'C compiler failed' in str(e)
        else:raise AssertionError('failed compiler accepted')
        assert exe.read_bytes()==saved and src.read_bytes()==code
        log=json.loads(report.read_text());assert log['returncode']!=0 and not log['timed_out']
        for options in ({'compile_timeout':0},{'compile_evidence':exe},{'compile_evidence':src}):
            try:build_bundled([a.compiler.resolve()],program,exe,ROOT/'runtime',stream=True,**(kwargs|options))
            except ValueError:pass
            else:raise AssertionError('unsafe output alias or timeout accepted')
            assert exe.read_bytes()==saved and src.read_bytes()==code
        # Child inherits stdout: killing only the parent would block the
        # communicate call until the child exits. Whole-group retirement must
        # preserve the already emitted raw diagnostic and return promptly.
        start=time.monotonic()
        try:compile_c([sys.executable,'-c','import subprocess,time; subprocess.Popen(["sleep","30"]); print("started",flush=True); time.sleep(30)'],timeout=3,evidence=report)
        except subprocess.TimeoutExpired:pass
        else:raise AssertionError('compiler timeout accepted')
        log=json.loads(report.read_text())
        assert log['timed_out'] and log['returncode']==-9 and log['stdout']=='started\n' and time.monotonic()-start<12,log
        print('DOC11_BUILD_EVIDENCE_PASS: real Stage-2 C output, failed compiler preserves executable and C, alias rejection, bounded compiler group termination and raw diagnostics')
if __name__=='__main__':main()
