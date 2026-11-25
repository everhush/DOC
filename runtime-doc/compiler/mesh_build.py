"""Native DOC mesh-stage transport and cross-stage ABI verification.

The native compiler owns name resolution, types, interval proof and WGSL.
This adapter maps explicit scene-interface bindings to emitted declaration IDs,
checks the two stages' compatible domains and validates actual upload buffers.
"""
from dataclasses import dataclass
import ast
import subprocess


@dataclass(frozen=True)
class MeshPlan:
    wgsl: bytes
    vertex: tuple
    draw: tuple
    varying: tuple
    colors: tuple

    def validate(self, vertices, draws, indices):
        if not 0<len(vertices)<=65536 or not 0<len(indices)<=196608 or len(indices)%3 or not 0<len(draws)<=128:
            raise ValueError('mesh capacity')
        if any(type(i) is not int or not 0<=i<len(vertices) for i in indices):
            raise ValueError('mesh index')
        for rows,domains in ((vertices,self.vertex),(draws,self.draw)):
            for row in rows:
                if len(row)!=len(domains) or any(type(x) is not int or not -2147483648<=x<=2147483647 for x in row):
                    raise ValueError('mesh scalar ABI')
                if any(d is not None and not d[0]<=v<=d[1] for v,d in zip(row,domains)):
                    raise ValueError('mesh input outside proven domain')


def invoke(tool, source, demand, *args):
    if len(source)>65536:raise ValueError('stage source capacity')
    cmd=[str(tool),'--input-stdin','--demand='+demand,*args]
    r=subprocess.run(cmd,input=source,capture_output=True,timeout=120)
    prefix=(demand+': ').encode()
    if r.returncode or not r.stdout.startswith(prefix) or not r.stdout.endswith(b'\n'):
        raise ValueError('DOC mesh stage rejected: '+r.stderr.decode(errors='replace')[-1000:])
    return r.stdout[len(prefix):-1]


def stage(tool, source, kind, binding_spec, output_spec, vary=None):
    symbols=invoke(tool,source,'symbols').decode('ascii').splitlines()
    if not 0<len(symbols)<=512 or len(symbols)!=len(set(symbols)):
        raise ValueError('mesh declaration directory')
    directory={name:i for i,name in enumerate(symbols)}
    vector=[0]*(4*len(symbols));domains={1:[None]*12,2:[None]*8,3:[None]*3};used=set()
    for record in binding_spec.split(',') if binding_spec else ():
        name,domain,raw_slot,raw_lo,raw_hi=record.split(':')
        k={'vertex':1,'draw':2,'varying':3}.get(domain)
        slot,lo,hi=map(int,(raw_slot,raw_lo,raw_hi))
        if name not in directory or name in used or k not in domains or not 0<=slot<len(domains[k]) or not -2147483648<=lo<=hi<=2147483647:
            raise ValueError('mesh binding')
        if domains[k][slot] is not None:raise ValueError('duplicate mesh slot')
        if k==3:
            if vary is None or not lo<=vary[slot][0]<=vary[slot][1]<=hi:raise ValueError('unproved varying domain')
            lo,hi=vary[slot]
        used.add(name);domains[k][slot]=(lo,hi);i=directory[name]*4;vector[i:i+4]=[k,slot,lo,hi]
    ids=[directory[n] for n in output_spec.split(',')]
    args=('stage='+str(kind),'bindings='+str(vector).replace(' ',''),'outputs='+str(ids).replace(' ',''))
    raw=ast.literal_eval(invoke(tool,source,'output_ranges',*args).decode('ascii'))
    if type(raw) is not list or len(raw)!=2*len(ids) or any(type(v) is not int for v in raw):raise ValueError('invalid compiler range record')
    ranges=tuple(zip(raw[::2],raw[1::2]))
    shader=invoke(tool,source,'shader',*args)
    if not shader or len(shader)>65536:raise ValueError('invalid compiler shader')
    return shader,ranges,domains


def compile_mesh(tool, vertex, fragment, vertex_bindings, fragment_bindings, clip, varying, color):
    v,vr,vd=stage(tool,vertex,0,vertex_bindings,clip+','+varying)
    f,fr,fd=stage(tool,fragment,1,fragment_bindings,color,vr[4:])
    draw=[]
    for a,b in zip(vd[2],fd[2]):
        if a is not None and b is not None and a!=b:raise ValueError('conflicting draw domains')
        draw.append(a if a is not None else b)
    return MeshPlan(v+f,tuple(vd[1]),tuple(draw),vr[4:],fr)
