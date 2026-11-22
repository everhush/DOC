# DOC Kaggle hardware testing

DOC's Kaggle runner follows **the Kaggle account's own GPU quota, available
accelerators, and platform session rules**. The repository adds **no arbitrary
weekly submission cap, quota reserve, maximum GPU session duration, mandatory
wait between tests, ban on reruns, deduplication gate, or workflow concurrency
limit**. Exact repeats are allowed.

## Architecture and usage

The normal GitHub Actions workflow continues native Rust and Goose CPU tests,
software-Vulkan (Mesa) validation, and cross-runtime parity without consuming
Kaggle GPU hours. The separate `.github/workflows/doc-kaggle-gpu.yml` runs
after successful trusted branch validation and can also be started manually.
The workflow submits a private Kaggle GPU notebook, using source and native
Rust `wgpu` and Goose SDL3 binaries built by the successful, exact-SHA CPU CI.
It checks the real remaining GPU balance through `kaggle quota --format json`
and defers to Kaggle's own quota enforcement; only zero/unknown balance blocks
submission. It does not impose DOC-side run-count or time limits.

The private notebook must confirm a **physical Vulkan GPU** (CUDA presence
alone is insufficient) and execute the 77 Goose GPU/CPU oracle checks and
42 independent Rust/Goose GPU-result parity cases. Native timing evidence
includes startup, device/pipeline initialization, dispatch and readback, and
must never be represented as isolated kernel latency or proof of GPU speedup.
The notebook now requires each Vulkan adapter exposed by its selected
NVIDIA ICD to have vendor ID `0x10de` and a physical integrated/discrete GPU
device type. A visible CUDA device or a mixed CPU-software Vulkan inventory
alone cannot certify native Rust/Goose GPU parity. Both the notebook and
the GitHub-side evidence verifier fail closed on incompatible adapter evidence.

Failing hardware access or mismatching results are correctly reported as
blocked/failed, not CPU-fallback GPU success. Metal, Direct3D and TPU require
separate platforms.

## Credentials

Use secret `KAGGLE_DOC_1` on the secondary repository; do not put it in any
notebook, log, source file or dataset. A raw Kaggle API token can use repository
variable `DOC_KAGGLE_USERNAME` for the account owner; legacy Kaggle JSON
credentials include username and key. Ensure the token can read, create and
check private Kaggle datasets and notebooks. Private datasets carry the
precompiled, cryptographically checked native build artifacts; no source
compiler or DOC GPU-host language crossover runs in Kaggle.

## Non-enforced best practices

- Prefer experiments that yield new evidence, but repeat any workload when
  reproducing results or investigating variance. No script blocks duplicates.
- Check Kaggle's real remaining GPU hours and prioritize valuable tests; using
  the whole available allowance is permitted.
- Prefer reviewing a job's output before launching another when debugging
  infrastructure errors, but there is no enforced waiting or run cap.
- Keep verified SHA, device type, raw logs, GPU/CPU parity, sample counts and
  conditions alongside benchmarking results.
- Be aware that GitHub-hosted CI and Kaggle each have their **own platform
  execution limits**. Those external limits are not DOC-created quotas.

Offline verification without Kaggle:
`python3 -m unittest discover -s ci/kaggle -p 'test_*.py' -v`

References: [Kaggle CLI kernel metadata](https://github.com/Kaggle/kaggle-cli/blob/main/docs/kernels_metadata.md),
[Kaggle CLI authentication](https://github.com/Kaggle/kaggle-cli/blob/main/skills/references/auth.md).
