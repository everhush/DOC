# Private development target and validation batching

The sole active development and CI repository is **imxade/DOC, master (private)**, repository ID 1317169134. The former rtu0/doc2 and x0796666-ui/doc2 repositories are historical only. Do not write engineering commits or request CI in them.

## Verified imported source

Latest source: x0796666-ui/doc2 commit `7448e3d13b4ec7cf9ca65c7d540a7aa3afe3dee9`, root tree `5cddf6c411ee9a11ab18c1eb0fd33cb5f5cf7b0c`. The exact snapshot is preserved privately at `967503455da471aa9ab83d4b9bf839704467c739` (branch `imported-development-2026-11-25`). All tracked paths, bytes and modes matched. Independent runtime tree `b89a54654b4569b8a9421c33377e57b2ebbcf51e`; frozen Rust tree `a95a38bc6e9300aae815f83b570db5f99d32f221`. The previous private master and its historical branches remain intact; the previous master is also pinned at `snapshot-master-before-private-migration-2026-11-25`. Five files unique to the older private tree remain on that backup, including the old legacy-branch-pruning workflow, not in the active migrated snapshot.

Earlier source anchor: rtu0/doc2 `ea58334a3209f8b599f3fef22e0a103c58512b45`, root `08d15da0d4078e26eff67d81d6d0d6fba378e922`; x0796666-ui/doc2 baseline `0e1b7e6a1f0316e1833b6773b84caf206d8a8e46` matched that source. This migration retains the private repository's original ancestry and imports an exact source snapshot, not the intervening public repositories' original commit objects. Historical Actions runs and artifacts do not transfer automatically. Preserve attribution to the original runs; do not relabel old evidence as private exact-SHA CI.

## Batch-first validation

Make a substantial implementation batch, run available local regressions, inspect the exact diff, then trigger a consolidated workflow. The independent workflow accepts deliberate changes to `ci/independent-batch-request.txt` on master or manual dispatch; normal source changes do not trigger it. All other validation workflows are manual-only. Repository-ID and branch guards reject execution elsewhere. Update the batch marker only after meaningful local work; do not use [skip ci] in intentional validation requests. Keep the frozen Rust tree unchanged. Verify completed jobs against the actual requested source SHA and inspect failure logs. Independent hardware proof requires actual device execution; the former repository's last consolidated run 45586218364 was cancelled and is not a pass. Configure Kaggle credentials (`KAGGLE_DOC_1` and `DOC_KAGGLE_USERNAME`) in the private repository if required; never publish credentials.

The canonical issues are already present in this repository. Finish #11, then #9, before declaring readiness for #14. No acceptance gate is waived by the move. Do not restart scheduled engineering tasks.
