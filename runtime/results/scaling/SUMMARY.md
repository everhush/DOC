# Externally limited scaling summary

Application graphs contain no participant count; `DOC_MAX_WORKERS` supplied limits externally. The same graph and output oracle were used at every externally passed limit.

| Externally allowed participants | Median time | Median paired speedup |
|---:|---:|---:|
| 1 | 142.589 ms | 1.000x |
| 2 | 72.274 ms | 1.959x |
| 3 | 49.605 ms | 2.853x |
| 4 | 37.527 ms | 3.847x |

Median time decreases monotonically from one through four participants. The four-CPU quota makes this a bounded single-host result, not a many-core or multi-host scaling claim.
