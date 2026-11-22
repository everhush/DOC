#!/usr/bin/env bash
# Large UTF-8 text and sampled read-effect correctness with independent
# Rust/Goose execution. Historical 8192/16384-byte limits were removed:
# these sizes are now valid test inputs, never expected errors.
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

checks=0
check_exact() {
    local expected_bytes=$1
    {
      printf 'first: '; cat "$tmp/a.txt"; printf '\nsecond: '; cat "$tmp/b.txt"
      printf '\njoined: '; cat "$tmp/a.txt" "$tmp/b.txt"
      printf '\nbytes: %s\n' "$expected_bytes"
    } > "$tmp/expected.txt"
    for bin in "$rust" "$goose"; do
      for workers in 1 4; do
        DOC_WORKERS=$workers "$bin" "$tmp/exact.doc" > "$tmp/actual.txt"
        sed '/^DOC_TYPED_EVALUATIONS=/d' "$tmp/actual.txt" > "$tmp/values.txt"
        cmp "$tmp/expected.txt" "$tmp/values.txt"
        checks=$((checks+1))
      done
    done
}
check_exact 16384

# The 16385-byte value is a VALID DOC result, not a boundary failure.
cat > "$tmp/extended.doc" <<'DOC'
effect first: text = read("a.txt")
effect second: text = read("b.txt")
effect extra: text = read("c.txt")
derive joined: text (first,second) = concat(first,second)
derive extended: text (joined,extra) = concat(joined,extra)
derive bytes: int (extended) = len(extended)
DOC

check_extended() {
    local expected_bytes=$1
    {
      printf 'first: '; cat "$tmp/a.txt"; printf '\nsecond: '; cat "$tmp/b.txt"
      printf '\nextra: '; cat "$tmp/c.txt"
      printf '\njoined: '; cat "$tmp/a.txt" "$tmp/b.txt"
      printf '\nextended: '; cat "$tmp/a.txt" "$tmp/b.txt" "$tmp/c.txt"
      printf '\nbytes: %s\n' "$expected_bytes"
    } > "$tmp/expected.txt"
    for bin in "$rust" "$goose"; do
      for workers in 1 4; do
        DOC_WORKERS=$workers "$bin" "$tmp/extended.doc" > "$tmp/actual.txt"
        sed '/^DOC_TYPED_EVALUATIONS=/d' "$tmp/actual.txt" > "$tmp/values.txt"
        cmp "$tmp/expected.txt" "$tmp/values.txt"
        checks=$((checks+1))
      done
    done
}
check_extended 16385

# An individual effect source may also exceed the old 8192-byte boundary.
printf D >> "$tmp/a.txt"
check_exact 16385
check_extended 16386

# A genuinely invalid dependent operation must fail atomically even when
# its valid input is a large immutable text value. Source text that was
# already derived must not be published before the failing sibling finishes.
cat > "$tmp/failing.doc" <<'DOC'
effect first: text = read("a.txt")
effect second: text = read("b.txt")
derive joined: text (first,second) = concat(first,second)
derive bytes: int (joined) = len(joined)
derive failure: int (bytes) = add(bytes,9223372036854775807)
DOC
for bin in "$rust" "$goose"; do
    if "$bin" "$tmp/failing.doc" > "$tmp/failure.txt" 2>&1; then
        echo 'Accepted overflowing DOC frontier after large text effect' >&2; exit 1
    fi
    if grep -Eq '^(joined|bytes|failure): ' "$tmp/failure.txt"; then
        echo 'Published a partial failing DOC frontier' >&2; exit 1
    fi
    checks=$((checks+1))
done

printf 'DOC_TEXT_BOUNDARY_AND_ATOMICITY_PASS: %s checks\n' "$checks" |
    tee "$logs/doc-text-boundary.log"
