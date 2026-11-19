#!/usr/bin/env bash
# Black-box finite DOC CLI conformance; deliberately separate from host-language unit tests.
set -euo pipefail
runtime=${1:?Pass the compiled Rust DOC CLI}
logs=${2:?Pass output directory}
mkdir -p "$logs"
scratch=$(mktemp -d)
trap 'rm -rf -- "$scratch"' EXIT
cat > "$scratch/lazy.doc" <<'DOC'
source flag: bool = true
source a: int = 7
derive chosen: int (flag,a) = if(flag,a,add(9223372036854775807,1))
DOC
cat > "$scratch/overflow.doc" <<'DOC'
source a: int = 1
derive valid: int (a) = add(a,1)
derive invalid: int (a) = add(a,9223372036854775807)
DOC
cat > "$scratch/illtyped.doc" <<'DOC'
source a: bool = true
derive invalid: int (a) = add(a,1)
DOC
printf 'flag: true\na: 7\nchosen: 7\n' > "$scratch/expected"
: > "$logs/doc-finite-cli-conformance.log"
for workers in 1 2 4; do
  DOC_WORKERS="$workers" "$runtime" "$scratch/lazy.doc" > "$scratch/actual" 2> "$logs/finite-lazy-w${workers}.stderr"
  diff -u "$scratch/expected" "$scratch/actual"
  printf 'PASS lazy-selected-branch workers=%s\n' "$workers" | tee -a "$logs/doc-finite-cli-conformance.log"
  for kind in overflow illtyped; do
    if DOC_WORKERS="$workers" "$runtime" "$scratch/$kind.doc" > "$scratch/actual" 2> "$logs/finite-${kind}-w${workers}.stderr"; then
      echo "FAIL $kind unexpectedly succeeded (workers=$workers)" >&2; exit 1
    fi
    if [[ -s "$scratch/actual" ]]; then
      echo "FAIL $kind emitted partial observation (workers=$workers)" >&2; exit 1
    fi
    printf 'PASS %s-rejected-no-partial-output workers=%s\n' "$kind" "$workers" | tee -a "$logs/doc-finite-cli-conformance.log"
  done
  if DOC_WORKERS="$workers" "$runtime" "$scratch/lazy.doc" flag=false > "$scratch/actual" 2> "$logs/finite-unselected-w${workers}.stderr"; then
    echo "FAIL selected-branch overflow unexpectedly succeeded (workers=$workers)" >&2; exit 1
  fi
  if [[ -s "$scratch/actual" ]]; then
    echo "FAIL selected-branch overflow emitted partial observation (workers=$workers)" >&2; exit 1
  fi
  printf 'PASS selected-overflow-rejected workers=%s\n' "$workers" | tee -a "$logs/doc-finite-cli-conformance.log"
done
