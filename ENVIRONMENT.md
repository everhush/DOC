# Environment and dependencies

## Supported assumptions

The supplied runtime is portable C++20 and was verified in a 64-bit Linux environment. The CMake configuration requires:

- CMake 3.20 or later;
- a C++20 compiler;
- POSIX threads through CMake's `Threads` package;
- Python 3 for the bounded model checkers;
- Ninja is recommended but not required.

The manuscript was compiled with Typst 0.15.1. Typst is not bundled; use a compatible local installation.

## Verification environment

- Debian GNU/Linux 13 (trixie), Linux 6.12.13, x86-64;
- GCC 14.2.0;
- Clang 17.0.0;
- CMake 3.31.6;
- Ninja 1.12.1;
- Python 3.13.5;
- Typst 0.15.1;
- five visible logical CPUs, with a four-CPU cgroup quota during verification.

The preserved headline benchmark campaigns record their own earlier host and run configuration in `runtime/results/primary/machine.json` and their raw CSV files. Timing values are host-specific; the fresh verification reruns correctness checks rather than relabeling new timings as the preserved campaign.
