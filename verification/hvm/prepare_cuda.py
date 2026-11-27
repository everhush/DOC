#!/usr/bin/env python3
"""Build exact HVM2 CUDA sources without a GPU; private comparison only."""
import json,subprocess,sys
from pathlib import Path
from compare_cpu import BEND,sort_source,sha
def main():
    out=Path('doc9-hvm-cuda');out.mkdir()
    assert '2.0.22' in subprocess.check_output(['hvm','--version'],text=True)
    assert '0.2.38' in subprocess.check_output(['bend','--version'],text=True)
    sizes={'add':(64,4096,65536,1048576,4194304),'poly':(64,4096,65536,1048576,4194304),'stress':(4096,65536,262144),'sort':(1024,16384,65536),'reduce':(1024,16384,65536)}
    cases=[]
    for w,ns in sizes.items():
        for n in ns:
            d=n.bit_length()-1
            for e in range(5 if w=='stress' else 2):
                full=(n<=65536 and w!='reduce') or w=='sort'
                src=sort_source(d,e) if w=='sort' else BEND+f'\ndef main():\n  return {"tree" if full else "fold"}({d},0,{e},{w}val)\n'
                stem=f'{w}-{n}-{e}'
                p=out/(stem+'.bend');p.write_text(src)
                r=subprocess.run(['bend','gen-cu',p],capture_output=True,timeout=180)
                (out/(stem+'.stderr')).write_bytes(r.stderr)
                if r.returncode or not r.stdout:raise RuntimeError('HVM CUDA codegen failed: '+stem+' '+r.stderr.decode(errors='replace')[-2000:])
                q=out/(stem+'.cu');q.write_bytes(r.stdout)
                cases.append(dict(work=w,n=n,epoch=e,full=full,stem=stem,source_sha=sha(p),cuda_sha=sha(q)))
    (out/'cases.json').write_text(json.dumps(cases,indent=2))
if __name__=='__main__':main()
