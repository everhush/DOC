#!/usr/bin/env python3
"""Bounded repair-admissibility and continued-source-update checker."""
from __future__ import annotations
from dataclasses import dataclass
from itertools import combinations, product
from typing import Callable, Iterable

Value=int

def xor(xs):
    r=0
    for x in xs:r^=x
    return r

def conjunction(xs): return int(all(xs))
FUNCS=(xor,conjunction)

@dataclass(frozen=True)
class Defn:
    premises: tuple[int,...]
    fi:int
@dataclass(frozen=True)
class Graph:
    source_count:int
    defs:tuple[Defn,...]
    @property
    def n(self): return self.source_count+len(self.defs)
    def d(self,s): return self.defs[s-self.source_count]
    def users(self):
        out=[set() for _ in range(self.n)]
        for s in range(self.source_count,self.n):
            for p in self.d(s).premises: out[p].add(s)
        return tuple(tuple(sorted(x)) for x in out)
@dataclass(frozen=True)
class Cfg:
    vals:tuple[int|None,...]
    active:frozenset[int]
    done:frozenset[int]

def subsets_nonempty(xs):
    for k in range(1,len(xs)+1): yield from combinations(xs,k)

def frontier(g,a):
    # Semantic definition: active states with no active strict ancestor.
    ready=[]
    for d in range(g.source_count,g.n):
        if d not in a: continue
        stack=list(g.d(d).premises)
        blocked=False
        seen=set()
        while stack:
            p=stack.pop()
            if p in seen: continue
            seen.add(p)
            if p>=g.source_count:
                if p in a:
                    blocked=True;break
                stack.extend(g.d(p).premises)
        if not blocked: ready.append(d)
    return tuple(ready)

def locally_satisfied(g,vals,d):
    ins=tuple(vals[p] for p in g.d(d).premises)
    return all(x is not None for x in ins) and vals[d]==FUNCS[g.d(d).fi](ins)

def admissible(g,vals,a):
    if any(vals[s] is None for s in range(g.source_count)): return False
    for d in range(g.source_count,g.n):
        if d not in a and not locally_satisfied(g,vals,d): return False
    return True

def oracle(g,vals):
    out=list(vals[:g.source_count])
    for d in range(g.source_count,g.n):
        ins=tuple(out[p] for p in g.d(d).premises)
        out.append(FUNCS[g.d(d).fi](ins))
    return tuple(out)

def step(g,u,c,sel,conservative):
    r=frontier(g,c.active)
    assert sel and all(x in r for x in sel)
    assert not any(x in c.done for x in sel)
    cand={}
    for d in sel:
        ins=tuple(c.vals[p] for p in g.d(d).premises)
        assert all(x is not None for x in ins)
        cand[d]=FUNCS[g.d(d).fi](ins)
    vals=list(c.vals); a=set(c.active); a.difference_update(sel)
    for d in sel:
        if conservative or vals[d]!=cand[d]:
            vals[d]=cand[d];a.update(u[d])
    n=Cfg(tuple(vals),frozenset(a),c.done.union(sel))
    assert admissible(g,n.vals,n.active)
    return n

def check_cfg(g,start,conservative):
    u=g.users(); stack=[start]; seen=set(); finals=set(); max_depth=0
    while stack:
        c=stack.pop()
        if c in seen: continue
        seen.add(c);max_depth=max(max_depth,len(c.done))
        assert len(c.done)<=len(g.defs)
        if not c.active:
            assert admissible(g,c.vals,c.active)
            assert all(v is not None for v in c.vals)
            finals.add(c.vals)
            continue
        r=frontier(g,c.active)
        assert r
        for sel in subsets_nonempty(r): stack.append(step(g,u,c,sel,conservative))
    assert finals=={oracle(g,start.vals)},(g,start,finals,oracle(g,start.vals))
    return len(seen),max_depth

def graphs():
    # 1 source + 3 derived, every ordered-by-ID acyclic premise subset including empty,
    # two Boolean functions per definition = 512 graph families.
    sc=1
    opts=[]
    for s in range(sc,sc+3):
        prev=range(s)
        opts.append([tuple(i for i in prev if mask>>i&1) for mask in range(1<<s)])
    for ps in product(*opts):
        for fs in product(range(2),repeat=3):
            yield Graph(sc,tuple(Defn(ps[i],fs[i]) for i in range(3)))

def configs(g):
    # all pointwise values (0,1,None) and all active sets; filter repair-admissible.
    ds=tuple(range(g.source_count,g.n))
    for src in product((0,1),repeat=g.source_count):
      for dvals in product((0,1,None),repeat=len(g.defs)):
       vals=tuple(src)+tuple(dvals)
       for mask in range(1<<len(ds)):
        a=frozenset(ds[i] for i in range(len(ds)) if mask>>i&1)
        if admissible(g,vals,a): yield Cfg(vals,a,frozenset())

gc=cc=states=updates=0; maxdepth=0
unique_starts=unique_states=0
for g in graphs():
    gc+=1
    u=g.users()
    # Many continued updates produce the same admissible start configuration.
    # Cache complete explorations by the exact semantic start and cutoff profile;
    # this changes only checker cost, never the explored transition relation.
    checked: dict[tuple[Cfg,bool], tuple[int,int]] = {}
    def verify(start: Cfg, conservative: bool) -> tuple[int,int]:
        key=(start,conservative)
        if key not in checked:
            checked[key]=check_cfg(g,start,conservative)
        return checked[key]
    for c in configs(g):
        cc+=1
        for cons in (False,True):
            key=(c,cons)
            was_new=key not in checked
            n,d=verify(c,cons)
            states+=n;maxdepth=max(maxdepth,d)
            if was_new:
                unique_starts+=1;unique_states+=n
        for new_sources in product((0,1),repeat=g.source_count):
            for cons in (False,True):
                vals=list(c.vals); active=set(c.active)
                for source,next_value in enumerate(new_sources):
                    if cons or vals[source] != next_value:
                        vals[source]=next_value
                        active.update(u[source])
                updated=Cfg(tuple(vals),frozenset(active),frozenset())
                assert admissible(g,updated.vals,updated.active)
                key=(updated,cons)
                was_new=key not in checked
                n,d=verify(updated,cons)
                if was_new:
                    unique_starts+=1;unique_states+=n
                maxdepth=max(maxdepth,d)
                updates+=1
print(
    f"repair model check passed: {gc} graphs, {cc} admissible seeds, "
    f"{states} base-seed explored configurations, {updates} continued source updates, "
    f"{unique_starts} unique start/profile checks, {unique_states} unique explored configurations, "
    f"max selections {maxdepth}"
)
