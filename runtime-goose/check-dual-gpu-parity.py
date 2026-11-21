#!/usr/bin/env python3
"""Independent evidence-only DOC GPU parity: Rust wgpu vs native Goose SDL3.

Reads outputs from two separately built, separately executed native GPU
backends. It NEVER dispatches Goose shaders with Rust, and is not part
of either DOC runtime, backend or compiler.
"""
import re
import sys
from pathlib import Path

if len(sys.argv) != 4:
    raise SystemExit("usage: check-dual-gpu-parity.py RUST_LOG_DIR GOOSE_LOG_DIR OUT_DIR")
rust = Path(sys.argv[1])
goose = Path(sys.argv[2])
out = Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
rpat = re.compile(
    r"^DOC_SIGNED_WEBGPU_COMPUTE_PASS: epoch=([01]) lanes=(\d+) equals=(\d+)$"
)
gpat = re.compile(
    r"^DOC_GOOSE_SDL3_GPU_PASS: op=(eq|lt|le) "
    r"epoch=([01]) lanes=(\d+) count=(\d+) backend=(\w+)$"
)
checked = 0
rows = []
for mode in ("eq", "lt", "le"):
    for lanes in (1, 63, 64, 65, 129, 257, 1024):
        rust_file = rust / f"rust-{mode}-{lanes}.log"
        goose_file = goose / "goose-sdl3" / f"sdl3-{mode}-{lanes}.log"
        rtext = rust_file.read_text()
        gtext = goose_file.read_text()
        if "DOC_SIGNED_WEBGPU_ADAPTER:" not in rtext:
            raise AssertionError(f"No Rust physical adapter evidence: {rust_file}")
        if "DOC_GOOSE_SDL3_DEVICE:" not in gtext:
            raise AssertionError(f"No Goose SDL3 device evidence: {goose_file}")
        rdata = {}
        for line in rtext.splitlines():
            m = rpat.match(line)
            if m:
                epoch, n, count = map(int, m.groups())
                if n != lanes or epoch in rdata:
                    raise AssertionError(f"Unexpected Rust batch: {rust_file}")
                rdata[epoch] = count
        gdata = {}
        for line in gtext.splitlines():
            m = gpat.match(line)
            if m:
                actual_mode, epoch, n, count, backend = m.groups()
                epoch, n, count = int(epoch), int(n), int(count)
                if actual_mode != mode or n != lanes or epoch in gdata:
                    raise AssertionError(f"Unexpected Goose SDL3 batch: {goose_file}")
                if backend != "vulkan":
                    raise AssertionError(f"Expected CI SDL3 Vulkan, got {backend}")
                gdata[epoch] = count
        if sorted(rdata) != [0, 1] or sorted(gdata) != [0, 1]:
            raise AssertionError(
                f"Missing one of two GPU source episodes: {rust_file} {goose_file}"
            )
        if rdata != gdata:
            raise AssertionError(
                f"Rust wgpu / Goose SDL3 GPU disagreement: {mode}/{lanes} "
                f"Rust={rdata}, Goose={gdata}"
            )
        for epoch in (0, 1):
            checked += 1
            rows.append(f"{mode},{lanes},{epoch},{rdata[epoch]}")
(out / "native-gpu-equivalence.csv").write_text(
    "operation,lanes,epoch,equal_or_true_count\n" + "\n".join(rows) + "\n"
)
(out / "native-gpu-equivalence.log").write_text(
    f"DOC_RUST_WGPU_GOOSE_SDL3_PARITY_PASS: {checked} observed GPU episodes\n"
)
print(f"DOC_RUST_WGPU_GOOSE_SDL3_PARITY_PASS: {checked} observed GPU episodes")
