#!/usr/bin/env bash
# Native Goose finite-DAG repair checks against independent Rust DOC execution.
set -euo pipefail
goose=$1
logs=$2
rust=$3
mkdir -p "$logs"
scratch=$(mktemp -d)
trap 'rm -rf -- "$scratch"' EXIT
native="$scratch/doc-graph"
fixture=runtime-rust/examples/boolean_diamond.doc
"$goose" check runtime-goose/doc_graph.goose 2>&1 | tee "$logs/goose-graph-check.log"
"$goose" build runtime-goose/doc_graph.goose --offline -o "$native" 2>&1 | tee "$logs/goose-graph-build.log"
: > "$logs/goose-graph-differential.log"
for a in false true; do
  for b in false true; do
    for next_a in false true; do
      for next_b in false true; do
        actual=$("$native" "$fixture" "$a" "$b" "$next_a" "$next_b")
        first=$(printf '%s\n' "$actual" | sed '/^DOC_GOOSE_NEXT$/,$d' | sed '/^DOC_GOOSE_EVALUATIONS=/d')
        second=$(printf '%s\n' "$actual" | sed '1,/^DOC_GOOSE_NEXT$/d' | sed '/^DOC_GOOSE_EVALUATIONS=/d')
        expected_first=$(DOC_WORKERS=1 "$rust" "$fixture" "a=$a" "b=$b" 2>/dev/null)
        expected_second=$(DOC_WORKERS=4 "$rust" "$fixture" "a=$next_a" "b=$next_b" 2>/dev/null)
        if [[ "$first" != "$expected_first" || "$second" != "$expected_second" ]]; then
          printf 'MISMATCH initial=%s,%s updated=%s,%s\n' "$a" "$b" "$next_a" "$next_b" >&2
          diff -u <(printf '%s\n' "$expected_first") <(printf '%s\n' "$first") || true
          diff -u <(printf '%s\n' "$expected_second") <(printf '%s\n' "$second") || true
          exit 1
        fi
        if [[ "$a" == "$next_a" && "$b" == "$next_b" ]]; then
          [[ "$(printf '%s\n' "$actual" | tail -n 1)" == 'DOC_GOOSE_EVALUATIONS=0' ]] || {
            echo 'Unchanged source batch unexpectedly recomputed' >&2; exit 1;
          }
        fi
        printf 'PASS initial=%s,%s updated=%s,%s\n' "$a" "$b" "$next_a" "$next_b" >> "$logs/goose-graph-differential.log"
      done
    done
  done
done
for kind in bad-boolean duplicate-name unknown-premise invalid-expression; do
  cp "$fixture" "$scratch/bad.doc"
  case "$kind" in
    bad-boolean) : ;;
    duplicate-name) printf 'source a: bool = false\n' >> "$scratch/bad.doc" ;;
    unknown-premise) sed -i 's/(equal,requested)/(equal,missing)/' "$scratch/bad.doc" ;;
    invalid-expression) sed -i 's/if(equal,requested,false)/if(equal,unknown,false)/' "$scratch/bad.doc" ;;
  esac
  if [[ "$kind" == bad-boolean ]]; then
    if "$native" "$scratch/bad.doc" invalid true > "$logs/goose-graph-negative-$kind.log" 2>&1; then
      echo "Accepted invalid $kind case" >&2; exit 1;
    fi
  else
    if "$native" "$scratch/bad.doc" true false > "$logs/goose-graph-negative-$kind.log" 2>&1; then
      echo "Accepted invalid $kind case" >&2; exit 1;
    fi
  fi
  grep -Fx DOC_GOOSE_GRAPH_ERROR "$logs/goose-graph-negative-$kind.log"
done
echo DOC_GOOSE_GRAPH_CONFORMANCE_PASS | tee -a "$logs/goose-graph-differential.log"
