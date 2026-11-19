#!/usr/bin/env bash
# Independent mathematical oracle plus cross-runtime DOC source-to-result comparison.
set -euo pipefail
rust=${1:?Rust DOC executable required}
goose=${2:?Goose DOC executable required}
logs=${3:?Output directory required}
mkdir -p "$logs"
: > "$logs/doc-rust-goose-differential.log"
for case_name in conditional interlock; do
  case "$case_name" in
    conditional) fixture=runtime-rust/examples/boolean_conditional.doc ;;
    interlock) fixture=runtime-rust/examples/boolean_interlock.doc ;;
  esac
  for a in false true; do
    for b in false true; do
      expected=false
      if [[ "$case_name" == conditional ]]; then
        if [[ "$a" == "$b" || "$a" == false ]]; then expected=true; fi
      elif [[ "$a" == true && "$b" == true ]]; then
        expected=true
      fi
      rust_out=$("$rust" "$fixture" "a=$a" "b=$b" 2> "$logs/rust-${case_name}-${a}-${b}.stderr")
      goose_out=$("$goose" "$fixture" "$a" "$b")
      rust_value=$(printf '%s\n' "$rust_out" | sed -n 's/^chosen: \(true\|false\)$/\1/p')
      goose_value=$(printf '%s\n' "$goose_out" | sed -n 's/^DOC_GOOSE_RESULT=\(true\|false\)$/\1/p')
      if [[ "$rust_value" != "$expected" || "$goose_value" != "$expected" ]]; then
        printf 'FAIL %s a=%s b=%s expected=%s rust=%s goose=%s\n' "$case_name" "$a" "$b" "$expected" "$rust_value" "$goose_value" | tee -a "$logs/doc-rust-goose-differential.log" >&2
        exit 1
      fi
      printf 'PASS %s a=%s b=%s expected=%s rust=%s goose=%s\n' "$case_name" "$a" "$b" "$expected" "$rust_value" "$goose_value" | tee -a "$logs/doc-rust-goose-differential.log"
    done
  done
done
