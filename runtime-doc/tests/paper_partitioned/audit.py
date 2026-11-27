#!/usr/bin/env python3
"""Independently recheck emitted descriptors, source hashes, graph counts and policy order."""
import hashlib,json,pathlib,re
from link import parse
H=pathlib.Path(__file__).resolve().parent
expected={'reduction':(6143,4095,64),'dense':(12287,8191,128),'financial':(24575,8191,256),'sorting':(23552,23040,246)}
results={}
for tag,(states,derived,modules) in expected.items():
 d=H/tag;j=json.loads((d/'link.json').read_text());assert (j['states'],j['derived'],len(j['modules']))==(states,derived,modules);assert hashlib.sha256((d/'linked.c').read_bytes()).hexdigest()==j['linked_c_sha256']
 for m in j['modules']:
  p=d/'modules'/m['file'];c=p.with_suffix('.c');assert hashlib.sha256(p.read_bytes()).hexdigest()==m['source_sha256'] and hashlib.sha256(c.read_bytes()).hexdigest()==m['c_sha256'];s=c.read_text();ma,rows=parse(s);assert len(rows)==m['states']
  demands=[int(a,16) for a,b in re.findall(r'if\(need\[(0x[0-9a-f]+)\]\)need\[(0x[0-9a-f]+)\]=1;',s)];blocks=[int(c,16) for a,b,c in re.findall(r'if\(dirty\[(0x[0-9a-f]+)\]\|\|blocked\[(0x[0-9a-f]+)\]\)blocked\[(0x[0-9a-f]+)\]=1;',s)];assert demands==sorted(demands,reverse=True) and blocks==sorted(blocks)
 results[tag]=dict(states=states,derived=derived,modules=modules,templates=j['templates'],edges=j['edges'],linked_c_sha256=j['linked_c_sha256'])
s=(H/'reduction/modules/0000.c').read_text();mods=[s.replace('static V S_s0;','static V S_s0;\nstatic V S_s0;',1),s.replace('if(id==','if(id!=',1),s.replace('static V E_s0(void){return ','static V E_s0(void){return doc_effect(',1),s.replace('"s0",','"wrong_name",',1)]
for i,m in enumerate(mods):
 assert m!=s,(i,'fixture not changed')
 try:parse(m)
 except (AssertionError,ValueError):pass
 else:raise AssertionError(i)
(H/'audit.json').write_text(json.dumps(dict(scope='restricted test-only relocation, no production linker claim',profiles=results,module_total=sum(x[2] for x in expected.values()),negative_descriptor_policy_cases=len(mods)),indent=2)+'\n');print('PARTITION_AUDIT_PASS',sum(x[2] for x in expected.values()),'modules;',len(mods),'negative cases')
