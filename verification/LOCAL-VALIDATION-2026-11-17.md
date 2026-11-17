# Local validation record — 2026-11-17

## Scope

This record reports only checks actually executed in the ChatGPT local execution container. **It is not a release qualification, proof of the full DOC model, Rust compilation result, or performance comparison.**

Original pre-Rust state: snapshot-2026-11-17-pre-rust-runtime at 1ab3e3987477b1638f1abde58102704fa353d656.

## Environment and constraints

- Debian GNU/Linux 13, x86-64, Python 3.13.5, 5 schedulable CPUs reported by nproc, AMD EPYC 9V74 processor model.
- `rustc`: unavailable.
- `cargo`: unavailable.
- Network/DNS: unavailable for installing a Rust toolchain.
- GitHub Actions quota exhausted; no GitHub Actions used for this local validation. The newly added Rust Actions workflow was subsequently removed to avoid wasting quota.

## Actual local execution

Local command: `python /mnt/data/doc-local-validation/finite_exhaustive.py` (independent finite-kernel checker of the same rules as the checked-in `verification/finite-calculus-local-exhaustive.py`).

Result:

```
PASS: 512 graphs, 59904 admissible seeds, 239616 source updates,
119808 unique schedule/profile explorations, 521584 explored configurations,
max 3 selections
```

Additional local syntax check: `python -m py_compile /mnt/data/doc-local-validation/finite_exhaustive.py` exited 0.

The independent checker evaluates all subsets of ready frontiers, both exact and conservative cutoffs, all admissible seeds over a one-source/three-derived Boolean family, and continued source updates. It checks ready-frontier calculations against an independent recursive ancestor-closure algorithm and checks final valuations against complete topological reevaluation.

These checks demonstrate consistency for a bounded finite family, **not** the theorem for arbitrary-sized graphs.

## Not performed or not established

- Rust `cargo check`, `cargo test`, `cargo clippy`, `cargo fmt`, debug/release builds, Rust CLI execution, or machine-code runtime benchmarks: **NOT RUN**.
- Full formal proofs, complete validation of versioned recurrence, immutable graph-version transitions, effects, typed physical realization, transport/placement, fail-stop recovery: **NOT ESTABLISHED** by this record.
- Memory safety under actual concurrent Rust machine execution, runtime performance scaling, HVM2/3 parity, production readiness: **NOT ESTABLISHED**.
- Original manuscript claims and C++ empirical evidence remain separate; this report does not supersede or modify them.

## Required next validation gate

Use an execution environment with a locally available stable Rust toolchain. Run `cargo fmt --all -- --check`, `cargo clippy --all-targets -- -D warnings`, `cargo test --all-targets`, release tests, example CLI, repeat single-/multi-CPU benchmarks and differential tests. Resolve every failure before claiming that even this limited Rust finite kernel has passed native validation. Add each separately qualified DOC extension with its own formal and executable evidence. Do not close issue #7 until these conditions are met.
