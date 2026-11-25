#!/usr/bin/env python3
"""Independent recursive-descent oracle for the DOC bootstrap syntax stage."""
import argparse
import ast
import os
import subprocess
import tempfile
from pathlib import Path
from test_lexer import oracle as lex


def oracle(data):
    raw = lex(data)
    ts = list(zip(raw[::3], raw[1::3], raw[2::3])) + [(10,len(data),0)]
    out = []
    pos = 0
    def kind():
        return ts[pos][0] if pos < len(ts) else 0
    def word():
        _,off,n = ts[pos]
        return data[off:off+n]
    def eat(k, tag, aux=0):
        nonlocal pos
        if kind() != k: raise ValueError((pos,k,kind()))
        out.extend((tag,pos,aux))
        pos += 1
    def expr(role, depth=0):
        c = kind()
        if c in (43,45):
            eat(c,11,c); eat(2,10,2)
        elif c == 91 and role == 1 and depth == 0:
            eat(91,17)
            if kind() != 93:
                while True:
                    c = kind()
                    if c in (43,45): eat(c,11,c)
                    eat(2,10,2)
                    if kind() != 44: break
                    eat(44,9)
            eat(93,18)
        elif c == 1 and pos+1<len(ts) and ts[pos+1][0] == 40:
            eat(1,13); eat(40,14)
            if kind()!=41:
                while True:
                    expr(role,depth+1)
                    if kind()!=44: break
                    eat(44,9)
            eat(41,15)
        elif c in (1,2,3): eat(c,10,c)
        else: raise ValueError((pos,'expression',c))
    while pos < len(ts):
        if kind() == 10:
            pos += 1; continue
        if kind()!=1: raise ValueError('declaration keyword')
        role = {b'source':1,b'derive':2,b'fn':3,b'import':4,b'effect':5}.get(word())
        if role is None: raise ValueError('declaration keyword')
        eat(1,1,role)
        if role == 4:
            if kind() not in (1,2,45,46,47): raise ValueError('missing path')
            while kind() in (1,2,45,46,47):
                c = kind(); eat(c,19,c)
        else:
            eat(1,2)
            if role!=3: eat(58,3); eat(1,4)
            if role not in (1,5):
                eat(40,5)
                if kind()!=41:
                    while True:
                        eat(1,6)
                        if kind()!=44: break
                        eat(44,9)
                eat(41,8)
            eat(61,7)
            expr(role)
        eat(10,16)
    return out


def run(command,data,expected,cwd,workers):
    result=subprocess.run([*command,'--demand=syntax','input=['+','.join(map(str,data))+']'],cwd=cwd,env={**os.environ,'DOC_WORKERS':str(workers)},capture_output=True,text=True,timeout=60)
    if expected is None:
        assert result.returncode and 'syntax:' not in result.stdout, (data,result.stdout,result.stderr)
    else:
        assert not result.returncode,(data[:100],result.stderr)
        rows=[line.partition(': ')[2] for line in result.stdout.splitlines() if line.startswith('syntax: ')]
        assert len(rows)==1 and ast.literal_eval(rows[0])==expected,(data[:100],rows[:1],expected[:100])


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--reference',type=Path,required=True); ap.add_argument('--source',type=Path,required=True); ap.add_argument('--native',type=Path); ap.add_argument('--fixtures',type=Path,nargs='*',default=[]); args=ap.parse_args()
    commands=[[str(args.reference.resolve()),str(args.source.resolve())]]
    if args.native: commands.append([str(args.native.resolve())])
    valid=[b'',b'\n#empty',b'source a: int = 2\nderive b: int (a) = add(a,1)\n',b'fn z() = empty()\n',b'fn f(a,b) = if(eq(a,b),-1,2)',b'source xs: ints = [1,-2,+3]\n',b'source xs: ints = []',b'import a/b.doc\n',b'effect a:ints=read("data.txt")', 'source name: text = "你好"\n'.encode(),b'derive b: int () = add(1,2)\n',b'fn g(a) = g(g(),g(a))',b'source a: nat = 123456789012345678901234567890',b'source m: maybe_int = some(-42)',b'source a: bool = false\r\nsource b: bool = true',b'fn f(a) = text("a b")']
    valid += [p.read_bytes() for p in args.fixtures]
    invalid=[b'derive b: int () = add(1,)\n',b'derive b: int () = add(1,2\n',b'source x: int =\n',b'fn f(a,) = a',b'source xs: ints = [1,]\n',b'fn f() = a b',b'source x: int = -',b'fn f(a = a',b'fn f(a) = a)',b'source x int = 2',b'import\n',b'unknown x',b'fn f() = (1)',b'source xs: ints = [1 2]',b'fn f() = add(,1)',b'fn f() = add(1\n,2)',b'source x: text = "unterminated']
    with tempfile.TemporaryDirectory(prefix='doc11-parser-') as cwd:
        for cmd in commands:
            for data in valid:
                expect=oracle(data)
                for workers in (1,4): run(cmd,data,expect,cwd,workers)
            for data in invalid:
                try: oracle(data)
                except ValueError: pass
                else: raise AssertionError(('invalid oracle accepted',data))
                run(cmd,data,None,cwd,1)
    print(f'DOC11_PARSER_PASS: {len(valid)} positive, {len(invalid)} negative, {len(commands)} execution paths, workers=1/4')

if __name__=='__main__': main()
