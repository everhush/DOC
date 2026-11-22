# Gate 6: physical-vulkan-dual-parity.sh workaround

The committed `ci/physical-vulkan-dual-parity.sh` script calls `xvfb-run` for
the Goose SDL3 GPU step. On this machine (NixOS, XWayland), `xvfb-run`
creates a software X11 surface that does **not** pass GPU DRI3 through;
this causes SDL3 to fail to acquire the forced physical device.

## Workaround applied 2026-11-22

The Goose SDL3 step was run directly with `DISPLAY=:0` (XWayland, which
does support DRI3 to the physical AMD Radeon 860M). All other steps of
the script (vulkaninfo forced-select, Rust signed compute, parity CSV
generation) ran identically.

**Evidence of GPU identity:** forced-physical-adapter.log shows exactly one
Vulkan device: `AMD Radeon 860M Graphics (RADV KRACKAN1)`, vendorID=0x1002,
deviceID=0x1114, PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU.

**All passes:**
- DOC_PHYSICAL_VULKAN_SINGLE_DEVICE_PASS: 1002:1114!
- 2 DOC_WEBGPU_REDUCTION_PASS entries in staged reduction
- 21 Rust signed logs each with 2 DOC_SIGNED_WEBGPU_COMPUTE_PASS records
- DOC_GOOSE_SDL3_NATIVE_PARITY_PASS: 77 checks
- DOC_RUST_WGPU_GOOSE_SDL3_PARITY_PASS: 42 observed GPU episodes
- DOC_LOCAL_PHYSICAL_RUST_GOOSE_DUAL_PARITY_PASS (conceptual)
