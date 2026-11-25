#!/usr/bin/env bash
# Independent Rust and Goose general-purpose CPU oracle for a mixed-type DOC
# definition. WGSL unit tests separately validate lowering of the same source.
# Does not claim real GPU dispatch or general-purpose GPU coverage.
set -euo pipefail

if [ "$#" -ne 3 ]; then
  echo "usage: $0 RUST_DOC GOOSE_DOC LOG_DIRECTORY" >&2
  exit 2
fi
rust=$1
goose=$2
logs=$3
fixture=runtime-rust/examples/mixed_comparison.doc
test -x "$rust"
test -x "$goose"
test -f "$fixture"
mkdir -p "$logs"
scratch=$(mktemp -d)
trap 'rm -rf -- "$scratch"' EXIT
: > "$logs/mixed-doc-source-parity.log"

# Signed i32 and i64 boundaries catch accidental GPU-width narrowing in
# native CPU semantics, sign errors and comparison mistakes. The independent
# oracle uses shell signed 64-bit comparisons (never arithmetic).
for gate in false true; do
  for a in -9223372036854775808 -2147483649 -2147483648 -1 0 1 2147483647 2147483648 9223372036854775807; do
    for b in -9223372036854775808 -2147483649 -2147483648 -1 0 1 2147483647 2147483648 9223372036854775807; do
      chosen=false
      if [ "$gate" = true ]; then
        if [ "$a" -eq "$b" ]; then chosen=true; fi
      else
        if [ "$a" -lt "$b" ]; then chosen=true; fi
      fi
      printf 'gate: %s\na: %s\nb: %s\nchosen: %s\n' \
        "$gate" "$a" "$b" "$chosen" > "$scratch/expected"
      "$goose" "$fixture" "gate=$gate" "a=$a" "b=$b" \
        > "$scratch/goose-raw"
      sed '/^DOC_TYPED_EVALUATIONS=/d' "$scratch/goose-raw" \
        > "$scratch/goose"
      diff -u "$scratch/expected" "$scratch/goose"
      for workers in 1 4; do
        DOC_WORKERS="$workers" "$rust" "$fixture" \
          "gate=$gate" "a=$a" "b=$b" > "$scratch/rust"
        diff -u "$scratch/expected" "$scratch/rust"
        diff -u "$scratch/rust" "$scratch/goose"
      done
      printf 'PASS gate=%s a=%s b=%s rust_workers=1,4\n' \
        "$gate" "$a" "$b" >> "$logs/mixed-doc-source-parity.log"
    done
  done
done

# One directly authored nested DOC arithmetic graph, independently checked
# against shell i64 arithmetic in a range where CPU DOC and portable GPU i32
# have identical exact results. This tests Rust/Goose CLI semantics and varied
# source assignments before the same source enters Mesa/physical GPU suites.
nested=runtime-rust/examples/gpu_nested_arithmetic.doc
test -f "$nested"
: > "$logs/nested-doc-arithmetic-parity.log"
for gate in false true; do
  for a in -4 0 2 4; do
    for b in -4 0 3 4; do
      for c in -4 1 4; do
        sum=$((a*b+c-a))
        if [ "$gate" = true ]; then
          branched=$((a*b-a))
        else
          branched=$((a+b))
        fi
        chosen=false
        if [ "$b" -lt "$sum" ]; then chosen=true; fi
        ok=false
        if [ "$sum" -eq "$branched" ]; then ok=true; fi
        printf 'a: %s\nb: %s\nc: %s\ngate: %s\nsum: %s\nchosen: %s\nbranched: %s\nok: %s\n' \
          "$a" "$b" "$c" "$gate" "$sum" "$chosen" "$branched" "$ok" \
          > "$scratch/expected"
        "$goose" "$nested" "gate=$gate" "a=$a" "b=$b" "c=$c" \
          > "$scratch/goose-raw"
        sed '/^DOC_TYPED_EVALUATIONS=/d' "$scratch/goose-raw" \
          > "$scratch/goose"
        diff -u "$scratch/expected" "$scratch/goose"
        for workers in 1 4; do
          DOC_WORKERS="$workers" "$rust" "$nested" \
            "gate=$gate" "a=$a" "b=$b" "c=$c" > "$scratch/rust"
          diff -u "$scratch/expected" "$scratch/rust"
          diff -u "$scratch/rust" "$scratch/goose"
        done
        printf 'PASS gate=%s a=%s b=%s c=%s workers=1,4\n' \
          "$gate" "$a" "$b" "$c" >> "$logs/nested-doc-arithmetic-parity.log"
      done
    done
  done
done
echo DOC_NESTED_RUST_GOOSE_CPU_ORACLE_PASS

# GPU lowering currently has its own strict range and typed-IR tests.
# This script asserts native CPU behavior only; it must remain valid when
# future supported real GPU configurations are added to the general CLI.
echo DOC_MIXED_RUST_GOOSE_CPU_ORACLE_PASS
