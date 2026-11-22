#!/usr/bin/env bash
# Black-box CPU/default and strict backend-rejection contract in both native CLIs.
set -euo pipefail
if [ "$#" -ne 2 ]; then
  echo "usage: bash $0 DOC_EXECUTABLE DOC_SOURCE" >&2
  exit 2
fi
bin=$1
source=$2
test -x "$bin"
test -f "$source"
scratch=$(mktemp -d)
trap 'rm -rf -- "$scratch"' EXIT
"$bin" "$source" a=4 b=1 > "$scratch/default" 2> "$scratch/default.err"
"$bin" "$source" --backend=cpu a=4 b=1 > "$scratch/cpu" 2> "$scratch/cpu.err"
diff -u "$scratch/default" "$scratch/cpu"
grep -Fx 'chosen: 10' "$scratch/cpu"
# Verify the offset remains correct for nontrivial DOC CLI modes as well.
fixtures=$(dirname "$source")
demand="$fixtures/demand_lazy.doc"
recurrence="$fixtures/recurrence_halt.doc"
previous="$fixtures/versions/old.doc"
replacement="$fixtures/versions/compatible.doc"
for scenario in demand recurrence replacement; do
  case "$scenario" in
    demand)
      src=$demand
      set -- --demand=copy a=7
      ;;
    recurrence)
      src=$recurrence
      set -- --until=halt --max-epochs=4 index=successor
      ;;
    replacement)
      src=$previous
      set -- "--replace=$replacement"
      ;;
  esac
  "$bin" "$src" "$@" > "$scratch/$scenario.default"
  "$bin" "$src" --backend=cpu "$@" > "$scratch/$scenario.cpu"
  diff -u "$scratch/$scenario.default" "$scratch/$scenario.cpu"
done
for selected in gpu auto invalid; do
  if "$bin" "$source" "--backend=$selected" a=4 b=1 > "$scratch/$selected" 2>&1; then
    echo "Unsupported backend was accepted: $selected" >&2
    exit 1
  fi
  if [ "$selected" = gpu ]; then
    grep -F 'DOC_GPU_UNSUPPORTED:' "$scratch/$selected"
  else
    grep -F 'DOC_BACKEND_INVALID:' "$scratch/$selected"
  fi
  if grep -Eq '^DOC_WEBGPU_COMPUTE_PASS:|^DOC_GOOSE_SDL3_GPU_PASS:' "$scratch/$selected"; then
    echo "Rejected backend falsely reported GPU execution" >&2
    exit 1
  fi
done

# Selection must happen BEFORE parsing the DOC source or admitting effects.
# GPU is intentionally unsupported by the general-purpose CLIs at this stage,
# so rejecting it may not require even a readable source file.
for selected in gpu auto invalid; do
  if "$bin" "$scratch/nonexistent.doc" "--backend=$selected" > "$scratch/preflight-$selected" 2>&1; then
    echo "Backend preflight accepted unsupported selection: $selected" >&2
    exit 1
  fi
  if [ "$selected" = gpu ]; then
    grep -F 'DOC_GPU_UNSUPPORTED:' "$scratch/preflight-$selected"
  else
    grep -F 'DOC_BACKEND_INVALID:' "$scratch/preflight-$selected"
  fi
done

# A rejected GPU request must not commit an output effect, even when the
# DOC source is valid and an --emit target is present.
cp "$source" "$scratch/effect-source.doc"
if "$bin" "$scratch/effect-source.doc" --backend=gpu --emit=chosen:forbidden.txt \
    > "$scratch/rejected-effect" 2>&1; then
  echo "Unsupported GPU request committed an effect" >&2
  exit 1
fi
grep -F 'DOC_GPU_UNSUPPORTED:' "$scratch/rejected-effect"
if [ -e "$scratch/forbidden.txt" ]; then
  echo "Rejected GPU request created an output file" >&2
  exit 1
fi

# An explicitly selected CPU is allowed to perform the documented effect.
"$bin" "$scratch/effect-source.doc" --backend=cpu --emit=chosen:permitted.txt \
    > "$scratch/cpu-effect" 2>&1
grep -Fx '10' "$scratch/permitted.txt"
echo DOC_EXPLICIT_BACKEND_CLI_PASS
