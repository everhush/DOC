#!/usr/bin/env python3
"""Native Goose old-reader pinning vs Rust snapshot semantics on same DOC."""
import subprocess,sys
from pathlib import Path
rust,goose,logs=sys.argv[1:]
fixture="runtime-rust/examples/snapshot_proof.doc"
goose_run=subprocess.run([goose,fixture,"--snapshot-proof"],
                         capture_output=True,text=True,timeout=30)
if goose_run.returncode:
    raise AssertionError(f"Goose owned snapshot program failed: {goose_run.stderr}")
if "DOC_GOOSE_PINNED_SNAPSHOT_PASS: 4 owned readers across pool compaction" not in goose_run.stdout:
    raise AssertionError("Goose reader root lifetime was not proved")
expected_after={
    "n":"12345678901234567890123456789012345678901234567890",
    "items":"[11,13,17,19]",
    "next":"12345678901234567890123456789012345678901234567891",
    "count":"4","first":"11",
}
for name,value in expected_after.items():
    if f"{name}: {value}" not in goose_run.stdout:
        raise AssertionError(f"Goose new snapshot: unexpected {name}")
# The native Rust program has the identical source, independently evaluated
# before and after typed source updates. Rust concurrency pinning has its own
# direct Rust tests; the Goose thread test above is not a proxy for that.
for args,expected in (
    ((),{"count":"3","first":"2",
          "n":"99999999999999999999999999999999999999999999999999"}),
    (("n=12345678901234567890123456789012345678901234567890",
      "items=[11,13,17,19]"),expected_after),
):
    p=subprocess.run([rust,fixture,*args],capture_output=True,text=True,timeout=20)
    if p.returncode:raise AssertionError(f"Rust DOC snapshot baseline: {p.stderr}")
    for name,value in expected.items():
        if f"{name}: {value}" not in p.stdout:
            raise AssertionError(f"Rust DOC snapshot mismatch: {name}")
Path(logs,"goose-pinned-snapshot.log").write_text(
    "DOC_GOOSE_PINNED_SNAPSHOT_PASS: 4 owned readers across pool compaction\n")
print("DOC_GOOSE_PINNED_SNAPSHOT_PASS: typed nat/list readers and source repair")
