# Development target and validation batching

The sole active development repository is x0796666-ui/doc2, main. Original rtu0/doc2 is historical and must not receive engineering commits or CI requests.

## Exact tracked snapshot

Imported source commit: ea58334a3209f8b599f3fef22e0a103c58512b45.
Source root tree: 08d15da0d4078e26eff67d81d6d0d6fba378e922.
Destination baseline commit: 0e1b7e6a1f0316e1833b6773b84caf206d8a8e46 (branch imported-source-baseline).
All 722 tracked files and file modes are preserved by exact tree equality. Frozen runtime-rust tree: a95a38bc6e9300aae815f83b570db5f99d32f221. No changes to the Rust reference are authorized.

This is an exact snapshot, not imported historical commit ancestry. Old GitHub-hosted Actions artifacts and run records are not copied by Git tree migration. The four issue mirrors and all 57 original comments were copied and verified. Historical evidence remains attributable to its original source/run; do not relabel it as exact CI for this repository.

## Batch-first CI policy

Implement a meaningful batch, run available local tests and inspect the exact diff before requesting CI. Normal source commits do not launch workflows. The independent workflow runs on manual dispatch or a deliberate main-branch change to ci/independent-batch-request.txt. Change that marker only for an intentional, consolidated validation batch; do not change it for individual small edits. Include the intended tested source and local evidence in the request commit. Do not use [skip ci] in a validation-request commit. CI results must be verified for the requested revision; do not infer a pass from queued jobs. The frozen Rust Linux and Kaggle workflows and the no-GPU permission diagnosis are manual-only, preserving quota; independent physical GPU validation requires its own exact-source proof. Kaggle credentials and username variable must be configured in the new repository independently.

Canonical requirements remain imxade/DOC #11 then #9, before #14. No acceptance gate is waived by migration.
