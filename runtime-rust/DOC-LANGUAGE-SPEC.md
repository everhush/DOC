# DOC source and runtime semantics — experimental specification

**Scope:** one directly authored .doc language interpreted by independent
native Rust and Goose code. This specification records the implemented
prototype. It does NOT replace the canonical manuscript, establish a
production ABI or assert that the complete #7/#9 gates have passed.

## Declarations and pure evaluation

- source NAME: TYPE = LITERAL — a uniquely authorized typed mutable source.
- derive NAME: TYPE (PREMISES) = EXPR — typed acyclic pure definition; explicit
  premise names determine the relevant ordered inputs. Duplicate premise
  positions remain meaningful and each derived state has one logical producer.
- fn NAME(formals) = EXPR — earlier-declared pure bounded function. Each
  frontend expands calls into its existing typed expression IR; arity is
  limited to four, body length to 512 bytes and recursion is rejected by
  bounded expansion. No external Python/source-code transpiler.
- import relative/path.doc — compile-time **function-only** module import,
  relative to the authored source file. Data/effects or nested imports
  inside the module are not permitted.
- effect NAME: TYPE = read("relative/path.txt") — explicit fallible
  typed file input sampled before pure graph evaluation, not an effect
  performed by a derived state.
- Host CLI FILE.doc --emit=STATE:relative/path.txt — an explicit fallible
  file output *after* stable evaluation, by staging and same-directory
  replacement. External I/O is neither exactly-once nor rollbackable.
- Blank lines and # comments are permitted.

Every source-update batch is checked fully before changing input facts.
A valid nonempty ready frontier is evaluated from one settled
pre-frontier valuation and its complete immutable candidates are
published together. Equality cutoff may suppress unchanged downstream
work. A failed candidate must not partially publish. The semantics are
distinct from physical placement and memory reclamation.

## Values

| Type | Value syntax | Semantics |
|---|---|---|
| bool | true / false | Exact Boolean |
| int | signed decimal | Checked signed 64-bit |
| nat | nonnegative decimal | Arbitrary-precision natural, canonical zero |
| ints | [1,-2,4] | Immutable signed-int collection, up to 4096 elements |
| maybe_int | none / some(-2) | First-class typed absence or integer |
| text | "UTF-8 text 🙂" | Immutable Unicode UTF-8 bytes, simple literals, up to 16KiB |

Text length is **UTF-8 bytes**, not Unicode characters/graphemes.
String escapes and embedded newlines are intentionally not available.
No raw allocation, freeing, GC/RC directives, borrows or pointers are
visible in ordinary DOC source.

Pure expression forms:

| Expression | Typed behavior |
|---|---|
| if(cond,yes,no) | Both branches type-check; only selected branch executes |
| eq(a,b) | Structural exact equality of same-typed values |
| lt(a,b), le(a,b) | Matching integer/natural ordering |
| add/sub/mul | Matching int with overflow checks or exact nat with underflow checks |
| nat(DECIMAL) | Canonical arbitrary natural |
| empty(), append(xs,n), len(xs), tail(xs) | Pure list construction/size/tail |
| get(xs,index) | Partial checked collection access |
| try_get(xs,index) | Total safe lookup into maybe_int |
| none(), some(n), unwrap_or(value,default) | Typed absence handling |
| text("..."), concat(a,b), starts_with(a,prefix) | Pure Unicode byte storage, join and prefix |
| len(text) | UTF-8 byte length |

Unexpected types, illegal source authority, partial arithmetic, unsupported
lookup and resource overrun are checked errors, not arbitrary DOC values.

## Demand and versioned recurrence

Demand materializes an ancestor-closed finite prerequisite subgraph.
Explicit typed forward carry makes a finite, acyclic step template into a
potentially unbounded logical recurrence. --through=N requests a finite
prefix; --until=halt and --max-epochs=N request a bounded halt search.
Failure to observe halt within a finite cap never proves divergence.
Typed epoch-local facts apply only at the requested epoch. Dynamic memory
and numerical resources remain physically finite.

Rust recurrence keeps a bounded snapshot window and an authoritative
sparse fact log for replay/reconstruction of evicted committed epochs.
The Rust PublishedRuntime API retains complete Arc-owned immutable
values under concurrent readers and checks source-epoch/graph-generation
tokens. Goose has native isolated worker-copy/pinned-reader testing,
pool compaction and graph replacement but not yet a full equivalent
persistent authoritative history/reconstruction API.

## Scheduling and memory

The pure ready-frontier can be evaluated by host CPU workers without
new source-language parallel directives. Goose currently automatically
parallelizes eligible wide total Boolean results over copied Boolean/
signed-integer inputs, with a typed message-queue publication barrier.
Variable-size pool handles may not cross to threads without owned copy.
Other mixed/partial operations remain serial. Rust has independently
tested worker scheduling and protected reader publication.

Rust uses safe ownership and Arc for published reader handles. Goose
uses native growable value pools and scope-checked owned copies. There is
no claim of universal bounded memory, automatic shared-address-space
parallelism, or guaranteed speedup. Snapshot retention is intentional
and can increase memory; obsolete values may be evicted only when
authoritative reconstruction/pinning obligations remain satisfied.

## Linux GPU execution status

The initial supported host target is Linux x86_64. The Rust `wgpu`
backend has strict selected-device evaluation for eligible finite, pure
Boolean-derived DOC dependency graphs when built with `--features webgpu`.
It also has bounded Boolean and signed-comparison GPU regression programs.
Source `int` values must fit i32 on the eligible GPU path. Unsupported
operations, effects, recurrence, nonportable values and device failures
must fail closed, without silent CPU execution.

The independent native Goose SDL3 `gfx` Vulkan path validates bounded
map/reduction kernels and direct Rust/Goose GPU-result parity; its
general DOC source CLI still lacks a comparable general-source GPU
executor. Both runtimes require broader semantic and device-failure
coverage before general-purpose GPU production acceptance.

Linux Mesa software Vulkan is a correctness oracle, not evidence of
physical hardware acceleration. Kaggle native Vulkan physical-GPU
verification and exact-SHA artifact provenance remain independent gates.
Native Linux release binaries are experimental build artifacts, not
production-approved releases. Runtime ownership remains in Rust and
Goose; upstream native toolchains may have C/C++ dependencies.

## Nonclaim and evidence rule

Tests and matched benchmark logs live in secondary CI and primary
issues #7/#9. Raw timed CLI samples include startup and parsing.
A finite test cannot prove the paper's mathematical universality,
a software adapter cannot prove physical acceleration, and a Rust
memory test cannot prove the Goose runtime safe. Do not label full
general-purpose, dual production runtime or WebGPU acceptance PASSED
until all their respective source/transport/memory/release gates
are independently verified on both implementations.
