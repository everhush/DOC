# Kaggle physical-GPU offload for DOC

The ordinary **DOC dual-runtime validation** pipeline retains Rust and Goose CPU execution, deterministic CPU fallback, oracle comparisons, portability, and Mesa **software-Vulkan** checks. Those Mesa jobs use GitHub CPU resources and never count as proof of a physical GPU.

The new **DOC Kaggle physical GPU parity (quota gated)** workflow offloads *hardware* GPU verification to a private Kaggle script running the exact trusted commit. It independently builds native Rust with wgpu and native Goose with SDL3 gfx, requires a physical NVIDIA Vulkan ICD, executes Goose's 77 GPU/CPU oracle checks, then compares 42 Rust wgpu versus Goose SDL3 result episodes. CUDA visibility alone is **not** DOC GPU support; Vulkan-less Kaggle sessions fail closed and retain diagnostics. TPU, Metal and D3D12 need different hardware and are not implied by this notebook.

## Setup

The secondary repository GitHub Actions secret must be named **KAGGLE_DOC_1**. It may contain a raw Kaggle API token or a legacy kaggle.json object with username and key. When using a raw token also set GitHub **repository variable DOC_KAGGLE_USERNAME** to the owner username. The private Kaggle kernel is uniquely named for each GitHub run. The credentials stay exclusively on GitHub and are not embedded in the kernel.

Manual dispatch is available once GitHub recognizes the workflow on the default branch. **DOC_KAGGLE_AUTORUN=true** is an optional repository variable that enables automatic offload after a successful trusted push CI; default is **OFF** to protect weekly quota. Manual and automatic submissions use the same strict policy.

## GPU quota controls

- Check **live GPU remaining hours** via `kaggle quota --format json` before every submission. Do not assume 30 GPU hours or infer GPU quota from AI benchmark quota.
- At most **two DOC submissions per rolling seven days**, including cancelled and failed attempts, maximum **30 remote minutes per submission** (manual 15/20/30).
- Retain at least **2 hours of account GPU quota** *after* the proposed run; other users' notebooks still count against the live account total.
- Serialize GitHub Kaggle jobs and **never auto-cancel** a remote kernel; cancelling GitHub alone does not terminate a Kaggle session. Kaggle push sets a remote session timeout.
- If quota, API state, source SHA, physical Vulkan adapter, or full 77/42 parity evidence cannot be verified, **never report hardware parity success**.

Run the policy tests locally, without consuming quota:
`python3 -m unittest discover -s ci/kaggle -p 'test_*.py' -v`

Evidence is retained in GitHub artifacts (`doc-kaggle-summary.json`, raw GPU parity logs, quota preflight). See [Kaggle CLI kernel docs](https://github.com/Kaggle/kaggle-cli/blob/main/docs/kernels.md), [Kaggle CLI quota](https://github.com/Kaggle/kaggle-cli/blob/main/CHANGELOG.md), and [Kaggle authentication](https://github.com/Kaggle/kaggle-cli/blob/main/skills/references/auth.md).

The dispatcher reads the owner from `kaggle config view` for modern raw tokens when `DOC_KAGGLE_USERNAME` is not set; if Kaggle cannot resolve it, set the variable. Workflow reruns are refused to avoid duplicate GPU spend. Result verification checks the archived native 77/42 pass markers, NVIDIA hardware-adapter information, exact source SHA and selected quota-limited accelerator.

If Kaggle exposes CUDA but no NVIDIA Vulkan ICD, the native notebook can attempt to install only `libnvidia-gl-<nvidia-smi driver branch>` from the image's configured APT repository, with a strict 220-second cap. This is user-space Vulkan support only, never an in-container kernel-driver override. It then rechecks a physical Vulkan device and fails closed on missing or incompatible drivers; no CUDA-only or llvmpipe run counts as DOC GPU parity.

The native GPU session can optionally record 54 random-interleaved Rust/Goose signed-equality/ordering CLI timings (plus 12 warmups) from exactly the same DOC inputs and verified GPU outputs, with raw CSV and median/p95 JSON. This is *end-to-end CLI timing* (including startup, SDL3 Xvfb, pipeline creation, transfers, dispatch and readback), **not** isolated GPU kernel latency or a claim of speedup. A remaining-time guard can skip this benchmark without misreporting the independently verified 77/42 hardware correctness result.

**Kaggle bootstrap reliability (after first real run #44950662134):** A T4 notebook was genuinely created and quota passed with 30h preflight remaining, but unconditional `apt-get update` timed out at 260 seconds *before any DOC GPU code ran*. The revised bootstrap now checks NVIDIA hardware first, detects installed APT packages and skips update/install entirely when possible. It uses pre-existing package metadata first and allows only one short bounded update/retry if essential libraries are missing. Timed-out APT commands preserve diagnostic logs and step metrics. The first session counts against the maximum two DOC attempts in a rolling week; do not claim GPU parity from that failed bootstrap.

## Quota-efficient prebuilt native execution (new)

The first real Kaggle T4 session failed **before GPU testing** because an unconditional `apt-get update` stalled for 260 seconds. For subsequent runs, **GitHub's standard CPU/Mesa CI builds and tests all the native Rust wgpu and Goose SDL3 executables**. Each successful exact-SHA standard CI run publishes a portable Rust Vulkan bundle, a statically linked native Goose SDL3 binary, and Xvfb helpers. The secret-backed GitHub Kaggle controller validates the source SHA and standard CI result, downloads those two verified artifacts with its GitHub token, packages the identical DOC source and parity oracles into a private Kaggle input dataset, verifies readiness and **only then** submits a GPU notebook. Kaggle no longer runs `apt-get update`, builds either runtime, or fetches DOC/Goose source. It just verifies the bundle hash, tests physical NVIDIA Vulkan availability, runs the native GPU programs and saves parity/optional latency measurements.

Private Kaggle datasets use upstream-license-preserving `other` metadata because Xvfb/Vulkan helper executables are third-party artifacts. Dataset uploads use Kaggle storage/API but **do not allocate a GPU session**. A missing NVIDIA graphics/Vulkan ICD is an infrastructure block; this path does **not** install GPU kernel drivers, call CUDA as if it were Vulkan, or count Mesa llvmpipe as physical GPU parity. Automatic GPU reruns remain disabled. <https://github.com/Kaggle/kaggle-cli/blob/main/docs/kernels_metadata.md> documents the private notebook `dataset_sources` contract.
