#!/usr/bin/env python3
"""Export and verify a deliberately narrow source-only DOC release candidate.

This is a staging input, not the final distributable. No tracked Git changes,
network access, binary inclusion, or new repository creation.
"""
import argparse, hashlib, json, pathlib, re, subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXACT = {
    "README.md", "LICENSE", "LICENSE-APACHE", "NOTICE", ".gitignore",
    "BACKEND-EXECUTION-CONTRACT.md",
    "paper/dependency-oriented-computation.typ", "paper/references.bib",
    "paper/REPRODUCIBILITY-NATIVE.md",
    "paper-calculus/dependency-oriented-calculus.typ",
    "paper-latex/dependency-oriented-computation.tex",
    "paper-latex/manuscript-body.tex", "paper-latex/manuscript-preamble.tex",
    "paper-latex/references.bib",
    "release/README.md", "release/rebuild_native.py", "release/verify_candidate.py",
}
TESTS = {
    "test_self_reproduction.py", "test_epoch_authority.py",
    "test_placement_policy.py", "test_allocation_failure.py",
    "test_graph_generation.py", "test_recurrence_policy.py",
    "scalable_scratch_test.c", "name_index_test.c", "scale_resource_boundary.c",
}
DENIED = re.compile(r"(^|/)(?:runtime-rust|runtime-goose|local-evidence|__pycache__|target|\.git|\.github)(/|$)|(?:_generated\.h|\.(?:pdf|zip|tar|gz|so|a|o|exe|bin|spv|png|jpg|wav|log|pyc))$", re.I)

def admitted(path):
    if path in EXACT:
        return True
    if path.startswith("runtime-doc/compiler/"):
        return pathlib.PurePosixPath(path).suffix in (".doc", ".py")
    if path.startswith("runtime-doc/runtime/"):
        return pathlib.PurePosixPath(path).suffix in (".doc", ".h", ".c") and not path.endswith("_generated.h")
    return path.startswith("runtime-doc/tests/") and pathlib.PurePosixPath(path).name in TESTS

def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=pathlib.Path, required=True)
    p.add_argument("--manifest", type=pathlib.Path, required=True)
    p.add_argument("--commit", required=True)
    a = p.parse_args()
    out = a.output.resolve()
    assert not out.exists(), "candidate output must be fresh"
    assert not a.manifest.resolve().is_relative_to(out), "manifest belongs outside the source tree"
    assert git("rev-parse", a.commit).decode().strip() == a.commit
    assert git("rev-parse", a.commit+":runtime-rust").decode().strip() == "a95a38bc6e9300aae815f83b570db5f99d32f221"
    out.mkdir(parents=True)
    entries=[]
    for record in git("ls-tree","-rz",a.commit).split(b"\0"):
        if not record:
            continue
        meta, raw = record.split(b"\t",1)
        mode, kind, oid = meta.decode().split()
        path = raw.decode("utf-8")
        if not admitted(path):
            continue
        assert kind == "blob" and mode in ("100644","100755") and not DENIED.search(path), path
        parts=pathlib.PurePosixPath(path)
        assert not parts.is_absolute() and ".." not in parts.parts
        data=git("cat-file","blob",oid)
        decoded=data.decode("utf-8")
        assert "\0" not in decoded and all(ord(c)>=32 or c in "\n\r\t\f" for c in decoded), path
        assert not data.startswith(b"version https://git-lfs.github.com/spec/"), path
        assert not re.search(r"-----BEGIN [A-Z ]*PRIVATE KEY-----",decoded),path
        dst=out/path
        dst.parent.mkdir(parents=True,exist_ok=True)
        dst.write_bytes(data)
        dst.chmod(0o755 if mode=="100755" else 0o644)
        entries.append(dict(path=path,git_blob=oid,sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),mode=mode))
    assert EXACT <= {x["path"] for x in entries}
    assert all("runtime-rust/" not in x["path"] and "runtime-goose/" not in x["path"] for x in entries)
    assert not list(out.rglob("*_generated.h"))
    assert {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()} == {x["path"] for x in entries}
    a.manifest.parent.mkdir(parents=True,exist_ok=True)
    a.manifest.write_text(json.dumps(dict(source_commit=a.commit,scope="development source-only candidate, not released",files=entries),indent=2)+"\n")
    print("DOC14_SOURCE_CANDIDATE_PASS",len(entries),"UTF-8 source files; generated outputs excluded")

if __name__=="__main__":
    main()
