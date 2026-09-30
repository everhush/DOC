// Dependency-Oriented Computation manuscript source.
// Active-set finite core: G=(S, Delta), Q=(nu, A)
// Uses only Typst standard-library features.

#set document(
  title: "Dependency-Oriented Computation: Persistent-Graph Semantics for Incremental Repair",
  author: "Rituraj Basak",
  keywords: ("dependency-oriented computation", "incremental computation", "persistent dependency graphs", "reactive computation", "parallel evaluation", "dataflow", "recurrence", "runtime semantics"),
)
#set page(
  paper: "a4",
  margin: (top: 20mm, bottom: 21mm, left: 22mm, right: 22mm),
  numbering: "1",
  number-align: center,
  header: context {
    if counter(page).get().first() > 1 {
      align(left)[#text(size: 7.8pt, fill: luma(105))[Dependency-Oriented Computation]]
    }
  },
)
#set text(size: 10.2pt, lang: "en")
#set par(justify: true, leading: 0.70em, first-line-indent: 0em)
#set heading(numbering: "1.")
#set figure(gap: 4pt)
#set math.equation(numbering: "(1)")
#set enum(numbering: "1.")
#set list(indent: 1.15em, body-indent: 0.55em)
#set table(inset: 5.5pt, stroke: 0.45pt + luma(205))
#show link: set text(fill: rgb("1f5a88"))
#show heading.where(level: 1): it => block(above: 1.25em, below: 0.65em, sticky: true)[
  #text(size: 15pt, weight: "bold", fill: rgb("203a5f"))[#it]
]
#show heading.where(level: 2): it => block(above: 1.05em, below: 0.48em, sticky: true)[
  #text(size: 12pt, weight: "bold", fill: rgb("284d6d"))[#it]
]
#show heading.where(level: 3): it => block(above: 0.92em, below: 0.38em, sticky: true)[
  #text(size: 10.65pt, weight: "semibold", fill: rgb("354f63"))[#it]
]
#show raw.where(block: true): it => block(
  width: 100%, inset: 8pt, fill: luma(247), stroke: 0.45pt + luma(205),
  radius: 3pt, breakable: true,
)[#it]
#show quote: it => block(
  width: 100%, inset: (x: 10pt, y: 7pt), fill: rgb("edf4fa"),
  stroke: 0.65pt + rgb("203a5f"), radius: 3pt,
  above: 0.55em, below: 0.55em,
)[#it.body]

#let ink = rgb("203a5f")
#let accent = rgb("2f6b92")
#let green = rgb("2f7358")
#let pale = rgb("f5f8fb")
#let warm = rgb("9a5a2b")
#let greenfill = rgb("eef7f1")
#let warmfill = rgb("fff7ed")
#let bluefill = rgb("eef4fa")

// Native Typst coordinate diagrams. Nodes and arrows share one coordinate plane,
// so every connector terminates at an explicit node boundary rather than at a grid gap.
#let dnode(x, y, body, w: 82pt, h: 28pt, fill: white, stroke: accent, size: 8.5pt) = place(
  top + left, dx: x, dy: y,
)[
  #rect(width: w, height: h, fill: fill, stroke: 0.75pt + stroke, radius: 4pt)[
    #align(center + horizon)[#text(size: size, weight: "semibold")[#body]]
  ]
]
#let dpanel(x, y, w, h, title, stroke: accent) = place(top + left, dx: x, dy: y)[
  #rect(width: w, height: h, fill: white, stroke: 0.7pt + stroke, radius: 4pt)[
    #align(center)[#text(size: 8.6pt, weight: "bold")[#title]]
  ]
]
#let dlabel(x, y, body, size: 8pt, fill: luma(70)) = place(top + left, dx: x, dy: y)[
  #text(size: size, fill: fill)[#body]
]
#let dline(x1, y1, x2, y2, stroke: 0.8pt + ink) = place(top + left, dx: x1, dy: y1)[
  #line(start: (0pt, 0pt), end: (x2 - x1, y2 - y1), stroke: stroke)
]
#let darrow(x1, y1, x2, y2, stroke: 0.8pt + ink, fill: ink) = {
  let dx = x2 - x1
  let dy = y2 - y1
  let angle = calc.atan2(dx / 1pt, dy / 1pt)
  dline(x1, y1, x2, y2, stroke: stroke)
  place(top + left, dx: x2, dy: y2)[
    #move(dx: -7pt, dy: -3.5pt)[
      #rotate(angle, origin: right + horizon)[
        #polygon((0pt, 0pt), (7pt, 3.5pt), (0pt, 7pt), fill: fill)
      ]
    ]
  ]
}
#let diagram(h, body, caption) = figure(
  block(width: 100%, height: h, breakable: false, inset: 4pt,
    fill: pale, radius: 4pt, stroke: 0.45pt + luma(215))[
    #body
  ],
  caption: caption,
  kind: "figure",
  supplement: [Figure],
  numbering: "1",
)
#let statement(kind, title, body, tone: "neutral", breakable: true) = {
  let color = if tone == "theorem" { ink }
    else if tone == "definition" { green }
    else if tone == "warning" { warm }
    else { accent }
  let fill = if tone == "theorem" { bluefill }
    else if tone == "definition" { greenfill }
    else if tone == "warning" { warmfill }
    else { rgb("f7f9fb") }
  block(
    width: 100%, inset: (x: 9pt, y: 7pt), radius: 3pt,
    fill: fill, stroke: 0.7pt + color, breakable: breakable,
    above: 0.55em, below: 0.55em,
  )[
    #strong[#kind]
    #(if title == none { [] } else { [#h(0.35em)#emph[#title]] })
    #linebreak()
    #body
  ]
}
#let formal-statement(kind, title, body, tone: "theorem", breakable: true) = figure(
  block(
    width: 100%, inset: (x: 9pt, y: 7pt), radius: 3pt,
    fill: if tone == "definition" { greenfill } else { bluefill },
    stroke: 0.7pt + if tone == "definition" { green } else { ink },
    breakable: breakable, above: 0.55em, below: 0.55em,
  )[
    #context {
      let n = counter(figure.where(kind: lower(kind))).get().first()
      strong[#kind #n.]
      h(0.35em)
      emph[#title]
    }
    #linebreak()
    #body
  ],
  kind: lower(kind),
  supplement: kind,
  numbering: "1",
)
#let definition(title, body) = formal-statement("Definition", title, body, tone: "definition")
#let theorem(title, body) = formal-statement("Theorem", title, body)
#let lemma(title, body) = formal-statement("Lemma", title, body)
#let corollary(title, body) = formal-statement("Corollary", title, body)
#let proof(body) = block(
  width: 100%, inset: (left: 10pt, right: 4pt, top: 3pt, bottom: 5pt),
  stroke: (left: 1.1pt + luma(185)), breakable: true,
  above: 0.25em, below: 0.55em,
)[#strong[Proof.] #body #h(1fr) $square.stroked.tiny$]
#let abstract-box(body) = block(
  width: 100%, breakable: true,
  inset: (x: 11pt, y: 9pt),
  fill: luma(248), stroke: 0.7pt + ink, radius: 3pt,
  above: 0.55em, below: 0.55em,
)[#text(size: 10.2pt)[#strong[Abstract.] #body]]
#let principle(title, body) = statement("Principle", title, body)
#let boundary(title, body) = statement("Boundary", title, body, tone: "warning")

#align(center)[
  #v(10mm)
  #text(size: 21.5pt, weight: "bold", fill: ink)[Dependency-Oriented Computation:]
  #linebreak()
  #text(size: 18pt, weight: "bold", fill: ink)[Persistent-Graph Semantics for Incremental Repair]
  #v(18pt)
  #text(size: 11.5pt, weight: "semibold")[Rituraj Basak]
  #linebreak()
  #text(size: 9.4pt)[Independent Researcher, India]
  #v(5pt)
  #text(size: 9.2pt)[Corresponding author: #link("mailto:ycantistudy@gmail.com")[ycantistudy\@gmail.com]]
  #linebreak()
  #text(size: 9.2pt)[ORCID: #link("https://orcid.org/0009-0002-7347-7064")[0009-0002-7347-7064]]
]
#v(20pt)

#abstract-box([
Long-lived programs such as compilers, build systems, maintained queries, and simulations repeatedly recompute after small changes. This paper defines *Dependency-Oriented Computation* (DOC), a semantics in which the persistent program state is an explicit finite graph of typed logical states and local definitions. For the finite kernel, a program is $G=(S,Delta)$ and a repair configuration is $Q=(nu,A)$: $nu$ is the retained valuation and $A$ is the transient set of derived states that may require reconsideration after a source update.

A derived state $d$ has an ordered premise sequence $P_d$ and a pure, total, deterministic transformation $f_d$. A repair transition selects any nonempty subset of the dependency-minimal active frontier, evaluates every selected definition from one settled pre-valuation, and atomically publishes the changed conclusions. A sound equality predicate may stop propagation when a recomputed value equals the retained value; an always-false predicate remains correct and simply performs more work.

For finite acyclic programs, the paper proves termination of every legal repair schedule, uniqueness of the stable valuation, agreement with complete topological reevaluation, schedule independence, a per-episode at-most-once evaluation bound, and dependency-local repair. The assumptions are explicit: failures and external effects must be represented as values or handled outside the pure finite kernel. Recurrence, immutable graph-version replacement, logical availability, placement, and fail-stop reconstruction are presented separately with their additional contracts rather than as consequences of the finite theorem.

A C++20 executable witness and five bounded model checkers test the stated semantics against complete reevaluation and independent oracles. Reproduced benchmarks on the supplied environment show the intended cost shape rather than universal speedup: sparse updates avoid most graph work, a coarse ready frontier uses up to four externally granted participants, a specialized cached financial baseline remains substantially faster than generic DOC repair, and a fine-grained sorting network is a negative case in which runtime overhead dominates.
])

#block(width: 100%, inset: (x: 2pt, y: 4pt))[
  #text(size: 9.4pt)[#strong[Keywords:] dependency-oriented computation; incremental computation; persistent dependency graphs; reactive computation; parallel evaluation; dataflow; recurrence; runtime semantics.]
]

#pagebreak()

= Introduction

Many long-lived programs repeatedly compute almost the same result. A compiler receives another edit, a build receives another file change, and a maintained query receives another transaction. The central execution question is therefore not only how to evaluate a program once, but how to preserve justified results and repair only the part whose premises may have changed.

This paper studies that problem through an explicit persistent dependency graph. A *state* is a stable logical identity with a typed value. A *source* receives an environmental fact. A *derived state* is produced by one local definition from an ordered sequence of premise states. A *persistent conclusion* in this paper means the currently retained value of a derived state together with its logical identity; it remains reusable only while the dependency semantics continues to justify it.

== Running example and repair problem

Consider four logical states:

```text
source a = 2
source b = 3
sum     = add(a, b)
doubled = multiply(sum, 2)
```

The premise occurrences induce the graph in @fig:running-graph. Initial evaluation materializes `sum = 5` and then `doubled = 10`. Suppose one atomic source batch later installs `a := 4` and `b := 1`. Only `sum` is directly invalidated. Recomputing `sum` again yields $5$. If the runtime can prove that the new value equals the retained value, propagation stops and `doubled = 10` remains justified without reevaluation. If equality cannot be proved cheaply, the runtime may conservatively reevaluate `doubled`; the final value is unchanged.

#diagram(84pt, [
  #dnode(18pt, 8pt, [$a$ source], w: 90pt, fill: greenfill, stroke: green)
  #dnode(18pt, 48pt, [$b$ source], w: 90pt, fill: greenfill, stroke: green)
  #dnode(190pt, 28pt, [$upright("sum")$], w: 92pt, fill: warmfill, stroke: warm)
  #dnode(360pt, 28pt, [$upright("doubled")$], w: 94pt, fill: bluefill)
  #darrow(108pt, 22pt, 190pt, 40pt)
  #darrow(108pt, 62pt, 190pt, 44pt)
  #darrow(282pt, 42pt, 360pt, 42pt)
], [The running program. Premise occurrence in the two local definitions induces the dependency graph used both for evaluation order and later repair.]) <fig:running-graph>

This small example contains the paper's finite mechanism. The program graph persists. The valuation persists. A source batch creates a temporary set of repair obligations. The next eligible work is determined from dependency order rather than from a separately maintained invalidation or scheduling graph. Equality cutoff is an optimization of propagation, not a correctness requirement.

== Problem statement

The finite problem addressed here is: given a persistent finite acyclic graph, retained values from a previous stable point, and a validated source update, define a repair relation that (i) never observes an inconsistent intermediate result, (ii) permits any dependency-respecting sequential or parallel schedule, (iii) terminates, and (iv) reaches the same result as complete reevaluation. The formal kernel in @sec:core gives that relation; @sec:metatheory proves its properties.

The model intentionally does not treat every practical concern as part of this theorem. Real compilers and build systems invoke fallible tools, interact with files and processes, and perform effects. Within the finite kernel, such behavior must either be made explicit in the value domain (for example, a typed success/error result) while the local transformation remains total and deterministic, or remain outside the kernel behind an explicit effect or recovery boundary. @sec:assumptions states these assumptions before the semantics is used.

== Scope and technical contribution

DOC does not claim that dependency graphs, incremental repair, demand, caching, or parallel evaluation are individually new. The contribution evaluated in this paper is the particular finite factorization around a declared persistent logical-state graph $G=(S,Delta)$, a retained valuation $nu$, an explicit repair-obligation set $A$, and one frontier-subset transition. The same rule covers first materialization and later repair; the dependency-minimal frontier supplies legal independent work; and sound one-way equality cutoff can reduce propagation without becoming part of the semantic equality relation.

The closest prior models often make different representational choices. Self-adjusting computation records and updates dynamic dependence structures produced by execution; Adapton adds demand to an incremental computation graph; build-system models separate scheduling and rebuilding components; differential/timely dataflow use richer version or timestamp structures for iterative distributed dataflow. @sec:related-work compares these choices directly rather than claiming historical priority for dependency tracking itself.

== Semantic boundary

A DOC local definition may be arithmetic, pattern matching, a query operator, a vector kernel, a verified routine, or another deterministic host function. DOC specifies the global relation among persistent states: which conclusions are justified, which states become repair obligations, what work is ready, when a repair episode is stable, and what stable value may be observed. It does not prescribe one universal syntax for the internals of every local function.

When internal structure matters for reuse or parallelism, a coarse local definition can be replaced by a finite boundary-equivalent DOC expansion. Conversely, an implementation may physically fuse several logical definitions when that preserves the same observations. This keeps the formal boundary small while making the granularity trade-off explicit.

#block(width: 100%, inset: (x: 9pt, y: 7pt), fill: rgb("f7f9fb"), stroke: 0.55pt + luma(210), radius: 3pt, above: 0.7em, below: 0.75em)[
  #text(size: 9.55pt)[#strong[Reading guide.] The next four sections establish the model intuition, assumptions, finite transition system, and central stabilization results. The paper then separates demand and recurrence, immutable graph change, and physical realization contracts from that finite theorem. The final sections report executable validation and performance evidence, state limitations, compare prior work, and conclude.]
]

= Model intuition and contributions

DOC separates logical meaning from physical mechanisms that may vary without changing it. @tab:claim-map states what is proved, what is conditional on additional contracts, and what is supported only by the current implementation or measurements.

#figure(
  table(
  columns: (1.08fr, 2.35fr, 1.55fr),
  table.header([*Layer*], [*Contains*], [*Status*]),
  [Finite core], [$G=(S,Delta)$, valuation, active set, source batch, frontier-subset transition, observation], [Proved; implemented; differentially and exhaustively checked in bounded domains],
  [Versioned recurrence], [Epoch-indexed templates, carry bindings, finite demanded prefixes, retention, divergence, universality argument], [Defined extension; finite-prefix execution implemented],
  [Immutable graph versions], [$G_k arrow.r G_(k+1)$, stable names, semantic compatibility, private validation and atomic commit], [Defined extension; implemented against from-scratch evaluation],
  [Safe realization], [Private evaluation, complete immutable publication, protected reads, roots, reclamation], [Normative contract; typed object-store witness],
  [Placed realization], [Resources, logical roles, TCP transport, generations, join, drain, and bounded fail-stop reconstruction], [Conditional theorem; executable loopback witness],
  [Policy-bearing boundaries], [Fixed points, conflict and replica policy, partitions, retention, irreversible external semantics], [Must be explicit; not inferred from dependency],
),
  caption: [Claim and evidence map. The finite theorem, extensions, physical contracts, and implementation evidence are intentionally separated.],
) <tab:claim-map>

The consequences in @tab:structural-properties are not additional theorem claims. They identify implementation opportunities exposed by the declared dependency structure. The table states only the structural reason each opportunity exists; scheduling, collection, transport, placement, and topology-version construction remain implementation choices constrained by the observation contracts stated later.

#figure(
  table(
  columns: (1.3fr, 3fr),
  table.header([*Property*], [*Structural basis*]),
  [Reactivity], [A source batch activates induced users; no separate watcher graph is required.],
  [Temporal reuse], [Stable retained values remain justified until an affected definition proves otherwise.],
  [Parallelism], [The ready frontier is dependency-minimal and its conclusions are distinct.],
  [Memory safety], [Logical identities and immutable publication permit protected use and automatic reclamation without physical pointers in ordinary programs.],
  [Distribution], [Remote premise occurrence becomes a transport obligation; placement and generation authority remain runtime concerns rather than application topology.],
  [Elasticity], [Resources may join, drain, or fail while logical identities and application graph remain unchanged; reconstruction follows authoritative sources and pure dependencies.],
),
  caption: [Structural consequences and their source in the persistent dependency representation.],
) <tab:structural-properties>

The status distinctions used throughout the paper are exact: *proved core* means a theorem about the finite relation; *defined extension* means additional semantics stated separately; *realization contract* means physical obligations required to preserve observation; *executable evidence* means tested behavior of one implementation; and *remaining boundary* means policy or physics that dependency cannot determine by itself.

= Standing assumptions and scopes <sec:assumptions>

The assumptions are collected here so later definitions and results need not restate them. @tab:assumptions is also the applicability checklist for compilers, build systems, and other motivating applications: fallible external tools must be represented as explicit values or placed outside the pure finite kernel.

The abstract finite transition rule itself needs no scheduler-fairness premise: every transition selects a nonempty ready subset, and the acyclic work argument bounds the number of selections. Fairness appears only in physical progress claims that allow work or reclamation to be postponed by a runtime.

For a compiler or build system, the purity and totality conditions in @tab:assumptions are a modeling obligation rather than a claim that external tools never fail. File contents, command-line arguments, tool versions, configuration, and other relevant environmental facts can be explicit source values. A fallible deterministic tool result can be represented as a typed value such as `Result<Artifact, Error>` if the invocation is fully determined by those premises. Nondeterministic process execution, network calls, authorization, and irreversible external actions instead occur outside the finite local transformation; their committed outcome becomes a later source fact. This distinction is what allows the finite theorem to remain precise without denying effects in the surrounding application.

#figure(
  table(
  columns: (1.05fr, 3fr),
  table.header([*Scope*], [*Assumptions*]),
  [Finite kernel], [The state family and every premise sequence are finite; the induced dependency graph is acyclic; each local transformation is pointwise typed, pure, deterministic, total, and terminating for every typed premise tuple; accepted source batches are pointwise typed; and every cutoff predicate is sound, although it may conservatively return false. A finite program satisfying these conditions is *well formed*. Stabilization begins from a repair-admissible configuration as defined in the finite semantics; stable boundaries are its quiescent special case.],
  [Sources, failures, and effects], [Environmental nondeterminism enters through committed source batches. Recoverable absence or failure is represented explicitly inside a value domain. Host exceptions, cancellation policy, authorization, and irreversible external actions are outside ordinary local transformations.],
  [Versioned recurrence], [Each epoch instance satisfies the finite-kernel assumptions. Carry is a typed single-authority partial function from next-epoch sources to previous-epoch states and points strictly forward in logical time. Every uncarried source receives an explicit epoch-local fact or declared fixed default. A completed observation requests only a finite epoch prefix; an indefinitely extended demand may diverge.],
  [Graph versions], [A candidate graph is well formed, validated and stabilized privately from a repair-admissible seed. Direct reuse requires stable identity, the same source/derived authority role, the same declared value domain and semantic equality, and an explicit observational-compatibility contract before atomic generation commit. A domain change marks the state affected and is expressed by an explicit candidate transformation.],
  [Physical realization], [Logical observations are returned only at committed stable boundaries. Values captured by active evaluation, publication, observation, or transport remain protected. Claims about eventual reclamation, transport, join, drain, or recovery apply only under their stated eventual-progress and quiescence conditions.],
),
  caption: [Standing assumptions by semantic scope. Only the finite-kernel row is assumed by the central stabilization theorem.],
) <tab:assumptions>

= Core semantics <sec:core>

This section defines the finite logical kernel used by the metatheory in @sec:metatheory. It proceeds from the program objects and satisfaction relation to initialization, source updates, the ready frontier, and the single repair transition. @tab:semantic-guide summarizes which later claims use this kernel directly and which require additional contracts.

#block[
  #set text(size: 8.75pt)
  #set table(inset: 3.6pt)
  #figure(
    table(
    columns: (1.22fr, 1.65fr, 1.25fr),
    table.header([*Layer*], [*Claim made here*], [*Evidence status*]),
    [Finite logical kernel], [Acyclic stabilization, unique stable values, complete-reevaluation agreement, schedule independence, sound cutoff, and source-local repair.], [Human-readable proof, bounded exhaustive checking, and executable differential tests.],
    [Demand and recurrence], [Ancestor-closed demand agrees with full evaluation; finite requested recurrence prefixes require finite support; unbounded demand supplies partial computation.], [Propositions by restriction and induction; bounded exhaustive and runtime checks of finite prefixes.],
    [Graph evolution], [A compatible immutable replacement agrees with from-scratch evaluation of the candidate graph.], [Conditional proposition under the declared compatibility contract; bounded and runtime checks.],
    [Physical realization], [Publication, storage, reconstruction, placement, transport, recovery, and effects preserve logical observations.], [Conformance contracts and targeted runtime tests, not unconditional theorems of the finite kernel.],
    [Performance], [Sparse change can avoid work and coarse frontiers can use granted processors; overhead can dominate dense or fine-grained work.], [Environment-specific empirical measurements with correctness oracles and negative controls.],
  ),
    caption: [Guide to the finite semantics and later evidence. Rows distinguish proved finite semantics from conditional extensions and empirical observations.],
  ) <tab:semantic-guide>
]

The table separates mathematical consequences of the kernel from extensions, realization obligations, and empirical evidence. None of the latter is stored in $G$ or $Q$.

== Basic objects and satisfaction

A finite DOC program is

$ G=(S,Delta), $ <eq:program>

where $S$ is a finite family of stable logical state identities and $Delta$ is a partial map whose domain contains exactly the derived states. Every $s in S$ has a declared value domain $V_s$. @eq:program fixes the notation used throughout the finite semantics; physical addresses, workers, and storage locations are not elements of $S$.

=== Typed state

#definition([State], [A state is a stable logical identity $s in S$ with a value domain $V_s$. Its identity is independent of a memory address, thread, process, machine, or storage location.]) <def:state>

A state may currently be unmaterialized. Each domain $V_s$ has its ordinary semantic equality. A realization may additionally provide a total decidable cutoff predicate

$ upright("same")_s: V_s times V_s arrow.r upright("Bool"), #h(1em) upright("same")_s #h(0.08em) (x,y)=upright("true") #h(0.3em) arrow.r.double #h(0.3em) x=y. $ <eq:cutoff-soundness>

The implication is the only soundness requirement: the predicate may conservatively return false even for equal values. The always-false predicate is therefore valid and yields complete propagation without cutoff. The C++20 witness uses exact signed-integer equality by default and also tests this conservative mode. Hash-only or tolerance tests are not valid unless returning true proves equality in the declared value domain.

The executable witness uses one scalar domain, but the model permits distinct domains.

=== Local definition

#definition([Local definition], [For each derived state $d$, let its ordered premise sequence be
$ P_d=(s_1,dots.h,s_k). $
The partial definition map stores
$ Delta(d)=(P_d,f_d), $
where
$ f_d: V_(s_1) times dots.h.c times V_(s_k) arrow.r V_d $
is a local transformation satisfying the standing finite-kernel assumptions in @sec:assumptions.]) <def:local-definition>

The conclusion is the map key $d$ itself. No separate computation identity, output map, source flag, or producer map is required. Zero-premise definitions represent constant derived states. Thus $P_d$ is notation for the premise sequence stored in $Delta(d)$; it is not an additional program component.

Let

$ D = upright("dom")(Delta), #h(1.5em) S_(upright("src")) = S-D. $ <eq:state-partition>

States in $D$ are derived. States outside $D$ are sources. Single-producer authority follows from the partial-map representation.

=== Dependency and users

A state $x$ is a direct premise of $d$ when $x$ occurs in the premise sequence of $Delta(d)$. Its transitive closure is dependency order. Users are induced rather than separately declared:

$ upright("users")(x) = {d in D | x upright(" occurs in ") P_d}. $ <eq:users>

=== Valuation and satisfaction

A valuation is pointwise typed:

$ nu(s) in V_s union {bot} #h(0.5em) upright("for every") #h(0.5em) s in S, $ <eq:valuation>

where $bot$ means no current materialization. It is not application-level null, deletion, failure, or unknown data; those meanings must be represented explicitly inside the relevant value domain. For $P_d=(s_1,dots.h,s_k)$, define the tuple shorthand

$ nu(P_d) := (nu(s_1),dots.h,nu(s_k)). $ <eq:premise-valuation>

If $Delta(d)=(P_d,f_d)$, then $d$ is locally satisfied when every component of $nu(P_d)$ is materialized and

$ nu(d)=f_d(nu(P_d)). $ <eq:satisfaction>

Thus expressions such as $f_d(nu(P_d))$ always mean application of $f_d$ to the ordered tuple in @eq:premise-valuation; no separate function $d(cases())$ is implied.

Local satisfaction uses equality in the declared value domain. The operational cutoff predicate is separate: it may decline to recognize an equality, but it may never claim sameness for unequal values. A quotient or approximate domain must therefore define its value domain and equality first; a heuristic hash or tolerance cannot silently change the semantics.

=== Observation

An observation requests the stable value of a logical state. Observation is an operation on the program, or an access policy outside it, not another component of $G$. The finite rule below is stated for whole-graph epochs. Demand-restricted execution is obtained by applying the same rule to the ancestor-closed induced subprogram of the requested state, with its boundary sources materialized. The C++20 witness conservatively stabilizes the whole finite graph.

== Computational expansion

A local definition may be too coarse to expose useful reuse, parallelism, placement, or repair. Expansion refines granularity without changing boundary meaning.

#definition([Expansion], [If $Delta(d)=(P,f_d)$, an expansion replaces it by a finite pure acyclic DOC subgraph that reads the same boundary premises $P$, publishes to the same boundary state $d$, uses fresh internal identities, and yields $f_d$ for every typed boundary tuple.]) <def:expansion>

#diagram(126pt, [
  #dlabel(10pt, 2pt, [coarse definition], size: 7.8pt)
  #dnode(24pt, 16pt, [$P$], w: 56pt, fill: greenfill, stroke: green)
  #dnode(126pt, 16pt, [opaque $f_d$], w: 88pt, fill: warmfill, stroke: warm)
  #dnode(260pt, 16pt, [$d$], w: 56pt, fill: bluefill)
  #darrow(80pt, 30pt, 126pt, 30pt)
  #darrow(214pt, 30pt, 260pt, 30pt)

  #dlabel(10pt, 60pt, [boundary-equivalent expansion], size: 7.8pt)
  #dnode(24pt, 74pt, [$P$], w: 56pt, fill: greenfill, stroke: green)
  #dnode(116pt, 74pt, [$g_1$], w: 54pt)
  #dnode(196pt, 74pt, [$g_2$], w: 54pt)
  #dnode(276pt, 74pt, [$g_3$], w: 54pt)
  #dnode(368pt, 74pt, [$d$], w: 56pt, fill: bluefill)
  #darrow(80pt, 88pt, 116pt, 88pt)
  #darrow(170pt, 88pt, 196pt, 88pt)
  #darrow(250pt, 88pt, 276pt, 88pt)
  #darrow(330pt, 88pt, 368pt, 88pt)
  #dlabel(120pt, 108pt, [same boundary premises $P$ and conclusion $d$; equal for every typed boundary tuple], size: 7.3pt, fill: ink)
], [Expansion replaces one coarse definition by a finite DOC subgraph with the same premises and boundary result; the two rows are alternatives, not connected computation stages.]) <fig:expansion>

@fig:expansion illustrates this refinement. An implementation may fuse or batch an expanded region physically while retaining its logical boundaries. Expansion is therefore a semantic granularity choice, not an obligation to schedule every primitive separately.

== Initial and later stabilization

Consider:

```text
source a = 2
source b = 3
sum     = add(a, b)
doubled = multiply(sum, 2)
```

=== Initial stabilization

Initially, sources are present, derived states are absent, and every definition is active. `sum` evaluates to $5$; then `doubled` evaluates to $10$.

=== Later stabilization after change

Now one atomic source batch changes both sources:

```text
a := 4
b := 1
```

`sum` is reconsidered and again produces $5$. Under the exact cutoff predicate used by the canonical example, the retained equality is proven, so `doubled` is not activated. With an always-propagate predicate, `doubled` would harmlessly reevaluate to the same $10$.

#diagram(122pt, [
  #dlabel(8pt, 7pt, [initial materialization], size: 7.8pt)
  #dnode(18pt, 22pt, [$a=2, b=3$], w: 116pt, fill: greenfill, stroke: green)
  #dnode(184pt, 22pt, [$upright("sum"):=5$], w: 108pt, fill: warmfill, stroke: warm)
  #dnode(342pt, 22pt, [$upright("doubled"):=10$], w: 116pt, fill: bluefill)
  #darrow(134pt, 36pt, 184pt, 36pt)
  #darrow(292pt, 36pt, 342pt, 36pt)
  #dlabel(8pt, 62pt, [later source batch], size: 7.8pt)
  #dnode(18pt, 76pt, [$a:=4, b:=1$], w: 116pt, fill: greenfill, stroke: green)
  #dnode(184pt, 76pt, [recompute $upright("sum")=5$], w: 108pt, fill: warmfill, stroke: warm)
  #dnode(342pt, 76pt, [equal: retain $10$], w: 116pt, fill: greenfill, stroke: green)
  #darrow(134pt, 90pt, 184pt, 90pt)
  #darrow(292pt, 90pt, 342pt, 90pt)
  #dlabel(338pt, 108pt, [cutoff: `doubled` is not activated], size: 7.6pt, fill: ink)
], [Initial materialization and later repair use the same stabilization relation. Retained equality stops the later wave.]) <fig:repair-example>

@fig:repair-example shows the equality-cutoff case. The difference between initial and later stabilization is only what is already retained: initial evaluation begins with $bot$ at every derived state; a later epoch begins with stable values that may remain useful.

== Finite active-set transition system

With the program $G$ fixed by @eq:program, the operational configuration is

$ Q=(nu,A), #h(2em) A subset.eq D. $ <eq:configuration>

$nu$ persists across epochs. $A$ is transient and records *repair obligations*: derived states whose definitions may need reconsideration. Membership in $A$ does not assert that the retained value is already known to be unequal; an active state may reevaluate to the same value and stop propagation.

A configuration $Q=(nu,A)$ is *repair-admissible* when every source is materialized and every inactive derived state is materialized and locally satisfied:

$ (forall s in S_(upright("src")): nu(s) != bot) #h(1em) upright("and") #h(1em)
  (forall d in D-A: nu(d) != bot #h(0.35em) upright("and") #h(0.35em) d upright(" is locally satisfied")). $ <eq:admissible>

An active derived state may retain an old materialization or may be $bot$. A configuration is *quiescent* when $A=emptyset$; a repair-admissible quiescent configuration is exactly a stable valuation. Initialization, accepted source repair, compatible graph-version seeds, and reconstruction all enter the same transition relation through this invariant.

=== Ready frontier

Write $e prec d$ when derived state $e$ is a transitive premise of $d$. For an active set $A$, define the dependency-minimal frontier

$ R(A)={d in A | exists.not e in A: e prec d}. $ <eq:ready-frontier>

Every member of $R(A)$ has no active strict ancestor. In a repair-admissible configuration, this implies that all of its premises are materialized: a source is materialized by definition; an inactive derived premise is materialized and satisfied; and an active derived premise, or one below an active ancestor, would prevent readiness. Distinct frontier members cannot depend on one another and have distinct conclusions.

=== Initialization

Let $I$ be a total pointwise-typed initial environment over $S_(upright("src"))$. Initialization constructs

$ nu_0(s)=cases(I(s) & s in S_(upright("src")), bot & s in D), #h(1.2em) A_0=D. $ <eq:initial-seed>

Here $nu_0$ names the seed valuation at the start of this stabilization episode; the subscript does not denote a different kind of valuation. Stabilization then performs ordinary first evaluation. The initialization configuration is repair-admissible because every derived state is active. More generally, $bot$ may occur only at an active derived state in any repair-admissible configuration.

=== Source update

Let $U_b$ be a finite pointwise-typed partial function whose domain is contained in $S_(upright("src"))$. A runtime accepts it only after validating every target and value. A list representation must also reject duplicate targets before changing any state; that rejection merely enforces that $U_b$ is a function.

Given a repair-admissible configuration $(nu,A)$, define the assignments not proven equal by the source cutoff predicates:

$ X={s in upright("dom")(U_b) | upright("same")_s #h(0.08em) (U_b(s),nu(s)) = upright("false")}. $ <eq:changed-sources>

The accepted source boundary step is

$ nu_0=nu[s arrow.r.bar U_b(s) #h(0.25em) upright("for") #h(0.25em) s in X], $ <eq:update-valuation>

$ A_0=A union union_(s in X) upright("users")(s). $ <eq:update-active>

@eq:update-valuation and @eq:update-active define the post-boundary seed $(nu_0,A_0)$ for the next stabilization episode. The subscript $0$ means "after the boundary event and before the first repair transition." The assignments in $X$ are installed atomically, and the direct users of those sources are added to any obligations already present. The step preserves repair-admissibility: an inactive direct user of a changed source becomes active, while every other inactive state remains locally satisfied until a changed active premise publishes. An empty batch, or a batch whose assignments are all proven equal, yields $X=emptyset$ and leaves $A$ unchanged. With a conservative always-false predicate, an exactly equal assignment may still start harmless repair. Stable-boundary epochs are the common case $A=emptyset$; after an exceptional frontier failure, a later serialized source batch may instead supersede the still-active obligations without discarding them.

=== One frontier-subset transition

Choose any nonempty finite frontier selection

$ emptyset != F subset.eq R(A). $ <eq:frontier-selection>

For each $d in F$ with $Delta(d)=(P_d,f_d)$, evaluate privately from the same pre-transition valuation:

$ v_d=f_d(nu(P_d)). $ <eq:candidate>

Let the propagating-conclusion set be

$ C_F={d in F | nu(d)=bot} union
  {d in F | nu(d) != bot #h(0.3em) upright("and") #h(0.3em) upright("same")_d #h(0.08em) (v_d,nu(d)) = upright("false")}. $ <eq:propagating-set>

Publish every candidate in $C_F$ as one logical commit and define

$ nu' = nu[d arrow.r.bar v_d #h(0.3em) upright("for") #h(0.3em) d in C_F], $ <eq:publish>

$ A' = (A-F) union union_(d in C_F) upright("users")(d). $ <eq:next-active>

Then

$ (nu,A) arrow.r (nu',A'). $ <eq:transition>

This is the sole finite repair rule. A singleton $F$ gives sequential execution. A larger $F$ gives parallel evaluation. All candidates read the same settled pre-state; the complete selected frontier joins before the logical commit. A candidate proven equal to its retained value is removed from $A$ but publishes no replacement and activates no user. If the cutoff predicate conservatively returns false, republishing and downstream activation remain correct but may do more work. The C++20 witness uses the deterministic policy $F=R(A)$ at every step; choosing a smaller eligible subset is allowed by the model but is not required of that witness.

=== Operational algorithm

@alg:finite-stabilization gives a stepwise reading of the equations from @eq:changed-sources through @eq:transition. It is not a second semantics: each loop iteration is exactly one valid transition of @eq:transition, while initialization and a later source batch differ only in how they construct the repair-admissible seed.

#figure(
  block(width: 100%, inset: 8pt, fill: luma(247), stroke: 0.45pt + luma(205), radius: 3pt)[
```text
Input: fixed finite program G=(S, Delta) and a repair-admissible seed Q=(nu, A)

1. Boundary step
   - Initial run: install all source facts, set every derived state to absent,
     and set A := D.
   - Later run: validate the whole source batch, atomically install the
     assignments not proven equal, and add their direct users to A.

2. While A is nonempty
   a. Compute R(A), the active states with no active strict ancestor.
   b. Choose any nonempty F subset of R(A).
   c. Evaluate every d in F privately from the same committed pre-valuation:
        v_d := f_d(nu(P_d)).
   d. After all selected evaluations complete, form C_F from candidates that
      are absent or not proven equal to their retained conclusions.
   e. Atomically publish the candidates in C_F.
   f. Remove F from A and add users(d) for every d in C_F.

3. When A is empty, expose the requested stable observation.
```
  ],
  caption: [Finite DOC stabilization. The scheduler may choose any nonempty subset of the ready frontier; the executable witness chooses the complete frontier.],
  kind: "algorithm",
  supplement: [Algorithm],
  numbering: "1",
) <alg:finite-stabilization>

#boundary([Failure before publication], [Typed `Result`, option, or error values are ordinary values when the local function remains total. A thrown host callback violates the finite theorem's totality premise. Defensively, if any candidate in $F$ throws before the barrier, the witness publishes none of that frontier and keeps every state in $F$ active. Accepted source facts remain committed. A realization may treat cancellation before publication the same way, but the witness exposes no cancellation API. Retry, rollback, and irreversible-action policy belong to the effect or recovery boundary rather than to pure stabilization.])

= Central metatheory <sec:metatheory>

#lemma([Frontier materialization and preservation], [In a repair-admissible configuration, every ready definition has materialized premises. An accepted source boundary step and every valid frontier-subset transition preserve repair-admissibility.]) <lem:preservation>

#proof([
Let $Q=(nu,A)$ be repair-admissible. If $d in R(A)$ and a premise $p$ is a source, $p$ is materialized by admissibility. If $p$ is derived and active, then $p prec d$, contradicting readiness; if it is inactive, admissibility makes it materialized and locally satisfied. Thus every candidate in a valid selection is defined.

For a source batch, consider any derived state left inactive after the batch. It was inactive before, and none of its source premises changed; otherwise it would be a direct user of a member of $X$ and would have been activated. Its value and all premises are therefore unchanged, so it remains materialized and satisfied.

For a frontier transition, let $x$ be inactive in $A'$. If $x in F$, all of its premises are outside $F$ and are unchanged by the commit. The candidate $v_x$ therefore satisfies its definition; if $x in.not C_F$, cutoff soundness gives $v_x=nu(x)$, so the retained value is the same satisfying value. If $x in.not F$, then $x$ was already inactive. Any selected premise that changed would place $x$ in the propagated user union, contrary to $x in.not A'$. Hence its conclusion and premises are unchanged and its prior satisfaction is preserved. Materialization follows in the same cases: selected unmaterialized conclusions are published, selected retained conclusions were already materialized, and previously inactive conclusions remain materialized.
])

#lemma([At-most-once selection and finite progress], [Fix one repair episode, meaning a repair-admissible seed followed only by frontier-subset transitions and no intervening accepted source batch. Every derived definition is selected at most once. Consequently every valid transition sequence in that episode is finite, and every maximal sequence ends quiescent.]) <lem:finite-progress>

#proof([
When $d$ is selected, it has no active strict ancestor. Suppose some strict ancestor of $d$ later became active, and choose the first such activation. Activation can arise only from publication by one of that ancestor's direct premises. That publishing premise is itself a strict ancestor of $d$ and must have been active and selected earlier, contradicting the choice of the first later ancestor activation. Sources do not change inside the fixed episode. Thus no strict ancestor of $d$ can publish after $d$ is selected, its premises cannot later change, and $d$ cannot be reactivated.

At most $|D|$ definitions are therefore selected, while each transition selects a nonempty set, so no valid sequence is infinite. If a finite maximal sequence ended with $A != emptyset$, acyclicity of the finite dependency order would give a minimal member of $A$, hence a nonempty ready frontier and another valid transition. Therefore a maximal sequence ends with $A=emptyset$.
])

#lemma([Canonical stable valuation], [For fixed current source values, there is exactly one stable valuation, namely complete topological reevaluation of every derived definition.]) <lem:canonical>

#proof([
Choose a topological order of $D$. Keep each current source value and define $mu(d)=f_d(mu(P_d))$ in that order. Totality and typing make $mu$ exist. Any stable valuation has the same source values. Inductively, when all premises of $d$ agree with $mu$, local satisfaction and determinism force its conclusion to equal $mu(d)$. Thus every stable valuation equals $mu$, and $mu$ is exactly complete reevaluation.
])

#theorem([Finite stabilization], [For every well-formed finite acyclic DOC program, begin from any repair-admissible configuration and hold sources fixed during the repair episode. Every valid frontier-subset transition sequence is finite. Every maximal sequence ends in the unique stable valuation produced by complete topological reevaluation. The result is independent of the eligible selections and their valid order, and sound exact cutoff does not change that result.]) <thm:finite-stabilization>

#proof([
@lem:preservation keeps every reached configuration repair-admissible. @lem:finite-progress makes every valid sequence finite and every maximal sequence quiescent. Quiescence together with repair-admissibility makes every derived state materialized and locally satisfied, so the terminal valuation is stable by @eq:admissible. @lem:canonical then identifies that terminal valuation uniquely with complete reevaluation. Hence every valid maximal schedule has the same result.

For exact cutoff, if $upright("same")_d(v_d,nu(d))$ is true, @eq:cutoff-soundness gives $v_d=nu(d)$. Retaining the old materialization is therefore observationally identical to publishing the candidate. An inactive direct user was satisfied before the transition and sees no changed premise, so it remains satisfied; an already active user remains active. Omitting activation through that equal conclusion therefore loses no repair obligation. Conservative false negatives may activate additional users, but preservation and uniqueness still force the same terminal valuation.
])

#corollary([Initial/later unity], [First materialization and later reactive repair are the same stabilization relation with different retained valuations.]) <cor:initial-later>

#corollary([Semantic caching and work bound], [At a stable boundary, every retained derived value is the unique correct value for its current premises. During one fixed repair episode each definition evaluates at most once. An accepted later source batch starts a new episode and unions its direct users with obligations retained after any exceptional failure.]) <cor:work-bound>

#corollary([Independent ready selections commute], [Let $F_1$ and $F_2$ be disjoint subsets of the same ready frontier. No selected conclusion is a premise of another selected conclusion, all candidates read the same settled values, writes target distinct states, and propagated users combine by set union. Evaluating and committing $F_1$ then $F_2$, $F_2$ then $F_1$, or $F_1 union F_2$ therefore yields the same valuation and active set.]) <cor:commute>

#corollary([Source-update locality], [For a source batch applied at a stable boundary, let $upright("Reach")^*(X)$ be the reflexive-transitive user closure containing the changed sources and every state reachable from them. Initial activation enters only direct users of $X$, and every later activation follows one user edge. No state outside that closure is selected or modified, so it retains its value.]) <cor:locality>

#corollary([Conservative cutoff], [Any cutoff predicate satisfying only the stated one-way soundness condition is correct. Returning false for equal values can add work inside the reachable region but cannot change the unique stable valuation.]) <cor:cutoff>

#theorem([Expansion preservation], [Replacing one definition by a finite acyclic boundary-equivalent expansion preserves every stable observation over the original states.]) <thm:expansion>

#proof([
Fix the source values and compare complete reevaluation of the original and expanded graphs. Every original state upstream of the replaced definition is unchanged. The fresh internal expansion has a unique stable valuation by @thm:finite-stabilization, and boundary equivalence makes its published value at $d$ equal to $f_d$ on the same boundary premises. A topological induction over the remaining original descendants then gives the same value at every original state. Schedule independence from @thm:finite-stabilization extends the argument from complete reevaluation to every valid stabilization schedule.
])

== Reactivity, reuse, and parallelism

Reactive systems are often described with subscriptions, observers, callbacks, or event handlers. DOC does not require a second event graph. The users induced by $Delta$ already state which definitions may be affected by a changed conclusion.

Consider the chain:

```text
temperature -> thermostat policy -> heater command
```

When `temperature` changes, only the thermostat definition is activated directly. If the policy result changes, the heater definition becomes active. If the cutoff predicate proves the newly derived policy equal to the retained policy, the wave stops and the retained heater command remains justified. Without such a proof, conservative propagation may reevaluate the heater but reaches the same command. Nothing else needs to subscribe to `temperature`: dependency is already the ordering relation, the possible-impact relation, and the path of repair.

== Retained values are semantic caches

At a stable boundary, every retained derived value is the unique result required by the current source values and local definitions. Reuse is therefore semantic rather than heuristic. A physical implementation may still hold an obsolete object temporarily, but that object cannot be returned as the current logical value after its state has become active.

The active set plays the role that manually maintained invalidation metadata often plays elsewhere. It says what may need reconsideration during the current source epoch. It does not duplicate the dependency graph and it disappears again when stabilization reaches $A=emptyset$.

== Incremental repair and equality cutoff

After a small source batch, the runtime repairs the propagated descendant region rather than reevaluating every definition. With exact cutoff, work follows actual value change; with a conservative predicate, the region may be larger but remains dependency-local. For a batch applied at a stable boundary, a state outside $upright("Reach")^*(X)$ receives no activation from that batch, so its stable value remains usable.

A reconsidered definition can still stop the wave. If the sound cutoff predicate proves that it computed the retained value, the definition is removed from the active set but its users are not activated. Determinism then makes retained descendants equal to what complete reevaluation would produce. If no practical equality test exists, the always-propagate predicate remains correct and merely gives up this optimization. Cutoff is therefore a verified refinement of stabilization, not a cache heuristic or a precondition for correctness.

The benefit depends on the workload. Dense change may activate nearly the whole graph. Expensive equality can erase savings. If definitions are extremely cheap, bookkeeping, synchronization, and publication can dominate. DOC exposes available reuse; it cannot manufacture useful reuse where the graph and update contain none.

== Parallelism from the same structure

Parallelism has the same cause as reactivity. The active region identifies work that may be necessary; its dependency-minimal frontier identifies independent next work.

#diagram(126pt, [
  #dlabel(164pt, 48pt, [same ready frontier $F subset.eq R(A)$], size: 7.9pt, fill: ink)
  #dnode(28pt, 8pt, [source $a$], w: 108pt, fill: greenfill, stroke: green)
  #dnode(28pt, 50pt, [left branch], w: 108pt, fill: warmfill, stroke: warm)
  #dnode(28pt, 92pt, [result $u$], w: 108pt, fill: bluefill)
  #dnode(330pt, 8pt, [source $b$], w: 108pt, fill: greenfill, stroke: green)
  #dnode(330pt, 50pt, [right branch], w: 108pt, fill: warmfill, stroke: warm)
  #dnode(330pt, 92pt, [result $v$], w: 108pt, fill: bluefill)
  #darrow(82pt, 36pt, 82pt, 50pt)
  #darrow(82pt, 78pt, 82pt, 92pt)
  #darrow(384pt, 36pt, 384pt, 50pt)
  #darrow(384pt, 78pt, 384pt, 92pt)
], [Independent active branches can belong to one ready frontier. No horizontal dependency edge connects the branches, and the program contains no thread count or concurrency syntax.]) <fig:frontier-parallelism>

@fig:frontier-parallelism shows two active branches in one ready frontier. No frontier member transitively depends on another frontier member: if it did, one member would require an active unsettled conclusion as a premise and would not be ready. Distinct frontier members also publish distinct logical conclusions because $Delta$ is a partial map keyed by conclusion state.

A DOC program therefore does not need to spell out `spawn`, `wait`, locks, queues, or a worker count merely to reveal independence. A realization may process a frontier sequentially, on several granted CPU cores, on accelerators, or across placed resources. The realization still needs synchronization: all selected candidates read one settled pre-state, private evaluation completes before the frontier publication barrier, and failed candidates must not leak partial publication. These mechanisms implement the semantic rule; they are not additional concurrency instructions in application code.

#principle([Shared cause], [Change exposes an affected dependency region; the dependency-minimal active frontier identifies necessary independent work. Reactivity, temporal reuse, and parallel readiness arise from the same persistent structure.])

== Reduction optimality and temporal reuse

Avoiding redundant work inside one isolated calculation and reusing results across later change are different objectives. They are compatible rather than mutually exclusive; @tab:optimization-boundaries makes the two optimization boundaries explicit.

#figure(
  table(
  columns: (1.22fr, 1.72fr, 1.72fr),
  table.header([*Question*], [*Local reduction optimization*], [*DOC temporal reuse*]),
  [Primary waste], [Repeated work within one execution], [Repeating maintained work after later partial change],
  [Boundary], [Inside a local definition or term], [Across persistent states and source-update epochs],
  [Best unit], [Expression, kernel, algorithm], [Affected dependency region and ready frontier],
  [Compatibility], [May optimize any $f_d$], [May retain or expand that optimized $f_d$ as one node],
),
  caption: [Different optimization boundaries: within one local transformation versus across persistent repair epochs.],
) <tab:optimization-boundaries>

Persistent editors, compilers, servers, simulations, dashboards, and workflows repeatedly receive partial change. DOC therefore treats temporal reuse as foundational while leaving local kernels free to use reduction-optimal, vectorized, incrementalized, or hardware-specific techniques.

== Types and provenance boundary

Each state has a value domain $V_s$, and each definition has the typed mapping stated by $Delta$. Types answer *what values may flow here?* Dependency answers *which current values justify this conclusion?* The two questions are related but not interchangeable.

For example, a typed syntax tree may have the same ordinary type before and after an edit. The graph still records whether the current diagnostics were derived from that tree together with the current symbol table and compiler options. This is computational provenance and currentness, not a new field that every result type must carry.

In the finite active-set core, $nu$ holds the current materializations and $A$ records conclusions that may need repair during one source epoch. Ordinary result types therefore need not be parameterized by source revision identifiers merely to support change propagation. The runtime's source-epoch serialization, private frontier evaluation, and publication barrier realize currentness without making revision numbers part of each application value.

DOC does not eliminate dependent types. Value-dependent invariants remain legitimate and often necessary: a vector's length, compatible matrix dimensions, a protocol phase, a verified bound, an arithmetic proposition, or a security property may depend on values. Those properties belong in the local language or the state type system when the program needs them.

#principle([Division of responsibility], [Ordinary and dependent types constrain values and value-level invariants. Dependency structure, valuation, and activation carry computational provenance, currentness, and change propagation. DOC removes only the need to encode those graph-level facts redundantly in ordinary result types.])

= Demand restriction, recurrence, and graph evolution

The proved finite kernel directly represents finite acyclic compositions under the standing assumptions. One fixed finite graph is not by itself a model of partial or unbounded computation. Full DOC obtains temporal unboundedness by composing this unchanged kernel across explicitly ordered logical epochs.

== Versioned recurrence

Let $q_t$ denote recurrent state at logical epoch $t$, and let a step transformation satisfying the standing local-definition assumptions define

$ q_(t+1)=T(q_t). $

The dependency points from an earlier epoch to a later epoch, never from a state back to itself inside the same epoch. Every materialized finite prefix therefore remains acyclic.

#definition([Versioned recurrence], [A recurrent DOC program is a finite acyclic graph template indexed by logical epochs, together with an initial epoch, a demand rule, and a typed partial carry function $K:S_(upright("src"))^E arrow.r S^E$. The meaning $K(s)=x$ is that source $s$ of epoch $t+1$ receives the value of state $x$ from epoch $t$. Thus each next-epoch source has at most one carry authority; its carried value must belong to the source domain. Every uncarried source receives an explicit epoch-local fact or declared fixed default. Demanding epoch $n$ instantiates and stabilizes only the finite prefix through $n$. An observation that continues demanding later epochs without reaching its stopping condition diverges.]) <def:recurrence>

#theorem([Demand-restriction agreement], [Let $T subset.eq S$ be a finite requested set and let $H_T$ be the ancestor-closed induced subprogram containing $T$, with every incoming boundary source materialized to the same fact as in the full program. Stabilizing $H_T$ yields exactly the restriction to $H_T$ of the unique stable valuation obtained by stabilizing the full program from those source facts.]) <thm:demand>

#proof([
Let $mu$ be the unique full-program stable valuation and let $mu_T$ be the unique stable valuation of $H_T$. Ancestor closure ensures that every premise of each retained derived definition is either retained in $H_T$ or supplied as a boundary source with the same value as in $mu$. Order the retained derived states topologically. The source and boundary cases agree by construction. If every premise of a retained derived state agrees with $mu$, determinism forces its conclusion to agree as well. Induction gives $mu_T=mu|_(H_T)$, including every requested state. Finite stabilization supplies existence and schedule independence on both graphs; demand restriction changes only the induced subprogram, not the transition rule.
])

#theorem([Finite support of requested recurrence prefixes], [For a finite epoch template, total local definitions, a single typed carry authority for each carried next-epoch source, and explicit facts or fixed defaults for every uncarried source, every requested finite prefix $0, dots, n$ requires only finitely many template instances and finitely many finite-kernel transitions. If an absorbing halt state is reached, requesting later epochs may reuse that same terminal meaning without additional machine progress; alternatively demand may stop at halt.]) <thm:recurrence-prefix>

#proof([
Induct on the requested epoch. Epoch zero has a finite source environment and finite acyclic graph, so finite stabilization terminates. Once epoch $t$ is stable, each carried source of epoch $t+1$ receives exactly one typed value and every other source receives its declared fact or default; the next finite instance is therefore repair-admissible after initialization and terminates. A finite prefix is a finite sum of finite episodes. Duplicate carry authority or an unprovided uncarried source fails construction rather than introducing nondeterminism.
])

Versioned recurrence is DOC's unbounded computational form, not an enlargement of $G$ or $Q$ for any individual epoch. This distinguishes temporal feedback from an instantaneous cyclic equation and prevents unbounded computation from being hidden inside an unspecified scheduler. Same-epoch fixed points may be useful, but they require their own convergence and observation semantics and are not part of the finite theorem.

=== Iteration and recursion

Iteration is repeated application of $T$. A loop state contains the variables and control location required for the next step. Recursion may be represented by a stack or continuation encoded in recurrent state, or by demand-driven creation of later invocation states with stable logical identities.

For example, factorial may use recurrent state $(n,a)$. While $n>0$, the transition is

$ T(n,a)=(n-1,n a). $

When $n=0$, the state is terminal and $a$ is observed. The important point is not this particular encoding: repeated computation advances through immutable later facts instead of destructive same-epoch self-dependence.

=== Mutable state as succession

DOC represents mutation as succession of logical facts. Work in epoch $t$ reads a complete value belonging to that epoch; environmental or derived authority may publish the later value used by epoch $t+1$. An already consumed premise does not retroactively change beneath active work.

The finite core's single derived producer is an authority normal form, not a claim that only one person, process, or device may contribute. Multiple contributors may publish distinct source or proposal states, and one explicit merge, transaction, priority, lattice, or adjudication definition may produce the authoritative conclusion. The runtime executes this shape through separate proposal sources and an explicit merge definition. What DOC cannot infer is which conflict rule the application intends. Retaining every historical epoch is also not automatic: recurrence policy must state which history remains rooted and which old materializations may be reclaimed.

=== Universality of the recurrence extension

A deterministic two-counter machine has a finite instruction table, a program counter, and two unbounded natural-number registers; this classical universality basis is due to Minsky @minsky1967. Encode a configuration as

$ q_t=(upright("pc")_t,r_(1,t),r_(2,t)). $

One finite local `Step` definition performs the instruction selected by the program counter and yields $q_(t+1)$. The forward-only construction is shown in @fig:recurrence. Increment, zero test, conditional decrement, and program-counter update simulate one machine transition.

#diagram(66pt, [
  #dnode(10pt, 18pt, [$q_t$], w: 60pt, fill: greenfill, stroke: green)
  #dnode(90pt, 18pt, [`Step` $t$], w: 70pt, fill: warmfill, stroke: warm, size: 7.9pt)
  #dnode(180pt, 18pt, [$q_(t+1)$], w: 70pt, fill: bluefill)
  #dnode(270pt, 18pt, [`Step` $t+1$], w: 70pt, fill: warmfill, stroke: warm, size: 7.6pt)
  #dnode(360pt, 18pt, [$q_(t+2)$], w: 70pt, fill: bluefill)
  #darrow(70pt, 32pt, 90pt, 32pt)
  #darrow(160pt, 32pt, 180pt, 32pt)
  #darrow(250pt, 32pt, 270pt, 32pt)
  #darrow(340pt, 32pt, 360pt, 32pt)
], [Versioned recurrence applies the finite `Step` transformation separately at each forward epoch, preserving acyclicity within every epoch.]) <fig:recurrence>

#theorem([Universality of versioned recurrence], [DOC with demand-driven unbounded epoch instantiation, unbounded natural values, finite case analysis, increment, zero test, and conditional decrement can simulate every deterministic two-counter machine step for step.]) <thm:universality>

Map each machine configuration to one epoch state and the finite instruction table to finite case analysis inside `Step`. Define the halt configuration as absorbing, or stop demand before requesting its successor. Induction on $t$ then shows that epoch $t$ denotes the machine configuration after $t$ steps. A halting machine yields a finite observed prefix; a non-halting machine demands an unbounded sequence and diverges.

#boundary([Recurrence evidence], [The witness checks demand-driven finite-prefix materialization, forward carry bindings, bounded stopping predicates, retention windows, and a deterministic two-counter-machine prefix against a direct interpreter. This validates the executable recurrence construction used by the universality argument; it is not a second proof of universality. A finite test cannot complete a non-halting run, and same-epoch fixed points remain a separate semantic problem.])

== Immutable graph-version change

Some programs change not only source values but also which logical states and definitions exist. DOC handles this without mutating the graph beneath active work. Let

$ G_0 arrow.r G_1 arrow.r G_2 arrow.r dots $

be an ordered sequence of immutable, individually well-formed graph versions.

#definition([Graph-version commit], [A commit from $G_k$ to candidate $G_(k+1)$ first stabilizes the current version and validates the candidate before reading any candidate-derived index. A current source fact crosses by stable logical name only when the candidate state remains a source with the same declared value domain and semantic equality. A retained derived value requires the same stable name, the same derived authority role, the same declared value domain and semantic equality, an explicit equivalence-bearing semantic key, identical ordered premise identities, and every ordered premise to be carried or retained compatibly and remain unaffected. If a state domain changes, that state is affected; migration is represented by an explicit candidate transformation rather than implicit value reuse. New states and every source/derived authority-role change are structurally affected. The private candidate seed must be repair-admissible; its affected region is then stabilized by the ordinary finite rule. Numeric runtime state identifiers are local to one immutable version, so cross-version update and observation APIs resolve stable names. The complete candidate graph and valuation replace the prior version atomically, advancing a runtime-scoped graph-generation token.]) <def:graph-commit>

An in-flight result captured under graph generation $k$ may publish only while that generation remains current. Retirement removes the old graph's logical roots after active observations release them; ordinary reachability then governs physical reclamation. A newly introduced source uses its declared initial fact and marks its user region affected. A stable name that changes between source and derived authority is likewise affected rather than reused. A newly introduced or structurally changed derived state begins as a repair obligation.

=== Operational semantic-key example

Consider a derived state with stable name `tax`, one premise `income`, and declared integer value domain. In graph version $G_k$, the builder installs a definition equivalent to `round(income * 20 / 100)` and assigns semantic key `tax-rule-v3`. A later graph version may replace its source code with a refactored implementation while retaining `tax-rule-v3` *only if the builder's compatibility process certifies the same mapping over the declared domain and the ordered premise identities remain unchanged*. In that case the retained `tax` value may seed the candidate graph.

If the policy changes to 22%, the builder assigns a different key such as `tax-rule-v4`; `tax` is then affected and its dependent region is repaired before commit. If the builder cannot establish compatibility—for example because a host function changed and no trusted equivalence certificate is available—the safe action is the same: treat the definition as changed and do not reuse its derived value. DOC therefore does not solve arbitrary function equivalence. The semantic key is an externally justified certificate identifier whose practical burden belongs to the compiler, build description, or application that creates graph versions.

#theorem([Conditional graph-version commit agreement], [Under the stated compatibility contract, every successful commit to $G_(k+1)$ has the same stable values as constructing $G_(k+1)$ from the carried current source facts and evaluating it completely from scratch. Retained compatible values change cost, not meaning.]) <thm:graph-commit>

#proof([
Let $mu^*$ be complete from-scratch evaluation of $G_(k+1)$ from the carried candidate source facts. Same-role compatible sources have exactly those values in the private candidate seed. Consider an inactive retained derived state in candidate topological order. The compatibility contract permits it to remain inactive only when its authority role, declared domain and equality, equivalence-bearing semantic key, ordered premise identities, and every premise are compatible and unaffected. Its source premises therefore equal $mu^*$, and its earlier retained derived premises equal $mu^*$ by induction. Boundary equivalence of the retained definition then makes its retained conclusion equal $mu^*$ as well. Hence every inactive candidate state is already materialized and locally satisfied; every state not justified by this induction is active. The private seed is repair-admissible.

@thm:finite-stabilization on the candidate graph now terminates at its unique stable valuation, which @lem:canonical identifies with $mu^*$. Atomic generation commit exposes only that stable candidate, and generation rejection prevents an older in-flight result from changing it. Retained compatible values therefore reduce repair work without changing from-scratch meaning.
])

#boundary([Topology identity boundary], [The runtime does not guess whether two arbitrary functions are semantically equivalent. Stable names and semantic keys are explicit compiler or builder contracts. Atomic graph replacement is implemented; distributed agreement on which graph version is authoritative remains a replica and partition policy.])

= Realization contracts and boundaries

Authority, logical availability, and physical lifetime are not extra instructions in the finite repair rule. They are constraints on realizations that preserve the rule's observations.

== Logical availability and safe realization

=== Logical authority and immutable publication

The partial-map representation gives one logical producer to every derived state. Source batches have environmental authority. Placement may move the physical executor or storage location, but it must not create a second logical producer for the same conclusion.

A conforming realization evaluates candidates privately and publishes complete immutable values. A reader observes either the previous complete materialization or the next complete materialization, never a partially mutated object. This distinction between logical authority and physical ownership permits many memory implementations without changing program meaning.

=== Logical availability and physical residency

#definition([Logical availability], [A logical value is available while the program's current state, a permitted observation, retained recurrence policy, active work, or an admitted external root still entitles it to be observed or consumed. A realization preserves that availability by retaining either a usable complete materialization or sufficient authoritative information to reconstruct an observationally equivalent complete value before use.]) <def:availability>

@fig:logical-availability distinguishes residency, reconstruction, and reclamation. A logically available value need not remain resident in its current physical form. A realization may evict, spill, compress, deduplicate, fuse, or discard a reconstructible derived materialization. It may retain current sources, a checkpoint, or another authoritative representation from which the same value can be recovered. Once a value has been pinned by an active observation, evaluation, publication, or transport, that complete physical object remains protected until the use finishes even if its state slot is concurrently evicted or replaced.

#diagram(132pt, [
  #dnode(12pt, 8pt, [logical value available], w: 124pt, fill: greenfill, stroke: green, size: 7.8pt)
  #dnode(176pt, 8pt, [resident immutable value], w: 120pt, fill: bluefill, size: 7.8pt)
  #dnode(338pt, 8pt, [protected observation], w: 116pt, fill: greenfill, stroke: green, size: 7.7pt)
  #darrow(136pt, 22pt, 176pt, 22pt)
  #darrow(296pt, 22pt, 338pt, 22pt)
  #dnode(12pt, 51pt, [logical value available], w: 124pt, fill: greenfill, stroke: green, size: 7.8pt)
  #dnode(176pt, 51pt, [authoritative information], w: 120pt, fill: warmfill, stroke: warm, size: 7.6pt)
  #dnode(338pt, 51pt, [reconstruct complete value], w: 116pt, fill: bluefill, size: 7.35pt)
  #darrow(136pt, 65pt, 176pt, 65pt)
  #darrow(296pt, 65pt, 338pt, 65pt)
  #dnode(12pt, 94pt, [no availability or pin], w: 124pt, fill: warmfill, stroke: warm, size: 7.5pt)
  #dnode(176pt, 94pt, [unreachable old object], w: 120pt, fill: warmfill, stroke: warm, size: 7.6pt)
  #dnode(338pt, 94pt, [automatic reclaim], w: 116pt, fill: greenfill, stroke: green)
  #darrow(136pt, 108pt, 176pt, 108pt)
  #darrow(296pt, 108pt, 338pt, 108pt)
], [The model determines logical availability. The realization chooses residency, reconstruction, and reclamation while protected uses keep complete physical objects alive.]) <fig:logical-availability>

=== Safe-realization contract

A conforming safe realization must:

1. preserve every logically available value either as a usable materialization or through authoritative reconstruction information;
2. protect complete values captured by active evaluation, observation, publication, or transport;
3. publish or reconstruct only complete values and never expose a partially constructed candidate;
4. serialize reconstruction admission with replacement, or use equivalent generation checks, so an older reconstruction cannot overwrite a newer publication;
5. prevent dangling access after logical replacement or physical eviction;
6. eventually reclaim physical materializations that remain unreachable under the stated reclamation-progress assumption.

Tracing from declared roots is one canonical implementation. Ownership, regions, reference counting, arenas, uniqueness, hardware-managed storage, recomputation, durable checkpoints, or hybrid collectors are also possible if they preserve the same observational and safety obligations. Ordinary DOC programs need not contain pointer arithmetic, manual deallocation, cache-residency controls, or physical ownership transfers.

=== What automatic reclamation does not mean

Dependency supplies useful reachability and reconstruction structure, but it is not itself a garbage collector or storage policy. The realization must implement roots, protected reads, publication atomicity, reconstruction admission, and reclamation. Nor does automatic reclamation imply a universal memory bound. A program may intentionally retain an unbounded recurrence prefix, audit history, or other logically available information; a runtime may change its physical representation but cannot discard information still required by policy.

#boundary([Memory-safety ceiling], [DOC can make physical lifetime and cache residency unnecessary in ordinary application code while still requiring an explicit runtime mechanism. It prevents dangling use only when the realization satisfies protected publication, reconstruction, and reclamation obligations; it does not promise bounded storage for intentionally retained logical information.])

== Placement over arbitrary resources

@fig:placement shows the separation between stable logical roles and movable physical resources. The logical program does not contain today's machines. For placement, define role-tagged physical entities

$ L_G={upright("value")(s) | s in S} union {upright("eval")(d) | d in D}. $

Let $R_t$ be the resources available at physical time $t$. The bounded single-authority profile uses a partial placement and a generation map

$ pi_t:L_G arrow.r (R_t union {bot}), #h(1.5em) gamma_t:L_G arrow.r NN. $

A role may be temporarily unassigned during join, reassignment, drain, or fail-stop recovery. Replicated authority is not represented by this profile and requires explicit policy. Value storage and definition evaluation may be co-located or separated without changing $G$, $nu$, or logical observations. A resource may represent a CPU core, accelerator, process, machine, storage node, cluster region, or future dependency-native mechanism.

#diagram(174pt, [
  #dpanel(8pt, 8pt, 188pt, 148pt, [Logical graph unchanged], stroke: accent)
  #dnode(22pt, 64pt, [$s_1$], w: 46pt, fill: greenfill, stroke: green)
  #dnode(82pt, 64pt, [$d_1$], w: 46pt)
  #dnode(142pt, 64pt, [$d_2$], w: 46pt)
  #darrow(68pt, 78pt, 82pt, 78pt)
  #darrow(128pt, 78pt, 142pt, 78pt)
  #dlabel(30pt, 111pt, [$G$, $nu$, and logical identities do not move], size: 7.6pt)

  #dpanel(222pt, 8pt, 236pt, 148pt, [Physical roles may move], stroke: warm)
  #dnode(234pt, 42pt, [resource A: $upright("value")(s_1)$], w: 98pt, size: 7.5pt)
  #dnode(348pt, 42pt, [resource B: $upright("eval")(d_1)$], w: 98pt, size: 7.5pt)
  #dnode(234pt, 83pt, [resource C joins], w: 98pt, fill: greenfill, stroke: green)
  #dnode(348pt, 83pt, [$upright("eval")(d_2)$ moves], w: 98pt, fill: bluefill, size: 7.7pt)
  #dnode(234pt, 124pt, [resource B fails or drains], w: 98pt, fill: warmfill, stroke: warm, size: 7.3pt)
  #dnode(348pt, 124pt, [generation changes], w: 98pt, size: 7.7pt)
  #darrow(332pt, 56pt, 348pt, 56pt)
  #darrow(332pt, 97pt, 348pt, 97pt)
  #darrow(332pt, 138pt, 348pt, 138pt)
  #dlabel(201pt, 62pt, [$pi_t$], size: 8.4pt, fill: ink)
  #darrow(196pt, 78pt, 222pt, 78pt)
], [Joining, reassignment, graceful drain, and bounded fail-stop recovery change physical placement, not logical identities or dependency meaning.]) <fig:placement>

=== Dependency transport and message admission

When a definition and one of its premise values are placed at different resources, the dependency becomes a communication obligation. The bounded wire profile carries logical state identity, committed source epoch, placement-role key, placement generation, checksum, and an immutable scalar value. Authentication and safe content references are production extensions of the same admission boundary, not new logical identities in $G$.

Reliable delivery may still be delayed, duplicated, or reordered. A receiver therefore admits a value only for the expected role and current placement generation. An older source epoch is stale; a duplicate value for the same epoch is harmless; a different value for the same state, role, and epoch is a conflict. A derived candidate may publish only after its role-generation token remains current.

The executable placed profile sends every premise through a real TCP loopback channel before evaluating its assigned definition. It is intentionally a one-process network witness rather than a production multi-host cluster, but transport, framing, checksum validation, duplicate admission, wrong-role rejection, stale-epoch rejection, and stale-generation rejection are exercised as code.

=== Location-transparent observation

An observation names a logical state, not a machine or service instance. A conforming ingress may satisfy it by returning a valid local materialization, retrieving a valid remote materialization, or stabilizing the required ancestor region and then returning its value. These alternatives must agree on the stable logical value. One logical endpoint therefore need not mean one physical server, and a requested result need not be stored everywhere.

=== Generation authority

Each assigned physical role $ell$ has a placement generation. Work captures a token $(ell,r,g)$ before execution. At physical time $t$, the token is admissible exactly when

$ pi_t(ell)=r #h(0.5em) upright("and") #h(0.5em) gamma_t(ell)=g. $

Publication is accepted only while the token remains admissible. Reassignment, drain, or failure first advances $gamma_t(ell)$ and may make $pi_t(ell)$ undefined, so late work from the previous resource cannot publish. The wire envelope also binds a stable key for $ell$; a generation number detached from its role is insufficient authority.

=== Bounded elastic transparency

#definition([Placed-epoch conformance], [A physical execution of one finite logical epoch is conforming when: (1) transport copies immutable materializations tagged with source epoch, role, and placement generation but does not alter their logical values; (2) every non-discarded derived publication has a conclusion $d$ that is currently active and belongs to $R(A)$, equals $f_d$ applied to the committed logical pre-valuation of that source epoch, and carries a currently admissible role token; (3) join, reassignment, and graceful drain change only $pi_t$, $gamma_t$, and physical copies, never $G$, source facts, or logical definition authority; and (4) after finitely many placement changes, every required transport and active logical role eventually completes.]) <def:placed-conformance>

#theorem([Failure-free join/drain transparency], [Every conforming placed execution projects, after duplicate and stale physical events are discarded, to a valid sequence of finite frontier-subset transitions. Consequently, after source and placement quiescence, its observable values equal local stabilization.]) <thm:join-drain>

A currently admitted publication is either one legal singleton frontier transition or part of a commuting frontier batch: its conclusion is active and ready, it was evaluated from the committed logical pre-valuation of that source epoch, it publishes one distinct logical conclusion, and it cannot be admitted from obsolete authority. Join and drain change where later work occurs, not the logical transition being represented.

=== Bounded fail-stop reconstruction

#definition([Recoverable placed profile], [Source facts acknowledged as recoverable are durably committed by one declared authority. Pure derived materializations are reconstructible caches. After a finite fail-stop loss, the realization invalidates every lost role generation, assigns the roles to surviving or newly joined resources, restores authoritative source facts, marks every lost derived state and its transitive user region as repair obligations, and stabilizes again.]) <def:recoverable-placement>

#theorem([Finite fail-stop reconstruction], [For a finite acyclic pure DOC graph, if authoritative source facts survive and remain fixed during the final recovery interval, at least one valid execution resource eventually remains or joins, generation invalidation rejects late failed work, transport eventually succeeds, and no further failure occurs during that interval, reconstruction reaches the same observable stable valuation as local evaluation from those source facts.]) <thm:fail-stop>

The replacement execution begins from the same sources as complete reevaluation. Every lost derived state and its transitive user region is active, so the recovery seed is repair-admissible even when a lost premise was previously used by a retained descendant. @thm:finite-stabilization gives termination and unique values; placement generations prevent obsolete candidates from replacing them. Checkpoints of expensive derived state may reduce work but are not required for correctness.

The executable profiles check both complete loss of volatile derived materialization followed by reconstruction from authoritative sources and failed-resource removal followed by role invalidation, reassignment, and affected-region repair.

=== Locality and live scaling

Dependency edges reveal potential communication and ready-frontier independence. A placement policy may consider computation cost, value size, update frequency, memory pressure, latency, failure domains, accelerator suitability, and resource capacity. Frequently interacting regions may be co-located; costly independent regions may be spread across available resources.

Adding resources enlarges $R_t$ while leaving application graph $G$ unchanged. The executable placed profile rebalances future definition roles over the enlarged resource set. Graceful removal stops new assignment, advances old generations, reassigns roles, and closes the drained endpoint. Fail-stop removal additionally discards lost derived materialization and repairs from surviving source authority. Application code contains neither the current processor count nor a list of machines.

#principle([Scaling as placement], [The programmer supplies logical relationships and access to resources. The realization decides whether, where, and when independent work should move. Live horizontal scaling is therefore a placement process over the graph, not a claim that transport cost, capacity limits, or failure policy disappear.])

#boundary([Distribution boundary], [The implemented and argued profile covers finite joins, graceful drains, and bounded fail-stop reconstruction under surviving source authority, eventual resource availability, reliable eventual transport, generation admission, and a final quiescent interval. Network partitions, election, quorum, replica consistency, stale-read policy, Byzantine behavior, and irreversible external effects remain explicit distributed-system policy.])

== Distribution and application structure

Ordinary DOC programs name logical states and definitions rather than machines, routes, topics, shard identifiers, or worker counts. The placed realization turns remote premise relations into transport obligations and may choose eager propagation, demand-driven stabilization, batching, co-location, or migration without changing the logical graph.

Where a message broker is used only to notify already-known dependents that current state changed, the users induced from $Delta$ already define that routing relation. A realization may transport changed logical values or activation information directly along placed dependency obligations. A sound cutoff proof at an intermediate state can stop the wave before it reaches more distant consumers.

#principle([Brokerless current-state propagation], [For communication whose only purpose is to maintain current derived state, application-visible producer, topic, subscription, and consumer-routing structure need not duplicate relationships already present in $Delta$. Consumers observe logical outputs while the realization routes what is required to justify them.])

This claim is deliberately narrower than replacing a durable event log. Ordered replay, independent consumer offsets, audit retention, ingestion buffering, historical queries, and exactly-once irreversible actions are different semantics. DOC can use a log or broker at an explicit boundary; it does not equate current-state dependency propagation with retained event history.

The intended long-term architecture is one logical application graph. Runtime-created processes, containers, storage partitions, or accelerator jobs remain useful physical units for isolation and capacity, but they need not become programmer-managed microservices that duplicate logical dependencies through APIs and message routes. Explicit service boundaries remain appropriate for public contracts, security domains, independently governed systems, legal isolation, distinct failure policy, or irreversible effects.

== Effects and external interaction

Under the standing finite-kernel assumptions, several practical concerns fit without changing the core. Nondeterministic observations enter as source updates. Recoverable absence and failure may be represented by typed option or result values. Private work cancelled before publication has no logical effect; a realization may leave its obligation active or let a later source epoch supersede it.

Irreversible interaction remains different. For file publication, payments, network commands, device control, or other externally visible actions, the canonical boundary is:

1. pure derivation of an intended effect value and stable idempotency identity;
2. explicit authorization and ordering policy;
3. durable recording of intent and attempt state where required;
4. external execution;
5. durable outcome recording and application-specific retry, deduplication, or reconciliation.

#boundary([Exactly-once honesty], [A crash after an external system accepted an action but before the local committed outcome was recorded leaves the journal *in flight*. The runtime deliberately does not retry automatically or claim exactly-once behavior. The external system's idempotency support, a reconciliation query, or explicit operator policy must resolve the uncertainty. Dependency can explain why an effect is proposed; it cannot infer authorization, rollback, or external atomicity.])

== Four worked interpretations

These interpretations use the same finite semantics. They differ in value types, local transformations, granularity, and effect boundaries.

=== Compiler - worked from source batch to observation

Suppose the logical states include source text $T$, compiler options $O$, a parsed declaration graph $P$, exported interface $I$, diagnostics $D_g$, optimized unit $U$, and generated object $B$. Definitions encode

```text
P  = parse(T)
I  = public_interface(P)
Dg = diagnose(P, O)
U  = optimize(P, O)
B  = generate(U)
```

An edit installs one atomic source batch changing $T$. Direct users of $T$ enter $A$. The dependency-minimal active frontier may initially contain `parse` alone. When `P` changes, its users become active; independent `diagnose`, `public_interface`, and `optimize` work may then share a frontier if their other premises are settled.

If the cutoff predicate proves the edited implementation's exported interface $I$ equal to the retained interface, users outside the module that depend only on $I$ are not activated. Diagnostics may still change, and the local optimized unit may still require regeneration. Observation of $B$ or $D_g$ waits for stabilization of the whole finite graph, or equivalently of the appropriate ancestor-closed induced subprogram in a demand-restricted realization. Writing an object file, invoking an external tool, or publishing diagnostics to another system remains an explicit effect boundary.

This one example exercises the entire finite pattern: sources, typed local definitions, activation, ready-frontier parallelism, private evaluation, equality cutoff, retained descendants, and stable observation.

=== Build system

Source files, configuration values, tool identities, generated artifacts, and test results form states. Definitions encode pure build transformations or intended external actions. A changed file activates only dependent targets. A rebuilt interface proven equal by the cutoff predicate prevents downstream activation. Retained artifacts are semantic caches only when their logical state is stable. Remote builders are placements of evaluation roles, not separate application semantics; file publication and external compiler invocation still need effect discipline.

=== Maintained query

Base records and parameters are source states; filtered sets, joins, aggregates, and views are derived states. A transaction activates reachable operators. A sound cutoff proof at an aggregate or materialized boundary may stop propagation. Specialized delta operators and indexes may optimize local definitions without changing the global dependency meaning. Distinct proposal states and an explicit merge can represent multiple contributors, while durable transaction history, isolation, and conflict policy remain database concerns beyond the finite core.

=== Long-lived information workflow

Evidence items, extracted facts, classifications, plans, and reports become logical states. New evidence repairs only conclusions that depend on it. Expensive independent analyses form ready frontiers and may be placed over available resources. Human approval, audit retention, external publication, and nondeterministic tool access are explicit observation, retention, or effect boundaries rather than hidden consequences of dependency.

Across these examples, the common operation is explicit: retain conclusions together with their declared premises, then repair only the affected dependency region after a committed source change.

= Experimental validation and reproducibility <sec:validation>

== Runtime conformance

The executable witness is subordinate to the model. Its normative direction is

```text
paper model -> observable obligations -> runtime refinement
```

not the reverse.

#definition([Finite interaction-trace conformance], [Let $eta$ be any finite admissible sequence of committed source batches, stable observations, and immutable graph-version commits beginning from $(G_0,Q_0)$. A physical realization $P$ conforms when

$ upright("Obs")_P(eta)=upright("Obs")_(upright("DOC"))(G_0,Q_0,eta). $

$eta$ is a mathematical test sequence, not retained application history and not a component of $G$ or $Q$. Internal schedules, materializations, cache states, reconstruction steps, placements, and reclamation events may differ.]) <def:trace-conformance>

This definition unifies repeated source updates, observations, and graph replacement without adding a history calculus to DOC. Recurrent observations are ordinary observations of epoch-indexed logical states within a finite demanded prefix.

=== Executed representation

@tab:witness-mapping links each semantic obligation to the concrete C++20 behavior used in the conformance tests.

#block[
  #set text(size: 8.8pt)
  #figure(
    table(
    columns: (1.12fr, 2.8fr),
    table.header([*Model obligation*], [*Witness behavior*]),
    [Finite kernel], [Stores one optional scalar value and one transient active marker per logical state; computes the dependency-minimal ready frontier; evaluates a complete selected frontier privately; and publishes changed candidates together.],
    [Atomic interaction], [Validates a complete source batch before mutation, serializes accepted source epochs, and allows observations only after the corresponding stable commit.],
    [Schedule independence], [Compares sequential, parallel, randomized, and every bounded legal frontier-subset schedule against complete reevaluation.],
    [Versioned recurrence], [Instantiates finite demanded epoch prefixes, applies forward carry bindings, enforces explicit retention, and compares a two-counter-machine prefix with a direct interpreter.],
    [Immutable graph succession], [Validates and stabilizes candidates privately, carries source facts by stable logical name, reuses only explicitly compatible regions, commits one new generation atomically, and rejects stale-generation publication.],
    [Logical availability], [Uses immutable publications and active-use pins, permits a state slot to evict a reconstructible value, reconstructs an equal complete value from authoritative information before observation, and reclaims obsolete unpinned objects.],
    [Placement and recovery], [Checks generation-bound admission, join, graceful drain, lost-derived-state reconstruction, and bounded fail-stop recovery from surviving authoritative source facts.],
    [Effect boundary], [Checks explicit request, authorization, in-flight uncertainty, outcome recording, and rejection of impossible state transitions without claiming external exactly-once behavior.],
  ),
    caption: [Mapping from semantic obligations to the executable witness.],
  ) <tab:witness-mapping>
]

Application graphs never specify a worker count. Experimental limits are imposed outside the graph through the execution environment. Resource join and removal are likewise realization operations over placement rather than application-level topology instructions.

=== Verification scope

The native runtime suite contains 36 named conformance suites and a separate benchmark-generator equivalence test. Its randomized differential component checks 9,600 update epochs against complete reevaluation, including randomized legal frontier-subset schedules. Twenty repeated optimized runs of the two native test executables completed successfully.

Five independent bounded checkers cover complementary state spaces. The ordinary finite checker enumerates 2,520 Boolean DAGs and 40,320 source epochs. The repair checker covers 512 graphs, 59,904 admissible seeds, 239,616 continued source updates, and 521,584 unique explored configurations. The graph-version checker covers 64 graph shapes and 15,360 commits, including source/derived authority transitions. The duplicate-premise checker covers 84 graphs and 2,592 admissible configurations. The demand/recurrence checker covers 364 demand templates, 21,840 demanded subsets, 364 recurrence templates, 17,472 finite prefixes, 2,912 stopping cases, and duplicate-carry rejection.

These finite enumerations check initialization, repair admissibility, continued source batches, every nonempty legal subset of each bounded ready frontier, exact and conservative cutoff, locality, schedule agreement, demand restriction, recurrence support, graph-role changes, graph-local identifier reorderings, and replacement agreement. Bounded checking is executable counterexample search over the stated finite spaces; it is not a proof of universal correctness.

#boundary([Current executable coverage], [The high-performance active-set evaluator remains specialized to scalar values; typed immutable objects, eviction, and reconstruction are checked in a separate safe-realization profile rather than a fully integrated generic evaluator. The placed runtime uses real transport but remains a bounded single-coordinator witness rather than a production multi-host platform. The finite metatheory is mathematically argued and bounded-exhaustively checked, not yet mechanized in a proof assistant. These limits concern evidence and engineering maturity, not hidden additions to the logical core.])

== Performance evaluation

The benchmark executable checks every DOC output against an independent correctness oracle and exits nonzero on disagreement. Reduction workloads compare against complete serial reevaluation; the financial workload additionally compares against a conventional serial cached segment tree; and the sorting-network workload checks both direct execution of the same Batcher network and `std::sort`. The benchmarked runtime uses signed 64-bit integer values with exact equality. Its concrete scheduling policy chooses the complete ready frontier $F=R(A)$ at each transition; `DOC_MAX_WORKERS` limits participant capacity externally and is not stored in the application graph.

The reproduced campaign used GCC 14.2.0 in Release mode on Linux 6.18.44 (x86-64, glibc 2.41) with an AMD EPYC 9V74 80-Core Processor. Five CPUs were visible by affinity and to the operating system, while the cgroup CPU quota was four CPUs (`cpu.max = 400000 100000`). The recorded environment also used Python 3.13.5 and CMake 3.31.6. Every reported row used 20 fresh processes plus one unrecorded warmup. Scenario order alternated forward and reverse between samples. Raw measurements are retained in full; the supplementary statistics also apply a symmetric Tukey 1.5-IQR sensitivity filter and report $n$, mean, median, standard deviation, 95% confidence interval, minimum, maximum, and filter sensitivity. Participant limits were 1--4 because of the four-CPU quota.

The exact campaign command is `python3 runtime/scripts/run_all_benchmarks.py --samples 20 --warmups 1 --max-participants 4`. Its outputs are under `runtime/results/revision-2026-09-29/`: `raw.csv` contains every process measurement, `statistics.csv` the distributions, `summary.csv` the raw/filtered summaries, `machine.json` the host and binary hashes, and `commands.log` the executed commands. The reported numerical evidence is fixed at benchmark commit `d2e9edb4f962f132e96d7e342bd14f48ff8446cc`; the submission source package includes the exact machine record and stable links to these retained files.

=== Workload structure and scheduler granularity

The 2,048-leaf reduction graph contains 2,048 source states, 2,048 expensive leaf definitions, and 2,047 reduction definitions: 6,143 states in total and 4,095 derived definitions. Each expensive leaf counts primes in a deterministic interval. The parallel-capacity workload uses 40 source states, 40 expensive leaf definitions, and 39 reduction definitions. Its first ready frontier therefore contains 40 independent expensive definitions, each scanning a 25,000-integer interval; later logarithmic reduction frontiers are much cheaper. This is the independent-work amount behind the single-host scaling result.

The dense cheap negative control uses 4,096 sources, 4,096 identity leaf definitions, and 4,095 sum definitions over 30 full-change epochs. The financial graph has 4,096 units, four source states per unit, one 360-period deterministic fixed-point forecast per unit, and 4,095 consolidation definitions: 24,575 states and 8,191 derived definitions. The sorting workload has 512 sources and a complete Batcher network with 11,520 compare-exchanges represented by 23,040 derived definitions, for 23,552 states. These graph sizes and the concrete scheduler policy make the timing granularity explicit rather than treating all workloads as interchangeable.

=== Sparse repair, saturation, and negative control

@tab:reduction-results reports raw process means from the reproduced campaign. Evaluation counts are deterministic for the specified update batches.

#block[
  #set text(size: 8.5pt)
  #set table(inset: 2.8pt)
  #figure(
    table(
      columns: (1.68fr, 0.92fr, 0.92fr, 0.82fr),
      table.header([*Scenario*], [*Direct raw mean*], [*DOC raw mean*], [*Evaluations*]),
      [Cold 2,048-leaf reduction], [194.648 ms], [195.767 ms], [4,095],
      [1 changed source], [193.009 ms], [0.384 ms], [12],
      [8 changed sources], [192.774 ms], [1.045 ms], [23],
      [64 changed sources], [192.349 ms], [6.029 ms], [132],
      [512 changed sources], [193.580 ms], [48.242 ms], [1,007],
      [2,048 changed sources], [189.052 ms], [189.989 ms], [4,038],
      [Dense cheap negative control], [0.223 ms], [33.887 ms], [245,730],
    ),
    caption: [Finite-kernel reduction workload on the reproduced 2026-09-29 environment. Timings are raw means over 20 fresh processes; evaluation counts are deterministic.],
  ) <tab:reduction-results>
]

#figure(
  block(width: 100%, height: 126pt, inset: 4pt, fill: pale, stroke: 0.45pt + luma(215), radius: 4pt)[
    #dline(42pt, 96pt, 448pt, 96pt, stroke: 0.65pt + luma(130))
    #dlabel(3pt, 8pt, [fraction of 4,095 definitions evaluated], size: 7.4pt)
    #place(top + left, dx: 58pt, dy: 94pt)[#rect(width: 46pt, height: 2pt, fill: accent)]
    #place(top + left, dx: 133pt, dy: 94pt)[#rect(width: 46pt, height: 2pt, fill: accent)]
    #place(top + left, dx: 208pt, dy: 93pt)[#rect(width: 46pt, height: 3pt, fill: accent)]
    #place(top + left, dx: 283pt, dy: 76pt)[#rect(width: 46pt, height: 20pt, fill: accent)]
    #place(top + left, dx: 358pt, dy: 17pt)[#rect(width: 46pt, height: 79pt, fill: accent)]
    #dlabel(60pt, 100pt, [1], size: 7.6pt)
    #dlabel(135pt, 100pt, [8], size: 7.6pt)
    #dlabel(207pt, 100pt, [64], size: 7.6pt)
    #dlabel(280pt, 100pt, [512], size: 7.6pt)
    #dlabel(350pt, 100pt, [2,048], size: 7.6pt)
    #dlabel(57pt, 82pt, [0.29%], size: 7pt)
    #dlabel(131pt, 81pt, [0.56%], size: 7pt)
    #dlabel(205pt, 79pt, [3.22%], size: 7pt)
    #dlabel(278pt, 64pt, [24.59%], size: 7pt)
    #dlabel(350pt, 6pt, [98.61%], size: 7pt)
    #dlabel(165pt, 114pt, [changed sources in the 2,048-leaf reduction], size: 7.5pt)
  ],
  caption: [Repair work grows with update density. Bars show selected definitions as a fraction of the 4,095 derived definitions; equality cutoff leaves the full-change row slightly below 100%.],
  kind: "figure",
  supplement: [Figure],
  numbering: "1",
) <fig:repair-density>

The structural trend in @fig:repair-density is the main result of this workload: sparse updates reconsider only the changed leaves and their ancestors, while dense updates approach complete work. Exact equality cutoff required one producer evaluation and one cutoff in its dedicated microbenchmark. Cold DOC and direct execution are near parity on this expensive reduction, whereas a complete source change also approaches parity. The deliberately cheap dense graph is a negative control: DOC is roughly two orders of magnitude slower because metadata, frontier construction, and synchronization dominate the useful arithmetic. The model therefore predicts *where work may be avoided*, not a universal timing improvement.

=== Externally granted parallel capacity

@tab:parallel-results uses the same 40-leaf graph and output oracle at every externally imposed participant limit. The table reports raw means and confidence intervals; speedup is the ratio of the one-participant raw mean to each raw mean.

#block[
  #set text(size: 8.2pt)
  #set table(inset: 2.6pt)
  #figure(
    table(
      columns: (1.2fr, 1.7fr, 0.9fr),
      table.header([*Participants*], [*Raw mean (95% CI)*], [*Raw speedup*]),
      [1], [150.221 ms (147.290--153.153)], [1.000$times$],
      [2], [82.267 ms (75.266--89.267)], [1.826$times$],
      [3], [60.325 ms (55.587--65.064)], [2.490$times$],
      [4], [46.412 ms (42.761--50.062)], [3.237$times$],
    ),
    caption: [Ready-frontier scaling under externally granted participant limits on one host with a four-CPU cgroup quota.],
  ) <tab:parallel-results>
]

#figure(
  block(width: 100%, height: 126pt, inset: 4pt, fill: pale, stroke: 0.45pt + luma(215), radius: 4pt)[
    #dline(58pt, 96pt, 430pt, 96pt, stroke: 0.65pt + luma(130))
    #place(top + left, dx: 82pt, dy: 76pt)[#rect(width: 52pt, height: 20pt, fill: accent)]
    #place(top + left, dx: 164pt, dy: 59pt)[#rect(width: 52pt, height: 37pt, fill: accent)]
    #place(top + left, dx: 246pt, dy: 46pt)[#rect(width: 52pt, height: 50pt, fill: accent)]
    #place(top + left, dx: 328pt, dy: 31pt)[#rect(width: 52pt, height: 65pt, fill: accent)]
    #dlabel(92pt, 101pt, [1], size: 7.7pt)
    #dlabel(174pt, 101pt, [2], size: 7.7pt)
    #dlabel(256pt, 101pt, [3], size: 7.7pt)
    #dlabel(338pt, 101pt, [4], size: 7.7pt)
    #dlabel(84pt, 64pt, [1.00$times$], size: 7.2pt)
    #dlabel(165pt, 47pt, [1.83$times$], size: 7.2pt)
    #dlabel(247pt, 34pt, [2.49$times$], size: 7.2pt)
    #dlabel(329pt, 19pt, [3.24$times$], size: 7.2pt)
    #dlabel(185pt, 114pt, [externally allowed participants], size: 7.5pt)
  ],
  caption: [Single-host ready-frontier speedup. The result demonstrates use of granted parallel capacity for a coarse frontier; it is not evidence of distributed scalability.],
  kind: "figure",
  supplement: [Figure],
  numbering: "1",
) <fig:parallel-speedup>

The reproduced single-host result reaches a raw-mean speedup of $3.237 times$ at four participants. The first frontier contains 40 independent expensive leaf definitions, so there is enough coarse work to amortize runtime overhead. @fig:parallel-speedup must not be extrapolated to more cores or multiple hosts: the experiment contains no inter-host transport and the cgroup allows only four CPUs. It supports only the narrower claim that a dependency-minimal frontier can consume externally granted local capacity without a worker count in the program.

=== Realistic persistent financial projection

The financial workload models 4,096 business units. Each unit has four source cells and one deterministic 360-period fixed-point cash-flow projection; a balanced tree consolidates unit values. Each changed unit updates both its revenue and payroll sources. Complete serial reevaluation, a conventional serial cached segment-tree repair, and DOC must produce the same total.

#block[
  #set text(size: 8.45pt)
  #set table(inset: 2.8pt)
  #figure(
    table(
      columns: (1fr, 1fr, 1fr, 1fr, 0.82fr),
      table.header([*Changed units*], [*Full raw mean*], [*Cached raw mean*], [*DOC raw mean*], [*DOC evals*]),
      [1], [4.823 ms], [0.00134 ms], [1.256 ms], [13],
      [64], [4.991 ms], [0.0795 ms], [1.397 ms], [133],
      [1,024], [4.965 ms], [1.296 ms], [2.682 ms], [2,049],
    ),
    caption: [Financial projection workload. The cached baseline is workload-specific and all three implementations are checked for equal output.],
  ) <tab:financial-results>
]

As @tab:financial-results shows, DOC is faster than complete reevaluation for all three displayed update sizes on this run, but the specialized cache is substantially faster than generic DOC repair. For one changed unit, DOC takes about 26% of full reevaluation time yet about 935 times the cached update time; at 64 units the cached baseline is about 17.6 times faster than DOC; at 1,024 units it remains about 2.1 times faster. The useful conclusion is therefore workload-specific: DOC's generic overhead is justified only when its reusable semantics, dynamic affected-region discovery, graph evolution, conformance properties, or common runtime mechanism are worth more than a hand-specialized incremental update path.

=== Fine-grained graph negative case

A 512-input Batcher sorting network contains 11,520 compare-exchanges represented by 23,040 derived definitions and 23,552 total states. Sparse updates avoid many definitions and expose equality cutoffs, but direct complete network execution is far faster: raw DOC update means range from 5.85 to 6.48 ms, while raw direct update means range from 0.0247 to 0.0413 ms. The DOC/direct ratio ranges from about $142 times$ to $263 times$ across the displayed update sizes. At full change, all 23,040 definitions execute and no cutoff remains. This negative case shows that exposing a dependency at every comparator can make the logical graph useful for reasoning while making the runtime granularity uneconomic; fusion, batching, or specialized operators would be required for a competitive implementation.

#boundary([Evaluation boundary], [These measurements support conformance and workload-specific cost-shape claims only. They do not establish universal speedup, production distributed scalability, accelerator efficiency, or a hardware-independent constant. Stronger scaling evidence requires new experiments on dedicated many-core and multi-host systems rather than extrapolation from @fig:parallel-speedup.])

= Limitations

1. *Finite acyclic theorem.* The central theorem covers finite acyclic programs. Versioned recurrence supplies temporal repetition and ordinary partial computation, but same-epoch cyclic equations require a separately stated order, convergence, and observation semantics.
2. *Equality and function contracts.* Sound cutoff, total deterministic definitions, stable-name compatibility, and semantic keys are supplied by a compiler, builder, or application contract; the runtime cannot decide arbitrary function equivalence.
3. *Policy-dependent physical behavior.* Placement, routing, replica authority, partition handling, retention, compaction, checkpoints, quotas, and irreversible-effect recovery are not determined by the logical kernel.
4. *No universal memory or performance bound.* Logically rooted recurrence or audit history may grow without bound. Direct or specialized incremental execution may outperform the generic runtime, especially for dense or fine-grained work.
5. *Evidence limits.* The finite metatheory is not proof-assistant mechanized. Exhaustive checking is bounded. The physical witness is a bounded single-coordinator implementation, and the present scaling measurements are limited to four quota-granted CPUs on one host.

= Related work <sec:related-work>

Dependency-oriented evaluation has several established lineages. Kahn process networks provide deterministic semantics for communicating processes @kahn1974. Attribute grammars attach semantic values to syntactic structure and expose dependency relations; Knuth established the framework @knuth1968 @knuth1971correction, and Demers, Reps, and Teitelbaum studied incremental reevaluation for syntax-directed editors @demers1981. INC is an early language explicitly designed for incremental computations @yellin1991. These works establish that dependency structure and incremental maintenance are not new ingredients of DOC.

The closest comparison is self-adjusting computation. Acar's model represents computations with dynamic dependence graphs and uses change propagation to adjust them after external changes @acar2005. Parallel self-adjusting computation develops additional machinery and work/span analysis for parallel change propagation @anderson2021. Adapton combines incremental computation with demand and introduces a demanded computation graph plus an explicit observer boundary @hammer2014adapton. DOC makes a different representational choice: the graph of logical state identities and definitions is declared as the persistent program for one graph version, while the transient repair state is represented separately by $A$; the finite repair relation then acts only on dependency-minimal active definitions. This is a distinction in factorization and proof boundary, not a claim that change propagation, memoization, demand, or parallel dependency processing originated here.

Build systems provide another close comparison because they preserve results across repeated changes. *Build Systems à la Carte* factors build systems into tasks plus scheduling and rebuilding components and systematically compares static and dynamic dependency strategies @mokhov2018. DOC instead fixes a language-neutral state/definition representation for the finite theorem and derives its ready relation from the current active set. A build engine could implement DOC's finite kernel, but DOC does not replace build-specific questions such as dependency discovery, command execution, artifact hashing, or failure policy.

Incremental dataflow systems occupy a richer iteration/distribution point in the design space. Differential dataflow associates state and updates with partially ordered logical versions and retains indexed differences to support incremental iterative computation @mcsherry2013. Naiad's timely dataflow is a distributed cyclic dataflow model with logical timestamps and progress coordination @murray2013. DOC deliberately does not place those mechanisms in its finite acyclic kernel; recurrence is expressed by forward-linked finite epochs, while placement and transport are realization contracts. This choice simplifies the finite theorem but gives up the native cyclic/timestamp semantics supplied by those dataflow systems.

@tab:related-comparison makes the technical comparison explicit. The “DOC distinction” column should be read as a representational difference relevant to this paper's proofs, not as an assertion that another system cannot emulate the behavior.

#block[
  #set text(size: 7.75pt)
  #set table(inset: 2.5pt)
  #figure(
    table(
      columns: (0.95fr, 1.45fr, 1.45fr, 1.55fr),
      table.header([*Approach*], [*Primary representation*], [*Repair / execution mechanism*], [*DOC distinction used here*]),
      [Self-adjusting computation @acar2005], [Dynamic dependence graph of an execution; dependence tracking is part of the self-adjusting mechanism.], [Change propagation adjusts computation and dependence structure after external change.], [One declared logical-state graph is fixed within a graph version; repair obligations are the separate set $A$, and the theorem ranges over frontier-subset schedules.],
      [Adapton @hammer2014adapton], [Demanded computation graph with explicit observer/inner-computation separation.], [Demand-driven incremental recomputation and reuse.], [Demand is a restriction of the same finite state graph; the proved whole-graph kernel does not require demand nodes or an observer calculus.],
      [Build Systems à la Carte @mokhov2018], [Keys/tasks plus parameterized scheduler and rebuilder; dependencies may be obtained by different strategies.], [Build-specific scheduling/rebuilding decides which tasks execute and whether results are current.], [DOC fixes one state/definition semantics and one repair relation; command effects and dependency discovery remain outside the pure theorem.],
      [Differential dataflow @mcsherry2013], [Collections of differences indexed by partially ordered logical versions.], [Incremental operators reuse updates across versions and nested iteration.], [Finite DOC has one retained valuation plus active set for the current epoch; recurrence is an additional forward-epoch construction rather than a partial-order timestamp algebra.],
      [Naiad / timely dataflow @murray2013], [Distributed cyclic dataflow with logical timestamps and progress tracking.], [Data-parallel cyclic execution with coordination based on timestamp progress.], [DOC's finite theorem is acyclic; transport, placement, and fail-stop reconstruction are separated as conditional realization contracts.],
    ),
    caption: [Focused comparison with the closest incremental and dataflow models. The table identifies which representation or repair boundary differs from DOC's finite kernel.],
  ) <tab:related-comparison>
]

Static differentiation takes a different route by deriving change functions for higher-order programs @cai2014; materialized-view maintenance derives incremental updates for database views @blakeley1986; and spreadsheet systems provide a familiar dependency-maintained interface, with recent work on scalable incremental spreadsheet applications @hadar2023. These approaches reinforce the paper's narrower positioning: DOC contributes neither a new general change calculus nor a domain-specific optimal incremental algorithm.

Persistent incremental traces also create storage-management problems. Hammer and Acar study memory management specifically for self-adjusting computation @hammer2008memory. DOC's logical-availability contract is intentionally less prescriptive: it states what must remain observable or reconstructible, while reclamation strategy belongs to a conforming realization. Minsky's counter-machine model supplies the classical universality basis used only for the forward recurrence construction @minsky1967.

The assessable technical claim is therefore limited to the finite factorization proved in @thm:finite-stabilization and its explicitly separated extensions: a persistent typed logical-state graph $G=(S,Delta)$; a retained valuation $nu$; a transient repair-obligation set $A$; dependency-minimal ready states; arbitrary nonempty ready-frontier subset selection from one settled pre-state; atomic publication of changed conclusions; and a one-way sound cutoff predicate whose always-false implementation remains correct. The experimental validation in @sec:validation asks whether this factorization is coherent, executable, and useful as a generic semantic boundary—not whether it dominates specialized incremental systems.

= Conclusion

The finite model makes dependency structure, retained values, and repair obligations explicit. Its compact representation is

$ G=(S,Delta), #h(2em) Q=(nu,A). $

A program is a family of typed logical states and partial local definitions. A stable valuation agrees with current sources and every required definition. A source change adds induced users to the current repair obligations. One transition selects any subset of the dependency-minimal active frontier, evaluates it from a common settled pre-state, and publishes complete candidates together. Candidates not proven equal propagate; a sound equality proof stops the wave.

The finite kernel deliberately contains only the persistent graph, retained valuation, repair obligations, and transition relation. Recurrence, graph replacement, and physical placement are separate layers with additional assumptions. Publication, reclamation, transport, authority, reconstruction, and effects therefore remain explicit contracts rather than consequences silently attributed to the finite theorem.

DOC does not claim universal speedup or distributed-systems guarantees. Its contribution is the specific finite repair semantics proved here, together with separately stated extension and realization contracts and an executable implementation that tests those boundaries.

#set heading(numbering: none)

= Appendix A. Compact formal summary <app:formal>

== A.1 Program

$ G=(S,Delta) $

where $S$ is the finite typed state family and $Delta$ is the partial definition map. The domains, cutoff predicates, local transformations, source batches, and induced graph satisfy the standing finite-kernel assumptions in @sec:assumptions.

== A.2 Configuration

$ Q=(nu,A), #h(1em) A subset.eq upright("dom")(Delta). $

$nu$ is the persistent pointwise-typed logical valuation. $bot$ denotes unmaterialized state, not application-level absence, and may occur only at an active derived state in a repair-admissible configuration. Physical residency is not represented in $Q$. $A$ is the transient repair-obligation set for one stabilization episode; it is not an assertion that every retained active value is unequal.

== A.3 Satisfaction

For $Delta(d)=(P_d,f_d)$, write $upright("Sat")_nu(d)$ when all premises are materialized and

$ nu(d)=f_d(nu(P_d)). $

== A.4 Repair admissibility

$ upright("Adm")(nu,A) equiv (forall s in S_(upright("src")): nu(s) != bot) #h(0.4em) and #h(0.4em)
(forall d in D-A: upright("Sat")_nu(d)). $

=== A.4.1 Ready frontier

$ R(A)={d in A | exists.not e in A: e prec d}. $

=== A.4.2 Initialization

For a total typed source environment $I$,

$ nu_0(s)=cases(I(s) & s in S_(upright("src")), bot & s in D), #h(1em) A_0=D. $

== A.5 Source batch

For a validated finite typed partial function $U_b$ over sources, let

$ X={s in upright("dom")(U_b) | upright("same")_s #h(0.08em) (U_b(s),nu(s)) = upright("false")}, $

$ nu_0=nu[s arrow.r.bar U_b(s) #h(0.2em) upright("for") #h(0.2em) s in X], #h(1em)
A_0=A union union_(s in X) upright("users")(s). $

== A.6 Transition

Choose $emptyset != F subset.eq R(A)$. Evaluate $v_d=f_d(nu(P_d))$ privately for every $d in F$ from the same pre-state. Let

$ C_F={d in F | nu(d)=bot} union
  {d in F | nu(d) != bot #h(0.3em) upright("and") #h(0.3em) upright("same")_d #h(0.08em) (v_d,nu(d)) = upright("false")}. $

Then

$ nu' = nu[d arrow.r.bar v_d #h(0.3em) upright("for") #h(0.3em) d in C_F], $

$ A' = (A-F) union union_(d in C_F) upright("users")(d), $

$ (nu,A) arrow.r (nu',A'). $

== A.7 Stable observation

A requested state is observable after the whole graph has stabilized. A demand-restricted realization applies the same rule to the requested state's ancestor-closed induced subprogram with materialized boundary sources.

=== A.7.1 Versioned recurrence extension

For one acyclic epoch template $G^E$, a typed partial function $K:S_(upright("src"))^E arrow.r S^E$ maps each carried next-epoch source to at most one previous-epoch origin. Each carried value must inhabit the declared domain of its next-epoch source, and every uncarried source receives an explicit epoch-local fact or declared fixed default. Demanding epoch $n$ materializes and stabilizes only epochs $0$ through $n$. A retention root set determines which completed epoch materializations remain observable.

== A.8 Immutable graph-version extension

A successful commit $G_k arrow.r G_(k+1)$ privately validates and stabilizes a repair-admissible candidate. Direct reuse requires the same stable name, authority role, declared value domain, and semantic equality. A retained derived value additionally requires an equivalence-bearing semantic key, identical ordered premise identities, and every premise to be compatibly retained and unaffected. Domain changes, new states, source/derived authority changes, and descendants of affected premises are repaired before atomic generation advance. Results captured under an older or different runtime's graph-generation token cannot publish into the new version.

== A.9 Recoverable placement profile

A non-discarded derived candidate is admissible only when its conclusion is currently active and in $R(A)$, it was evaluated from the committed logical pre-valuation of its source epoch, and its expected role and placement generation remain current. Finite join, graceful drain, and fail-stop reconstruction preserve logical observations when authoritative source facts survive and remain fixed during the final recovery interval, required resources and transport eventually become available, and that interval is free of further failures.

== A.10 Realization conformance

For every finite admissible interaction sequence $eta$,

$ upright("Obs")_P(eta)=upright("Obs")_(upright("DOC"))(G_0,Q_0,eta). $

The sequence is a meta-level conformance test, not stored history or logical configuration.

= Appendix B. Terminology <app:terminology>

@tab:terminology consolidates the terms used for logical state, repair, graph versions, observation, and physical placement so that similarly named concepts are not conflated.

#set text(size: 8.65pt)
#set table(inset: 2.8pt)
#figure(
  table(
  columns: (1.25fr, 3fr),
  table.header([*Term*], [*Meaning in this paper*]),
  [State], [Stable logical identity with a typed value domain.],
  [Source], [State without a local definition; receives environmental assignments.],
  [Derived state], [State in the domain of $Delta$.],
  [Definition], [Ordered premises and one local transformation whose conclusion is the map key.],
  [Valuation], [Current optional value at every logical state.],
  [Active set], [Transient set of definitions that may require reconsideration in one epoch.],
  [Ready frontier], [Dependency-minimal active definitions; independent next work.],
  [Repair-admissible], [All sources are materialized and every inactive derived state is materialized and locally satisfied.],
  [Stabilization], [A maximal sequence of valid frontier-subset transitions from a repair-admissible seed; the theorem establishes a unique stable result.],
  [Cutoff predicate], [A decidable sound test that may prove two values equal; always-false is valid and causes conservative propagation.],
  [Expansion], [Boundary-equivalent refinement of one definition into a finite DOC subgraph.],
  [Logical availability], [Entitlement to observe or consume a value, preserved by residency or authoritative reconstruction.],
  [Physical residency], [Current presence of one materialized representation; a realization choice, not a component of $Q$.],
  [Placement generation], [Physical authority token changed by reassignment or drain; not a logical value revision.],
),
  caption: [Terminology used throughout the manuscript.],
) <tab:terminology>

#set text(size: 10.2pt)
#set table(inset: 5.5pt)

#heading(level: 1, numbering: none, outlined: true)[Declarations]

#strong[Funding.] This research received no specific grant from any funding agency in the public, commercial, or not-for-profit sectors.

#strong[Competing interests.] The author declares no competing interests.

#strong[Code and data availability.] The manuscript source and compilation instructions are included with this submission. The complete runtime implementation, tests, bounded model checkers, benchmark driver, retained benchmark data, and verification materials are available in the repository submission snapshot #link("https://github.com/imxade/DOC/tree/submission-2026-09-30")[`submission-2026-09-30`]. The retained campaign used for the reported numerical results is fixed independently at benchmark commit #link("https://github.com/imxade/DOC/tree/d2e9edb4f962f132e96d7e342bd14f48ff8446cc/runtime/results/revision-2026-09-29")[`d2e9edb4f962f132e96d7e342bd14f48ff8446cc`].

#strong[Generative-AI disclosure.] During the preparation of this work, the author used OpenAI ChatGPT to assist with language refinement, manuscript critique, implementation review, test design, and supporting development tasks. The author reviewed and edited all generated material, independently checked the formal claims, references, implementation, and reported results, and takes full responsibility for the content of the article.

#bibliography("references.bib", title: [References], style: "ieee")
