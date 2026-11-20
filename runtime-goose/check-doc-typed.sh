#!/usr/bin/env bash
# Independently compiled Goose DOC int/bool interpreter vs Rust finite DAG.
# The comparison uses the SAME authored DOC source, with a separate oracle.
set -euo pipefail
goose=$1
rust=$2
logs=$3
mkdir -p "$logs"
tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
native="$tmp/doc-typed"
"$goose" check runtime-goose/doc_typed.goose 2>&1 | tee "$logs/goose-typed-check.log"
"$goose" build runtime-goose/doc_typed.goose --offline -o "$native" 2>&1 | tee "$logs/goose-typed-build.log"
fixture=runtime-rust/examples/typed_arithmetic.doc
oracle() {
    local a=$1 b=$2 gate=$3
    local sum=$((a+b)) delta=$((a-b)) product=$(((a+b)*(a-b)))
    local equal=false chosen=$delta confirm=false
    if ((delta == 0)); then equal=true; fi
    if [[ "$gate" == true ]]; then chosen=$product; confirm=$equal; fi
    printf 'a: %s\nb: %s\ngate: %s\nsum: %s\ndelta: %s\nproduct: %s\nequal: %s\nchosen: %s\nconfirm: %s' \
        "$a" "$b" "$gate" "$sum" "$delta" "$product" "$equal" "$chosen" "$confirm"
}
: > "$logs/goose-typed-differential.log"
for a in -3 0 2 7; do
 for b in -3 0 2 7; do
  for gate in false true; do
   next_a=$((a+1))
   next_b=$((b-1))
   if [[ "$gate" == true ]]; then next_gate=false; else next_gate=true; fi
   actual=$("$native" "$fixture" "a=$a" "b=$b" "gate=$gate" --next \
       "a=$next_a" "b=$next_b" "gate=$next_gate")
   first=$(printf '%s\n' "$actual" | sed '/^DOC_TYPED_NEXT$/,$d' | sed '/^DOC_TYPED_EVALUATIONS=/d')
   second=$(printf '%s\n' "$actual" | sed '1,/^DOC_TYPED_NEXT$/d' | sed '/^DOC_TYPED_EVALUATIONS=/d')
   expected=$(oracle "$a" "$b" "$gate")
   expected_next=$(oracle "$next_a" "$next_b" "$next_gate")
   rust_first=$(DOC_WORKERS=1 "$rust" "$fixture" "a=$a" "b=$b" "gate=$gate" 2>/dev/null)
   rust_next=$(DOC_WORKERS=4 "$rust" "$fixture" "a=$next_a" "b=$next_b" "gate=$next_gate" 2>/dev/null)
   if [[ "$first" != "$expected" || "$second" != "$expected_next" ||
        "$rust_first" != "$expected" || "$rust_next" != "$expected_next" ]]; then
       printf 'Typed mismatch initial %s,%s,%s and updated %s,%s,%s\n' \
           "$a" "$b" "$gate" "$next_a" "$next_b" "$next_gate" >&2
       diff -u <(printf '%s\n' "$expected") <(printf '%s\n' "$first") || true
       exit 1
   fi
   printf 'PASS a=%s b=%s gate=%s next=%s,%s,%s\n' "$a" "$b" "$gate" \
       "$next_a" "$next_b" "$next_gate" >> "$logs/goose-typed-differential.log"
  done
 done
done
# Unselected overflow must not be computed.
out=$("$native" runtime-rust/examples/typed_lazy.doc a=7 gate=true)
printf '%s\n' "$out" | grep -Fx 'chosen: 7'
if "$native" runtime-rust/examples/typed_lazy.doc a=7 gate=false \
    > "$logs/goose-typed-overflow.log" 2>&1; then
    echo 'Goose accepted overflowing selected branch' >&2; exit 1
fi
grep -Fx DOC_TYPED_ERROR "$logs/goose-typed-overflow.log"
for invalid in 'a=invalid' 'a=true' 'gate=3' 'chosen=2' 'a=1 a=2'; do
    set -- $invalid
    if "$native" "$fixture" "$@" > "$logs/goose-typed-negative.log" 2>&1; then
        echo "Goose accepted invalid argument $invalid" >&2; exit 1
    fi
    grep -Fx DOC_TYPED_ERROR "$logs/goose-typed-negative.log"
done
for badsource in \
    'source a: int = 0|derive b: bool (a) = add(a,1)' \
    'source a: bool = false|derive b: int (a) = if(a,1,false)' \
    'source a: int = 1|derive b: int (a) = add(a,unknown)' \
    'source a: int = 1|derive b: int (a) = if(true,a,add(a,true))'; do
    printf '%s\n' "$badsource" | tr '|' '\n' > "$tmp/invalid.doc"
    if "$native" "$tmp/invalid.doc" > "$logs/goose-typed-source-error.log" 2>&1; then
        echo "Goose accepted ill-typed DOC source: $badsource" >&2; exit 1
    fi
    grep -Fx DOC_TYPED_ERROR "$logs/goose-typed-source-error.log"
done
echo DOC_TYPED_FINITE_PASS | tee -a "$logs/goose-typed-differential.log"
