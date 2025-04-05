# Revision decision log

This file records publication-affecting decisions made during the 2026-09-29 reviewer revision.

| Decision | Reason | Enforcement / evidence |
|---|---|---|
| Treat the finite acyclic kernel as the proved semantic core. | Reviewer 2 requested separation between proved properties, conditional extensions, and runtime evidence. | Manuscript claim map, finite theorem assumptions, `CLAIM-EVIDENCE-MAP.md`, manuscript checker. |
| Define all finite-kernel notation before use, including `S`, `D`, `P_d`, the valuation, active set, and ready frontier. | Reviewer 1 identified undefined/late-defined symbols. | Numbered definitions/equations and `verification/check_manuscript.py`. |
| Add an explicit finite-stabilization algorithm. | Reviewer 1 requested a stepwise flow across semantic layers. | Algorithm label and cross-reference gate. |
| Compare DOC by representation/repair/guarantee rather than claiming dependency tracking is new. | Both reviewers requested assessable novelty positioning. | Related-work comparison and bounded novelty language. |
| Treat graph-version semantic keys as external compatibility certificates; do not claim arbitrary function equivalence is decidable. | Reviewer 2 requested an operational compatibility account. | Graph-version example and explicit caveat checked by the manuscript gate. |
| Present specialized cached baselines and fine-grained negative cases prominently. | Reviewer 2 requested stronger interpretation of performance limits. | Revised evaluation text and retained raw campaign. |
| Bound the parallel claim to one host and externally granted capacity. | Reviewer 2 warned against distributed-scalability extrapolation. | Four-participant wording and CI/retained evidence. |
| Keep all manuscript diagrams/charts native to Typst. | The revised article must remain editable, consistent, and vector-native. | Source checker rejects `image(...)`; PDF preflight rejects embedded image XObjects. |
| Use one Typst figure counter for all nine visual figures. | Separate custom kinds can restart visible numbering. | Shared `kind: "figure"` plus checker. |
| Pin Typst 0.15.1 in CI and build the PDF there. | The paper must compile without a user-supplied binary. | Manuscript CI job downloads the pinned upstream release and uploads the PDF/renders. |
| Use GitHub Actions artifacts rather than GitHub Releases for generated evidence. | Releases are persistent while the requested evidence-retention window is one day. | Every `upload-artifact` step has `retention-days: 1`; no release credentials are needed. |
| Give CI read-only repository permission and require no secrets. | Validation should run on push/PR without manual credential setup. | Workflow `permissions: contents: read`; policy checker rejects `secrets.*` and write permissions. |
| Retain one authoritative reproduced benchmark campaign in the repository. | Multiple stale campaigns can contradict revised manuscript numbers. | `runtime/results/revision-2026-09-29/` is retained; older primary/scaling snapshots are removed. |

## Validation history

The first GitHub Actions run established that the manuscript job compiled, preflighted, rendered, and uploaded correctly; it was superseded when a citation-scanner false-positive fix was committed. Run 2 (commit `b569982186c6546f78161d7b1b4500a438b90b21`) completed successfully across GCC, Clang, ASan/UBSan, ThreadSanitizer, Typst/PDF validation, the full benchmark campaign, CI policy, and the final publication gate.

The manuscript artifact from that run was downloaded and visually inspected page by page. The generated article contains 31 A4 pages and nine sequentially numbered native-vector figures; no clipping, overlap, broken glyph, or raster-diagram regression was observed.
