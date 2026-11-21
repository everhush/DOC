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
integer_fixture=runtime-rust/examples/integer_equality.doc
"$native" "$integer_fixture" --emit-wgsl equal "$logs/goose-webgpu/integer-equality.wgsl"
test -s "$logs/goose-webgpu/integer-equality.wgsl"
ordered_fixture=runtime-rust/examples/integer_ordering.doc
"$native" "$ordered_fixture" --emit-wgsl less "$logs/goose-webgpu/integer-less.wgsl"
"$native" "$ordered_fixture" --emit-wgsl less_or_equal "$logs/goose-webgpu/integer-le.wgsl"
grep -Fq 'a0 < a1' "$logs/goose-webgpu/integer-less.wgsl"
grep -Fq 'a0 <= a1' "$logs/goose-webgpu/integer-le.wgsl"
grep -Fq 'bitcast<i32>(input_0.data[idx])' "$logs/goose-webgpu/integer-equality.wgsl"
grep -Fq 'bitcast<i32>(input_1.data[idx])' "$logs/goose-webgpu/integer-equality.wgsl"
for invalid in   'source a: int = 1|derive bad: bool (a) = eq(add(a,1),0)'   'source a: nat = 1|derive bad: bool (a) = eq(a,nat(1))'; do
    printf '%s\n' "$invalid" | tr '|' '\n' > "$tmp/gpu-ineligible.doc"
    if "$native" "$tmp/gpu-ineligible.doc" --emit-wgsl bad "$tmp/rejected-int.wgsl"       > "$logs/goose-gpu-ineligible.log" 2>&1; then
        echo "Goose emitted unsafe signed GPU shader" >&2
        exit 1
    fi
    test ! -e "$tmp/rejected-int.wgsl"
done
for target in sum equal; do
    if "$native" "$fixture" --emit-wgsl "$target" "$tmp/rejected.wgsl" > "$logs/goose-typed-wgsl-rejection-$target.log" 2>&1; then
        echo "Goose lowered an unsupported definition: $target" >&2
        exit 1
    fi
    grep -Fx DOC_TYPED_ERROR "$logs/goose-typed-wgsl-rejection-$target.log"
    test ! -e "$tmp/rejected.wgsl"
done
write_gpu_oracle() {
    local source=$1 target=$2 a b lane result
    declare -A oracle_word
    for a in false true; do
        for b in false true; do
            result=$("$native" "$source" "a=$a" "b=$b" | grep "^$target: ")
            case "$result" in
                "$target: true") oracle_word[$a,$b]=1 ;;
                "$target: false") oracle_word[$a,$b]=0 ;;
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
    }
}

write_gpu_oracle "$boolean_fixture" chosen > "$logs/goose-webgpu/expected.txt"
staged_fixture=runtime-rust/examples/boolean_staged.doc
"$native" "$staged_fixture" --emit-wgsl chosen "$logs/goose-webgpu/stage-1.wgsl"
"$native" "$staged_fixture" --emit-wgsl verified "$logs/goose-webgpu/stage-2.wgsl"
write_gpu_oracle "$staged_fixture" verified > "$logs/goose-webgpu/staged-expected.txt"

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

# A direct instruction oracle for the bounded two-counter transfer example.
for stop in true false; do
    machine="$tmp/counter-$stop.doc"
    sed "s/^source stop_on_zero: bool = true$/source stop_on_zero: bool = $stop/" \
        runtime-rust/examples/counter_transfer.doc > "$machine"
    pc=0 left=3 right=0
    {
        for ((epoch = 0; epoch <= 40; epoch++)); do
            next_pc=$pc next_left=$left next_right=$right
            case "$pc" in
                0)
                    if ((left > 0)); then
                        next_left=$((left - 1))
                        next_pc=1
                    elif [[ "$stop" == true ]]; then
                        next_pc=2
                    fi
                    ;;
                1) next_right=$((right + 1)); next_pc=0 ;;
                2) ;;
                *) exit 1 ;;
            esac
            printf 'epoch: %s\npc: %s\nleft: %s\nright: %s\nstop_on_zero: %s\nnext_pc: %s\nnext_left: %s\nnext_right: %s\n' \
                "$epoch" "$pc" "$left" "$right" "$stop" "$next_pc" "$next_left" "$next_right"
            pc=$next_pc left=$next_left right=$next_right
        done
    } > "$logs/counter-$stop-oracle.log"
    machine_carry=(--through=40 pc=next_pc left=next_left right=next_right)
    "$native" "$machine" "${machine_carry[@]}" > "$logs/counter-$stop-goose.log"
    diff -u "$logs/counter-$stop-oracle.log" "$logs/counter-$stop-goose.log"
    for workers in 1 4; do
        DOC_WORKERS=$workers "$rust" "$machine" "${machine_carry[@]}" > "$logs/counter-$stop-rust-$workers.log"
        diff -u "$logs/counter-$stop-oracle.log" "$logs/counter-$stop-rust-$workers.log"
    done
done


# Frontier-wide failure must not publish a partial observable valuation.
cat > "$tmp/frontier-atomic.doc" <<'DOC'
source a: int = 1
derive safe: int (a) = add(a,1)
derive overflow: int (a) = add(9223372036854775807,a)
DOC
for bin in "$native" "$rust"; do
    label=rust
    if [[ "$bin" == "$native" ]]; then label=goose; fi
    if "$bin" "$tmp/frontier-atomic.doc" > "$logs/frontier-atomic-$label.log" 2>&1; then
        echo "Accepted overflowing ready frontier: $label" >&2
        exit 1
    fi
    if grep -Eq '^(safe|overflow): ' "$logs/frontier-atomic-$label.log"; then
        echo "Published a partial ready frontier: $label" >&2
        exit 1
    fi
    "$bin" "$tmp/frontier-atomic.doc" a=0 > "$logs/frontier-safe-$label.log"
    sed '/^DOC_TYPED_EVALUATIONS=/d' "$logs/frontier-safe-$label.log" > "$tmp/frontier-values-$label.log"
    diff -u <(printf 'a: 0\nsafe: 1\noverflow: 9223372036854775807\n') "$tmp/frontier-values-$label.log"
done


# Version boundary: a successful epoch may precede a failed next generation.
# This tests observable publication, not physical snapshot retention/reclamation.
cat > "$tmp/epoch-overflow.doc" <<'DOC'
source counter: int = 9223372036854775805
derive next_counter: int (counter) = add(counter,1)
DOC
for bin in "$native" "$rust"; do
    label=rust
    if [[ "$bin" == "$native" ]]; then label=goose; fi
    if "$bin" "$tmp/epoch-overflow.doc" --through=2 counter=next_counter > "$logs/epoch-overflow-$label.log" 2>&1; then
        echo "Accepted overflowing epoch: $label" >&2
        exit 1
    fi
    grep -Fx 'epoch: 0' "$logs/epoch-overflow-$label.log" >/dev/null
    grep -Fx 'epoch: 1' "$logs/epoch-overflow-$label.log" >/dev/null
    grep -Fx 'counter: 9223372036854775806' "$logs/epoch-overflow-$label.log" >/dev/null
    if grep -q '^epoch: 2$' "$logs/epoch-overflow-$label.log"; then
        echo "Published failed epoch: $label" >&2
        exit 1
    fi
done

bash runtime-goose/check-doc-recurrence-policy.sh "$native" "$rust" "$logs"
bash runtime-goose/check-doc-demand.sh "$native" "$rust" "$logs"
python3 runtime-goose/check-doc-nat.py "$native" "$rust" "$logs"
python3 runtime-goose/check-doc-counter-program.py "$native" "$rust" "$logs"
bash runtime-goose/check-doc-factorial.sh "$rust" "$native" "$logs"
python3 runtime-goose/check-doc-sorting.py "$rust" "$native" "$logs"
python3 runtime-goose/check-doc-functions.py "$rust" "$native" "$logs"
python3 runtime-goose/check-doc-modules.py "$rust" "$native" "$logs"
python3 runtime-goose/check-doc-effect.py "$rust" "$native" "$logs"
python3 runtime-goose/check-doc-list.py "$rust" "$native" "$logs"
python3 runtime-goose/check-doc-parallel.py "$rust" "$native" "$logs"
python3 runtime-goose/check-doc-signed-parallel.py "$rust" "$native" "$logs"
python3 runtime-goose/check-doc-maybe.py "$rust" "$native" "$logs"
python3 runtime-goose/check-doc-snapshot.py "$rust" "$native" "$logs"
python3 runtime-goose/check-doc-write.py "$rust" "$native" "$logs"
python3 runtime-goose/check-doc-text.py "$rust" "$native" "$logs"
python3 runtime-goose/check-doc-memory-soak.py "$rust" "$native" "$logs"
python3 runtime-goose/check-doc-graph-replace.py "$rust" "$native" "$logs"
python3 runtime-goose/check-doc-graph-traversal.py "$rust" "$native" "$logs"
python3 runtime-goose/benchmark-matched.py "$rust" "$native" "$logs"
python3 runtime-goose/bench-workers.py "$rust" "$native" "$logs"
echo DOC_TYPED_FINITE_PASS | tee -a "$logs/goose-typed-differential.log"
