# Goose-native WebGPU boundary: W1 FFI probe (NOT GPU acceptance)

This directory is independent of `gfx`, SDL3 and the Rust DOC runtime.
`abi_probe.c` is a **C ABI test library**, not a WebGPU provider or
DOC GPU evaluator. `ffi_probe.goose` binds that library with Goose's native
`extern "lib"` support, copies signed i32 payloads, and verifies invalid
arguments cannot mutate output buffers.

```sh
gcc -std=c11 -O2 -Wall -Wextra -Werror -fPIC -shared \
  runtime-goose/webgpu/abi_probe.c -o libdoc_gpu_ffi_probe.so
LD_LIBRARY_PATH="$PWD" goose run runtime-goose/webgpu/ffi_probe.goose
```

**W1 still open:** actual version-pinned Dawn `webgpu.h` and loadable native
WebGPU library; callback-safe adapter, opaque device/queue/buffer handles,
device-loss and mapping error paths. Do **not** accept a mock library or
successful ABI transport as a WebGPU compute backend. W2 requires Goose's
independent WGSL to be executed on a real WebGPU device, with typed DOC output
and raw evidence. The existing Goose SDL3 path cannot be deleted until the
independent replacement is proven under W2-W7. No C DOC evaluation logic is
permitted in the eventual adapter.
