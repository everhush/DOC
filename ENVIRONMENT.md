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

The authoritative article benchmark campaign is `runtime/results/independent-dedicated-100/`. Its `machine.json` records Linux 6.18.53 x86-64 with glibc 2.42, GCC 15.3.0 in Release mode, Python 3.14.7, CMake 4.4.2, and an AMD Ryzen AI 7 350 w/ Radeon 860M on bare metal. Eight physical cores / 16 logical CPUs were visible by affinity/OS, no cgroup CPU quota was recorded, and the campaign deliberately capped participants at four. Every reported row uses 100 fresh processes after three unrecorded warmups. Timing values remain host- and workload-specific.
