#!/usr/bin/env bash
# Independent oracle for all 64 initial/updated three-source Boolean assignments.
set -euo pipefail
native=$1
rust=$2
logs=$3
fixture=runtime-rust/examples/boolean_network.doc
: > "$logs/goose-named-differential.log"
oracle() {
  local a=$1 b=$2 c=$3
  local ab=false bc=false both=false chosen=false
  if [[ $a == "$b" ]]; then ab=true; fi
  if [[ $b == "$c" ]]; then bc=true; fi
  if [[ $ab == true && $bc == true ]]; then both=true; fi
  if [[ $c == true ]]; then
    chosen=$both
  elif [[ $both == false ]]; then
    chosen=true
  fi
  printf 'a: %s\nb: %s\nc: %s\neq_ab: %s\neq_bc: %s\nboth: %s\nchosen: %s' \
    "$a" "$b" "$c" "$ab" "$bc" "$both" "$chosen"
}
for a in false true; do
 for b in false true; do
  for c in false true; do
   for next_a in false true; do
    for next_b in false true; do
     for next_c in false true; do
      result=$("$native" "$fixture" "a=$a" "b=$b" "c=$c" --next \
         "a=$next_a" "b=$next_b" "c=$next_c")
      first=$(printf '%s\n' "$result" | sed '/^DOC_GOOSE_NEXT$/,$d' | sed '/^DOC_GOOSE_EVALUATIONS=/d')
      second=$(printf '%s\n' "$result" | sed '1,/^DOC_GOOSE_NEXT$/d' | sed '/^DOC_GOOSE_EVALUATIONS=/d')
      one=$(oracle "$a" "$b" "$c")
      two=$(oracle "$next_a" "$next_b" "$next_c")
      rust_one=$(DOC_WORKERS=1 "$rust" "$fixture" "a=$a" "b=$b" "c=$c" 2>/dev/null)
      rust_two=$(DOC_WORKERS=4 "$rust" "$fixture" "a=$next_a" "b=$next_b" "c=$next_c" 2>/dev/null)
      if [[ "$first" != "$one" || "$second" != "$two" ||
            "$rust_one" != "$one" || "$rust_two" != "$two" ]]; then
        echo "Named-source mismatch: $a,$b,$c -> $next_a,$next_b,$next_c" >&2
        exit 1
      fi
      if [[ "$a" == "$next_a" && "$b" == "$next_b" && "$c" == "$next_c" ]]; then
        [[ "$(printf '%s\n' "$result" | tail -n 1)" == DOC_GOOSE_EVALUATIONS=0 ]] ||
          { echo 'Unchanged sources reevaluated' >&2; exit 1; }
      fi
      printf 'PASS %s,%s,%s -> %s,%s,%s\n' \
        "$a" "$b" "$c" "$next_a" "$next_b" "$next_c" >> "$logs/goose-named-differential.log"
     done
    done
   done
  done
 done
done
for bad in 'a=invalid' 'chosen=true' 'missing=true' 'a=true a=false' '--next --next'; do
  set -- $bad
  if "$native" "$fixture" "$@" > "$logs/goose-named-negative.log" 2>&1; then
    echo "Invalid source batch accepted: $bad" >&2
    exit 1
  fi
  grep -Fx DOC_GOOSE_GRAPH_ERROR "$logs/goose-named-negative.log"
done
echo DOC_GOOSE_NAMED_CONFORMANCE_PASS | tee -a "$logs/goose-named-differential.log"
