#!/usr/bin/env bash
# Native Goose/Rust same-source balanced reduction with independent arithmetic oracle.
set -euo pipefail
goose=$1
rust=$2
logs=$3
mkdir -p "$logs"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
"$goose" check runtime-goose/doc_typed.goose > "$logs/reduction-goose-check.log" 2>&1
"$goose" build runtime-goose/doc_typed.goose --offline -o "$tmp/doc-typed" > "$logs/reduction-goose-build.log" 2>&1
fixture=runtime-rust/examples/balanced_reduction.doc
: > "$logs/reduction-oracle.log"
for seed in 0 1 2 3 7 11 19 31; do
  args=()
  expected=0
  for ((i=0;i<8;i++)); do
    value=$(( ((seed * 17 + i * 29 + i * seed) % 41) - 20 ))
    args+=("v$i=$value")
    expected=$((expected + value))
  done
  "$tmp/doc-typed" "$fixture" "${args[@]}" > "$logs/reduction-goose-$seed.log"
  grep -Fx "total: $expected" "$logs/reduction-goose-$seed.log" >/dev/null
  sed '/^DOC_TYPED_EVALUATIONS=/d' "$logs/reduction-goose-$seed.log" > "$tmp/goose-values"
  for workers in 1 2 4; do
    DOC_WORKERS=$workers "$rust" "$fixture" "${args[@]}" > "$logs/reduction-rust-$seed-$workers.log"
    diff -u "$tmp/goose-values" "$logs/reduction-rust-$seed-$workers.log"
  done
  printf 'PASS seed=%s sum=%s workers=1,2,4\n' "$seed" "$expected" >> "$logs/reduction-oracle.log"
done
printf 'DOC_BALANCED_REDUCTION_PASS\n'
