#!/usr/bin/env bash
# Independent Boolean oracle, identical DOC source, and Rust worker-count differential.
set -euo pipefail
rust=${1:?Rust DOC executable required}
goose=${2:?Goose DOC executable required}
logs=${3:?Output directory required}
mkdir -p "$logs"
: > "$logs/doc-rust-goose-differential.log"
for case_name in conditional interlock xor; do
  case "$case_name" in
    conditional) fixture=runtime-rust/examples/boolean_conditional.doc ;;
    interlock) fixture=runtime-rust/examples/boolean_interlock.doc ;;
    xor) fixture=runtime-rust/examples/boolean_xor.doc ;;
  esac
  for a in false true; do
    for b in false true; do
      expected=false
      case "$case_name" in
        conditional)
          if [[ "$a" == "$b" || "$a" == false ]]; then expected=true; fi ;;
        interlock)
          if [[ "$a" == true && "$b" == true ]]; then expected=true; fi ;;
        xor)
          if [[ "$a" != "$b" ]]; then expected=true; fi ;;
      esac
      goose_out=$("$goose" "$fixture" "$a" "$b" 2> "$logs/goose-${case_name}-${a}-${b}.stderr")
      if [[ "$goose_out" != "DOC_GOOSE_RESULT=$expected" ]]; then
        printf 'FAIL goose %s a=%s b=%s expected=%s output=%s\n' "$case_name" "$a" "$b" "$expected" "$goose_out" | tee -a "$logs/doc-rust-goose-differential.log" >&2
        exit 1
      fi
      for workers in 1 2 4; do
        rust_out=$(DOC_WORKERS="$workers" "$rust" "$fixture" "a=$a" "b=$b" 2> "$logs/rust-${case_name}-${a}-${b}-w${workers}.stderr")
        rust_value=$(printf '%s\n' "$rust_out" | sed -n 's/^chosen: \(true\|false\)$/\1/p')
        if [[ "$rust_value" != "$expected" || $(printf '%s\n' "$rust_out" | grep -c '^chosen: ') -ne 1 ]]; then
          printf 'FAIL rust %s a=%s b=%s workers=%s expected=%s output=%s\n' "$case_name" "$a" "$b" "$workers" "$expected" "$rust_out" | tee -a "$logs/doc-rust-goose-differential.log" >&2
          exit 1
        fi
        printf 'PASS %s a=%s b=%s workers=%s expected=%s rust=%s goose=%s\n' "$case_name" "$a" "$b" "$workers" "$expected" "$rust_value" "$expected" | tee -a "$logs/doc-rust-goose-differential.log"
      done
    done
  done
done
