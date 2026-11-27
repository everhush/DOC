#!/usr/bin/env python3
"""Matched one/two CPU worker controls using exact previously verified programs."""
import json,os,re,statistics,subprocess
from pathlib import Path
from compare_cpu import cap,run,result,oracle,sha

def main():
    source=Path('doc9-qualified-hvm').resolve();doc=Path('doc11-stage2-gpu-evidence/scale').resolve()
    out=Path('doc9-hvm-workers').resolve();out.mkdir()
    mask=cap();assert len(mask)>=2,'two CPU workers not available'
    mask=mask[:2];rows=[];failures=[]
    env=dict(os.environ)
    for k in ('DOC_WORKERS','DOC_GPU_ALLOW_SOFTWARE','DOC_DIAG_GROUP_CAP','DOC_GPU_TEST_FAIL_DISPATCH'):env.pop(k,None)
    env.update(DOC_REGION_METRICS='1',DOC_REQUIRE_PHYSICAL_GPU='1')
    (out/'machine.json').write_text(json.dumps(dict(affinity=mask,cpuinfo=Path('/proc/cpuinfo').read_text(),kernel=os.uname().release,gcc=subprocess.check_output(['gcc','--version'],text=True)),indent=2))
    # Exact previously passed largest workloads, plus small controls.
    cases=[('add',4096),('add',4194304),('poly',65536),('poly',4194304),('stress',262144),('sort',65536),('reduce',65536)]
    for w,n in cases:
        family=w in ('add','poly');rounds=5 if w=='stress' else 2
        root=out/f'{w}-{n}';root.mkdir()
        category='families' if family else 'algorithms'
        key=('production/' if family else '')+w
        docbin=doc/category/key/'bench'
        rec=json.loads((doc/category/'build.json').read_text())[key]
        assert sha(docbin)==rec['sha256']
        docbin.chmod(0o700)
        expected=[sum(oracle(w,n,e)) for e in range(rounds)]
        for workers in (1,2):
            target=root/str(workers);target.mkdir()
            affinity=['taskset','-c',','.join(map(str,mask[:workers]))]
            denv={**env,'DOC_WORKERS':str(workers)}
            executables=[]
            for e in range(rounds):
                orig=source/f'{w}-{n}/epoch-{e}'
                record=json.loads((orig/'identity.json').read_text())
                c=orig/'main.c';assert sha(c)==record['generated']
                assert b'#ifndef TPC_L2' in c.read_bytes() and b'#define TPC_L2' in c.read_bytes()
                exe=target/f'hvm-{e}'
                rc,_,err,ns=run(['gcc','-O2',f'-DTPC_L2={workers.bit_length()-1}',c,'-o',exe,'-lm','-lpthread'],target/f'compile-{e}',timeout=180)
                if rc:raise RuntimeError('HVM worker compile failed '+err.decode(errors='replace')[-1000:])
                executables.append((e,exe,record,ns))
            (target/'identity.json').write_text(json.dumps([dict(epoch=e,source=rec['source'],generated=rec['generated'],binary=sha(exe),compile_ns=ns,workers=workers) for e,exe,rec,ns in executables],indent=2))
            for sample in range(3):
                # Same affinity and worker setting; no overlap between engines.
                rc,stdout,stderr,wall=run(affinity+['/usr/bin/time','-f','MAX_RSS_KIB=%M',docbin,'cpu',n,rounds],target/f'doc-{sample}',env=denv,timeout=240)
                pat=rb'epoch=(\d+) wall_ns=(\d+) evals=(\d+) checksum=(-?\d+)' if family else rb'round=(\d+) epoch_sum_ns=(\d+) algorithm_ns=(\d+) checksum=(-?\d+)'
                got=[tuple(map(int,v)) for v in re.findall(pat,stdout)]
                actual=max([1]+[int(x) for x in re.findall(rb'DOC11_CPU_FAMILY: lanes=\d+ workers=(\d+)',stderr)])
                ok=rc==0 and b'live=0' in stdout and actual==workers and [x[0] for x in got]==list(range(rounds)) and [x[3] for x in got]==expected
                rows.append(dict(engine='DOC',work=w,n=n,sample=sample,workers=workers,actual_workers=actual,wall_ns=wall,rounds=rounds,epochs=got,ok=ok,rc=rc))
                if not ok:failures.append([w,n,workers,'DOC',rc])
                for e,exe,rec,_ in executables:
                    v=oracle(w,n,e);offset=4096 if family else 0
                    rc,stdout,stderr,wall=run(affinity+['/usr/bin/time','-f','MAX_RSS_KIB=%M',exe],target/f'hvm-{e}-{sample}',env=env,timeout=240)
                    ok=False
                    try:
                        got=result(stdout)
                        ok=(got==[x+offset for x in v]) if rec['full_vector'] else (len(got)==2 and got[0]+65536*got[1]==sum(v)+n*offset)
                    except ValueError:pass
                    ok=ok and rc==0 and not re.search(rb'(?i)\bOOM\b|out of memory',stdout+stderr)
                    rows.append(dict(engine='HVM2',work=w,n=n,epoch=e,sample=sample,workers=workers,wall_ns=wall,ok=ok,rc=rc,full_vector=rec['full_vector'],expected=sum(v)))
                    if not ok:failures.append([w,n,workers,e,'HVM2',rc])
                (out/'samples.json').write_text(json.dumps(rows,indent=2))
                (out/'failures.json').write_text(json.dumps(failures,indent=2))
            for _,exe,_,_ in executables:exe.unlink()
            print('DOC9_HVM_WORKER_CONTROL',w,n,workers,len(rows),len(failures),flush=True)
    summary=[]
    for w,n in cases:
        for engine in ('HVM2','DOC'):
            med=[]
            for workers in (1,2):
                rr=[r['wall_ns']/1e6/r.get('rounds',1) for r in rows if r['work']==w and r['n']==n and r['engine']==engine and r['workers']==workers and r['ok']]
                med.append(statistics.median(rr) if rr else None)
            summary.append(dict(work=w,n=n,engine=engine,one_ms=med[0],two_ms=med[1],speedup=med[0]/med[1] if all(med) else None))
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    if failures:raise RuntimeError('unqualified worker controls '+str(failures))
    print('DOC9_HVM_WORKERS_PASS',flush=True)
if __name__=='__main__':main()
