#!/usr/bin/env bash
# Cross-runtime compositional Boolean test: same authored DOC graph, independent truth oracle.
set -euo pipefail
rust=${1:?Rust DOC CLI}
goose=${2:?Goose DOC CLI}
logs=${3:?Log directory}
mkdir -p "$logs"
scratch=$(mktemp -d)
trap 'rm -rf -- "$scratch"' EXIT
: > "$logs/composed-boolean.log"
# Truth-table masks ordered (false,false), (false,true), (true,false), (true,true).
expressions=(
  'eq(eq(a,b),true)'
  'if(eq(a,false),b,a)'
  'if(a,eq(b,false),b)'
  'eq(if(a,b,false),if(b,a,false))'
  'if(eq(a,b),if(a,false,true),if(b,true,false))'
)
# The last expression evaluates true,true,false,false in the documented input order.
masks=(1001 0111 0110 1111 1100)
for i in "${!expressions[@]}"; do
  cat > "$scratch/case.doc" <<DOC
source a: bool = false
source b: bool = false
derive chosen: bool (a,b) = ${expressions[$i]}
DOC
  index=0
  for a in false true; do
    for b in false true; do
      expected=false
      if [[ ${masks[$i]:index:1} == 1 ]]; then expected=true; fi
      actual=$("$goose" "$scratch/case.doc" "$a" "$b")
      [[ $actual == "DOC_GOOSE_RESULT=$expected" ]] || { echo "Goose mismatch case=$i a=$a b=$b got=$actual" >&2; exit 1; }
      for workers in 1 2 4; do
        output=$(DOC_WORKERS="$workers" "$rust" "$scratch/case.doc" "a=$a" "b=$b")
        expected_output=$(printf 'a: %s\nb: %s\nchosen: %s' "$a" "$b" "$expected")
        [[ $output == "$expected_output" ]] || { echo "Rust mismatch case=$i a=$a b=$b workers=$workers got=$output" >&2; exit 1; }
      done
      printf 'PASS case=%s a=%s b=%s result=%s workers=1,2,4\n' "$i" "$a" "$b" "$expected" >> "$logs/composed-boolean.log"
      ((index+=1))
    done
  done
done
