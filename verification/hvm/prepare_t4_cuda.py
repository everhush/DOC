#!/usr/bin/env python3
"""Build stock and minimal T4-compatible HVM2 CUDA sources; compile on CUDA 12.8."""
import json,subprocess,sys,re,struct
from pathlib import Path
from compare_cpu import family_source,sort_source,sha
def patch_t4(source):
    # Preserve per-thread local capacity: 8192/128 = 4096/64.
    # Keep TPB_L2 == BPG_L2: GROW uses max() to index spawn[TPB].
    # This changes launch width and block count, never the Bend program.
    text=source.decode()
    for old,new in [('const u32 L_NODE_LEN = 0x2000;', 'const u32 L_NODE_LEN = 0x1000;'),('const u32 L_VARS_LEN = 0x2000;', 'const u32 L_VARS_LEN = 0x1000;'),('const u32 TPB_L2 = 7;', 'const u32 TPB_L2 = 6;'),('const u32 BPG_L2 = 7;', 'const u32 BPG_L2 = 6;')]:
        assert text.count(old)==1,old
        text=text.replace(old,new)
    assert 'const u32 TPB_L2 = 6;' in text and 'const u32 BPG_L2 = 6;' in text
    m=re.search(r'^\s*static const u8 BOOK_BUF\[\]\s*=\s*\{([\d,\s]+)\};',text,re.M)
    assert m
    data=bytes(int(v) for v in re.findall(r'\d+',m[1]))
    words=struct.unpack('<'+'I'*(len(data)//4),data)
    pos=1; maxima=[0,0,0]
    for _ in range(words[0]):
        pos+=65
        safe,redexes,nodes,variables,root=words[pos:pos+5]
        pos+=5+2*(redexes+nodes)
        maxima=[max(a,b) for a,b in zip(maxima,[redexes,nodes,variables])]
    assert pos==len(words) and max(maxima)<=64,maxima
    return text.encode(),maxima

def main():
    out=Path('doc9-hvm-cuda');out.mkdir(); stock=out/'stock';stock.mkdir()
    assert '2.0.22' in subprocess.check_output(['hvm','--version'],text=True)
    assert '0.2.38' in subprocess.check_output(['bend','--version'],text=True)
    sizes={'add':(64,4096,65536,1048576,4194304),'poly':(64,4096,65536,1048576,4194304),'stress':(4096,65536,262144),'sort':(1024,16384,65536),'reduce':(1024,16384,65536)}
    cases=[]
    for w,ns in sizes.items():
        for n in ns:
            d=n.bit_length()-1
            for e in range(5 if w=='stress' else 2):
                full=(n<=65536 and w!='reduce') or w=='sort'
                src=sort_source(d,e) if w=='sort' else family_source(w,d,e,full)
                stem=f'{w}-{n}-{e}'
                p=out/(stem+'.bend');p.write_text(src)
                r=subprocess.run(['bend','gen-cu',p],capture_output=True,timeout=180)
                (out/(stem+'.stderr')).write_bytes(r.stderr)
                if r.returncode or not r.stdout:raise RuntimeError('HVM CUDA codegen failed: '+stem+' '+r.stderr.decode(errors='replace')[-2000:])
                original=stock/(stem+'.cu');original.write_bytes(r.stdout)
                q=out/(stem+'.cu');patched,maxima=patch_t4(r.stdout);q.write_bytes(patched)
                cases.append(dict(work=w,n=n,epoch=e,full=full,stem=stem,source_sha=sha(p),stock_cuda_sha=sha(original),cuda_sha=sha(q),max_definition_slots=maxima))
    nvcc='/usr/local/cuda-12.8/bin/nvcc'
    version=subprocess.check_output([nvcc,'--version'],text=True)
    assert 'release 12.8' in version,version
    (out/'toolkit.txt').write_text(version)
    for c in cases:
        stem=c['stem']; exe=out/(stem+'.elf')
        r=subprocess.run([nvcc,'-O2','-arch=sm_75','--cudart=static',out/(stem+'.cu'),'-o',exe],capture_output=True,timeout=300)
        (out/(stem+'.compile.stdout')).write_bytes(r.stdout)
        (out/(stem+'.compile.stderr')).write_bytes(r.stderr)
        if r.returncode:raise RuntimeError(stem+' CUDA12 compile: '+r.stderr.decode(errors='replace')[-4000:])
        c['binary_sha']=sha(exe)
        print('HVM_T4_COMPILED',stem,c['binary_sha'],flush=True)
    (out/'cases.json').write_text(json.dumps(cases,indent=2))
if __name__=='__main__':main()
