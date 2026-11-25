# DOC-TYPED-IR/1 — typed evaluator to native compiler handoff

**Status:** scoped Issue #10 versioned semantic baseline, **not** C code generation,
AOT, or Issue #11 implementation. The source of truth is the native Rust DOC
evaluator in runtime-rust/src/lib.rs. The checked exporter is
runtime-rust/src/typed_ir.rs, with golden tests in
runtime-rust/tests/typed_ir_contract.rs. The #11 Stage-0 compiler lowers this checked in-memory typed structure to specialized native C and preserves canonical IR export; see [DOC-AOT.md](DOC-AOT.md). No new source dialect is introduced.

## Canonical wire representation

The export is canonical UTF-8 with LF line endings and tab-separated rows.
Names are validated ASCII identifiers; literal payloads are lowercase
hexadecimal UTF-8 bytes so user text cannot inject row delimiters.
State IDs are zero-based declaration order. Expression argument indices
refer to the local **ordered premise list**, not global states.

~~~
DOC-TYPED-IR/1
states<TAB>N
source<TAB>ID<TAB>NAME<TAB>TYPE<TAB>HEX_UTF8_TYPED_VALUE
derive<TAB>ID<TAB>NAME<TAB>TYPE<TAB>COMMA_SEPARATED_PREMISE_STATE_IDS<TAB>EXPR
carry<TAB>SOURCE_STATE_ID<TAB>PREVIOUS_STATE_ID
~~~

There must be exactly N state rows, followed by zero or more carry rows.
Each carry source is unique, has a source (not derived) role, and its type
matches its previous state. Unknown versions, types or opcodes must be
rejected rather than silently coerced.

Example (actual tabs in the canonical output):

~~~
DOC-TYPED-IR/1
states	3
source	0	x	int	33
source	1	y	int	2d34
derive	2	sum	int	0,1	add(arg(0),arg(1))
~~~

## Types and literal bytes

| Type | Meaning and canonical payload before hex encoding |
| --- | --- |
| int | checked signed 64-bit decimal integer; no wraparound |
| bool | true or false |
| nat | arbitrary-precision nonnegative canonical decimal |
| ints | immutable ordered i64 vector, e.g. [1,-2] |
| maybe_int | none or some(-2) |
| text | raw UTF-8 bytes, including non-ASCII and newline |

Thus int 3 encodes as hex 33, int -4 as 2d34, text Hi as 4869,
and a text newline as 0a. This is not a machine-word binary dump.

## Expression encoding and exact semantics

- arg(i) reads the derive's local premise i; lit(type,hex) is a typed constant.
- empty is an empty ints list; none is an absent maybe_int.
- add, sub, mul accept identical int or nat operands. Signed overflow and
  negative nat subtraction are errors.
- eq requires matching types; lt and le require matching numeric types.
- if(cond,a,b) requires a bool condition and equal branch types. Evaluation
  is **branch-lazy**: the unselected expression is not evaluated.
- append(list,int), remove_at(list,index), replace_at(list,index,value),
  get(list,index), try_get(list,index), tail(list), len(list).
  Invalid get/remove/replace indices error; try_get returns none; tail
  of an empty list is empty. len(text) is UTF-8 **byte length**.
- some(int), unwrap_or(maybe_int,default_int).
- concat(text,text) and starts_with(text,prefix).

Imported functions and pure DOC modules are elaborated into these expression
nodes by the reference DOC frontend before export. The expression tree is a
closed pure operation set; it does not include host function pointers,
unvalidated effects, file/device/network instructions, or an implicit
native GPU API.

## Graph, recurrence and publication semantics for Issue #11

1. Validate a typed DAG of source and derived states. Every derived state
   explicitly lists its premise state IDs and has one statically known type.
2. Compute a ready frontier from stable predecessors. Candidate derived
   values are evaluated against the same prior valuation. A failed candidate
   cannot partially publish the current frontier. Typed source update batches
   are validated together.
3. A carry pair grants exclusive next-epoch authority over a named source.
   Facts for other sources are epoch-local, and a failed epoch does not advance.
4. A fork or durable checkpoint saves the latest *stable typed source facts*.
   Restored evaluation starts at a **fresh epoch 0**. Historic epochs are not
   reconstructed or implicitly replayed by disk restore.
5. Explicit external effects occur outside pure frontiers, after stabilization
   for output. Output cannot be transactionally undone once published.
6. CPU is the default backend; explicit WebGPU/WGSL selection admits only
   supported pure compute and cannot silently fall back to the CPU. A software
   WebGPU adapter in Linux CI is not physical GPU evidence.

## Error and compatibility policy

Invalid types, graph cycles, malformed IR, unknown opcodes, integer overflow,
negative/out-of-bounds indexing, capacity exhaustion, stale carried authority,
and failed effects must return explicit errors, not successful substitute
values. A compiler must preserve observable results and failure behavior,
including lazy branches, recurrence and partial-publication boundaries.

The current output is a **textual, versioned typed AST contract**, not a
self-hosted compiler, binary ABI, IR parser, generated C, standalone native
program or full general-purpose language completeness claim. Formatting or
semantic changes require a new format version and conformance tests. The
checkpoint format is independently versioned and validates graph schema.
Effects are sampled and represented as typed source facts; original effect
provenance belongs to the host input manifest.

GUI/editor/HUD, asset generation and 3D remain user-deferred.


### Runtime-sized dependency families (initial #24 extension)

`map_ints(arg(list),body)` is a named derive with an `ints` premise and pure scalar `int` result per lane. In the body only, argument index equal to the premise count refers to the lane item (int). Other arguments are normal captures; only referenced int/bool captures enter the generated child frontier. Source syntax: `derive ys: ints (xs,bias) = map_ints(xs,item,add(item,bias))`. The binder cannot shadow a premise. Every input item contributes an independent derived state, including empty/shrinking/growing inputs; collection order is logical index order, not worker completion order. No user-specified iteration, placement or schedule. Checked failure rejects the entire ready frontier; the list publishes only after all lanes and other selected candidates succeed. Limits: 4096 lanes per family, 32768 expanded lanes and 65536 child states per ready frontier, scalar pure bodies only in this first extension. Named families compose through normal derived premises. Nested maps require separate named derives. The existing scheduler can run eligible lanes on actual CPU/GPU frontiers. The native Stage-0 compiler specializes lane callbacks in C, uses automatic bounded CPU workers and owned result storage, and joins before publication; explicit GPU remains unsupported by native Stage-0. Old IR opcodes remain unchanged; readers must reject unknown opcodes rather than silently coerce. Full general-purpose types, data-dependent recursive derivations and native effects are separate outstanding #24 foundations.


### Input-dependent causal derivations

`recur(arg(seed),terminal,successor)` denotes a private chain of typed dependencies. Source form `recur(seed,previous,condition,successor)` binds `previous` to the current value (IR argument index equal to the premise count). Seed must be a named premise; the terminal predicate is bool and successor has the same type as seed (any existing DOC value type). The predicate is evaluated before the successor; a true terminal predicate publishes that current value and does not evaluate its successor. Only the necessary causal chain is ordered; independent named derives remain ready for automatic scheduling. A chain is not an externally visible epoch sequence; intermediate states are private, and failure rejects the containing ready frontier. The shared transition budget is 65536, with 65536 items/bytes per state. Initial implementation executes these chains on CPU; independent collection families still use CPU/GPU placement as admitted. Nested dynamic derives require separate names. Native C uses a specialized successor and predicate, uniquely owned current value and temporary arena per step, freeing superseded state after successful replacement; no runtime source interpreter or programmer-authored loop/worker control. `examples/causal_token.doc` demonstrates arbitrary input-length numeric token accumulation and a separate independent causal derive. The bounded resource policy is not a claim of unrestricted recursion or complete compiler expressiveness.


### Exact words and UTF-8 bytes

`quot` and `rem` are signed int64 operations truncating division toward zero; zero divisors and INT64_MIN/-1 reject both. `bit_and`, `bit_or`, `bit_xor`, `bit_not`, `shift_left`, `shift_right` operate on the exact 64-bit two's-complement representation, returning int64 with the resulting bits. Both shifts require 0..63, left discards overflowing bits and right zero-fills. `utf8_bytes(text)` produces an ordered ints collection of byte values 0..255; `utf8_text(ints)` validates all byte values and canonical UTF-8, then returns text. Both have 65536-byte resource limit. No implicit pointer, native memory access, endianness or narrowing. These are typed IR unary/binary opcodes with the same names; native lowering uses checked C helpers and owned immutable values. GPU admission remains conservative: these exact 64-bit/partial and collection operations run on CPU until a correct lowering is available. `examples/byte_token.doc` combines byte access and causal derivation to consume actual variable-sized textual input and reject invalid digits/overflow. This is a foundation, not a complete tokenizer or networking library.


### Lexical pure-function specialization

Pure `fn` declarations are now parsed once as lexical expression templates, referencing only their formals and previously declared pure functions. Calls specialize expression trees by argument position, never by replacing literal text. Unicode literal bytes, punctuation and lazy branch semantics are preserved. The old fixed four-formal and 512-byte expansion restrictions are replaced by explicit implementation resource budgets: 256 formals, 64KiB function source, 65536 expression construction/specialization nodes per expression, 128 depth and 1048576 total expression nodes per parsed program. These are denial-of-service limits, not a prescribed language execution order. Dynamic dependency families and causal recurrences remain named derives, and their scalar/pure bodies may use these functions. The result still uses the canonical typed expression IR, so CPU and native generated C consume the same specialized graph. This does not yet introduce first-class runtime function values or a recursive call ABI.

### Checked immutable collection subranges

`slice(ints,start,count)` yields an `ints` collection of exactly count items beginning at zero-based start. Both offsets are signed int; negative values, start beyond length or count beyond remaining length reject without publication. A zero-length slice at the end is valid, including an empty input. This is a pure typed ternary IR opcode `slice`; no raw pointer or programmer-controlled lifetime. Native lowering may borrow the subrange within expression evaluation, but clones the published result before input/arena retirement. CPU-only until admitted GPU lowering is implemented. No implicit UTF-8 character indexing; byte payloads must pass `utf8_text` validation when decoded.
