#!/usr/bin/env bash
set -euo pipefail
# A practical, directly authored DOC factorial recurrence. Both independently
# compiled engines must agree with exact mathematical checkpoints.
if (( $# != 3 )); then echo 'usage: check-doc-factorial.sh RUST GOOSE LOGDIR' >&2; exit 2; fi
rust=$1 goose=$2 logs=$3
mkdir -p "$logs"
source=runtime-rust/examples/factorial_nat.doc
for runtime in rust goose; do
  bin=$rust
  if [[ "$runtime" == goose ]]; then bin=$goose; fi
  "$bin" "$source" --through=30 n=next_n product=next_product > "$logs/factorial-$runtime.log"
  test "$(grep -c '^epoch: ' "$logs/factorial-$runtime.log")" -eq 31
  grep -Fx 'product: 265252859812191058636308480000000' "$logs/factorial-$runtime.log"
  grep -Fx 'next_product: 8222838654177922817725562880000000' "$logs/factorial-$runtime.log"
  for epoch in 0 1 2 5 10 20 30; do
    grep -Fx "epoch: $epoch" "$logs/factorial-$runtime.log"
  done
  if "$bin" "$source" --through=2 n=next_n n=next_product > "$logs/factorial-invalid-$runtime.log" 2>&1; then
    echo "Accepted duplicate carry in $runtime" >&2; exit 1
  fi
done
diff -u "$logs/factorial-rust.log" "$logs/factorial-goose.log"
echo DOC_FACTORIAL_NAT_RECURRENCE_PASS
