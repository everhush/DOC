#!/usr/bin/env python3
"""Regenerate portable recurrence policy and test its actual host boundary."""
import argparse,os,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'compiler'))
from doc_build import emit
def main():
    p=argparse.ArgumentParser();p.add_argument('--managed',type=Path,required=True);p.add_argument('--reactive',type=Path,required=True);p.add_argument('--headers',type=Path,default=ROOT/'runtime');a=p.parse_args()
    headers=a.headers.resolve()
    policy=(headers/'recurrence_policy.doc').read_bytes()+b'source marker:int=0\n'
    actual=[x for x in emit([a.managed.resolve()],policy,stream=True).splitlines() if x.startswith(b'#define F_rec_')]
    assert len(actual)==6 and b'\n'.join(actual)+b'\n'==(headers/'recurrence_policy_generated.h').read_bytes()
    source=b'source a:int=1\nsource b:int=2\nsource xs:ints=[1]\nderive sum:int(a,b)=add(a,b)\nderive list:ints(xs,sum)=append(xs,sum)\nderive done:bool(sum)=lt(5,sum)\n'
    with tempfile.TemporaryDirectory() as td:
        cwd=Path(td);(cwd/'generated.c').write_bytes(emit([a.reactive.resolve()],source,True,stream=True))
        exe=cwd/'host'
        subprocess.run(['cc','-std=gnu11','-O1','-pthread','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie','-I',str(headers),'-I',td,str(Path(__file__).resolve().parent/'recurrence_authority_host.c'),'-lm','-o',str(exe)],check=True,timeout=120)
        result=subprocess.run([exe],cwd=cwd,capture_output=True,timeout=120,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1'))
        assert result.returncode==0 and b'DOC11_RECURRENCE_AUTHORITY_PASS:' in result.stdout,result.stderr[-4000:]
        print(result.stdout.decode().strip())
if __name__=='__main__':main()
