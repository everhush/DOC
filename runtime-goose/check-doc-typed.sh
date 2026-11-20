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

# Whitespace and an operator spelling used as a premise name are shared syntax.
cat > "$tmp/syntax.doc" <<'DOC'
source add:int=+7
source b: int = 3
derive sum:int(add, b) = add(add,b)
derive neg: int(sum)=sub(0,sum)
DOC
goose_syntax=$("$native" "$tmp/syntax.doc" | sed '/^DOC_TYPED_EVALUATIONS=/d')
rust_syntax=$("$rust" "$tmp/syntax.doc" 2>/dev/null)
expected_syntax=$(printf 'add: 7\nb: 3\nsum: 10\nneg: -10')
test "$goose_syntax" = "$expected_syntax"
test "$rust_syntax" = "$expected_syntax"
printf '%s\n' "$goose_syntax" | tee "$logs/goose-typed-shared-syntax.log"

# Export the independently lowered shader and independently evaluated CPU oracle.
mkdir -p "$logs/goose-webgpu"
boolean_fixture=runtime-rust/examples/boolean_conditional.doc
shader="$logs/goose-webgpu/conditional.wgsl"
"$native" "$boolean_fixture" --emit-wgsl chosen "$shader"
test -s "$shader"
for target in sum equal; do
    if "$native" "$fixture" --emit-wgsl "$target" "$tmp/rejected.wgsl" > "$logs/goose-typed-wgsl-rejection-$target.log" 2>&1; then
        echo "Goose lowered an unsupported definition: $target" >&2
        exit 1
    fi
    grep -Fx DOC_TYPED_ERROR "$logs/goose-typed-wgsl-rejection-$target.log"
    test ! -e "$tmp/rejected.wgsl"
done
declare -A oracle_word
for a in false true; do
    for b in false true; do
        result=$("$native" "$boolean_fixture" "a=$a" "b=$b" | grep '^chosen: ')
        case "$result" in
            'chosen: true') oracle_word[$a,$b]=1 ;;
            'chosen: false') oracle_word[$a,$b]=0 ;;
            *) exit 1 ;;
        esac
    done
done
{
    printf 'DOC_WEBGPU_COMPUTE_PASS: ['
    for ((lane = 0; lane < 130; lane++)); do
        a=false b=false
        if ((lane % 3 == 0)); then a=true; fi
        if ((lane % 5 < 2)); then b=true; fi
        if ((lane > 0)); then printf ', '; fi
        printf '%s' "${oracle_word[$a,$b]}"
    done
    printf ']\n'
} > "$logs/goose-webgpu/expected.txt"

# Independent native epoch engines, unchanged DOC source and a closed-form oracle.
triangle=runtime-rust/examples/triangular.doc
carry=(--through=12 index=next_index total=next_total)
"$native" "$triangle" "${carry[@]}" > "$logs/goose-recurrence.log"
for workers in 1 4; do
    DOC_WORKERS=$workers "$rust" "$triangle" "${carry[@]}" > "$logs/rust-recurrence-$workers.log"
    diff -u "$logs/goose-recurrence.log" "$logs/rust-recurrence-$workers.log"
done
for ((epoch = 0; epoch <= 12; epoch++)); do
    printf 'epoch: %s\nindex: %s\ntotal: %s\nincrement: 1\nnext_index: %s\nnext_total: %s\n' \
        "$epoch" "$epoch" "$((epoch * (epoch + 1) / 2))" \
        "$((epoch + 1))" "$(((epoch + 1) * (epoch + 2) / 2))"
done > "$logs/recurrence-oracle.log"
diff -u "$logs/recurrence-oracle.log" "$logs/goose-recurrence.log"
for bin in "$native" "$rust"; do
    if "$bin" "$triangle" --through=1 index=next_index index=next_total > "$tmp/carry-invalid.log" 2>&1; then
        echo "Duplicate carry accepted by $bin" >&2
        exit 1
    fi
    if grep -q '^epoch:' "$tmp/carry-invalid.log"; then
        echo "Invalid carry produced an epoch in $bin" >&2
        exit 1
    fi
done

echo DOC_TYPED_FINITE_PASS | tee -a "$logs/goose-typed-differential.log"
