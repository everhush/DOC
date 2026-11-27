#!/usr/bin/env python3
"""Private issue #9 CPU comparison; exact DOC workload values, no production changes.
HVM2/Bend1 is compiled to native C. Pure one-shot output is distinguished from
DOC's persistent reactive epochs. No software adapter, no GPU claim.
"""
import argparse, hashlib, json, math, os, re, statistics, subprocess, time
from pathlib import Path

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def run(cmd, prefix, env=None, timeout=120, cwd=None):
    start=time.perf_counter_ns()
    try:
        p=subprocess.run([str(x) for x in cmd],capture_output=True,env=env,timeout=timeout,cwd=cwd)
        rc, out, err=p.returncode,p.stdout,p.stderr
    except subprocess.TimeoutExpired as e:
        rc,out,err=124,e.stdout or b'',e.stderr or b''
    ns=time.perf_counter_ns()-start
    prefix.with_suffix('.stdout').write_bytes(out)
    prefix.with_suffix('.stderr').write_bytes(err)
    return rc,out,err,ns

def cap():
    mask=sorted(os.sched_getaffinity(0))
    n=len(mask)
    for line in Path('/proc/self/cgroup').read_text().splitlines():
        if line.startswith('0::/'):
            root=Path('/sys/fs/cgroup')
            path=root/line[4:]
            for d in (path,*path.parents):
                if not d.is_relative_to(root): continue
                if (d/'cpu.max').exists():
                    q,t=(d/'cpu.max').read_text().split()
                    if q!='max': n=min(n,max(1,int(q)//int(t)))
    return mask[:n]

# All lane values are encoded as nonnegative integers for HVM's u24.
# For add/poly the reversible +4096 shift avoids signed-overflow ambiguity.
# Modulo 2^24 intermediate representation preserves the exact small final value.
# The modular multiplication is split before reduction to avoid 24-bit wrap.
BEND = """def modstep(x, b):
  a = (((x / 256) * 25173) % 65521) * 256
  c = ((x % 256) * 25173) % 65521
  return ((a % 65521) + c + b) % 65521

def stress(x, b, k):
  switch k:
    case 0:
      return x
    case _:
      return stress(modstep(x,b),b,k-1)

def addval(i,e):
  return ((i+e)%32760) + (e%7) + 4093

def polyval(i,e):
  x = ((i+e)%9) + 16777212
  b = (e%7) + 16777213
  v1 = b*x+b
  v2 = v1*x+b
  v3 = v2*x+b
  v4 = v3*x+b
  v5 = v4*x+b
  return v5+4096

def stressval(i,e):
  return stress((i+e)%32760,13849+e,32)

def reduceval(i,e):
  return (i+e)%2

def pluspair(a,b):
  (al,ah) = a
  (bl,bh) = b
  z = al+bl
  return (z%65536,ah+bh+(z/65536))

def fold(d,i,e,f):
  switch d:
    case 0:
      v = f(i,e)
      return (v%65536,v/65536)
    case _:
      return pluspair(fold(d-1,i,e,f),fold(d-1,i+(1 << (d-1)),e,f))

def tree(d,i,e,f) -> Any:
  switch d:
    case 0:
      return f(i,e)
    case _:
      return (tree(d-1,i,e,f),tree(d-1,i+(1 << (d-1)),e,f))
"""

# 32-bit LCG using two 16-bit limbs. Products needed for carry are computed
# from 8-bit pieces; the remaining low-word arithmetic is exact modulo 65536.
SORT = """def affine(lo,hi,ml,mh,cl,ch):
  p0 = (lo%256)*(ml%256)
  p1 = (lo/256)*(ml%256)+(lo%256)*(ml/256)+(p0/256)
  low = (p0%256)+256*(p1%256)+cl
  high = (lo/256)*(ml/256)+(p1/256)+lo*mh+hi*ml+ch+(low/65536)
  return (low%65536,high%65536)

def swap(s,a,b):
  switch s:
    case 0:
      return (a,b)
    case _:
      return (b,a)

def warp(d,s,a,b):
  switch d:
    case 0:
      return swap(s ^ (a>b),a,b)
    case _:
      (al,ar)=a
      (bl,br)=b
      (xl,yl)=warp(d-1,s,al,bl)
      (xr,yr)=warp(d-1,s,ar,br)
      return ((xl,xr),(yl,yr))

def down(d,s,t):
  switch d:
    case 0:
      return t
    case _:
      (a,b)=t
      return (rots(d-1,s,a),rots(d-1,s,b))

def rots(d,s,t):
  switch d:
    case 0:
      return t
    case _:
      (a,b)=t
      return down(d,s,warp(d-1,s,a,b))

def sort(d,s,t):
  switch d:
    case 0:
      return t
    case _:
      (a,b)=t
      return rots(d,s,(sort(d-1,0,a),sort(d-1,1,b)))
"""

def sort_source(d,e):
    # Same LCG as DOC, not a sorted/reversed or smaller substitute.
    m,c=1664525,1013904223
    chunks=[SORT, f'def g0(lo,hi):\n  (l,h)=affine(lo,hi,{m%65536},{m//65536},{c%65536},{c//65536})\n  return h%32768\n']
    for level in range(1,d+1):
        chunks.append(f'def g{level}(lo,hi) -> Any:\n  (l,h)=affine(lo,hi,{m%65536},{m//65536},{c%65536},{c//65536})\n  return (g{level-1}(lo,hi),g{level-1}(l,h))\n')
        c=(c*(m+1))%(1<<32)
        m=(m*m)%(1<<32)
    chunks.append(f'def main():\n  return sort({d},0,g{d}({2026+e},0))\n')
    return '\n'.join(chunks)

def oracle(w,n,e):
    if w=='sort':
        seed=2026+e
        a=[]
        for _ in range(n):
            seed=(seed*1664525+1013904223)&0xffffffff
            a.append((seed>>16)&32767)
        return sorted(a)
    if w=='add': return [(i+e)%32760+e%7-3 for i in range(n)]
    if w=='poly':
        b=e%7-3
        table=[]
        for x in range(-4,5):
            v=b
            for _ in range(5): v=v*x+b
            table.append(v)
        return [table[(i+e)%9] for i in range(n)]
    if w=='stress':
        b=13849+e
        # Recurrence independently evaluated on its complete input period.
        a=list(range(32760))
        for _ in range(32): a=[(x*25173+b)%65521 for x in a]
        return [a[(i+e)%32760] for i in range(n)]
    if w=='reduce': return [(i+e)&1 for i in range(n)]
    raise ValueError(w)

def result(out):
    # Generated C emits a raw interaction-net result; require exactly one
    # result line consisting only of numeric leaves and tuple punctuation.
    m=re.findall(rb'^Result:\s*([^\r\n]+)',out,re.M)
    if len(m)!=1 or not re.fullmatch(rb'[\d(), \t]+',m[0]):
        raise ValueError('unexpected HVM result format')
    return list(map(int,re.findall(rb'\d+',m[0])))

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--doc',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--samples',type=int,default=3)
    a=p.parse_args(); out=a.out.resolve(); out.mkdir(exist_ok=False,parents=True)
    doc=a.doc.resolve(); mask=cap(); assert mask
    env=dict(os.environ)
    for k in ('DOC_WORKERS','DOC_GPU_ALLOW_SOFTWARE','DOC_REQUIRE_PHYSICAL_GPU','DOC_DIAG_GROUP_CAP','DOC_GPU_TEST_FAIL_DISPATCH'):env.pop(k,None)
    env.update(DOC_REQUIRE_PHYSICAL_GPU='1',DOC_REGION_METRICS='1')
    affinity=['taskset','-c',','.join(map(str,mask))]
    machine=dict(affinity=mask,platform=os.uname().release,cpuinfo=Path('/proc/cpuinfo').read_text(),
                 compiler=subprocess.check_output(['gcc','--version'],text=True),
                 hvm=subprocess.check_output(['hvm','--version'],text=True),
                 bend=subprocess.check_output(['bend','--version'],text=True))
    assert '2.0.22' in machine['hvm'] and '0.2.38' in machine['bend']
    (out/'machine.json').write_text(json.dumps(machine,indent=2))
    sizes={'add':(64,4096,65536,1048576,4194304),'poly':(64,4096,65536,1048576,4194304),
           'stress':(4096,65536,262144),'sort':(1024,16384,65536),'reduce':(1024,16384,65536)}
    rows=[]; failures=[]
    for w,ns in sizes.items():
        for n in ns:
            d=n.bit_length()-1; assert n==1<<d
            base=out/f'{w}-{n}'; base.mkdir()
            family=w in ('add','poly')
            rounds=2 if family or w!='stress' else 5
            docbin=doc/('families/production' if family else 'algorithms')/w/'bench'
            manifest=json.loads((doc/('families' if family else 'algorithms')/'build.json').read_text())
            assert sha(docbin)==manifest[('production/' if family else '')+w]['sha256']
            for e in range(rounds):
                case=base/f'epoch-{e}';case.mkdir()
                values=oracle(w,n,e); expected=sum(values)
                offset=4096 if family else 0
                # Output all HVM vector leaves at modest sizes; fold into exact
                # two-limb checksum at larger sizes. Sort always emits all leaves.
                full=(n<=65536 and w!='reduce') or w=='sort'
                if w=='sort':
                    src=sort_source(d,e)
                else:
                    call='tree' if full else 'fold'
                    src=BEND+f'\ndef main():\n  return {call}({d},0,{e},{w}val)\n'
                source=case/'main.bend';source.write_text(src)
                rc,c,err,build_ns=run(affinity+['bend','gen-c',source],case/'bend',timeout=180)
                if rc or not c: failures.append([w,n,e,'HVM codegen',rc]); continue
                generated=case/'main.c';generated.write_bytes(c)
                exe=case/'hvm-bench'
                rc,_,_,cc_ns=run(['gcc','-O2',generated,'-o',exe,'-lm','-lpthread'],case/'gcc',timeout=180)
                if rc: failures.append([w,n,e,'HVM C compile',rc]); continue
                (case/'identity.json').write_text(json.dumps(dict(source=sha(source),generated=sha(generated),binary=sha(exe),build_ns=build_ns,cc_ns=cc_ns,expected=expected,full_vector=full),indent=2))
                for sample in range(a.samples):
                    rc,stdout,stderr,wall=run(affinity+['/usr/bin/time','-f','MAX_RSS_KIB=%M',exe],case/f'hvm-{sample}',timeout=90,env=env)
                    ok=False
                    try:
                        got=result(stdout)
                        ok=(got==[x+offset for x in values]) if full else (len(got)==2 and got[0]+65536*got[1]==expected+n*offset)
                    except ValueError: pass
                    rows.append(dict(engine='HVM2',work=w,n=n,epoch=e,sample=sample,wall_ns=wall,rc=rc,ok=not rc and ok,full_vector=full,expected=expected))
                    if rc or not ok: failures.append([w,n,e,'HVM execution/oracle',rc]);break
                del values
            # DOC actual production binary with the unchanged epoch/round protocol
            # and per-lane oracle checks, on the SAME affinity and runner.
            for sample in range(a.samples):
                rc,stdout,stderr,wall=run(affinity+['/usr/bin/time','-f','MAX_RSS_KIB=%M',docbin,'cpu',n,rounds],base/f'doc-{sample}',timeout=180,env=env)
                pat=rb'epoch=(\d+) wall_ns=(\d+) evals=(\d+) checksum=(-?\d+)' if family else rb'round=(\d+) epoch_sum_ns=(\d+) algorithm_ns=(\d+) checksum=(-?\d+)'
                got=[tuple(map(int,v)) for v in re.findall(pat,stdout)]
                expected=[sum(oracle(w,n,e)) for e in range(rounds)]
                ok=rc==0 and b'live=0' in stdout and [x[0] for x in got]==list(range(rounds)) and [x[3] for x in got]==expected
                rows.append(dict(engine='DOC',work=w,n=n,sample=sample,wall_ns=wall,rc=rc,ok=ok,rounds=rounds,epochs=got))
                if not ok: failures.append([w,n,'all','DOC execution/oracle',rc]);break
            (out/'samples.json').write_text(json.dumps(rows,indent=2))
            (out/'failures.json').write_text(json.dumps(failures,indent=2))
            print('HVM_DOC_CPU',w,n,'rows',len(rows),'failures',len(failures),flush=True)
    summary=[]
    for w,ns in sizes.items():
        for n in ns:
            group=[r for r in rows if r['work']==w and r['n']==n]
            h=[r['wall_ns']/1e6 for r in group if r['engine']=='HVM2' and r['ok']]
            d=[r['wall_ns']/1e6/r['rounds'] for r in group if r['engine']=='DOC' and r['ok']]
            summary.append(dict(work=w,n=n,hvm_process_ms_median=statistics.median(h) if h else None,doc_process_amortized_ms_median=statistics.median(d) if d else None,hvm_samples=len(h),doc_samples=len(d),failed=[f for f in failures if f[0]==w and f[1]==n]))
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    # Never silently pass a failed/partial case. Artifact uploaded even on failure.
    if failures: raise SystemExit(f'{len(failures)} failed or unqualified cases')
    print('HVM_DOC_CPU_ALL_PASS',flush=True)

if __name__=='__main__': main()
