#!/usr/bin/env python3
"""Regression for native compiler timeout, status and evidence retention."""
import json
import pathlib
import subprocess
import tempfile
from test_self_reproduction import run_cc

def main():
    with tempfile.TemporaryDirectory() as t:
        p=pathlib.Path(t);(p/'sample.c').write_text('int main(void){return 0;}\n')
        run_cc(['cc','-std=gnu11','-O1','-g0','-s',p/'sample.c','-o',p/'sample'],p,p,'sample',10)
        assert subprocess.run([p/'sample']).returncode==0
        report=json.loads((p/'compile-sample.json').read_text())
        assert report['returncode']==0 and not report['timed_out']
        for label,cmd,timeout in [('fail',['cc','missing.c'],10),('timeout',['sh','-c','sleep 30 & wait'],0.2)]:
            try: run_cc(cmd,p,p,label,timeout)
            except AssertionError: pass
            else: raise AssertionError(label)
            report=json.loads((p/f'compile-{label}.json').read_text())
            assert report['returncode']!=0 and report['timed_out']==(label=='timeout')
            assert report['argv']==cmd and report['seconds']<10
        print('DOC11_SELF_COMPILE_EVIDENCE_PASS: real C compile, failed compile, process-group timeout and retained diagnostics')
if __name__=='__main__':main()
