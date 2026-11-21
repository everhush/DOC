#!/usr/bin/env bash
# Bounded UTF-8 text and sampled read effect: independent Rust/Goose oracle.
set -euo pipefail
rust=$1 goose=$2 logs=$3
mkdir -p "$logs"
tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
printf '%8192s' '' | tr ' ' A > "$tmp/a.txt"
printf '%8192s' '' | tr ' ' B > "$tmp/b.txt"
printf C > "$tmp/c.txt"
cat > "$tmp/exact.doc" <<'DOC'
effect first: text = read("a.txt")
effect second: text = read("b.txt")
derive joined: text (first,second) = concat(first,second)
derive bytes: int (joined) = len(joined)
DOC
{
  printf 'first: '; cat "$tmp/a.txt"; printf '\nsecond: '; cat "$tmp/b.txt"
  printf '\njoined: '; cat "$tmp/a.txt" "$tmp/b.txt"
  printf '\nbytes: 16384\n'
} > "$tmp/expected.txt"
checks=0
for bin in "$rust" "$goose"; do
  for workers in 1 4; do
    DOC_WORKERS=$workers "$bin" "$tmp/exact.doc" > "$tmp/actual.txt"
    sed '/^DOC_TYPED_EVALUATIONS=/d' "$tmp/actual.txt" > "$tmp/values.txt"
    cmp "$tmp/expected.txt" "$tmp/values.txt"
    checks=$((checks+1))
  done
done
cat > "$tmp/overflow.doc" <<'DOC'
effect first: text = read("a.txt")
effect second: text = read("b.txt")
effect extra: text = read("c.txt")
derive joined: text (first,second) = concat(first,second)
derive overflow: text (joined,extra) = concat(joined,extra)
DOC
for bin in "$rust" "$goose"; do
  if "$bin" "$tmp/overflow.doc" > "$tmp/failure.txt" 2>&1; then
    echo 'Accepted 16385-byte DOC concat' >&2; exit 1
  fi
  if grep -Eq '^(joined|overflow): ' "$tmp/failure.txt"; then
    echo 'Published partial overflowing DOC frontier' >&2; exit 1
  fi
  checks=$((checks+1))
done
printf D >> "$tmp/a.txt"
for bin in "$rust" "$goose"; do
  if "$bin" "$tmp/exact.doc" > "$tmp/failure.txt" 2>&1; then
    echo 'Accepted 8193-byte DOC read effect' >&2; exit 1
  fi
  checks=$((checks+1))
done
printf 'DOC_TEXT_BOUNDARY_AND_ATOMICITY_PASS: %s checks\n' "$checks" | tee "$logs/doc-text-boundary.log"
