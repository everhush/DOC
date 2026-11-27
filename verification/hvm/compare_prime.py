#!/usr/bin/env python3
"""Same-run comparison of the integrated forty-interval prime graph."""
import argparse,json,math,os,statistics,subprocess
from pathlib import Path
from compare_cpu import cap,run,result,sha

PRIME="""def trial(n,d):
  if d*d > n:
    return 1
  else:
    if n % d == 0:
      return 0
    else:
      return trial(n,d+2)

def isprime(n):
  if n % 2 == 0:
    return 0
  else:
    return trial(n,3)

def interval(n,end,total):
  if n == end:
    return total
  else:
    return interval(n+1,end,total+isprime(n))
"""
def expr(terms):
    if len(terms)==1:return terms[0]
    m=len(terms)//2
    return '('+expr(terms[:m])+' + '+expr(terms[m:])+')'

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--reactive',type=Path,required=True);a=p.parse_args()
    out=a.out.resolve();out.mkdir()
    mask=cap()[:4];affinity=['taskset','-c',','.join(map(str,mask))]
    env=dict(os.environ);env.pop('DOC_WORKERS',None)
    # Exact original independent oracle and identical 40 shifted half-open intervals.
    limit=525040;sieve=bytearray(b'\1')*limit;sieve[:2]=b'\0\0'
    for i in range(2,math.isqrt(limit-1)+1):
        if sieve[i]:sieve[i*i:limit:i]=b'\0'*(((limit-1-i*i)//i)+1)
    expected=sum(sum(sieve[500000+i:525000+i]) for i in range(40));assert expected==76216
    src=out/'prime40.bend';src.write_text(PRIME+'\ndef main():\n  return '+expr([f'interval({500000+i},{525000+i},0)' for i in range(40)])+'\n')
    rc,c,err,ns=run(affinity+['bend','gen-c',src],out/'codegen',env=env,timeout=180)
    assert rc==0 and c,err[-2000:]
    generated=out/'prime40.c';generated.write_bytes(c)
    exe=out/'prime-hvm'
    rc,_,err,compile_ns=run(['gcc','-O2',generated,'-o',exe,'-lm','-lpthread'],out/'compile',env=env,timeout=180)
    assert rc==0,err[-2000:]
    (out/'identity.json').write_text(json.dumps(dict(source=sha(src),generated=sha(generated),binary=sha(exe),codegen_ns=ns,compile_ns=compile_ns,affinity=mask,expected=expected),indent=2))
    # Reuse actual production integrated benchmark, not a native callback replacement.
    rc,_,err,_=run(affinity+['python3','-u','runtime-doc/tests/benchmark_integrated_prime.py','--reactive',a.reactive.resolve(),'--out',out/'doc','--samples','3','--cc','clang-18'],out/'doc-build-and-run',env=env,timeout=1200)
    assert rc==0,err[-3000:]
    rows=[]
    for sample in range(3):
        rc,stdout,stderr,ns=run(affinity+['/usr/bin/time','-f','MAX_RSS_KIB=%M',exe],out/f'hvm-{sample}',env=env,timeout=240)
        ok=False
        try:ok=rc==0 and result(stdout)==[expected]
        except ValueError:pass
        rows.append(dict(sample=sample,wall_ns=ns,rc=rc,ok=ok))
        (out/'hvm-samples.json').write_text(json.dumps(rows,indent=2))
        if not ok:raise RuntimeError('HVM prime execution or oracle failed')
    doc=json.loads((out/'doc/summary.json').read_text())
    (out/'summary.json').write_text(json.dumps(dict(expected=expected,affinity=mask,doc=doc,hvm_process_median_ms=statistics.median(r['wall_ns'] for r in rows)/1e6,samples=rows),indent=2))
    print('DOC9_HVM_PRIME_PASS',flush=True)
if __name__=='__main__':main()
