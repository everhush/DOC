# Physical GPU validation evidence — local NixOS workstation

This directory contains the unedited text logs committed by the local agent in
`feat/physical-gpu-parity`, at commit
`b8111b6f601ab152307b13cc78e3e3f2489e00eb`. The source code under test was the branch base
`70394f1b65ee6d6ddad348cf497eb9b6f1fa8d52`.

## Local hardware and observations

- CPU: AMD Ryzen AI 7 350 (16 logical cores); RAM: approximately 24 GB
- Physical Vulkan adapter: AMD Radeon 860M (RADV KRACKAN1), Mesa 26.3.0,
  NixOS kernel 6.18.62. `vulkan-adapter.log` also shows an available CPU
  llvmpipe device; its presence is NOT proof that every client selected AMD.
- Rust wgpu logs print selected **IntegratedGpu** (vendor 4098, device 4372)
  via Vulkan RADV. Staged repair, 42 eq/lt/le observations and failure
  boundaries are retained in `rust/`.
- Native Goose SDL3 logs in `goose/goose-sdl3/` print
  `DOC_GOOSE_SDL3_DEVICE: vulkan`, 77 independent SDL3 oracle checks and
  42 matching observed GPU-result episodes. However, **SDL3 logs expose
  the Vulkan backend, not the selected GPU device name/type**. They do
  not independently rule out Goose selecting llvmpipe. This is an OPEN
  device-identity proof obligation, not an excuse to discard observed parity.
- `parity/native-gpu-equivalence.csv` stores 42 per-operation, per-epoch
  result counts. `goose/benchmark-typed.log` reports medians and p95
  for 31 samples per runtime/worker count; underlying individual
  timing samples were not committed, and kernel-only timings were not
  measured. These remain necessary for complete reproducible benchmarking.
- These are **local-agent submitted evidence artifacts**, not tests newly
  executed by GitHub Actions on physical GPU. Verify source revision,
  device selection and exact logs before declaring the broader DOC
  physical realization contract fully accepted.

## Reproduction

See `runtime-goose/README.md`,
`.github/workflows/doc-validation.yml` and secondary
[Issue #1](https://github.com/x0796666-ui/DOC/issues/1).
The local source test harnesses include
`runtime-goose/check-doc-sdl3-gpu.py`,
`runtime-goose/check-dual-gpu-parity.py`,
`runtime-goose/benchmark-matched.py` and
`runtime-goose/bench-workers.py`.

Do not claim release readiness solely from physical GPU parity. The
non-game acceptance contracts in issue #1/#7 include lifetime,
reclamation/reconstruction, typed failures, placement/transport,
complete paper-ordered evidence, and distributable release QA.
