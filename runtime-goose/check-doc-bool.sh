#!/usr/bin/env bash
set -euo pipefail

goose=${1:?Pass the path to the Goose compiler}
logs=${2:?Pass a directory for the validation logs}
mkdir -p "$logs"
scratch=$(mktemp -d)
trap 'rm -rf -- "$scratch"' EXIT
native="$scratch/doc-bool"
fixture=runtime-rust/examples/boolean_conditional.doc

"$goose" check runtime-goose/doc_bool.goose 2>&1 | tee "$logs"/goose-doc-check.log
"$goose" build runtime-goose/doc_bool.goose --offline -o "$native" 2>&1 | tee "$logs/goose-doc-build.log"
: > "$logs/goose-doc-truth-table.log"
for a in false true; do
  for b in false true; do
    actual=$("$native" "$fixture" "$a" "$b")
    if [[ "$a" == "$b" || "$a" == false ]]; then expected=true; else expected=false; fi
    printf '%s,%s expected=%s actual=%s\n' "$a" "$b" "$expected" "$actual" | tee -a "$logs"/goose-doc-truth-table.log
    test "$actual" = "DOC_GOOSE_RESULT=$expected"
  done
done
if "$native" "$fixture" invalid true > "$logs"/goose-doc-negative.log 2>&1; then
  echo 'Goose DOC accepted invalid boolean input' >&2
  exit 1
fi
grep -Fx 'DOC_GOOSE_ERROR' "$logs"/goose-doc-negative.log
for kind in duplicate-source missing-source malformed-expression unknown-identifier trailing-expression premature-definition too-deep; do
  negative="$logs/goose-negative-${kind}.doc"
  case "$kind" in
    duplicate-source) cat "$fixture" > "$negative"; printf 'source a: bool = true\n' >> "$negative" ;;
    missing-source) grep -v '^source b:' "$fixture" > "$negative" ;;
    malformed-expression) sed 's/eq(a,b)/eq(a,)/' "$fixture" > "$negative" ;;
    unknown-identifier) sed 's/eq(a,b)/eq(a,c)/' "$fixture" > "$negative" ;;
    premature-definition) { tail -n 1 "$fixture"; head -n 2 "$fixture"; } > "$negative" ;;
    too-deep)
      head -n 2 "$fixture" > "$negative"
      {
        printf 'derive chosen: bool (a,b) = '
        for ((i = 0; i < 128; i++)); do printf 'eq(a,'; done
        printf 'b'
        for ((i = 0; i < 128; i++)); do printf ')'; done
        printf '\n'
      } >> "$negative"
      ;;
    trailing-expression) sed 's/eq(a,b)/eq(a,b)garbage/' "$fixture" > "$negative" ;;
  esac
  if "$native" "$negative" true false > "$logs/goose-negative-${kind}.log" 2>&1; then
    echo "Goose DOC accepted invalid ${kind} source" >&2
    exit 1
  fi
  grep -Fx 'DOC_GOOSE_ERROR' "$logs/goose-negative-${kind}.log"
done
