#!/usr/bin/env bash
# DOC Rust-only local source validation; native GPU admission remains explicit.
# Hardware acceptance is performed separately by the SHA-pinned Kaggle workflow.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== DOC Rust CPU and WebGPU local verification ==="
echo "Commit: $(git rev-parse HEAD)"
echo "Date: $(date -u)"
python3 ci/check-rust-only-scope.py
python3 -m unittest discover -s ci/kaggle -p 'test_*.py' -v

cargo test --release --manifest-path runtime-rust/Cargo.toml --all-targets
cargo test --release --manifest-path runtime-rust/Cargo.toml --features webgpu --lib
cargo build --release --manifest-path runtime-rust/Cargo.toml --features webgpu --bin doc --examples

scratch="$(mktemp -d)"
trap 'rm -rf -- "$scratch"' EXIT
doc="runtime-rust/target/release/doc"
DOC_WORKERS=1 "$doc" runtime-rust/examples/repair.doc --backend=cpu a=4 b=1 > "$scratch/cpu-1"
DOC_WORKERS=4 "$doc" runtime-rust/examples/repair.doc --backend=cpu a=4 b=1 > "$scratch/cpu-4"
diff -u "$scratch/cpu-1" "$scratch/cpu-4"
grep -Fx 'chosen: 10' "$scratch/cpu-1"
bash ci/check-explicit-backend.sh "$doc" runtime-rust/examples/repair.doc

# Software WebGPU correctness is developer opt-in and never physical evidence.
if [[ "${DOC_GPU_ALLOW_SOFTWARE:-0}" == "1" ]]; then
  for fixture in boolean_staged gpu_arithmetic_chain gpu_nested_arithmetic parallel_frontier; do
    source="runtime-rust/examples/$fixture.doc"
    "$doc" "$source" --backend=cpu > "$scratch/$fixture.cpu"
    "$doc" "$source" --backend=gpu > "$scratch/$fixture.gpu"
    diff -u "$scratch/$fixture.cpu" "$scratch/$fixture.gpu"
  done
  echo DOC_RUST_LOCAL_WEBGPU_SOFTWARE_PARITY_PASS
fi
echo "DOC_RUST_LOCAL_SOURCE_CHECKS_PASS (not physical-GPU or final release acceptance)"
