#!/usr/bin/env bash
# Real X11 events, not injected replay commands or a mock window.
set -euo pipefail
scene=$1
file=$2
log=$3
DOC_GPU_ALLOW_SOFTWARE=1 "$scene" "$file" --window --verify-pixels >"$log" 2>&1 &
pid=$!
trap 'kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true' EXIT
await_record() {
  for _ in $(seq 1 200); do
    if grep -Eq "$1" "$log"; then return 0; fi
    if ! kill -0 "$pid" 2>/dev/null; then cat "$log"; return 1; fi
    sleep .05
  done
  cat "$log"
  return 1
}
await_record '^DOC_SCENE_PRESENTED: epoch=0$'
id=$(xdotool search --onlyvisible --name '^DOC_SCENE_FRAME:' | head -n1)
xdotool windowfocus --sync "$id"
xdotool key j
await_record '^DOC_SCENE_INPUT: key=j$'
await_record '^DOC_SCENE_FRAME:.*next_elevation=24 '
xdotool key d
await_record '^DOC_SCENE_INPUT: key=d$'
await_record '^DOC_SCENE_FRAME:.*next_x=2 '
xdotool windowsize "$id" 640 480
await_record '^DOC_SCENE_RESIZE: 640x480$'
# Require a new successful presentation AFTER the native resize notification.
for _ in $(seq 1 200); do
  if awk '/^DOC_SCENE_RESIZE: 640x480$/{seen=1} seen&&/^DOC_SCENE_PRESENTED:/{ok=1} END{exit !ok}' "$log"; then break; fi
  sleep .05
done
awk '/^DOC_SCENE_RESIZE: 640x480$/{seen=1} seen&&/^DOC_SCENE_PRESENTED:/{ok=1} END{exit !ok}' "$log"
xdotool key Escape
wait "$pid"
trap - EXIT
echo DOC_SCENE3D_X11_INPUT_RESIZE_PASS
