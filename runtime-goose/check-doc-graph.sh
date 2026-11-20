#!/usr/bin/env bash
# Native dual-runtime bounded finite-DAG conformance and negative-source checks.
set -euo pipefail
goose=${1:?Pass the native Goose compiler}
rust=${2:?Pass the compiled Rust DOC CLI}
logs=${3:?Pass the validation log directory}
mkdir -p "$logs"
scratch=$(mktemp -d)
trap 'rm -rf -- "$scratch"' EXIT
native="$scratch/doc-graph"
"$goose" check runtime-goose/doc_graph.goose 2>&1 | tee "$logs/goose-graph-check.log"
"$goose" build runtime-goose/doc_graph.goose --offline -o "$native" 2>&1 | tee "$logs/goose-graph-build.log"
fixture=runtime-rust/examples/boolean_diamond.doc
: > "$logs/finite-graph-differential.log"
for a in false true; do
  for b in false true; do
    left=false
    if [[ $a == true && $b == true ]]; then left=true; fi
    right=false
    if [[ $a == "$b" ]]; then right=true; fi
    joined=false
    if [[ $left == true && $right == true ]]; then joined=true; fi
    expected=$(printf 'a: %s\nb: %s\nleft: %s\nright: %s\njoined: %s' "$a" "$b" "$left" "$right" "$joined")
    actual=$("$native" "$fixture" "a=$a" "b=$b")
    [[ $actual == "$expected" ]] || { printf 'FAIL native-Goose a=%s b=%s\nexpected: %s\nactual: %s\n' "$a" "$b" "$expected" "$actual" >&2; exit 1; }
    for workers in 1 2 4; do
      rust_out=$(DOC_WORKERS="$workers" "$rust" "$fixture" "a=$a" "b=$b")
      [[ $rust_out == "$expected" ]] || { printf 'FAIL Rust a=%s b=%s workers=%s\n' "$a" "$b" "$workers" >&2; exit 1; }
      printf 'PASS a=%s b=%s workers=%s output=%s\n' "$a" "$b" "$workers" "$joined" >> "$logs/finite-graph-differential.log"
    done
  done
done

# Reject invalid programs and batches before any successful observations.
cat > "$scratch/forward.doc" <<'DOC'
source a: bool = false
derive joined: bool (later) = later
derive later: bool (a) = a
DOC
cat > "$scratch/undeclared.doc" <<'DOC'
source a: bool = false
source b: bool = false
derive joined: bool (a) = eq(a,b)
DOC
cat > "$scratch/duplicate.doc" <<'DOC'
source a: bool = false
source a: bool = true
DOC
cat > "$scratch/malformed.doc" <<'DOC'
source a: bool = false
derive joined: bool (a) = eq(a,)
DOC
cat > "$scratch/type.doc" <<'DOC'
source a: int = 1
DOC
cat > "$scratch/invalid-dependency.doc" <<'DOC'
source a: bool = false
derive joined: bool (missing) = missing
DOC
for kind in forward undeclared duplicate malformed type invalid-dependency; do
  if "$native" "$scratch/$kind.doc" > "$logs/graph-negative-$kind.log" 2>&1; then
    echo "Goose graph interpreter accepted invalid $kind program" >&2
    exit 1
  fi
  grep -Fx DOC_GOOSE_ERROR "$logs/graph-negative-$kind.log"
done
for arg in 'joined=true' 'a=invalid'; do
  if "$native" "$fixture" "$arg" > "$logs/graph-negative-override.log" 2>&1; then
    echo "Goose graph interpreter accepted invalid override $arg" >&2
    exit 1
  fi
  grep -Fx DOC_GOOSE_ERROR "$logs/graph-negative-override.log"
done
if "$native" "$fixture" a=true a=false > "$logs/graph-negative-duplicate-update.log" 2>&1; then
  echo 'Goose graph interpreter accepted duplicate source assignment' >&2
  exit 1
fi
grep -Fx DOC_GOOSE_ERROR "$logs/graph-negative-duplicate-update.log"
