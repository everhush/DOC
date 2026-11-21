#!/usr/bin/env python3
"""Native DOC UTF-8 source, recurrence and emitted byte equivalence."""
import random,subprocess,sys,tempfile
from pathlib import Path
rust,goose,logs=sys.argv[1:]
fixed="runtime-rust/examples/text_program.doc"
root=Path(logs)
root.mkdir(parents=True,exist_ok=True)
characters=["a","B"," ","ñ","世界","🙂","ह","💻","ê","0"]
rng=random.Random(1133)
cases=0
def run(binary,program,*args,success=True):
    p=subprocess.run([binary,str(program),*args],capture_output=True,
                     text=True,encoding="utf-8",timeout=30)
    if success and p.returncode:
        raise AssertionError(f"{binary} text execution failed: {p.stderr}\n{p.stdout}")
    if not success and p.returncode==0:
        raise AssertionError(f"{binary} accepted bad DOC text source")
    return p
def expected(name,prefix):
    value=prefix+name
    return {"joined":value,"byte_count":str(len(value.encode("utf-8"))),
            "is_greeting":str(value.startswith("Hello")).lower(),
            "is_cjk":str(name=="世界").lower(),
            "selected":value if value.startswith("Hello") else "no"}
sources=[("世界","Hello, "),("🙂","Hi "),("",""),("漢字","Hello")]
sources.extend(("".join(rng.choice(characters) for _ in range(rng.randrange(0,20))),
                "".join(rng.choice(characters) for _ in range(rng.randrange(0,12))))
               for _ in range(125))
with tempfile.TemporaryDirectory(prefix="doc_utf8_") as td:
    temp=Path(td)
    for n,(name,prefix) in enumerate(sources):
        file=temp/f"text_{n}.doc"
        raw=Path(fixed).read_text().replace('source name: text = "世界"',
            f'source name: text = "{name}"').replace(
            'source prefix: text = "Hello, "',f'source prefix: text = "{prefix}"')
        file.write_text(raw,encoding="utf-8")
        correct=expected(name,prefix)
        for binary in (rust,goose):
            p=run(binary,file)
            vals={}
            for line in p.stdout.splitlines():
                if ": " not in line:continue
                field,v=line.split(": ",1)
                if field in correct:vals[field]=v
            if vals!=correct:
                raise AssertionError(f"UTF-8 output mismatch {binary}: {vals} != {correct}")
            # The DOC output effect must preserve the exact UTF-8 bytes.
            out=f"emitted_{n}.txt"
            emitted=run(binary,file,f"--emit=joined:{out}")
            if (temp/out).read_bytes()!=(prefix+name+"\n").encode("utf-8"):
                raise AssertionError(f"{binary} DOC byte emission mismatch")
            cases+=2

    # Long UTF-8 values and explicitly admitted file effects are bounded by
    # real host resources, not the old artificial 8/16KiB DOC limits.
    large="世界🙂"*2500
    large_doc=temp/"large-text.doc"
    large_doc.write_text(
        f'source payload: text = "{large}"\n'
        'derive expanded: text (payload) = concat(payload,text("!"))\n'
        'derive bytes: int (expanded) = len(expanded)\n',
        encoding="utf-8")
    large_file=temp/"large-text-input.txt"
    large_file.write_text(large,encoding="utf-8")
    effect_doc=temp/"large-text-effect.doc"
    effect_doc.write_text(
        'effect payload: text = read("large-text-input.txt")\n'
        'derive expanded: text (payload) = concat(payload,text("!"))\n'
        'derive bytes: int (expanded) = len(expanded)\n',
        encoding="utf-8")
    for document in (large_doc,effect_doc):
        for binary in (rust,goose):
            stdout=run(binary,document).stdout
            rows={}
            for line in stdout.splitlines():
                if line.startswith(("payload: ","expanded: ","bytes: ")):
                    name,value=line.split(": ",1)
                    rows[name]=value
            if rows!={"payload":large,"expanded":large+"!",
                      "bytes":str(len((large+"!").encode("utf-8")))}:
                raise AssertionError(f"{binary} large UTF-8 DOC mismatch")
            cases+=1
    rec="runtime-rust/examples/text_recurrence.doc"
    for epochs in (0,1,2,3,20,60):
        for binary in (rust,goose):
            p=run(binary,rec,f"--through={epochs}","text_value=next")
            if f"epoch: {epochs}\ntext_value: {'🙂'*(epochs+1)}\n" not in p.stdout:
                raise AssertionError(f"{binary} UTF-8 recurrence mismatch {epochs}")
            cases+=1
    for invalid in [
        'source a: text = "unterminated\n',
        'source a: text = "x\\\\y"\n',
        'source a: int = 1\nderive bad: text (a) = concat(a,text("yes"))\n'
    ]:
        f=temp/"invalid.doc";f.write_text(invalid,encoding="utf-8")
        for binary in (rust,goose):
            run(binary,f,success=False)
            cases+=1
    # Both runtimes must reject malformed UTF-8 at the source boundary,
    # including overlong, lone continuation, surrogate and >U+10FFFF bytes.
    for i,invalid_bytes in enumerate((
        b"\xff", b"\xc0\xaf", b"\xed\xa0\x80",
        b"\xf4\x90\x80\x80", b"\xe2\x82", b"\x80"
    )):
        invalid_source=temp/f"utf8-invalid-{i}.doc"
        invalid_source.write_bytes(
            b"source text_value: text = \""+invalid_bytes+b"\"\n")
        for binary in (rust,goose):
            p=subprocess.run([binary,str(invalid_source)],
                             capture_output=True,timeout=20)
            if p.returncode==0:
                raise AssertionError(f"{binary} accepted invalid UTF-8 source {i}")
            cases+=1
    invalid_data=temp/"bad-utf8.txt"
    invalid_data.write_bytes(b"\xed\xa0\x80")
    effect_file=temp/"bad-input.doc"
    effect_file.write_text(
        'effect text_value: text = read("bad-utf8.txt")\n')
    for binary in (rust,goose):
        p=subprocess.run([binary,str(effect_file)],
                         capture_output=True,timeout=20)
        if p.returncode==0:
            raise AssertionError(f"{binary} accepted invalid UTF-8 file effect")
        cases+=1
print(f"DOC_NATIVE_UTF8_TEXT_PASS: {cases} independent cross-runtime cases")
(root/"doc-utf8-text.log").write_text(
    f"DOC_NATIVE_UTF8_TEXT_PASS: {cases} independent cross-runtime cases\n")
