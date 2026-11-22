#!/usr/bin/env bash
# Independent LOCAL run-all entrypoint for DOC verification
# Allows local developers and agents to run full regression without hosted CI.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== DOC Local Acceptance Run-All Entrypoint ==="
echo "Commit: $(git rev-parse HEAD)"
echo "Date: $(date -u)"

GOOSE_BIN="${GOOSE_BIN:-/tmp/doc-goose-plain-build/goose}"
if [ ! -x "$GOOSE_BIN" ]; then
  if command -v goose >/dev/null 2>&1; then
    GOOSE_BIN="$(command -v goose)"
  else
    echo "Warning: Goose compiler not found at $GOOSE_BIN or on PATH. Set GOOSE_BIN to run Goose tests." >&2
  fi
fi

echo "--- 1. Rust cargo test --all-targets ---"
cargo test --release --manifest-path runtime-rust/Cargo.toml --all-targets

echo "--- 2. Rust WebGPU example and feature build ---"
cargo test --release --manifest-path runtime-rust/Cargo.toml --features webgpu --example webgpu_integer_eq
cargo build --release --manifest-path runtime-rust/Cargo.toml --bin doc
cargo build --release --manifest-path runtime-rust/Cargo.toml --features webgpu --examples

echo "--- 2b. Rust CLI strict backend selection ---"
bash ci/check-explicit-backend.sh runtime-rust/target/release/doc runtime-rust/examples/repair.doc

echo "--- 3. Python unit and integration tests (ci/) ---"
python3 -m unittest discover -s ci -p 'test_*.py' -v

echo "--- 4. Verify committed local GPU evidence ---"
python3 ci/verify-local-gpu-evidence.py local-evidence
if [ -d local-evidence/forced-hardware ]; then
  python3 ci/verify-local-gpu-evidence.py local-evidence/forced-hardware
fi

if [ -x "$GOOSE_BIN" ]; then
  echo "--- 5. Native Goose typed check & differential suite ---"
  SCRATCH_DIR="$(mktemp -d)"
  trap 'rm -rf -- "$SCRATCH_DIR"' EXIT
  bash runtime-goose/check-doc-typed.sh "$GOOSE_BIN" runtime-rust/target/release/doc "$SCRATCH_DIR"
  echo "Goose typed checks passed in $SCRATCH_DIR"
  "$GOOSE_BIN" build runtime-goose/doc_typed.goose --offline -o "$SCRATCH_DIR/doc-goose"
  bash ci/check-explicit-backend.sh "$SCRATCH_DIR/doc-goose" runtime-rust/examples/repair.doc
fi

echo "=== ALL LOCAL ACCEPTANCE CHECKS PASSED ==="
