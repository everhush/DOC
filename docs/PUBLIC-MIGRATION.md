# Public DOC development migration

Active development: rtu0/doc2, main. Canonical issue numbering and acceptance ledger remain imxade/DOC.

The import parent commit f3327d8ff61d84316282884731022b8cc6dedd98 contains all 596 tracked files of private development branch feat/webgpu-dual-runtime-ci at 142c47958a80df0345bd6c26ec8ad31d9e085a90. A recursive tree comparison verified all paths, modes and blob hashes, with no missing, extra or different file. The original repository remains the history/branch/issue archive; this is a complete working-tree snapshot import, not a mirror of Git history, tags, PRs, or Actions artifacts. No repository secrets or account settings were copied.

The normal Linux CPU and software-WebGPU workflow now validates exact source on the public main branch. Standard GitHub-hosted runner eligibility is governed by GitHub. The repository owner has authorized configured Kaggle physical-GPU jobs on trusted main. No additional variable-based enable gate is required. To pause Kaggle, disable the physical workflow in GitHub Actions. Only trusted main pushes (after successful exact-SHA native validation) and main manual dispatches can run physical work. Credentials remain in repository secrets and fail closed when missing or invalid; no software adapter is physical GPU evidence.

Canonical [#22](https://github.com/imxade/DOC/issues/22) remains open until the integrated DOC-authored Radar Chase and real automatic CPU-thread/WebGPU mixed-frontier execution pass exact-source validation with negative cases, worker parity, replay, resource/latency measurement and honest adapter labels. Canonical [#11](https://github.com/imxade/DOC/issues/11) must not begin before the gate passes. The earlier scoped #10 closure and deferred #21 GUI/assets/3D remain unchanged.

## Single-branch development

Use `main` exclusively. The green strengthened development revision `770e64692e5753c02eecd92746d9eed364d34f4b` and exact archive snapshots `97156e3124e133c416f6f933f59fc98d52707749` (private master), `b7fa2028a4a3c65f22d85d54b53b22e4c8ff64b9` (Kaggle experiment) are retained as parents of the consolidation commit, without merging obsolete files into the active tree. Redundant public branch refs can be deleted after that ancestry is verified; private source/history stays intact. Native CI and physical validation are main-only.

The one-time branch cleanup [45323278639](https://github.com/rtu0/doc2/actions/runs/45323278639) passed, preserving all three tips in main ancestry and atomically deleting their redundant refs. The temporary contents-write workflow has been removed; ordinary CI has read-only contents access.
