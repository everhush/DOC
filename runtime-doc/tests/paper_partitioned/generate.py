from pathlib import Path
import json,sys
HERE=Path(__file__).resolve().parent
M=33554432
class Graph:
 def __init__(self,tag):self.tag=tag;self.nodes=[];self.helpers=[];self.sources=[];self.payroll=[];self.outputs=[]
 def src(self,name,kind,value):self.nodes.append(dict(name=name,kind=kind,role=1,expr=value,deps=[]));return name
 def der(self,name,kind,deps,expr):self.nodes.append(dict(name=name,kind=kind,role=2,expr=expr,deps=deps));return name
 def reduce(self,cur,list_kind=False):
  level=0
  while len(cur)>1:
   nxt=[]
   for i in range(0,len(cur),2):
    if i+1==len(cur):nxt.append(cur[i]);continue
    a,b=cur[i:i+2];va=f'get({a},0)' if list_kind and level==0 else a;vb=f'get({b},0)' if list_kind and level==0 else b;nxt.append(self.der(f'z{level}_{i//2}','int',[a,b],f'add({va},{vb})'))
   cur=nxt;level+=1
  self.outputs=cur
 def write(self,limit):
  p=HERE/self.tag;p.mkdir(exist_ok=True);mods=p/'modules';mods.mkdir(exist_ok=True);decl={x['name']:x for x in self.nodes};known=set();manifest=[]
  for i in range(0,len(self.nodes),limit):
   new=self.nodes[i:i+limit];nn={x['name'] for x in new};imports=sorted({d for x in new for d in x['deps'] if d not in nn},key=lambda x:decl[x]['id']);assert all(x in known for x in imports)
   lines=list(self.helpers)
   for n in imports:lines.append(f"source {n}:{decl[n]['kind']}="+('0' if decl[n]['kind']=='int' else '[]'))
   for x in new:
    n=x['name'];k=x['kind'];expr=x['expr'];deps=','.join(x['deps']);lines.append(f'source {n}:{k}={expr}' if x['role']==1 else f'derive {n}:{k}({deps})={expr}')
   file=f'{i//limit:04d}.doc';(mods/file).write_text('\n'.join(lines)+'\n');manifest.append(dict(file=file,imports=imports,exports=[x['name'] for x in new]));known|=nn
  (p/'manifest.json').write_text(json.dumps(dict(tag=self.tag,states=self.nodes,sources=self.sources,payroll=self.payroll,outputs=self.outputs,modules=manifest),indent=2)+'\n');print(self.tag,len(self.nodes),len(manifest),flush=True)
def graph(tag,limit=96,small=False):
 g=Graph(tag)
 if tag=='reduction' or tag=='dense':
  n=(64 if small else 2048 if tag=='reduction' else 4096);cur=[]
  if tag=='reduction':
   block=8;g.helpers=['fn candidate(s)=shift_right(s,25)','fn pcount(s)=bit_and(shift_right(s,10),32767)','fn divisor(s)=bit_and(s,1023)',f'fn c{block}(n,d)=add(d,{2*block})']
   for j in range(block-1,-1,-1):
    d='d' if j==0 else f'add(d,{2*j})';g.helpers.append(f'fn c{j}(n,d)=if(le({d},quot(n,{d})),if(eq(rem(n,{d}),0),33554435,c{j+1}(n,d)),33555459)')
   g.helpers+=['fn phase(s)=add(bit_and(s,-1024),if(eq(bit_and(candidate(s),1),0),33554435,c0(candidate(s),divisor(s))))']
  for i in range(n):
   s=g.src(f's{i}','int',str((100000+i)*M+3 if tag=='reduction' else i));g.sources.append(s)
   expr=f'recur({s},x,lt(x,33554432),if(eq(candidate(x),add(candidate({s}),1200)),pcount(x),phase(x)))' if tag=='reduction' else s
   cur.append(g.der(f'l{i}','int',[s],expr))
  g.reduce(cur)
 elif tag=='financial':
  n=32 if small else 4096;cur=[]
  g.helpers=['fn pack(m,r,c,t)=append(append(append(append(empty(),m),r),c),t)','fn nr(x)=add(get(x,1),add(quot(get(x,1),400),mul(sub(rem(get(x,0),12),6),3)))','fn nc(x)=add(get(x,2),add(quot(get(x,2),500),rem(get(x,0),5)))','fn advance(x)=if(eq(get(x,0),360),append(empty(),get(x,3)),pack(add(get(x,0),1),nr(x),nc(x),add(get(x,3),quot(sub(nr(x),nc(x)),add(100,quot(get(x,0),12))))))']
  for i in range(n):
   r=g.src(f'r{i}','ints',f'[{250000+(i*7919)%90000},0]');m=g.src(f'm{i}','int',str(70000+(i*3571)%30000));p=g.src(f'p{i}','int',str(60000+(i*1237)%25000));o=g.src(f'o{i}','int',str(20000+(i*331)%12000));g.sources.append(r);g.payroll.append(p)
   cur.append(g.der(f'l{i}','ints',[r,m,p,o],f'recur({r},x,eq(len(x),1),if(eq(len(x),2),pack(0,get(x,0),add(add({m},{p}),{o}),0),advance(x)))'))
  g.reduce(cur,True)
 elif tag=='sorting':
  n=32 if small else 512;seed=list(map(int,(HERE/'sort-seeds.txt').read_text().split()))[:n];cur=[]
  for i,v in enumerate(seed):cur.append(g.src(f's{i}','int',str(v)))
  g.sources=cur.copy();k=2;stage=0
  while k<=n:
   j=k//2
   while j:
    nxt=cur.copy()
    for i in range(n):
     p=i^j
     if p<=i:continue
     a,b=cur[i],cur[p];lo=g.der(f'a{stage}_{i}','int',[a,b],f'if(le({a},{b}),{a},{b})');hi=g.der(f'b{stage}_{i}','int',[a,b],f'if(le({a},{b}),{b},{a})');nxt[i],nxt[p]=(lo,hi) if i&k==0 else (hi,lo)
    cur=nxt;stage+=1;j//=2
   k*=2
  g.outputs=cur
 else:raise ValueError(tag)
 for i,x in enumerate(g.nodes):x['id']=i
 if small:g.tag+='-small'
 g.write(limit)
if __name__=='__main__':
 for tag in sys.argv[1:]:graph(tag.removesuffix('-small'),small=tag.endswith('-small'))
