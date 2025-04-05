# CI design

The publication workflow is `.github/workflows/publication-validation.yml`.

It deliberately separates five evidence classes: dual-compiler runtime conformance, sanitizer execution, manuscript/PDF validation, fresh performance measurements, and workflow-policy validation. A final publication gate depends on all of them.

The workflow installs Typst 0.15.1 itself, so manuscript compilation does not depend on a binary supplied to an interactive session. The manuscript job also renders every PDF page and uploads the source snapshot, compiled PDF, checksums, logs, provenance, and page renders.

No repository secret is required. Checkout credentials are not persisted and the workflow has only `contents: read`. Generated evidence is uploaded through GitHub's built-in artifact service with one-day retention. This is intentionally used instead of persistent Releases because the requested retention period is one day.

Benchmarks are rerun in CI as fresh host-specific evidence. They are validated structurally, but CI measurements are not silently substituted into the manuscript: the article's printed values remain tied to the retained `revision-2026-09-29` campaign and are cross-checked mechanically.

The workflow is suitable for push, pull request, and manual dispatch. Branch protection can later require the single `Publication gate` status without changing the workflow.
