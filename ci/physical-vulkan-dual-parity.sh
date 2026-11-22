#!/usr/bin/env bash
# Local Linux/Mesa physical-device proof for independent DOC GPU runtimes.
# No quota, time, deduplication, or retry restrictions are imposed here.
set -euo pipefail

if [ "$#" -ne 4 ]; then
  echo "usage: DOC_HW_VK_SELECT=vid:did! bash ci/physical-vulkan-dual-parity.sh RUST_BOOL RUST_SIGNED GOOSE_SDL3 EVIDENCE_DIR" >&2
  exit 2
fi
rust_bool=$1
rust_signed=$2
goose_bin=$3
out=$4

selector=${DOC_HW_VK_SELECT:-}
if ! [[ $selector =~ ^[[:xdigit:]]{4}:[[:xdigit:]]{4}!$ ]]; then
  echo "Specify DOC_HW_VK_SELECT as Mesa vid:did! (for example 1002:1114!)" >&2
  exit 2
fi
for program in vulkaninfo xvfb-run python3; do
  command -v "$program" >/dev/null || { echo "Missing $program" >&2; exit 2; }
done
for program in "$rust_bool" "$rust_signed" "$goose_bin"; do
  test -x "$program" || { echo "Not executable: $program" >&2; exit 2; }
done

mkdir -p "$out/rust" "$out/goose/goose-sdl3" "$out/parity"
# The Mesa device-select layer (not the GPU runtime) must expose ONLY the
# requested PCI device. If it cannot, fail instead of certifying software
# Vulkan as a physical GPU. Preserve this exact environment for BOTH hosts.
export MESA_VK_DEVICE_SELECT="$selector"
export MESA_VK_DEVICE_SELECT_DEBUG=1
{
  printf 'DOC source SHA: '
  git rev-parse HEAD
  printf 'Vulkan device filter: %s\n' "$MESA_VK_DEVICE_SELECT"
  printf 'OS/kernel: '
  uname -srmo
} > "$out/physical-run-metadata.log"

vulkaninfo --summary > "$out/forced-physical-adapter.log" 2>&1
python3 - "$out/forced-physical-adapter.log" "$MESA_VK_DEVICE_SELECT" <<'PY'
import pathlib, re, sys
log = pathlib.Path(sys.argv[1]).read_text(errors="replace")
selector = sys.argv[2]
vid, did = (int(x, 16) for x in selector[:-1].split(":"))
devices = re.findall(r"(?ms)^GPU\d+:\s*\n(.*?)(?=^GPU\d+:|\Z)", log)
if len(devices) != 1:
    raise SystemExit(f"physical GPU proof blocked: expected ONLY one Vulkan device, found {len(devices)}")
data = devices[0]
def field(name):
    m = re.search(r"(?m)^\s*" + re.escape(name) + r"\s*=\s*(\S+)", data)
    if not m:
        raise SystemExit(f"physical GPU proof blocked: missing {name}")
    return m.group(1)
if field("deviceType") not in ("PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU", "PHYSICAL_DEVICE_TYPE_DISCRETE_GPU"):
    raise SystemExit("physical GPU proof blocked: selected device is not physical GPU")
if int(field("vendorID"), 16) != vid or int(field("deviceID"), 16) != did:
    raise SystemExit("physical GPU proof blocked: selected Vulkan PCI IDs disagree")
print("DOC_PHYSICAL_VULKAN_SINGLE_DEVICE_PASS:", selector, field("deviceName"))
PY

# A real physical hardware requirement is part of correctness, not a usage cap.
export DOC_GPU_REQUIRE_HARDWARE=1
export DOC_GPU_EXECUTION=gpu
DOC_GPU_REDUCTION=1 "$rust_bool" --staged-repair > "$out/rust/rust-staged-reduction.log" 2>&1
test "$(grep -c '^DOC_WEBGPU_REDUCTION_PASS:' "$out/rust/rust-staged-reduction.log")" = 2

for mode in eq lt le; do
  for lanes in 1 63 64 65 129 257 1024; do
    target="$out/rust/rust-$mode-$lanes.log"
    if [ "$mode" = eq ]; then
      DOC_GPU_LANES="$lanes" "$rust_signed" > "$target" 2>&1
    else
      DOC_GPU_LANES="$lanes" "$rust_signed" "--$mode" > "$target" 2>&1
    fi
    grep -Eq '^DOC_SIGNED_WEBGPU_ADAPTER: .*type=(IntegratedGpu|DiscreteGpu) .*backend=Vulkan ' "$target" || {
      echo "Physical Vulkan adapter not identified by Rust: $target" >&2
      exit 1
    }
    test "$(grep -c '^DOC_SIGNED_WEBGPU_COMPUTE_PASS:' "$target")" = 2
  done
done

# xvfb-run provides an X11 surface, NOT GPU acceleration. Mesa's device
# selection above must still expose only the physical device to Goose.
xvfb-run -a env GOOSE_GFX_HEADLESS=1 SDL_VIDEODRIVER=x11 SDL_GPU_DRIVER=vulkan \
  python3 runtime-goose/check-doc-sdl3-gpu.py \
  "$goose_bin" "$out/goose/goose-sdl3"
grep -Fx 'DOC_GOOSE_SDL3_NATIVE_PARITY_PASS: 77 checks' \
  "$out/goose/goose-sdl3/doc-goose-sdl3-summary.log"

python3 runtime-goose/check-dual-gpu-parity.py \
  "$out/rust" "$out/goose" "$out/parity"
grep -Fx 'DOC_RUST_WGPU_GOOSE_SDL3_PARITY_PASS: 42 observed GPU episodes' \
  "$out/parity/native-gpu-equivalence.log"

echo "DOC_LOCAL_PHYSICAL_RUST_GOOSE_DUAL_PARITY_PASS"
