#!/usr/bin/env python3
"""Independent finite-DAG oracle. Not used by the DOC runtime."""
import argparse
import ast
import itertools
import os
import random
import subprocess
import tempfile
from pathlib import Path


def values(flags):
    return '['+','.join(map(str, flags))+']'


def oracle(case):
    r,o,p,a,m,x,d,f,c=(case[key] for key in ('roles','offsets','premises','active','materialized','source_changed','requested','selected','changed'))
    n=len(r); direct=[set(p[o[i]:o[i+1]]) for i in range(n)]
    def ancestors(i):
        result=set(direct[i])
        for pred in direct[i]: result |= ancestors(pred)
        return result
    def mask(indices): return [int(i in indices) for i in range(n)]
    def indices(bits): return {i for i,v in enumerate(bits) if v}
    def users(changed): return {i for i in range(n) if direct[i]&changed}
    active=indices(a)|users(indices(x))
    ready={i for i in active if not ancestors(i)&active}
    closure=indices(d)
    for i in indices(d): closure |= ancestors(i)
    eligible=ready&closure
    selected=indices(f); changed=indices(c)
    result={'after_update':mask(active),'ready':mask(ready),'closure':mask(closure),'eligible':mask(eligible)}
    if selected:
        assert selected<=eligible and changed<=selected and (selected-indices(m))<=changed
        result['after_frontier']=mask((active-selected)|users(changed))
        result['after_materialized']=mask(indices(m)|selected)
        result['proof']=sum((result[key] for key in ('after_update','ready','closure','eligible','after_frontier','after_materialized')),[])
    return result


def run(cmd,case,target,expect,cwd,workers):
    output=subprocess.run([*cmd,'--demand='+target,*[f'{k}={values(v)}' for k,v in case.items()]],env={**os.environ,'DOC_WORKERS':str(workers)},cwd=cwd,capture_output=True,text=True,timeout=30)
    if expect is None:
        assert output.returncode and target+':' not in output.stdout,(case,target,output.stdout,output.stderr)
    else:
        assert output.returncode==0,(case,target,output.stderr)
        rows=[line.partition(': ')[2] for line in output.stdout.splitlines() if line.startswith(target+': ')]
        assert len(rows)==1 and ast.literal_eval(rows[0])==expect,(case,target,rows,expect)


def base_case():
    return dict(roles=[0,1],offsets=[0,0,1],premises=[0],active=[0,1],materialized=[1,0],source_changed=[0,0],requested=[1,1],selected=[0,1],changed=[0,1])


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--reference',type=Path,required=True); ap.add_argument('--source',type=Path,required=True); ap.add_argument('--native',type=Path); args=ap.parse_args()
    commands=[[str(args.reference.resolve()),str(args.source.resolve())]]
    if args.native: commands.append([str(args.native.resolve())])
    rng=random.Random(15011); cases=[]
    # Exhaust all ordered four-node DAG topologies. Each has an initial seed,
    # and seven later active masks, including inactive intermediate vertices.
    possible=[(p,u) for u in range(4) for p in range(u)]
    for bits in range(1<<len(possible)):
        edges=[e for j,e in enumerate(possible) if bits>>j&1]
        offsets=[0]; premises=[]
        for u in range(4): premises.extend(p for p,v in edges if v==u); offsets.append(len(premises))
        for active_bits in range(8):
            active=[0,*[active_bits>>i&1 for i in range(3)]]
            materialized=[1]+[rng.randrange(2) if a else 1 for a in active[1:]]
            case=dict(roles=[0,1,1,1],offsets=offsets,premises=premises,active=active,materialized=materialized,source_changed=[rng.randrange(2),0,0,0],requested=[rng.randrange(2) for _ in range(4)],selected=[0]*4,changed=[0]*4)
            eligible=oracle(case)['eligible']
            chosen=[int(bool(v) and bool(rng.randrange(2))) for v in eligible]
            if any(eligible) and not any(chosen): chosen[eligible.index(1)]=1
            case['selected']=chosen; case['changed']=[int(bool(f) and (not m or bool(rng.randrange(2)))) for f,m in zip(chosen,materialized)]
            cases.append(case)
    # A specific active ancestor hidden behind an inactive intermediate.
    cases.append(dict(roles=[0,1,1,1],offsets=[0,0,1,2,3],premises=[0,1,2],active=[0,1,0,1],materialized=[1,1,1,1],source_changed=[0]*4,requested=[0,0,0,1],selected=[0,1,0,0],changed=[0,0,0,0]))
    # Repeated premise occurrences retain the same graph relation.
    cases.append(dict(roles=[0,1,1],offsets=[0,0,2,4],premises=[0,0,0,1],active=[0,1,1],materialized=[1,0,0],source_changed=[0,0,0],requested=[0,0,1],selected=[0,1,0],changed=[0,1,0]))
    invalid=[]
    for k,v in [('roles',[0,2]),('offsets',[0,0]),('offsets',[0,1,1]),('offsets',[0,0,2]),('premises',[1]),('premises',[-1]),('active',[1,1]),('active',[0,2]),('materialized',[0,0]),('materialized',[1]),('source_changed',[0,1]),('requested',[1,2]),('selected',[1,1]),('changed',[1,1]),('selected',[0,0]),('changed',[0,0]),('requested',[1,0])]:
        case=base_case();case[k]=v;invalid.append(case)
    case=base_case();case['active']=[0,0];invalid.append(case)
    with tempfile.TemporaryDirectory(prefix='doc11-repair-') as cwd:
        for cmd in commands:
            for i,case in enumerate(cases):
                expected=oracle(case)
                if 'proof' in expected:
                    run(cmd,case,'proof',expected['proof'],cwd,1 if i%2==0 else 4)
                else:
                    for target in ('ready','closure','after_update','eligible'):
                        run(cmd,case,target,expected[target],cwd,1 if i%2==0 else 4)
            for case in invalid: run(cmd,case,'proof',None,cwd,1)
    print(f'DOC11_REPAIR_PASS: {len(cases)} DAG/repair/demand cases, {len(invalid)} negative, {len(commands)} execution paths, workers=1/4')

if __name__=='__main__': main()
