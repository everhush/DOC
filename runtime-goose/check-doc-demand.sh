#!/usr/bin/env bash
# Ancestor-closed demand and failure-isolation conformance, Goose vs Rust.
set -euo pipefail
goose=$1
rust=$2
logs=$3
fixture=runtime-rust/examples/demand_lazy.doc
: > "$logs/demand-differential.log"
for a in 1 3 7 19; do
    for target in a target copy; do
        case "$target" in
            a) expected=$a ;;
            target) expected=$((a + 2)) ;;
            copy) expected=$((a + 3)) ;;
        esac
        actual=$("$goose" "$fixture" "--demand=$target" "a=$a")
        reference=$("$rust" "$fixture" "--demand=$target" "a=$a")
        test "$actual" = "$reference"
        test "$actual" = "$target: $expected"
        printf 'PASS a=%s demand=%s expected=%s\n' "$a" "$target" "$expected" \
            >> "$logs/demand-differential.log"
    done
done
for binary in "$goose" "$rust"; do
    for bad in \
        '--demand=broken a=1' \
        '--demand=unknown a=1' \
        '--demand=copy a=invalid' \
        '--demand=copy a=true' \
        '--demand=copy a=2 a=3' \
        '--demand=copy broken=7'; do
        set -- $bad
        if "$binary" "$fixture" "$@" > "$logs/demand-negative.log" 2>&1; then
            echo "Demand unexpectedly succeeded: $bad" >&2
            exit 1
        fi
        if grep -Eq '^(copy|broken|target|a): ' "$logs/demand-negative.log"; then
            echo "Demand published before validation: $bad" >&2
            exit 1
        fi
    done
done
echo DOC_ANCESTOR_CLOSED_DEMAND_PASS | tee -a "$logs/demand-differential.log"
