# DOC — Dependency-Oriented Computation

DOC is a typed dependency-oriented programming model and native compiler for computations that change over time. Rather than rerunning an entire program when an input changes, a DOC program declares typed facts and their actual dependencies. The realization determines which conclusions need repair, which independent work is ready, and how to use the available computation resources.

**Current implementation:** independent DOC-authored native compiler and runtime in `runtime-doc/`; Linux x86-64; CPU by default, with compiler-generated WebGPU/WGSL for admitted GPU work. This is the canonical development repository. The separate source-only distribution is still being qualified in [issue #14](https://github.com/everhush/DOC/issues/14); no stable downloadable product release is claimed.

[Quick start](#quick-start) · [Write a DOC program](#write-a-doc-program) · [Incremental updates](#incremental-updates) · [GPU execution](#gpu-execution) · [Research and evidence](#research-and-evidence) · [Repository guide](#repository-guide)

## What makes DOC different?

- **Dependencies are explicit:** each derived state declares the premises on which its value depends.
- **Incremental repair and exact cutoff:** when an input changes, only affected work needs reconsideration; an unchanged derived value can stop downstream propagation.
- **Demand:** request a particular result rather than materializing every state.
- **Runtime-sized finite families:** the data itself can determine how much independent work is ready. Application source need not specify hardware worker counts or GPU dispatch sizes.
- **Native compilation:** DOC-authored compiler stages emit native C and, for admitted GPU fragments, WGSL. A C toolchain builds the executable. Running the resulting CPU program does not require the original evaluator, the DOC source or a Python interpreter.
- **Controlled state publication:** the supported reactive runtime evaluates private candidates, checks failure boundaries, and exposes stable observations. Typed recurrence, startup effects and resource lifetimes have separate admitted profiles and authority rules.

## Quick start

### 1. Requirements

Use a Linux x86-64 development machine with Python 3, Git, a C toolchain (`cc`, GNU C11, pthread support and sanitizer support for the qualification tests), binutils, standard shell tools and `unzip`. For the signed artifact route below, also install [GitHub CLI](https://cli.github.com/) with `gh attestation verify` support and authenticate if required. On Ubuntu, the base C/build tools can be installed with:

```sh
sudo apt install build-essential binutils python3 git unzip curl
```

There is no published package to install with a package manager yet. The commands below use the **development candidate**, not a final product distribution. They intentionally keep the native bootstrap separate from the text-only source.

### 2. Get and authenticate the native build inputs

The following reproducible development example uses the historical consolidated candidate [run 46110130109](https://github.com/everhush/DOC/actions/runs/46110130109), exact source `9c45e6ec87dd9f4ac1ac9824e5df53c2633563ae`. Its source export, bootstrap build and signed attestation verification passed; full exact-revision hardware acceptance is still outstanding. CI artifacts expire, so preserve authenticated copies separately or use a later qualified exact run and its corresponding commit. Never mix artifacts from different revisions.

From a fresh working directory:

```sh
mkdir doc-work
cd doc-work
RUN=46110130109
COMMIT=9c45e6ec87dd9f4ac1ac9824e5df53c2633563ae
REPO=everhush/DOC

gh run download "$RUN" -R "$REPO" -n doc14-source-candidate -D candidate-evidence
gh run download "$RUN" -R "$REPO" -n doc14-internal-native-bootstrap -D bootstrap-evidence
gh run download "$RUN" -R "$REPO" -n doc14-build-provenance -D provenance-evidence

# Authenticate every subject before executing any downloaded verifier or compiler.
for subject in candidate-evidence/candidate.tar \
  candidate-evidence/source-manifest.json \
  candidate-evidence/verify_candidate.py \
  bootstrap-evidence/managed bootstrap-evidence/module_scan \
  bootstrap-evidence/SHA256SUMS; do
  gh attestation verify "$subject" \
    --bundle provenance-evidence/attestation.jsonl \
    --repo "$REPO" --source-ref refs/heads/master \
    --source-digest "$COMMIT" \
    --signer-workflow "$REPO/.github/workflows/doc14-release-candidate.yml" \
    --deny-self-hosted-runners || exit 1
done

sha256sum -c candidate-evidence/candidate.sha256 || exit 1
(cd bootstrap-evidence && sha256sum -c SHA256SUMS && chmod +x managed module_scan) || exit 1
python3 candidate-evidence/verify_candidate.py \
  --archive candidate-evidence/candidate.tar \
  --manifest candidate-evidence/source-manifest.json \
  --commit "$COMMIT" --output clean
```

The verifier checks the exact commit, file inventory, modes, sizes and hashes, rejects unsafe archive paths, and extracts into a new directory. A checksum alone is not authentication.

### 3. Rebuild the native compiler and install it

Continue from the same directory after successful verification. The clean rebuild regenerates the policy headers from DOC, builds the native Stage-2 compiler and scanner, checks compiler self-reproduction, and runs the CPU regressions. It can be computationally substantial; use a fresh clean source tree for each rebuild.

```sh
set -e
python3 clean/release/rebuild_native.py \
  --bootstrap bootstrap-evidence/managed \
  --bootstrap-sha256 "$(awk '$2=="managed"{print $1}' bootstrap-evidence/SHA256SUMS)" \
  --scanner bootstrap-evidence/module_scan \
  --scanner-sha256 "$(awk '$2=="module_scan"{print $1}' bootstrap-evidence/SHA256SUMS)" \
  --evidence clean-evidence

# The manifest below is produced by your own authenticated rebuild.
python3 clean/release/install_native.py \
  --prefix "$PWD/doc-install" \
  --source-commit "$COMMIT" \
  --native-evidence clean-evidence \
  --native-manifest-sha256 "$(sha256sum clean-evidence/native-hashes.json | cut -d' ' -f1)"

export PATH="$PWD/doc-install/bin:$PATH"
doc --help
```

The installer creates a new, relocatable prefix, never overwrites an existing one, and installs no external GPU library. Python and the C toolchain are needed for compilation; the native CPU application itself does not invoke them. Keep the prefix or add its absolute `bin` directory to your shell's PATH for future sessions.

**Working from a Git checkout instead?** Use `git clone https://github.com/everhush/DOC.git` to explore the development sources. The frozen Rust reference is internal bootstrap/oracle infrastructure, not the current product runtime. The exact local export and locked bootstrap generation commands are in the [qualification workflow](https://github.com/everhush/DOC/blob/9c45e6ec87dd9f4ac1ac9824e5df53c2633563ae/.github/workflows/doc14-release-candidate.yml) (the `stage` job). To test a modified source revision, export that exact commit and generate its bootstrap, then run the clean rebuild above; local builds are not GitHub-signed builds. Do not run the clean-source rebuild in the full development checkout: it intentionally rejects the reference and deprecated evaluator directories. See [candidate validation](release/README.md).

## Write a DOC program

Create `example.doc` in a writable working directory:

```text
source a:int=9
source b:int=3
derive sum:int(a,b)=add(a,b)
derive doubled:int(sum)=mul(sum,2)
```

A `source` is an authoritative typed input with a default value. A `derive` declares a typed result, lists its explicit premises in parentheses and supplies an expression. Here `doubled` depends on `sum`, not directly on `a` or `b`. Expressions use calls such as `add(a,b)`, `mul(sum,2)` and `if(condition,then,else)`.

Compile and run:

```sh
doc example.doc -o example --reactive --emit-c example.c
./example
```

Expected standard output:

```text
a: 9
b: 3
sum: 12
doubled: 24
```

Diagnostic counters may also appear on standard error. The `--reactive` compile option selects managed reactive lowering; omit it for initial managed evaluation only. `--emit-c` is optional and preserves the generated C for inspection.

### Language at a glance

| Construct | Example |
| --- | --- |
| Integer and Boolean sources | `source n:int=5`, `source ready:bool=true` |
| Derived value | `derive twice:int(n)=mul(n,2)` |
| Pure lexical function | `fn twice(x)=add(x,x)` |
| Conditional | `if(ready,n,0)` |
| Integer list | `source xs:ints=[1,2,3]` |
| Runtime-sized family | `map_ints(xs,item,add(item,5))` |

The managed frontend supports six value kinds (`int`, `bool`, `ints`, `maybe_int`, `text` and `nat`) within documented resource bounds. The compiler validates types, declared premises, graph structure and admitted operations. Ordinary function/import handling, startup effects, recurrence and native ABI profiles have additional restrictions; do not assume that every language feature is available through every compiler entry point. The finite acyclic mathematical model and the richer implementation profiles are distinguished in the papers and [execution contract](BACKEND-EXECUTION-CONTRACT.md).

## Incremental updates

The reactive executable accepts typed source assignments, `--demand=STATE` to observe a specific result, and `--next` to separate successive update batches within a single process.

```sh
./example --backend=cpu --demand=doubled a=9 b=3 \
  --next --demand=doubled a=10 b=2 \
  --next --demand=doubled a=10 b=4
```

Expected standard output:

```text
epoch: 0
doubled: 24
epoch: 1
doubled: 24
epoch: 2
doubled: 28
```

The middle batch changes both sources, but their sum remains 12. The reactive diagnostic reports only one evaluation for that batch: `sum` is reconsidered, while the unchanged result cuts off propagation to `doubled`. The final batch changes the sum and consequently the doubled result. These are invocation-local update batches, not a promise of an externally persistent database or arbitrary live code reload.

### Runtime-sized independent work

Create `family.doc`:

```text
source xs:ints=[1,2,3]
source bias:int=5
derive ys:ints(xs,bias)=map_ints(xs,item,add(item,bias))
```

```sh
doc family.doc -o family --reactive
./family --backend=cpu --demand=ys 'xs=[4,5,6]' bias=10
```

Expected standard output:

```text
ys: [14,15,16]
```

The size of `xs` determines the family extent, including zero extent. CPU workers are admitted from the host's available affinity, cgroup quota and independent ready work. For diagnosis or controlled comparisons, `DOC_WORKERS=2` bounds worker admission; it does not force two workers on a tiny workload. `DOC_REGION_METRICS=1` enables region accounting. Neither setting belongs in application source.

The CPU examples above were executed locally using the independently built native compiler and relocated installation helper from verified development evidence. They are not a new exact-revision CI result.

## GPU execution

GPU support is optional and requires the native GPU planner plus the separate pinned WebGPU ABI and a usable adapter. The CPU-only installation above does not include the planner. The development qualification uses [wgpu-native v27.0.4.1](https://github.com/gfx-rs/wgpu-native/releases/tag/v27.0.4.1); the ABI archive is an external dependency, not part of the text-only source. Verify its integrity and applicable upstream notices before use.

From the same authenticated rebuild workspace:

```sh
curl -fL --retry 3 \
  https://github.com/gfx-rs/wgpu-native/releases/download/v27.0.4.1/wgpu-linux-x86_64-release.zip \
  -o wgpu.zip
echo '9385b8a9e4e6f0b00264757577511097104fedf6db7819aa3e34a106c3dc0a42  wgpu.zip' \
  | sha256sum -c -
unzip -q wgpu.zip -d wgpu

# Build the native planner and physical fixture without opening a GPU.
python3 clean/release/physical_gpu.py \
  --stage2 clean-evidence/self/stage2 \
  --scanner clean-evidence/scanner2 \
  --reactive clean-evidence/reactive2 \
  --wgpu wgpu --commit "$COMMIT" --output gpu-build

# Install a separate GPU-capable prefix from the same build.
python3 clean/release/install_native.py \
  --prefix "$PWD/doc-gpu-install" \
  --source-commit "$COMMIT" \
  --native-evidence clean-evidence \
  --native-manifest-sha256 "$(sha256sum clean-evidence/native-hashes.json | cut -d' ' -f1)" \
  --gpu-build gpu-build \
  --gpu-manifest-sha256 "$(sha256sum gpu-build/build.json | cut -d' ' -f1)"

"$PWD/doc-gpu-install/bin/doc" family.doc -o family-gpu \
  --wgpu-root "$PWD/wgpu" --emit-wgsl family.wgsl
DOC_REQUIRE_PHYSICAL_GPU=1 ./family-gpu --backend=gpu \
  --demand=ys 'xs=[4,5,6]' bias=10
```

The GPU program requires the external provider at execution. Keep the ABI installation available. The expected numerical output is the same as the CPU example; physical execution of this newly curated candidate is still being qualified, so the commands are a documented development path, not a guarantee of support on every device.

| Runtime backend | Meaning |
| --- | --- |
| `--backend=cpu` | CPU only; the default. |
| `--backend=gpu` | Strict GPU admission; reject unsupported work or unavailable devices rather than silently falling back. |
| `--backend=auto` | Automatic heterogeneous placement for a GPU-enabled build; reports CPU-only placement when appropriate and no physical GPU is explicitly required. |

DOC source does not select native GPU APIs or driver-specific hardware. The provider handles hardware scheduling. Generated WGSL is limited to admitted, range-proven Boolean and signed-32-bit arithmetic and finite families, not arbitrary managed values, effects, or general recurrence. Device buffer limits, region budgets and compiler bounds remain enforced. Once an admitted attempt fails, do not publish partial state or silently retry that attempt on CPU. Software adapters are not physical hardware evidence. See [the backend contract](BACKEND-EXECUTION-CONTRACT.md).

## Research and evidence

DOC investigates the conditions under which dependency-oriented computation stabilizes, agrees with complete reevaluation, is independent of valid schedules and permits sound equality cutoff. The finite acyclic model gives conditional mathematical arguments under explicit typing, totality, determinism and graph assumptions; these are not proof-assistant mechanized. Input-dependent finite graph generation, recurrence across epochs and physical scheduling are distinct constructions.

- [Computation-model preprint](preprint-model/dependency-oriented-computation.typ) — semantics, metatheory, conditional dynamic dependency generation and evaluation, including a typed expression instance in Appendix C.
- [DOC-only reproducibility supplement](preprint-model/REPRODUCIBILITY-NATIVE.md).
- [Claim/evidence map](https://github.com/everhush/DOC/blob/master/CLAIM-EVIDENCE-MAP.md) and [autonomous scaling audit](https://github.com/everhush/DOC/blob/master/verification/AUTONOMOUS-SCALING-AUDIT.md).

### Build the preprint

Install [Typst](https://typst.app/) (the manuscript workflow uses v0.13.1) and the required fonts. From the repository root, build the editable manuscript:

```sh
mkdir -p manuscript-output
typst compile --root . preprint-model/dependency-oriented-computation.typ manuscript-output/preprint-model.pdf
```

The model is the single maintained Typst preprint; the finite expression calculus is incorporated as Appendix C. The [previous standalone calculus draft](https://github.com/everhush/DOC/tree/c10b1adf2e6d1e6d3ffa72f3030c871c35d76b08/preprint-calculus) remains in Git history. The former LaTeX folder was removed from master; its [historical sources](https://github.com/everhush/DOC/tree/ffc93d672b404179d1bd2c8ee0e5a4527b81cd3a/paper-latex) and prior submissions remain intact in Git history. Generated PDFs are build artifacts, not tracked sources. See the [manuscript review workflow](https://github.com/everhush/DOC/actions/workflows/doc14-manuscript-review.yml).

In the earlier final production development campaign, all six validation jobs passed, including actual Tesla T4 execution. Automatic two-worker CPU prime-counting achieved 1.741-fold speedup (87.0% efficiency); representative same-session warm modular work achieved 13.85-fold automatic-backend speedup over one CPU worker. Cheap work, small reductions and device startup can be slower. These are specific measurements under documented methods, not universal acceleration, optimal scheduling, distributed scalability or unbounded memory claims. They do not substitute for physical acceptance of the separately curated source.

## Repository guide

| Location | Purpose |
| --- | --- |
| `runtime-doc/compiler/` | DOC-authored frontend, native C lowering, module scanner, reactive compiler and GPU planner. |
| `runtime-doc/runtime/` | DOC-owned runtime policy and portable/platform substrate. |
| `runtime-doc/tests/` | Compiler reproduction, independent oracles, authority, region, GPU and scaling regressions. |
| `release/` | Text-only candidate verification, clean rebuild, native installer and bounded physical fixture tools. |
| `preprint-model/` | Research and manuscript sources. |
| `runtime-rust/` | Frozen reference and internal bootstrap; excluded from the curated product source. |
| `runtime-goose/` | Deprecated historical implementation; excluded from the curated product source. |

Further development resources (in the canonical repository, not necessarily exported into the candidate): [independent implementation](https://github.com/everhush/DOC/blob/master/runtime-doc/README.md), [general-purpose programs](https://github.com/everhush/DOC/blob/master/docs/GENERAL-PURPOSE-PROGRAMS.md), [generated compute](https://github.com/everhush/DOC/blob/master/docs/DOC-GENERATED-COMPUTE.md), [Radar Chase game](https://github.com/everhush/DOC/blob/master/engine/RADAR-CHASE.md) and [3D game](https://github.com/everhush/DOC/blob/master/engine/RADAR-CHASE-3D.md). The optional game was validated in development but is not included in the current core source candidate.

## Validation and release status

- [Native compiler validation (#11)](https://github.com/everhush/DOC/issues/11) and [performance evidence (#9)](https://github.com/everhush/DOC/issues/9).
- [Release qualification (#14)](https://github.com/everhush/DOC/issues/14), [readiness register](https://github.com/everhush/DOC/blob/master/docs/RELEASE-READINESS.md) and [qualification runs](https://github.com/everhush/DOC/actions/workflows/doc14-release-candidate.yml).
- [Candidate validation guide](release/README.md) describes the separate signed bootstrap, clean CPU rebuild, exact physical fixture, scaling and device-retirement checks.

The previous signed clean CPU rebuild and GPU executable compilation passed. The consolidated 90-file candidate's staging and signed verification passed, but the full consolidated run is still outstanding. A build-only pass is not physical execution; historical hardware evidence is not an exact-revision acceptance. Master retains historical evidence and immutable reference/bootstrap source. No public installable compiler release, product support promise or automatic manuscript resubmission is implied.

## Licensing and collaboration

The existing [LICENSE](LICENSE), [Apache 2.0 text](LICENSE-APACHE) and [NOTICE](NOTICE) govern their stated scope: research and documentation under CC BY 4.0, original software additionally available under Apache-2.0. Previous grants are not revoked; third-party material retains its applicable terms. The future source-available distribution requires specific reviewed license terms and third-party/publisher rights clearance. Research questions, bug reports and reproducibility findings can be discussed through the [issue tracker](https://github.com/everhush/DOC/issues). Include the exact revision, host/toolchain and reproducible command when reporting an issue.
