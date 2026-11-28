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
    "preprint-model/dependency-oriented-computation.typ", "preprint-model/references.bib",
    "preprint-model/REPRODUCIBILITY-NATIVE.md",
    "release/README.md", "release/rebuild_native.py", "release/verify_candidate.py", "release/test_install.py", "release/test_gpu_candidate.py", "release/physical_gpu.py", "release/install_native.py",
}
TESTS = {
    "test_self_reproduction.py", "test_epoch_authority.py",
    "test_placement_policy.py", "test_allocation_failure.py",
    "test_graph_generation.py", "test_recurrence_policy.py", "recurrence_authority_host.c",
    "scalable_scratch_test.c", "name_index_test.c", "scale_resource_boundary.c",
    "build_autonomous_scale.py", "benchmark_gpu_family_host.c", "scale_algorithm_host.c",
    "benchmark_autonomous_family.py", "benchmark_autonomous_algorithms.py",
    "benchmark_scale_pipeline.py", "verify_autonomous_evidence.py",
    "test_gpu.py", "gpu_pool_metrics_test.c", "gpu_graph_generation_host.c",
    "gpu_epoch_authority_host.c", "webgpu_loss_evidence_test.c",
}
COMPILER_FILES = {
    "common_core.doc",
    "doc_build.py",
    "general.doc",
    "general_core.doc",
    "gpu_core.doc",
    "gpu_plan.doc",
    "gpu_range_core.doc",
    "lexer.doc",
    "lexer_core.doc",
    "managed.doc",
    "managed_core.doc",
    "managed_reactive.doc",
    "managed_reactive_core.doc",
    "module_scan.doc",
    "module_scan_core.doc",
    "native_scalar.doc",
    "native_scalar_core.doc",
    "parser.doc",
    "parser_core.doc",
    "reactive.doc",
    "reactive_core.doc",
    "scalar.doc",
    "scalar_core.doc",
}
RUNTIME_FILES = {
    "checkpoint_io.h",
    "effects_policy.doc",
    "epoch_authority.doc",
    "epoch_authority.h",
    "gpu_pool_metrics.h",
    "gpu_values.h",
    "graph_generation.doc",
    "graph_host.h",
    "graph_reader_slots.h",
    "graph_variant_abi.h",
    "graph_variant_adapter.h",
    "placed_authority.h",
    "placed_epoch.h",
    "placed_policy.doc",
    "placed_transport.h",
    "placement_policy.doc",
    "reactive_values.h",
    "recurrence_policy.doc",
    "recurrence_values.h",
    "repair_core.doc",
    "repair_plan.doc",
    "value_primitives.h",
    "webgpu_loss_evidence.h",
    "webgpu_retirement.h",
}
REQUIRED = (EXACT | {"runtime-doc/compiler/"+name for name in COMPILER_FILES}
            | {"runtime-doc/runtime/"+name for name in RUNTIME_FILES}
            | {"runtime-doc/tests/"+name for name in TESTS})
DENIED = re.compile(r"(^|/)(?:runtime-rust|runtime-goose|paper-latex|preprint-calculus|local-evidence|__pycache__|target|\.git|\.github)(/|$)|(?:_generated\.h|\.(?:pdf|zip|tar|gz|so|a|o|exe|bin|spv|png|jpg|wav|log|pyc))$", re.I)

def admitted(path):
    return path in REQUIRED

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
    assert REQUIRED == {x["path"] for x in entries}, "missing required source: "+str(sorted(REQUIRED-{x["path"] for x in entries}))
    assert all("runtime-rust/" not in x["path"] and "runtime-goose/" not in x["path"] for x in entries)
    assert not list(out.rglob("*_generated.h"))
    assert {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()} == {x["path"] for x in entries}
    a.manifest.parent.mkdir(parents=True,exist_ok=True)
    a.manifest.write_text(json.dumps(dict(source_commit=a.commit,scope="development source-only candidate, not released",files=entries),indent=2)+"\n")
    print("DOC14_SOURCE_CANDIDATE_PASS",len(entries),"UTF-8 source files; generated outputs excluded")

if __name__=="__main__":
    main()
