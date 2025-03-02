#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass
from itertools import product, combinations

def xor(x):
 r=0
 for v in x:r^=v
 return r
def conj(x):return int(all(x))
F=(xor,conj)
@dataclass(frozen=True)
class D: ps:tuple[int,...]; fi:int
@dataclass(frozen=True)
class G:
 ds:tuple[D,...]
 @property
 def n(self):return 1+len(self.ds)
 def d(self,i):return self.ds[i-1]
 def users(self):
  u=[set() for _ in range(self.n)]
  for d in range(1,self.n):
   for p in self.d(d).ps:u[p].add(d)
  return tuple(tuple(x) for x in u)

def local(g,v,d):
 ins=tuple(v[p] for p in g.d(d).ps)
 return v[d] is not None and all(z is not None for z in ins) and v[d]==F[g.d(d).fi](ins)
def adm(g,v,a):return v[0] is not None and all(d in a or local(g,v,d) for d in range(1,g.n))
def front(g,a):
 out=[]
 for d in a:
  stack=list(g.d(d).ps);seen=set();blocked=False
  while stack:
   p=stack.pop()
   if p in seen:continue
   seen.add(p)
   if p>=1:
    if p in a:blocked=True;break
    stack+=list(g.d(p).ps)
  if not blocked:out.append(d)
 return tuple(sorted(out))
def subs(x):
 for k in range(1,len(x)+1):yield from combinations(x,k)
def oracle(g,v):
 o=[v[0]]
 for d in range(1,g.n):o.append(F[g.d(d).fi](tuple(o[p] for p in g.d(d).ps)))
 return tuple(o)
def check(g,v,a,cons):
 u=g.users();stack=[(v,frozenset(a),frozenset())];seen=set();fin=set()
 while stack:
  v,a,done=stack.pop();key=(v,a,done)
  if key in seen:continue
  seen.add(key)
  if not a:fin.add(v);continue
  fr=front(g,a);assert fr
  for sel in subs(fr):
   assert not any(d in done for d in sel)
   cand={d:F[g.d(d).fi](tuple(v[p] for p in g.d(d).ps)) for d in sel}
   nv=list(v);na=set(a)-set(sel)
   for d in sel:
    if cons or nv[d]!=cand[d]:nv[d]=cand[d];na.update(u[d])
   nv=tuple(nv);na=frozenset(na);assert adm(g,nv,na)
   stack.append((nv,na,done.union(sel)))
 assert fin=={oracle(g,v)}

# one source, two derived; premise sequences length 0..2 with repetition, respecting ID order
opts=[]
for d in (1,2):
 prev=tuple(range(d)); seqs=[()]
 for l in (1,2):seqs.extend(product(prev,repeat=l))
 opts.append(seqs)
gc=cc=0
for ps in product(*opts):
 for fs in product(range(2),repeat=2):
  g=G(tuple(D(ps[i],fs[i]) for i in range(2)));gc+=1
  for vals in product((0,1,None),repeat=3):
   if vals[0] is None:continue
   for mask in range(4):
    a=frozenset(1+i for i in range(2) if mask>>i&1)
    if adm(g,vals,a):
     cc+=1
     check(g,vals,a,False);check(g,vals,a,True)
print(f'duplicate-premise check passed: {gc} graphs, {cc} admissible configurations')
