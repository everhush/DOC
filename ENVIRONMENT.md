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

The authoritative article benchmark campaign is `runtime/results/revision-2026-09-29/`. Its `machine.json` records Linux 6.18.44 x86-64 with glibc 2.41, GCC 14.2.0 in Release mode, Python 3.13.5, CMake 3.31.6, an AMD EPYC 9V74 80-Core Processor, five CPUs visible by affinity/OS, and a four-CPU cgroup quota (`cpu.max = 400000 100000`). Every reported row uses 20 fresh processes after one unrecorded warmup. Timing values remain host- and workload-specific.
