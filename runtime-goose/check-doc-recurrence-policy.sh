#!/usr/bin/env bash
# Identical DOC source and bounded halt demand under independent Rust and Goose.
set -euo pipefail
goose=$1
rust=$2
logs=$3
scratch=$(mktemp -d)
trap 'rm -rf -- "$scratch"' EXIT
src=runtime-rust/examples/recurrence_halt.doc
: > "$logs/recurrence-halt-policy.log"
for cap in 3 4 5 9; do
    "$goose" "$src" --until=halt "--max-epochs=$cap" index=successor \
        > "$logs/recurrence-halt-goose-$cap.log"
    for workers in 1 2 4; do
        DOC_WORKERS=$workers "$rust" "$src" --until=halt "--max-epochs=$cap" index=successor \
            > "$logs/recurrence-halt-rust-$cap-$workers.log"
        diff -u "$logs/recurrence-halt-goose-$cap.log" "$logs/recurrence-halt-rust-$cap-$workers.log"
    done
    grep -Fx 'DOC_RECURRENCE_HALT: 3' "$logs/recurrence-halt-goose-$cap.log"
    if grep -Eq '^epoch: [4-9]$' "$logs/recurrence-halt-goose-$cap.log"; then
        echo 'Recurrent halt did not stop before later epoch' >&2
        exit 1
    fi
    printf 'HALT cap=%s\n' "$cap" >> "$logs/recurrence-halt-policy.log"
done
# A smaller cap reports incompletion rather than pretending a halt.
for exe in "$goose" "$rust"; do
    if "$exe" "$src" --until=halt --max-epochs=2 index=successor \
        > "$scratch/capped.log" 2>&1; then
        echo 'Accepted unhalted finite cap' >&2; exit 1
    fi
    grep -Fx 'epoch: 2' "$scratch/capped.log"
    if grep -q '^DOC_RECURRENCE_HALT:' "$scratch/capped.log"; then
        echo 'Falsely reported successful halt' >&2; exit 1
    fi
    for bad in \
        '--until=index --max-epochs=4 index=successor' \
        '--until=missing --max-epochs=4 index=successor' \
        '--until=halt --max-epochs=-1 index=successor' \
        '--until=halt --max-epochs=abc index=successor' \
        '--until=halt index=successor' \
        '--until=halt --max-epochs=4 index=successor index=successor'; do
        set -- $bad
        if "$exe" "$src" "$@" > "$scratch/invalid.log" 2>&1; then
            echo "Accepted invalid recurrence demand: $bad" >&2
            exit 1
        fi
        if grep -q '^epoch:' "$scratch/invalid.log"; then
            echo "Invalid recurrence request produced output: $bad" >&2
            exit 1
        fi
    done
done
# Halt already present at epoch 0: do not materialize later epochs.
sed 's/source index: int = 0/source index: int = 3/' "$src" > "$scratch/initial-halt.doc"
for exe in "$goose" "$rust"; do
    "$exe" "$scratch/initial-halt.doc" --until=halt --max-epochs=30 index=successor \
      > "$scratch/zero.log"
    grep -Fx 'DOC_RECURRENCE_HALT: 0' "$scratch/zero.log"
    if grep -q '^epoch: 1$' "$scratch/zero.log"; then exit 1; fi
done
echo DOC_RECURRENCE_HALT_POLICY_PASS | tee -a "$logs/recurrence-halt-policy.log"
