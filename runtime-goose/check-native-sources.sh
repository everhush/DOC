#!/usr/bin/env bash
# DOC-owned runtime source must be written in native Rust and native Goose.
# Host compiler / OS device drivers are external toolchain components.
set -euo pipefail
if find runtime-rust runtime-goose -type f \
   \( -name '*.c' -o -name '*.cc' -o -name '*.cpp' -o -name '*.cxx' \
      -o -name '*.h' -o -name '*.hpp' -o -name '*.hxx' \) | grep -q .; then
    echo 'Forbidden C or C++ runtime source detected' >&2
    exit 1
fi
if grep -REn 'extern[[:space:]]*"C"|unsafe[[:space:]]*extern|#include[[:space:]]*[<"]|__attribute__\(' \
    runtime-rust/src runtime-goose --include='*.rs' --include='*.goose'; then
    echo 'Forbidden C ABI or C/C++ runtime code detected' >&2
    exit 1
fi
# Keep rejected Goose WGSL and Rust GPU bridge code permanently absent.
if grep -REn 'fn[[:space:]]+shader_index\(|fn[[:space:]]+shader_expr\(|fn[[:space:]]+emit_shader\(|fn[[:space:]]+emit_signed_equality\(|--emit-wgsl|wgpu::' \
  runtime-goose --include='*.goose'; then
    echo 'Obsolete Goose WGSL generator or Rust GPU bridge detected' >&2
    exit 1
fi
echo DOC_NATIVE_RUST_GOOSE_SOURCE_POLICY_PASS
