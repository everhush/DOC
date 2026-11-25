#!/usr/bin/env python3
"""Build normal source files with confined pure modules through native DOC stages."""
import argparse, os, subprocess, tempfile, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'compiler'))
from doc_build import build, bundle


def main():
    p=argparse.ArgumentParser();p.add_argument('--reference',required=True,type=Path);p.add_argument('--scanner-source',type=Path);p.add_argument('--compiler-source',type=Path);p.add_argument('--scanner',type=Path);p.add_argument('--compiler',type=Path);p.add_argument('--headers',type=Path,default=Path(__file__).resolve().parent.parent/'runtime');a=p.parse_args()
    ref=a.reference.resolve()
    if a.scanner:scanner=[a.scanner.resolve()];compiler=[a.compiler.resolve()]
    else:scanner=[ref,a.scanner_source.resolve()];compiler=[ref,a.compiler_source.resolve()]
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);sub=d/'lib';sub.mkdir();(sub/'math.doc').write_text('# helper\nfn twice(x) = add(x,x) # comment\n');(d/'label.doc').write_text('fn label(x) = concat(text("result: "),x)\n')
        source=d/'program.doc';source.write_text('# main\nimport lib/math.doc # ok\nsource n:int=5\nderive two:int(n)=twice(n)\nimport label.doc\nsource t:text="héllo"\nderive final:text(t)=label(t)\n');exe=d/'output';code=build(scanner,compiler,source,exe,a.headers);assert b'F_twice' in code and b'F_label' in code
        for args in ([],['n=19'],['--demand=final','t="世界"']):
            expected=subprocess.check_output([ref,source,*args]);got=subprocess.check_output([exe,*args]);assert got==expected,(got,expected)
        saved=exe.read_bytes();(d/'bad.doc').write_text('source hidden:int=1\n');(d/'nested.doc').write_text('import lib/math.doc\n');(d/'link.doc').symlink_to(sub/'math.doc');(d/'linkdir').symlink_to(sub,target_is_directory=True);os.mkfifo(d/'fifo.doc')
        invalid=['import ../outside.doc','import /tmp/foo.doc','import lib//math.doc','import lib/./math.doc','import lib/../label.doc','import link.doc','import linkdir/math.doc','import fifo.doc','import bad.doc','import nested.doc','import missing.doc','import lib/math.doc\nimport lib/math.doc','import lib/ math.doc','import lib/math.txt']
        for line in invalid:
            source.write_text(line+'\nsource n:int=1\n')
            try:build(scanner,compiler,source,exe,a.headers)
            except (ValueError,OSError,subprocess.SubprocessError):pass
            else:raise AssertionError('accepted invalid import: '+line)
            assert exe.read_bytes()==saved,'failed build replaced prior native artifact'
        source.unlink();(sub/'math.doc').unlink();(d/'label.doc').unlink();assert subprocess.check_output([exe,'n=7'])==b'n: 7\ntwo: 14\nt: h\xc3\xa9llo\nfinal: result: h\xc3\xa9llo\n'
    print(f'DOC11_MODULE_BUILD_PASS: 3 reference comparisons, {len(invalid)} invalid imports, atomic artifact preservation, source-free ELF')
if __name__=='__main__':main()
