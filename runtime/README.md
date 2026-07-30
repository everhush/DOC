# DOC runtime

This directory contains the C++20 executable witness for the finite Dependency-Oriented Computation kernel and its bounded realization profiles.

The application graph contains no worker or processor count. The runtime derives capacity from the execution environment; experiments may limit it externally with `DOC_MAX_WORKERS`, CPU affinity, cgroups, containers, or sandbox quotas.

From this directory:

```sh
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build
ctest --test-dir build --output-on-failure
```

The registered suite includes native runtime tests, benchmark-generator equivalence tests, and five Python bounded model checkers. Benchmark executables check their output against independent or complete-reevaluation oracles and exit nonzero on disagreement.
