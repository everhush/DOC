# Benchmark evidence

The authoritative campaign used by the revised article is:

- `independent-dedicated-100/` — 100 fresh processes per reported row, three warmups, at most four externally granted participants, on a bare-metal AMD Ryzen host with no recorded cgroup CPU quota; the directory contains raw data, retained data, machine/configuration records, outlier sensitivity, aggregate statistics, and the generated report.

The earlier `revision-2026-09-29/` 20-process EPYC campaign is retained as historical reviewer-revision evidence. It is no longer the source of numerical values printed in the article.

Older `primary/` and `scaling/` snapshots were removed during the reviewer revision because they were produced under superseded environments and could contradict the article's revised numbers.

GitHub Actions also runs a fresh publication-scale campaign on every push/PR. Those host-specific measurements are uploaded as one-day workflow artifacts and are not committed as replacement article data.
