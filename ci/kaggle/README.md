# Native Rust physical WebGPU on Kaggle — validated host-only repair

The NVIDIA Tesla T4 graphics userspace package was missing in the Kaggle
notebook image even though NVIDIA CUDA/device nodes were present.
[An isolated exact-SHA experiment](https://github.com/rtu0/DOC/actions/runs/45116122612)
proved that installing `libnvidia-gl-<actual NVIDIA driver major>` and
`libvulkan1` into the **temporary Kaggle notebook host** exposes the
physical T4 through Rust `wgpu`. 42/42 signed GPU episodes and 62/62 authored
DOC CPU/GPU source parity cases passed at pinned native source
`be76df5b59273fde3394cbd6bb9e0eb05325684d`. The precise driver
branch is discovered per session; never hard-code the Colab/Kaggle 580
version, set native graphics API overrides, or perform driver selection
in DOC. This host provision is OS infrastructure only, not a new
GPU backend or a DOC runtime dependency.

All physical admissions require actual `DiscreteGpu`/`IntegratedGpu`
from `wgpu`, genuine WGSL dispatch, typed readback and exact-commit
source comparisons. Missing GPU quota/packages/device results are
INFRA_BLOCKED/failed CI, never a fake green physical test. Report raw
logs and benchmark regressions independently of Linux software-adapter
checks. Free Kaggle quota is not guaranteed.

---

# DOC Kaggle Rust WebGPU hardware tests

**Only Rust `wgpu` and WGSL are active.** The old Goose/SDL3 compute
implementation is preserved as deprecated source, not a release dependency.
No DOC code selects a native graphics API or edits a driver configuration.

## Exact-SHA physical validation

The trusted [Rust Linux CI](../../.github/workflows/doc-validation.yml)
runs the active CPU and WebGPU software-adapter tests, then publishes native
Rust binaries only after successful source/negative tests. The
[Kaggle workflow](../../.github/workflows/doc-kaggle-gpu.yml) is triggered
by a successful trusted push run or can be started explicitly. The
dispatcher checks Kaggle's actual GPU quota and authenticated access.

An exact-commit package includes the three Rust binaries
(`webgpu_bool`, `webgpu_integer_eq`, `doc-rust-gpu`), vetted authored
DOC source/oracle cases, SHA256 file manifest and the source CI run ID.
No platform graphics tools or native graphics loader libraries are
bundled. The notebook downloads a **private** archive, accepts a mounted
input only on complete SHA256 match and validates each extracted file.
GitHub authentication and Kaggle secrets are never uploaded.

The WebGPU provider in the Rust runtime chooses its own native device.
The source and CI **never** inspect native driver configuration or force
a platform GPU API. The physical evidence is admitted only if actual Rust
compute returns from a WebGPU `DiscreteGpu` or `IntegratedGpu`, and
the same authored DOC program matches CPU and independent expected values.
A software adapter, failed device, missing artifact, incomplete readback,
invalid/partial state or mismatched SHA is a hard failure.

## Required evidence

- **42** signed Rust GPU episodes across comparison operators and lane
  widths; 1/multiworkgroup and staged operations must really run.
- **62** selected `doc FILE.doc --backend=gpu` authored Boolean/integer
  source cases, paired with `--backend=cpu` and independent oracles.
- `report/rust-gpu-conformance.log` contains the actual signed case count.
- `report/doc-selected-gpu-equivalence.log` contains case details and the
  exact 62-case marker.
- `report/webgpu-device-admission.log` contains 62 WebGPU physical-adapter
  records and is revalidated by the GitHub-side verifier.
- Whole-process shuffled benchmark distributions, cold/warm observations,
  actual device/workgroup metadata and failure outputs are preserved.
  Never turn a negative speedup or missing benchmark into a superiority claim.

The account and Kaggle platform control GPU quota, timing and accelerator
availability. DOC imposes **no artificial weekly run cap, quota reserve,
session limit, automatic-stop threshold or limit on repeated valid trials**.
Invalid credentials, absent input attachment and hardware failures must
retain distinct diagnostics.

## Private archive transport recovery

Kaggle has previously preserved opaque `.bin` bytes while inconsistently
listing `.tar.gz` files. The submitted file is named
`doc-gpu-bundle.bin` but its bytes remain a gzip-compressed tar archive.
The dispatcher verifies private downloaded archive bytes before submission.
For a failed authenticated private status endpoint, the same account can
use a verified private download as evidence; no status-only success can
replace byte-level integrity. A missing notebook mount may trigger a
narrow, exact-SHA/same-dataset retry. Other failures never count as passes.

**Acceptance is still pending** until complete actual physical Rust WebGPU
execution, exact-SHA CI success, benchmark and release evidence are recorded
in [#9](https://github.com/imxade/DOC/issues/9).
