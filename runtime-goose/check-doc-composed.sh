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
# Independent per-case Boolean oracle; avoids transcription errors in bit masks.
oracle() {
  local case_id=$1 a=$2 b=$3
  case "$case_id" in
    0) [[ "$a" == "$b" ]] ;;
    1) [[ "$a" == false && "$b" == true || "$a" == true ]] ;;
    2) [[ "$a" == true && "$b" == false || "$a" == false && "$b" == true ]] ;;
    3) return 0 ;; # (a AND b) equals (b AND a)
    4) [[ "$a" == false ]] ;;
    *) return 2 ;;
  esac
}

for i in "${!expressions[@]}"; do
  cat > "$scratch/case.doc" <<DOC
source a: bool = false
source b: bool = false
derive chosen: bool (a,b) = ${expressions[$i]}
DOC
  for a in false true; do
    for b in false true; do
      expected=false
      if oracle "$i" "$a" "$b"; then expected=true; fi
      actual=$("$goose" "$scratch/case.doc" "$a" "$b")
      [[ $actual == "DOC_GOOSE_RESULT=$expected" ]] || { printf "Goose mismatch case=%s a=%s b=%s expected=%s actual=%q\\n" "$i" "$a" "$b" "$expected" "$actual" >&2; exit 1; }
      for workers in 1 2 4; do
        output=$(DOC_WORKERS="$workers" "$rust" "$scratch/case.doc" "a=$a" "b=$b")
        expected_output=$(printf 'a: %s\nb: %s\nchosen: %s' "$a" "$b" "$expected")
        [[ $output == "$expected_output" ]] || { echo "Rust mismatch case=$i a=$a b=$b workers=$workers got=$output" >&2; exit 1; }
      done
      printf 'PASS case=%s a=%s b=%s result=%s workers=1,2,4\n' "$i" "$a" "$b" "$expected" >> "$logs/composed-boolean.log"
    done
  done
done
