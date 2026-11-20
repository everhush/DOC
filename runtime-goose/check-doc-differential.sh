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
      baseline=''
      for workers in 1 2 4; do
        rust_out=$(DOC_WORKERS="$workers" "$rust" "$fixture" "a=$a" "b=$b" 2> "$logs/rust-${case_name}-${a}-${b}-w${workers}.stderr")
        # Check the complete observation: no duplicate, missing, or extra state.
        expected_out=$(printf 'a: %s\nb: %s\nchosen: %s' "$a" "$b" "$expected")
        if [[ "$rust_out" != "$expected_out" ]]; then
          printf 'FAIL rust %s a=%s b=%s workers=%s expected-observation=%q actual=%q\n' "$case_name" "$a" "$b" "$workers" "$expected_out" "$rust_out" | tee -a "$logs/doc-rust-goose-differential.log" >&2
          exit 1
        fi
        if [[ -n "$baseline" && "$rust_out" != "$baseline" ]]; then
          printf 'FAIL worker-dependent observation %s a=%s b=%s workers=%s\n' "$case_name" "$a" "$b" "$workers" | tee -a "$logs/doc-rust-goose-differential.log" >&2
          exit 1
        fi
        baseline=$rust_out
        printf 'PASS %s a=%s b=%s workers=%s expected=%s\n' "$case_name" "$a" "$b" "$workers" "$expected" | tee -a "$logs/doc-rust-goose-differential.log"
      done
    done
  done
done

# Expand beyond fixed fixtures with nested compositions and independent truth tables.
bash runtime-goose/check-doc-composed.sh "$rust" "$goose" "$logs"
