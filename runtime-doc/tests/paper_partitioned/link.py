#!/usr/bin/env python3
"""Bounded test-only relocation of actual DOC-emitted pure DAG state descriptors.
No source expressions are interpreted or synthesized by this linker. Only
compiler-generated code bodies, typed symbols and dependency indices are used.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import subprocess,re,json,hashlib,sys,time
HERE=Path(__file__).resolve().parent
COMP=HERE.parent/'games/reactive2'
HEADER=HERE.parent/'paper-scale/tuned'
# Exact compiler-emitted C grammar for this admitted scalar/list fixed graph profile.
IDENT=r'[A-Za-z_][A-Za-z0-9_]*'; NUM=r'0x[0-9a-f]+LL'
ROW=re.compile(r'\{"('+IDENT+r')",('+NUM+r'),('+NUM+r'),&S_('+IDENT+r'),E_('+IDENT+r'),\(const size_t\[\]\)\{0((?:,'+NUM+r')*)\}\+1,('+NUM+r')\},')
FUNC=re.compile(r'static V E_('+IDENT+r')\(void\)\{return (.*);\}')
SLOT=re.compile(r'static V S_('+IDENT+r');')
MACRO=re.compile(r'#define (F_'+IDENT+r')\(.*')
def number(x):return int(x[:-2],16)
def sha(data):return hashlib.sha256(data).hexdigest()
def emit(p):
 data=p.read_bytes();out=p.with_suffix('.c')
 if out.exists():return out.read_text()
 def invoke(target,*extra):
  q=subprocess.run([COMP,'--demand='+target,'--input-stdin',*extra],input=data,capture_output=True,timeout=180);prefix=(target+': ').encode()
  if q.returncode or not q.stdout.startswith(prefix) or not q.stdout.endswith(b'\n'):raise ValueError((p.name,target,q.stderr.decode(errors='replace')))
  return q.stdout[len(prefix):-1]
 try:code=invoke('code')
 except ValueError:
  n=int(invoke('chunk_count'));assert 1<=n<=128;code=b''.join(invoke('code',f'chunk={i}') for i in range(n))
 out.write_bytes(code);return code.decode()
def parse(code):
 assert code.startswith('#include "reactive_values.h"\n')
 before,rest=code.split('static const State states[]={\n',1);table,tail=rest.split('};static void doc_mark(',1)
 macros={};slots=set();funcs={}
 for line in before.splitlines()[1:]:
  if not line:continue
  m=MACRO.fullmatch(line)
  if m:assert m[1] not in macros;assert not re.search(r'\bS_',line);macros[m[1]]=line;continue
  m=SLOT.fullmatch(line)
  if m:assert m[1] not in slots;slots.add(m[1]);continue
  m=FUNC.fullmatch(line)
  if m:assert m[1] not in funcs;assert not re.search(r'\b(?:doc_asset|doc_effect|doc_map_family|E_|L_)',m[2]);funcs[m[1]]=m[2];continue
  raise ValueError('unsupported compiler output '+line[:100])
 rows=[]
 for line in table.splitlines():
  if not line:continue
  if line=='{0},':rows.append(None);continue
  m=ROW.fullmatch(line);assert m,line
  n,k,role,s,e,deps,nd=m.groups();assert n==s==e and n in slots and n in funcs
  d=[number(x) for x in deps.split(',') if x];assert len(d)==number(nd) and all(i<len(rows) and rows[i] is not None for i in d)
  rows.append(dict(name=n,kind=number(k),role=number(role),deps=[rows[i]['name'] for i in d],body=funcs[n]))
 assert {r['name'] for r in rows if r}==slots==set(funcs)
 # Independently check that each compiler-emitted policy's actual edge/ready
 # membership equals the descriptor table before relocation.
 expected_edges=[(d,i) for i,r in enumerate(rows) if r and r['role']==2 for d in [next(j for j,x in enumerate(rows) if x and x['name']==n) for n in r['deps']]]
 mark=[(int(a,16),int(b,16)) for a,b in re.findall(r'if\(id==(0x[0-9a-f]+)\)dirty\[(0x[0-9a-f]+)\]=1;',tail)]
 demand=[(int(b,16),int(a,16)) for a,b in re.findall(r'if\(need\[(0x[0-9a-f]+)\]\)need\[(0x[0-9a-f]+)\]=1;',tail)]
 block=[(int(a,16),int(c,16)) for a,b,c in re.findall(r'if\(dirty\[(0x[0-9a-f]+)\]\|\|blocked\[(0x[0-9a-f]+)\]\)blocked\[(0x[0-9a-f]+)\]=1;',tail) if a==b]
 selected=[int(a,16) for a,b,c,d in re.findall(r'if\(dirty\[(0x[0-9a-f]+)\]&&need\[(0x[0-9a-f]+)\]&&!blocked\[(0x[0-9a-f]+)\]\)queue\[count\+\+\]=(0x[0-9a-f]+);',tail) if a==b==c==d]
 assert sorted(mark)==sorted(demand)==sorted(block)==sorted(expected_edges),(mark[:2],demand[:2],block[:2],expected_edges[:2]);assert selected==[i for i,r in enumerate(rows) if r and r['role']==2]
 return macros,[r for r in rows if r]
def link(p):
 manifest=json.loads((p/'manifest.json').read_text());expect={x['name']:x for x in manifest['states']};macros={};nodes=[];known={};build=[];templates={}
 for m in manifest['modules']:
  src=p/'modules'/m['file'];code=src.with_suffix('.c').read_text();ma,rows=parse(code)
  for k,v in ma.items():assert k not in macros or macros[k]==v;macros[k]=v
  imports=set(m['imports']);exports=m['exports'];assert len(set(exports))==len(exports) and not imports.intersection(exports);assert [r['name'] for r in rows if r['name'] not in imports]==exports
  assert {r['name'] for r in rows if r['name'] in imports}==imports
  for r in rows:
   n=r['name'];kind=r['kind'];role=r['role'];assert kind in (0,3)
   if n in imports:assert n in known and role==1 and not r['deps'] and known[n]['kind']==kind;continue
   assert n not in known and n in expect and role in (1,2)
   ex=expect[n];assert role==ex['role'] and kind=={'int':0,'ints':3}[ex['kind']] and r['deps']==ex['deps'] and all(d in known for d in r['deps'])
   r['id']=len(nodes);nodes.append(r);known[n]=r
   # Parameterize only compiler-emitted reads of admitted premise slots.
   # All values are immutable V borrows until private candidate evaluation ends.
   deps=list(dict.fromkeys(r['deps']));index={x:f'A_{i}' for i,x in enumerate(deps)}
   def subst(match):assert match[1] in index,(n,match[1],deps);return index[match[1]]
   body=re.sub(r'\bS_('+IDENT+r')\b',subst,r['body']);assert not re.search(r'\bS_',body)
   key=(len(deps),body);fn='G_'+sha((str(key[0])+':'+body).encode())[:24];assert key not in templates or templates[key]==fn;templates[key]=fn;r['template']=fn;r['args']=deps
  build.append(dict(file=m['file'],source_sha256=sha(src.read_bytes()),c_sha256=sha(code.encode()),states=len(rows),imports=len(imports),exports=len(exports)))
 assert len(nodes)==len(expect)==len(known)
 assert len(set(templates.values()))==len(templates)
 text=['#include "reactive_values.h"',*macros.values()]
 text.extend(f'static V S_{r["name"]};' for r in nodes)
 for (n,body),fn in templates.items():text.append(f'static __attribute__((noinline)) V {fn}('+(','.join(f'V A_{i}' for i in range(n)) or 'void')+'){return '+body+';}')
 for r in nodes:text.append(f'static V E_{r["name"]}(void){{return {r["template"]}('+','.join('S_'+n for n in r['args'])+');}')
 text.append('static const State states[]={')
 for r in nodes:
  n=r['name'];ds=[str(known[d]['id']) for d in r['deps']];text.append(f'{{"{n}",{r["kind"]},{r["role"]},&S_{n},E_{n},(const size_t[]){{0'+(''+','+','.join(ds) if ds else '')+f'}}+1,{len(ds)}}},')
 text.append('};')
 users=[[] for _ in nodes]
 for i,r in enumerate(nodes):
  for d in r['deps']:users[known[d]['id']].append(i)
 offsets=[0];flat=[]
 for u in users:flat.extend(u);offsets.append(len(flat))
 def arr(name,values):return 'static const size_t '+name+'[]={'+','.join(map(str,values or [0]))+'};'
 text.extend([arr('user_offsets',offsets),arr('user_ids',flat),arr('sources',[known[n]['id'] for n in manifest['sources']]),arr('payroll',[known[n]['id'] for n in manifest['payroll']]),arr('outputs',[known[n]['id'] for n in manifest['outputs']])])
 text.extend(['static const size_t ns=sizeof(states)/sizeof(states[0]);','static void doc_mark(size_t id,unsigned char *dirty){for(size_t i=user_offsets[id];i<user_offsets[id+1];i++)dirty[user_ids[i]]=1;}','static void doc_demand(unsigned char *need){for(size_t i=ns;i-->0;)if(need[i])for(size_t j=0;j<states[i].ndeps;j++)need[states[i].deps[j]]=1;}','static void doc_block(const unsigned char *dirty,unsigned char *blocked){for(size_t i=0;i<ns;i++)for(size_t j=0;j<states[i].ndeps;j++){size_t p=states[i].deps[j];if(dirty[p]||blocked[p]){blocked[i]=1;break;}}}','static size_t doc_select(const unsigned char *dirty,const unsigned char *need,const unsigned char *blocked,size_t *queue){size_t n=0;for(size_t i=0;i<ns;i++)if(states[i].role==2&&dirty[i]&&need[i]&&!blocked[i])queue[n++]=i;return n;}'])
 text.append('#include "bench_host.h"');out=p/'linked.c';out.write_text('\n'.join(text)+'\n')
 (p/'link.json').write_text(json.dumps(dict(states=len(nodes),derived=sum(r['role']==2 for r in nodes),edges=len(flat),templates=len(templates),modules=build,linked_c_sha256=sha(out.read_bytes())),indent=2)+'\n');print('LINK',p.name,len(nodes),'states',len(templates),'templates',len(build),'modules',flush=True)
def build(p):
 manifest=json.loads((p/'manifest.json').read_text());paths=[p/'modules'/m['file'] for m in manifest['modules']]
 with ThreadPoolExecutor(max_workers=4) as pool:
  for i,_ in enumerate(pool.map(emit,paths)):
   if (i+1)%10==0 or i+1==len(paths):print('EMIT',p.name,i+1,'/',len(paths),flush=True)
 link(p)
if __name__=='__main__':
 for tag in sys.argv[1:]:build(HERE/tag)
