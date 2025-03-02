#!/usr/bin/env python3
"""Enumerates small immutable graph-version authority-role transitions."""
from __future__ import annotations
from dataclasses import dataclass
from itertools import product
NAMES=('a','b','c')
def xor(xs):
 r=0
 for x in xs:r^=x
 return r
def conj(xs):return int(all(xs))
FUNCS=(xor,conj)
@dataclass(frozen=True)
class Node:
 source:bool
 initial:int|None=None
 premises:tuple[int,...]=()
 fi:int|None=None
@dataclass(frozen=True)
class Graph:
 nodes:tuple[Node,...]
 def eval(self,over=None):
  over=over or {};v=[]
  for i,n in enumerate(self.nodes):v.append(over.get(i,n.initial) if n.source else FUNCS[n.fi](tuple(v[p] for p in n.premises)))
  return tuple(v)
def graphs():
 opts=[]
 for i in range(3):
  o=[Node(True,0),Node(True,1)]
  if i:
   for m in range(1,1<<i):
    ps=tuple(j for j in range(i) if m>>j&1)
    for fi in range(2):o.append(Node(False,None,ps,fi))
  opts.append(o)
 for ns in product(*opts):yield Graph(tuple(ns))
def compat(old,i,new,j):
 o=old.nodes[i];n=new.nodes[j]
 return (not o.source and not n.source and o.fi==n.fi and tuple(NAMES[p] for p in o.premises)==tuple(NAMES[p] for p in n.premises))
def stabilize(g,vals,active):
 vals=list(vals);active=set(active)
 while active:
  ready=[d for d in sorted(active) if not any(p in active for p in g.nodes[d].premises if not g.nodes[p].source)]
  if not ready:raise AssertionError('no frontier')
  cand={d:FUNCS[g.nodes[d].fi](tuple(vals[p] for p in g.nodes[d].premises)) for d in ready}
  for d in ready:active.remove(d)
  for d in ready:
   if vals[d]!=cand[d]:
    vals[d]=cand[d]
    for u,n in enumerate(g.nodes):
     if not n.source and d in n.premises:active.add(u)
 return tuple(vals)
def commit(old,new,oldvals):
 seed=[None]*3;affected=[False]*3;active=set()
 for i,n in enumerate(new.nodes):
  o=old.nodes[i]
  if n.source:
   if o.source:seed[i]=oldvals[i]
   else:seed[i]=n.initial;affected[i]=True
   continue
  pa=any(affected[p] for p in n.premises);c=compat(old,i,new,i)
  if not o.source:seed[i]=oldvals[i]
  must=(not c) or pa;affected[i]=must
  if must:active.add(i)
 return stabilize(new,seed,active)
def check():
 gs=list(graphs());cases=0
 for old in gs:
  ids=[i for i,n in enumerate(old.nodes) if n.source]
  for bits in product((0,1),repeat=len(ids)):
   oldvals=old.eval(dict(zip(ids,bits)))
   for new in gs:
    cases+=1
    expected=new.eval({i:oldvals[i] for i,n in enumerate(new.nodes) if n.source and old.nodes[i].source})
    if commit(old,new,oldvals)!=expected:raise AssertionError('graph-version repair disagreed with from-scratch evaluation')
 print(f'graph-version model check passed: {len(gs)} graphs, {cases} commits including source/derived authority transitions')
if __name__=='__main__':check()
