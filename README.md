# Dependency-Oriented Computation supplementary artifact

This archive accompanies the manuscript **Dependency-Oriented Computation**. It contains the neutral final manuscript source and PDF, the C++20 executable witness, registered tests, bounded model checkers, benchmark implementation, preserved raw benchmark evidence, verification records, and citation metadata.

## Relationship to the manuscript

The paper's finite metatheory is a mathematical argument. The executable material checks representative and bounded cases; it does not replace the proofs. The runtime is a bounded witness for the realization contracts, not a production consensus or partition-tolerant distributed platform. Timing data supports workload- and host-specific cost-shape claims, not universal performance superiority. See `CLAIM-EVIDENCE-MAP.md` for the exact classification of each major claim.

## Layout

- `paper/` — final Typst source, compiled PDF, and verified BibTeX metadata mirror;
- `runtime/include`, `runtime/src`, `runtime/examples` — C++20 runtime and example;
- `runtime/tests` — native and randomized/differential tests;
- `runtime/formal` — five bounded model checkers;
- `runtime/benchmarks` and `runtime/scripts` — benchmark implementation and complete campaign driver;
- `runtime/results/primary` — preserved 20-process-per-row campaign for sparse/dense, cutoff, financial, and sorting-network results;
- `runtime/results/scaling` — preserved local-machine scaling evidence and a summary matching Section 9.2;
- `verification/` — one consolidated verification report, supporting logs, and the citation ledger.

## Dependencies

Use a 64-bit Linux environment with CMake 3.20+, a C++20 compiler, POSIX threads, Python 3, and optionally Ninja. Typst 0.15.1 or a compatible release is required only to rebuild the manuscript. Typst and fonts are not bundled.

## Build the runtime

From the artifact root:

```sh
cmake -S runtime -B build/release -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build/release
```

When Ninja is unavailable, omit `-G Ninja`.

## Run the full registered suite

```sh
ctest --test-dir build/release --output-on-failure
```

This runs both native executables and all five bounded model checkers.

## Run bounded verification directly

```sh
python3 runtime/formal/model_check.py
python3 runtime/formal/repair_model_check.py
python3 runtime/formal/graph_version_model_check.py
python3 runtime/formal/duplicate_premise_model_check.py
python3 runtime/formal/demand_recurrence_model_check.py
```

The repair and demand/recurrence checkers are the longest of these checks.

## Run benchmark correctness checks

The following commands execute each benchmark family once. Each process checks result equality and exits nonzero on disagreement. The timings are only a smoke check and must not be substituted for the preserved campaigns.

```sh
DOC_MAX_WORKERS=1 build/release/doc_benchmark cold
DOC_MAX_WORKERS=1 build/release/doc_benchmark density 1
DOC_MAX_WORKERS=1 build/release/doc_benchmark density 2048
DOC_MAX_WORKERS=1 build/release/doc_benchmark cutoff
DOC_MAX_WORKERS=4 build/release/doc_benchmark parallel
DOC_MAX_WORKERS=1 build/release/doc_benchmark dense-cheap
DOC_MAX_WORKERS=1 build/release/doc_benchmark financial 1
DOC_MAX_WORKERS=1 build/release/doc_benchmark financial 1024
DOC_MAX_WORKERS=1 build/release/doc_benchmark bitonic 1
DOC_MAX_WORKERS=1 build/release/doc_benchmark bitonic 512
```

The complete campaign driver is included at `runtime/scripts/run_all_benchmarks.py`. Its `--help` output documents campaign options. A full timing campaign is intentionally not required for correctness verification because new timings are expected to vary by host and must not be substituted silently for the preserved evidence.

## Compile the manuscript

```sh
typst compile paper/dependency-oriented-computation.typ paper/rebuilt.pdf
```

The supplied PDF was compiled with Typst 0.15.1.

## Raw data and summaries

- `runtime/results/primary/raw.csv` is the unfiltered primary campaign.
- `runtime/results/primary/statistics.csv` and `summary.csv` contain the generated distributions and filtered/raw summaries.
- `runtime/results/scaling/raw.csv` preserves the supplied local-machine paired scaling measurements.
- `runtime/results/scaling/SUMMARY.md` reproduces the Section 9.2 median-time and paired-speedup series.



## Continuous publication validation

`.github/workflows/publication-validation.yml` rebuilds and tests the C++20 runtime with GCC and Clang, runs ASan/UBSan and ThreadSanitizer native suites, executes the bounded model checkers through CTest, recompiles the Typst manuscript with pinned Typst 0.15.1, preflights the generated PDF, renders every PDF page, and executes a fresh publication-scale benchmark campaign.

The workflow uses read-only repository permissions and no manually configured credentials or secrets. All uploaded workflow artifacts use `retention-days: 1`. The generated PDF, page renders, benchmark measurements, and validation logs are therefore reproducible CI evidence rather than long-lived generated files in version control.
