#!/usr/bin/env python3
"""Bootstrap subset: Stage 1 emits its own bundled DOC into Stage 2;
Stage 2 repeats emission, and the native C outputs must reproduce exactly.
The driver only assembles explicitly listed modules, transfers bytes and
invokes the platform C compiler. It never parses or lowers DOC expressions.
"""
import argparse, hashlib, os, pathlib, subprocess, tempfile, time
ROOT=pathlib.Path(__file__).resolve().parent.parent
PARTS=['lexer_core.doc','parser_core.doc','common_core.doc','general_core.doc','managed_core.doc','managed.doc']

def bundle():
    return '\n'.join('\n'.join(line for line in (ROOT/'compiler'/part).read_text().splitlines() if line.strip() and not line.startswith(('import ','#'))) for part in PARTS)+'\n'

def run(cmd,cwd,timeout=180,input_bytes=None):
    p=subprocess.run([str(x) for x in cmd],cwd=cwd,capture_output=True,text=True,input=input_bytes,timeout=timeout,env=dict(os.environ,DOC_REGION_METRICS='1'))
    assert p.returncode==0,(str(cmd[0]),p.stderr[-4000:]);return p.stdout,p.stderr

def source_arg(src):
    return 'input=['+','.join(map(str,src.encode()))+']'

def emit(compiler,src,cwd,label,stream=False):
    arg='--input-stdin' if stream else source_arg(src)
    if not stream: assert len(arg.encode())<130000,'bootstrap CLI input limit'
    payload=src if stream else None
    out,_=run([compiler,'--demand=chunk_count',arg],cwd,input_bytes=payload);n=int(out.partition(': ')[2]);assert n>0
    parts=[];start=time.monotonic()
    for i in range(n):
        out,err=run([compiler,'--demand=code',arg,'chunk='+str(i)],cwd,input_bytes=payload)
        assert out.startswith('code: ') and out.endswith('\n'),(i,out[:200]);parts.append(out[len('code: '):-1])
        print(f'DOC11_SELF_CHUNK: {label} {i+1}/{n}, bytes={len(parts[-1].encode())}',flush=True)
        if label=='stage2':assert 'DOC11_REGIONS: live=0 ' in err,err
    code=''.join(parts);print(f'DOC11_SELF_EMIT: {label}, bytes={len(code.encode())}, seconds={time.monotonic()-start:.3f}, sha256={hashlib.sha256(code.encode()).hexdigest()}',flush=True);return code

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--native',required=True,type=pathlib.Path);ap.add_argument('--evidence',required=True,type=pathlib.Path);a=ap.parse_args();stage1=a.native.resolve();evidence=a.evidence.resolve();evidence.mkdir(parents=True,exist_ok=True)
    src=bundle();(evidence/'bundle.doc').write_text(src)
    with tempfile.TemporaryDirectory() as tmp:
        cwd=pathlib.Path(tmp);c=cwd/'compiler.c';stage2=cwd/'stage2';stage3=cwd/'stage3'
        one=emit(stage1,src,cwd,'stage1');c.write_text(one);(evidence/'stage2.c').write_text(one)
        flags=['cc','-std=gnu11','-O1','-g0','-s','-I',ROOT/'runtime',c,'-o']
        run([*flags,stage2],cwd,240);assert stage2.stat().st_size>0
        two=emit(stage2,src,cwd,'stage2',stream=True);(evidence/'stage3.c').write_text(two);assert one==two,'self-generated C differs'
        c.write_text(two);run([*flags,stage3],cwd,240);assert stage2.read_bytes()==stage3.read_bytes(),'native binary differs'
        sample='fn twice(x)=add(x,x)\nsource a:int=9\nderive b:int(a)=twice(a)\nsource xs:ints=[1,2,3]\nderive ys:ints(xs)=map_ints(xs,x,mul(x,2))\n'
        sample_one=emit(stage1,sample,cwd,'sample-stage1');sample_two=emit(stage2,sample,cwd,'sample-stage2',stream=True);assert sample_one==sample_two
        assert sample_two==emit(stage2,sample,cwd,'sample-stage2-argv')
        for argv,payload in [(['--input-stdin','input=[]'],b''),(['--input-stdin','--input-stdin'],b''),(['--input-stdin'],b'x'*65537)]:
            bad=subprocess.run([str(stage2),'--demand=code',*argv],input=payload,capture_output=True,cwd=cwd,timeout=30)
            assert bad.returncode and not bad.stdout,(argv,bad.stderr)
        c.write_text(sample_two);app=cwd/'app';run([*flags,app],cwd);c.unlink();out,err=run([app],cwd);assert out=='a: 9\nb: 18\nxs: [1,2,3]\nys: [2,4,6]\n' and 'DOC11_REGIONS: live=0 ' in err,(out,err)
        linkage,_=run(['readelf','-d',stage2],cwd);assert 'libc.so.6' in linkage and 'libdoc' not in linkage and 'librust' not in linkage
        (evidence/'stage2-linkage.txt').write_text(linkage);(evidence/'stage2').write_bytes(stage2.read_bytes());(evidence/'stage3').write_bytes(stage3.read_bytes())
        print('DOC11_SELF_REPRODUCTION_PASS: bundled pure compiler, identical Stage2/Stage3 C and stripped ELF, independent sample application, no Rust evaluator dependency',flush=True)
if __name__=='__main__':main()
