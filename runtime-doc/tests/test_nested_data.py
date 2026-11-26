#!/usr/bin/env python3
"""Frozen tagged-data fixture: independent recursive oracle vs native and Rust."""
import argparse,hashlib,json,os,random,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def parse(rows):
    def node(i):
        t=rows[i];i+=1
        if t==0:rows[i];return i+1,1
        if t==1:
            if rows[i] not in (0,1):raise ValueError()
            return i+1,1
        if t==2:
            n=rows[i];i+=1
            if n<0 or i+n>len(rows):raise ValueError()
            bytes(rows[i:i+n]).decode('utf-8');return i+n,1
        if t==3:
            n=rows[i];i+=1
            if not 0<=n<=65536:raise ValueError()
            total=1
            for _ in range(n):i,k=node(i);total+=k
            return i,total
        if t==4:return i,1
        if t==5:
            i,k=node(i);return i,1+k
        raise ValueError()
    try:
        i,n=node(0);return n if i==len(rows) else None
    except (IndexError,ValueError,UnicodeError,RecursionError):return None

def cases():
    rows=[[0,-2**63],[1,0],[1,1],[2,0],[2,2,195,169],[3,0],[4],[5,4],[3,3,0,42,5,2,2,195,169,4],[3,2,3,2,1,1,0,-7,5,3,1,2,1,65],[],[0],[1,2],[2,-1],[2,2,65],[2,1,255],[2,1,256],[2,1,-1],[2,2**63-1],[3,-1],[3,65537],[3,2,4],[5],[6],[4,4]]
    rng=random.Random(110724)
    def gen(d):
        t=rng.randrange(6) if d<5 else rng.choice([0,1,2,4])
        if t==0:return [0,rng.randrange(-10000,10000)]
        if t==1:return [1,rng.randrange(2)]
        if t==2:
            b=rng.choice(['','é','नमस्ते','🙂','a\x00b','東京']).encode();return [2,len(b),*b]
        if t==3:
            n=rng.randrange(4);return [3,n,*[k for _ in range(n) for k in gen(d+1)]]
        if t==4:return [4]
        return [5,*gen(d+1)]
    for _ in range(40):
        v=gen(0);rows.extend([v,v[:-1],v+[4]])
    return rows

def main():
    p=argparse.ArgumentParser()
    for name in ('managed','reactive','reference','evidence'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();source=ROOT/'runtime-rust/examples/nested_data.doc';raw=source.read_bytes();headers=ROOT/'runtime-doc/runtime'
    out=a.evidence.resolve();out.mkdir(parents=True,exist_ok=True);results={}
    env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1','DOC_REGION_METRICS':'1'}
    def run(cmd,**kw):return subprocess.run([str(x) for x in cmd],cwd=out,env=env,capture_output=True,timeout=180,**kw)
    for name,compiler in [('managed',a.managed.resolve()),('reactive',a.reactive.resolve())]:
        e=run([compiler,'--demand=code','--input-stdin'],input=raw);assert e.returncode==0 and e.stdout.startswith(b'code: '),e.stderr[-3000:]
        c=out/(name+'.c');c.write_bytes(e.stdout[6:]);exe=out/name
        cc=run(['cc','-std=gnu11','-O1','-g','-pthread','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie','-I',headers,c,'-lm','-o',exe]);assert cc.returncode==0,cc.stderr[-3000:]
        good=bad=0
        for rows in cases():
            args=['--demand=summary','encoded=['+','.join(map(str,rows))+']'];x=run([a.reference.resolve(),source,*args]);y=run([exe,*args]);n=parse(rows)
            assert (x.returncode==0)==(y.returncode==0) and x.stdout==y.stdout,(name,rows,n,x.returncode,y.returncode,x.stdout,y.stdout,x.stderr,y.stderr)
            assert not any(t in y.stderr for t in (b'AddressSanitizer',b'LeakSanitizer',b'runtime error:')),y.stderr
            if n is None:assert y.returncode and not y.stdout;bad+=1
            else:assert y.returncode==0 and y.stdout==f'summary: [{len(rows)},0,{n}]\n'.encode() and b'DOC11_REGIONS: live=0 ' in y.stderr;good+=1
        if name=='reactive':
            args=['--demand=summary','encoded=[4]','--next','--demand=summary','encoded=[3,2,5,0,8,2,1,65]','--next','--demand=summary','encoded=[3,0]','--next','--demand=summary','encoded=[3,1]']
            x=run([a.reference.resolve(),source,*args]);y=run([exe,*args]);assert x.returncode and y.returncode and x.stdout==y.stdout and b'epoch: 2\nsummary: [2,0,1]\n' in y.stdout and b'epoch: 3' not in y.stdout and b'DOC11_REGIONS: live=0 ' in y.stderr,(x.stdout,y.stdout,y.stderr)
            (out/'rollback.stdout').write_bytes(y.stdout);(out/'rollback.stderr').write_bytes(y.stderr)
        assert (good,bad)==(50,95),(good,bad)
        results[name]={'good':good,'bad':bad,'c_sha256':hashlib.sha256(c.read_bytes()).hexdigest(),'elf_sha256':hashlib.sha256(exe.read_bytes()).hexdigest()}
        print(name,results[name],flush=True)
    (out/'summary.json').write_text(json.dumps(results,indent=2)+'\n')
    print('DOC11_NESTED_DATA_PASS: original frozen fixture, independent recursive oracle, malformed inputs and failed reactive update; ASan/UBSan',flush=True)
if __name__=='__main__':main()
