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
# Boundary and rejection cases: independent checked-i64 arithmetic contract.
for bin in "$tmp/doc-typed" "$rust"; do
  label=rust
  if [[ "$bin" == "$tmp/doc-typed" ]]; then label=goose; fi
  # No intermediate addition overflows, although the input magnitude is large.
  args=(v0=9223372036854775807 v1=-9223372036854775807 v2=0 v3=0 v4=0 v5=0 v6=0 v7=0)
  "$bin" "$fixture" "${args[@]}" > "$logs/reduction-boundary-$label.log"
  grep -Fx 'total: 0' "$logs/reduction-boundary-$label.log" >/dev/null
  # A checked overflowing pair must reject before publishing any derived value.
  args=(v0=9223372036854775807 v1=1 v2=0 v3=0 v4=0 v5=0 v6=0 v7=0)
  if "$bin" "$fixture" "${args[@]}" > "$logs/reduction-overflow-$label.log" 2>&1; then
    echo "Accepted overflowing reduction pair: $label" >&2; exit 1
  fi
  if grep -Eq '^(p[0-3]|q[01]|total): ' "$logs/reduction-overflow-$label.log"; then
    echo "Published partial reduction on overflow: $label" >&2; exit 1
  fi
  for bad in 'v0=not-an-integer' 'v0=true' 'v8=1' 'v0=1 v0=2'; do
    read -r -a invalid <<< "$bad"
    if "$bin" "$fixture" "${invalid[@]}" > "$logs/reduction-invalid-$label.log" 2>&1; then
      echo "Accepted invalid reduction input: $label $bad" >&2; exit 1
    fi
  done
  printf 'PASS boundary, checked overflow, invalid input: %s\n' "$label" >> "$logs/reduction-oracle.log"
done
printf 'DOC_BALANCED_REDUCTION_PASS\n'
