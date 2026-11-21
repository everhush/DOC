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
