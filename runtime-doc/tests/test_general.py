import argparse, subprocess, pathlib, ast, re, os
p=pathlib.Path(__file__).resolve().parent
def invoke(command, src, workers):
    return subprocess.run(command+['--demand=types','input=['+','.join(map(str,src.encode()))+']'],capture_output=True,text=True,timeout=90,env=dict(os.environ,DOC_WORKERS=str(workers)))
positive=[('source a: int = -9223372036854775808',[0]),('source a: bool = true',[1]),('source a: nat = 123456789012345678901234567890',[2]),('source a: ints = [1,2,-3]\nsource b: maybe_int = some(-3)\nsource c: text = "héllo"',[3,4,5]),('source x: maybe_int = none',[4]),('fn twice(x)=add(x,x)\nsource a:int=2\nderive b:int(a)=twice(a)',[-1,0,0]),('fn twice(x)=add(x,x)\nsource a:nat=2\nderive b:nat(a)=twice(a)',[-1,2,2]),('fn same(x,y)=eq(x,y)\nsource a:text="hi"\nderive b:bool(a)=same(a,text("hi"))',[-1,5,1]),('fn plus(x,y)=add(x,y)\nfn double(x)=plus(x,x)\nsource a:int=2\nderive b:int(a)=double(a)',[-1,-1,0,0]),('source x:ints=[1,2]\nderive y:ints(x)=map_ints(x,v,add(v,1))',[3,3]),('source x:int=0\nderive y:int(x)=recur(x,v,eq(v,5),add(v,1))',[0,0]),('source x:ints=[]\nderive y:ints(x)=recur(x,v,eq(len(v),3),append(v,1))',[3,3]),('source x:text="hello"\nderive y:ints(x)=utf8_bytes(x)\nderive z:text(y)=utf8_text(y)',[5,3,5]),('derive a:nat()=nat(99999999999999999999999999999999)',[2]),('derive a:maybe_int()=try_get(empty(),0)',[4]),('derive a:int()=unwrap_or(none(),3)',[0]),('derive a:bool()=starts_with(text("foo"),text("f"))',[1]),('derive a:ints()=replace_at(append(empty(),1),0,2)',[3]),('derive a:int()=shift_left(bit_and(2,3),1)',[0]),('fn zero()=0\nderive x:int()=zero()',[-1,0]),('',[])]
negative=['source a:int=9223372036854775808','source a:nat=-1','source a:bool=1','source a:int=true','source a:ints=1','source a:maybe_int=some(true)','source a:text=123','source a:int=1\nsource a:int=2','source a:int=1\nderive b:int()=a','derive a:int(a)=a','fn f(x)=f(x)','fn f(x)=unknown(x)','fn f(x)=add(x)','fn f(x,x)=x','fn f(x)=x\nderive a:int()=f()','fn f(x)=x\nderive a:bool()=f(1)','derive a:int()=add(1,true)','derive a:bool()=eq(1,nat(1))','derive a:int()=if(1,2,3)','derive a:int()=if(true,1,false)','derive a:int()=nat(-1)','derive a:text()="x"','source a:ints=[1]\nderive b:ints(a)=map_ints(a,a,a)','source a:ints=[1]\nderive b:ints(a)=map_ints(a,x,true)','source a:int=1\nderive b:int(a)=recur(a,x,1,2)','source a:int=1\nderive b:int(a)=add(recur(a,x,true,2),1)','source a:int=1\nderive b:int(a,a)=a','source a:int=1\nfn f(x)=a','fn f(x)=x\nderive a:int(f)=f']
def expected_types(src):
    kinds = dict(int=0, bool=1, nat=2, ints=3, maybe_int=4, text=5)
    out=[]
    for line in src.splitlines():
        if line.startswith('fn '): out.append(-1)
        elif line.startswith(('source ', 'derive ')):
            match=re.match(r'(?:source|derive)\s+\w+\s*:\s*(\w+)',line)
            assert match, line
            out.append(kinds[match.group(1)])
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--reference',required=True); ap.add_argument('--source',required=True); ap.add_argument('--native',required=True); a=ap.parse_args()
    root=pathlib.Path(a.source).resolve().parent.parent
    specs=[('lexer',['compiler/lexer_core.doc','compiler/lexer.doc']),('parser',['compiler/lexer_core.doc','compiler/parser_core.doc','compiler/parser.doc']),('repair',['runtime/repair_core.doc','runtime/repair_plan.doc']),('scalar',['compiler/lexer_core.doc','compiler/parser_core.doc','compiler/common_core.doc','compiler/scalar_core.doc','compiler/scalar.doc'])]
    fixtures=[]
    for name,parts in specs:
        src='\n'.join('\n'.join(l for l in (root/f).read_text().splitlines() if not l.startswith('import ')) for f in parts)
        fixtures.append((src,expected_types(src)))
    for command in [[a.reference,a.source],[a.native]]:
        for workers in (1,4):
            for src,expected in positive+fixtures:
                r=invoke(command,src,workers)
                assert r.returncode==0,(src[:100],r.stderr)
                assert ast.literal_eval(r.stdout.strip().split(': ',1)[1])==expected,(src[:100],r.stdout,expected)
            for src in negative:
                r=invoke(command,src,workers)
                assert r.returncode!=0 and not r.stdout.strip(),(src,r.stdout,r.stderr)
    print(f'DOC11_GENERAL_PASS: {len(positive)} positive, {len(negative)} negative, {len(fixtures)} bundled compiler/runtime sources; two execution paths, workers=1/4')
if __name__=='__main__': main()
