# Restricted original-size DOC-emitted benchmark

This is **test/reproducibility tooling only**, not the public production linker or
a general module language extension. The independent compiler emits every
numeric definition, including the packed prime recurrence and financial
projection. The test linker checks compiler state rows, declared imports,
roles/types, edges and ready/demand/block policy membership; it relocates
immutable premise reads and deduplicates emitted computation templates.
It generates equivalent CSR graph metadata. C in the host is timing, source
update setup and independent oracles, not the measured numerical computation.
The ordinary compiler's monolithic admission limits remain unchanged.

Use a new scratch directory and Python without -O (assertions are verification).
Copy this directory to scratch/partition. Extract the verified games artifact
of CI 46020955848 into scratch/games, chmod +x reactive2, and verify the
reactive2 SHA256 5ccab55fb4f6f7aa0ef688a3759215426a4661018e0dd7cb0c8c72dcb7016912.
Copy runtime-doc/runtime from the exact accepted production runtime tree
e2715a19ad35f74f7a4ac5869c672f71715171dc to scratch/paper-scale/tuned.
Keep expected.csv as a deterministic regression fixture, derived from the
original-size host benchmark and independent checked outputs; its variant
column is retained for compatibility with the exact local campaign driver.
Use the original historical benchmark independently when regenerating these
expectations. No timings are encoded as expectations.

Run from scratch:
    cp partition/expected.csv paper-scale/final-fullsize-samples.csv
    c++ -std=c++20 -O2 partition/seed.cpp -o partition/seed
    partition/seed > partition/sort-seeds.txt
    python partition/generate.py reduction dense financial sorting
    python partition/link.py reduction dense financial sorting
    python partition/audit.py
    for tag in reduction dense financial sorting; do
      clang -std=gnu11 -O1 -pthread -I paper-scale/tuned -I partition \
        partition/$tag/linked.c -o partition/$tag/native || exit 1
    done
    python partition/campaign.py 3

The local campaign used a Linux x86_64 host with four granted CPUs and
Clang 17 -O1. Pin or otherwise grant the recorded worker capacity before
running comparative timings. Source counts, dependency edges, expected
evaluation counts and numerical values are the portable checks. Latency
and worker speedup are hardware-specific. Preserve all valid samples.
Source generation, emission, linked output and native build are separate
from timed runtime epochs. Generated C, executables and raw timing files
remain untracked artifacts.
