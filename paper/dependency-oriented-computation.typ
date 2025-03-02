// Dependency-Oriented Computation manuscript source.
// Active-set finite core: G=(S, Delta), Q=(nu, A)
// Uses only Typst standard-library features.

#set document(
  title: "Dependency-Oriented Computation",
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
#set par(justify: true, leading: 0.68em, first-line-indent: 0em)
#set heading(numbering: "1.")
#set enum(numbering: "1.")
#set list(indent: 1.15em, body-indent: 0.55em)
#set table(inset: 5.5pt, stroke: 0.45pt + luma(205))
#show link: set text(fill: rgb("1f5a88"))
#show heading.where(level: 1): it => block(above: 1.15em, below: 0.55em)[
  #text(size: 15pt, weight: "bold", fill: rgb("203a5f"))[#it]
]
#show heading.where(level: 2): it => block(above: 0.9em, below: 0.35em)[
  #text(size: 12pt, weight: "bold", fill: rgb("284d6d"))[#it]
]
#show heading.where(level: 3): it => block(above: 0.65em, below: 0.25em)[
  #text(size: 10.7pt, weight: "bold")[#it]
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
#let figcounter = counter("doc-figure")
#let diagram(h, body, caption) = context {
  let n = figcounter.get().first() + 1
  figcounter.step()
  block(width: 100%, breakable: false, above: 0.55em, below: 0.65em)[
    #block(width: 100%, height: h, breakable: false, inset: 4pt,
      fill: pale, radius: 4pt, stroke: 0.45pt + luma(215))[
      #body
    ]
    #v(3pt)
    #align(center)[#text(size: 8pt)[*Figure #n.* #caption]]
  ]
}
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
#let definition(title, body) = statement("Definition", title, body, tone: "definition")
#let theorem(title, body) = statement("Theorem", title, body, tone: "theorem")
#let lemma(title, body) = statement("Lemma", title, body, tone: "theorem")
#let corollary(title, body) = statement("Corollary", title, body, tone: "theorem")
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
  #text(size: 23pt, weight: "bold", fill: ink)[Dependency-Oriented Computation]
  #v(6pt)
  #text(size: 13.4pt, weight: "semibold")[A Computational Model Based on Dependency and Consistency]
  #v(18pt)
  #text(size: 11.5pt, weight: "semibold")[Rituraj Basak]
  #linebreak()
  #text(size: 9.4pt)[Independent Researcher, India]
  #v(5pt)
  #text(size: 9.2pt)[Corresponding author: #link("mailto:ycantistudy@gmail.com")[ycantistudy\@gmail.com]]
  #linebreak()
  #text(size: 9.2pt)[ORCID: #link("https://orcid.org/0009-0002-7347-7064")[0009-0002-7347-7064]]
]
#v(18pt)
#align(center)[
  #block(width: 88%, inset: (x: 12pt, y: 10pt), fill: bluefill,
    stroke: 0.85pt + ink, radius: 4pt)[
    #align(center)[#text(size: 11.2pt, weight: "semibold", style: "italic")[Computation is the restoration of consistency in a persistent dependency graph.]]
  ]
]
#v(12pt)

#abstract-box([
This paper introduces *Dependency-Oriented Computation* (DOC), a computational model in which a program is a persistent graph of typed logical states and local definitions. Premise occurrence supplies the program's global organization rather than metadata for a separately ordered procedure. Sources receive environmental facts; each derived state has one pure deterministic local transformation; a valuation is stable when every required conclusion agrees with its current premises.

The finite operational kernel is

$ G=(S, Delta), #h(2em) Q=(nu,A). $

$S$ is the typed state family, $Delta$ maps derived states to ordered premises and transformations, $nu$ is the persistent valuation, and $A$ is the transient repair-obligation set for one source epoch. One transition evaluates any nonempty subset of the dependency-minimal active frontier from one settled pre-state and publishes the complete subset together. Conclusions not proven equal activate their users; proven-equal conclusions stop propagation. The always-propagate profile remains correct, so stabilization does not depend on decidable semantic equality.

One theorem gives termination, unique stable values, complete-reevaluation agreement, schedule independence, and sound cutoff for finite acyclic programs; a source-update corollary gives dependency-local repair. Initial materialization and later repair use the same relation. Retained stable values are therefore semantic caches, and each frontier exposes parallel work without source-level threads or worker counts.

The unchanged finite kernel is also the building block of full DOC. Versioned recurrence forms the unbounded computational extension by connecting finite acyclic epochs strictly forward in logical time. Immutable graph versions permit structural succession through private validation, stabilization, compatibility-controlled reuse, and atomic generation commit. Safe and placed realizations may vary storage, scheduling, reconstruction, transport, and placement while remaining conformant when they preserve the same stable observations over every finite admissible interaction sequence.

An executable witness checks the finite semantics, recurrence, immutable graph replacement, observation atomicity, logical availability across eviction and reconstruction, and bounded fail-stop recovery. Measurements illustrate the predicted trade-off: sparse change can avoid most work, coarse ready frontiers can use granted processors, and dense or very fine-grained graphs can lose to direct evaluation.
])

#block(width: 100%, inset: (x: 2pt, y: 4pt))[
  #text(size: 9.4pt)[#strong[Keywords:] dependency-oriented computation; incremental computation; persistent dependency graphs; reactive computation; parallel evaluation; dataflow; recurrence; runtime semantics.]
]

#pagebreak()
#set text(size: 9.05pt)
#set par(justify: true, leading: 0.48em, first-line-indent: 0em)
#outline(title: [Contents], depth: 2)
#set text(size: 10.2pt)
#set par(justify: true, leading: 0.68em, first-line-indent: 0em)
#pagebreak()

= Introduction

Large programs are often introduced as sequences of instructions, messages, callbacks, services, or tasks. That description is useful when a machine performs one instruction after another. It becomes incomplete when a system remains alive while its environment changes.

A compiler receives another edit. A build sees a changed file. A maintained query receives another transaction. A simulation advances. A long-lived information workflow receives new evidence. In each case, one question repeatedly becomes more important than the original textual order:

#quote(block: true)[
#strong[What depends on what?]
]

That question determines several things together: which retained conclusions may no longer be justified, which prior conclusions remain useful, what work must precede other work, and what work is independent. Conventional systems often encode these relationships repeatedly through ordered procedures, cache keys, invalidation rules, subscriptions, tasks, queues, or service routes. DOC asks whether one persistent dependency structure can instead be the primary global organization.

DOC does not require every local calculation to be decomposed into one universal term language. A local definition may be arithmetic, pattern matching, a query operator, a vector kernel, a verified routine, or an efficient opaque host function. DOC specifies how such definitions remain related across initial evaluation, later change, reuse, parallel execution, lifetime, and placement.

#principle([Starting point], [Do not begin by asking what executes next. Begin by asking what depends on what.])

== Why persistent computation?

A one-shot evaluator may discard every intermediate after producing an answer. Long-lived software instead receives repeated partial change. Editors, servers, simulations, dashboards, build systems, compilers, and workflows carry a large stable context from one event to the next. Reconstructing that context from nothing after each event discards information already justified by unchanged premises.

A persistent dependency graph retains logical identities and current values. Change then becomes a repair problem: restore consistency only where current justification may have changed. A one-shot program remains a special case: install one initial environment, stabilize once, observe, and discard the graph. The persistent interpretation is more general because first evaluation and later repair use the same semantics.

== Why call this a computational model?

The graph gives global organization, not local arithmetic. Each definition still supplies a transformation. The model determines when a definition has sufficient premises, what conclusion it may derive, what may need repair, why a retained conclusion remains usable, which repair obligations are independent, and what it means for an observation to be complete. It leaves local expression syntax and optimized kernels parameterized.

The graph is therefore not a scheduling hint attached to an otherwise complete instruction sequence. Physical queues, worker counts, processors, networks, and container boundaries may vary while stable logical observations remain the same.

#diagram(84pt, [
  #dnode(18pt, 8pt, [$a$ source], w: 90pt, fill: greenfill, stroke: green)
  #dnode(18pt, 48pt, [$b$ source], w: 90pt, fill: greenfill, stroke: green)
  #dnode(190pt, 28pt, [$upright("sum")$], w: 92pt, fill: warmfill, stroke: warm)
  #dnode(360pt, 28pt, [$upright("doubled")$], w: 94pt, fill: bluefill)
  #darrow(108pt, 22pt, 190pt, 40pt)
  #darrow(108pt, 62pt, 190pt, 44pt)
  #darrow(282pt, 42pt, 360pt, 42pt)
], [Premise occurrence in local definitions induces the program graph. No second invalidation, subscription, or scheduling graph is part of the program.])

== The change in viewpoint

Instruction-oriented descriptions ask what should happen next. DOC asks what relationships must hold when an observation is made. The programmer or compiler supplies those relationships. Execution is a restoration process derived from them rather than a second hand-written coordination program.

This change matters because later updates are not exceptional events attached to a one-shot meaning. Retained results, invalidation, repair, equality cutoff, and observation are ordinary consequences of the same persistent program.

== The chosen semantic boundary

DOC is a global computational model. It defines how persistent conclusions are organized, repaired, reused, observed, and placed. It does not require one universal local instruction calculus inside every definition.

#principle([Two-level semantics], [A complete DOC program consists of the dependency graph together with the typed local transformations attached to derived states. Local transformations determine values. Dependency, valuation, activation, and stabilization determine global execution across time and resources. Parameterizing the local language is a deliberate compositional boundary, not missing semantics.])

Where the internal structure of an opaque transformation matters for reuse, parallelism, placement, or repair, it may be replaced by a boundary-equivalent DOC expansion. The model can therefore expose more structure without requiring every useful local language or optimized kernel to be rebuilt as one closed low-level calculus.

= Model intuition and contributions

DOC separates logical meaning from physical mechanisms that may vary without changing it.

#table(
  columns: (1.08fr, 2.35fr, 1.55fr),
  table.header([*Layer*], [*Contains*], [*Status*]),
  [Finite core], [$G=(S,Delta)$, valuation, active set, source batch, frontier-subset transition, observation], [Proved; implemented; differentially and exhaustively checked in bounded domains],
  [Versioned recurrence], [Epoch-indexed templates, carry bindings, finite demanded prefixes, retention, divergence, universality argument], [Defined extension; finite-prefix execution implemented],
  [Immutable graph versions], [$G_k arrow.r G_(k+1)$, stable names, semantic compatibility, private validation and atomic commit], [Defined extension; implemented against from-scratch evaluation],
  [Safe realization], [Private evaluation, complete immutable publication, protected reads, roots, reclamation], [Normative contract; typed object-store witness],
  [Placed realization], [Resources, logical roles, TCP transport, generations, join, drain, and bounded fail-stop reconstruction], [Conditional theorem; executable loopback witness],
  [Policy-bearing boundaries], [Fixed points, conflict and replica policy, partitions, retention, irreversible external semantics], [Must be explicit; not inferred from dependency],
)

A property is *naturally implicit* when it follows from program structure together with unavoidable realization obligations, while ordinary programs do not separately prescribe its mechanism. Conforming runtimes may choose different schedulers, collectors, transports, placements, or topology-version builders without changing defined logical observations.

#table(
  columns: (1.3fr, 3fr),
  table.header([*Property*], [*Why it is naturally implicit*]),
  [Reactivity], [A source batch activates induced users; no separate watcher graph is required.],
  [Temporal reuse], [Stable retained values remain justified until an affected definition proves otherwise.],
  [Parallelism], [The ready frontier is dependency-minimal and its conclusions are distinct.],
  [Memory safety], [Logical identities and immutable publication permit protected use and automatic reclamation without physical pointers in ordinary programs.],
  [Distribution], [Remote premise occurrence becomes a transport obligation; placement and generation authority remain runtime concerns rather than application topology.],
  [Elasticity], [Resources may join, drain, or fail while logical identities and application graph remain unchanged; reconstruction follows authoritative sources and pure dependencies.],
)

The status distinctions used throughout the paper are exact: *proved core* means a theorem about the finite relation; *defined extension* means additional semantics stated separately; *realization contract* means physical obligations required to preserve observation; *executable evidence* means tested behavior of one implementation; and *remaining boundary* means policy or physics that dependency cannot determine by itself.

= Standing assumptions and scopes <sec:assumptions>

The assumptions are collected here so later definitions and results need not restate them.

#table(
  columns: (1.05fr, 3fr),
  table.header([*Scope*], [*Assumptions*]),
  [Finite kernel], [The state family and every premise sequence are finite; the induced dependency graph is acyclic; each local transformation is pointwise typed, pure, deterministic, total, and terminating for every typed premise tuple; accepted source batches are pointwise typed; and every cutoff predicate is sound, although it may conservatively return false. A finite program satisfying these conditions is *well formed*. Stabilization begins from a repair-admissible configuration as defined in the finite semantics; stable boundaries are its quiescent special case.],
  [Sources, failures, and effects], [Environmental nondeterminism enters through committed source batches. Recoverable absence or failure is represented explicitly inside a value domain. Host exceptions, cancellation policy, authorization, and irreversible external actions are outside ordinary local transformations.],
  [Versioned recurrence], [Each epoch instance satisfies the finite-kernel assumptions. Carry is a typed single-authority partial function from next-epoch sources to previous-epoch states and points strictly forward in logical time. Every uncarried source receives an explicit epoch-local fact or declared fixed default. A completed observation requests only a finite epoch prefix; an indefinitely extended demand may diverge.],
  [Graph versions], [A candidate graph is well formed, validated and stabilized privately from a repair-admissible seed. Direct reuse requires stable identity, the same source/derived authority role, the same declared value domain and semantic equality, and an explicit observational-compatibility contract before atomic generation commit. A domain change marks the state affected and is expressed by an explicit candidate transformation.],
  [Physical realization], [Logical observations are returned only at committed stable boundaries. Values captured by active evaluation, publication, observation, or transport remain protected. Claims about eventual reclamation, transport, join, drain, or recovery apply only under their stated eventual-progress and quiescence conditions.],
)

The abstract finite transition rule itself needs no scheduler-fairness premise: every transition selects a nonempty ready subset, and the acyclic work argument bounds the number of selections. Fairness appears only in physical progress claims that allow work or reclamation to be postponed by a runtime.

= Core semantics

#block[
  #set text(size: 8.75pt)
  #set table(inset: 3.6pt)
  #table(
    columns: (1.22fr, 1.65fr, 1.25fr),
    table.header([*Layer*], [*Claim made here*], [*Evidence status*]),
    [Finite logical kernel], [Acyclic stabilization, unique stable values, complete-reevaluation agreement, schedule independence, sound cutoff, and source-local repair.], [Human-readable proof, bounded exhaustive checking, and executable differential tests.],
    [Demand and recurrence], [Ancestor-closed demand agrees with full evaluation; finite requested recurrence prefixes require finite support; unbounded demand supplies partial computation.], [Propositions by restriction and induction; bounded exhaustive and runtime checks of finite prefixes.],
    [Graph evolution], [A compatible immutable replacement agrees with from-scratch evaluation of the candidate graph.], [Conditional proposition under the declared compatibility contract; bounded and runtime checks.],
    [Physical realization], [Publication, storage, reconstruction, placement, transport, recovery, and effects preserve logical observations.], [Conformance contracts and targeted runtime tests, not unconditional theorems of the finite kernel.],
    [Performance], [Sparse change can avoid work and coarse frontiers can use granted processors; overhead can dominate dense or fine-grained work.], [Environment-specific empirical measurements with correctness oracles and negative controls.],
  )
]

The table separates mathematical consequences of the kernel from extensions, realization obligations, and empirical evidence. None of the latter is stored in $G$ or $Q$.

== Basic objects and satisfaction

=== Typed state

#definition([State], [A state is a stable logical identity $s$ with a value domain $V_s$. Its identity is independent of a memory address, thread, process, machine, or storage location.])

A state may currently be unmaterialized. Each domain $V_s$ has its ordinary semantic equality. A realization may additionally provide a total decidable cutoff predicate

$ upright("same")_s: V_s times V_s arrow.r upright("Bool"), #h(1em) upright("same")_s #h(0.08em) (x,y)=upright("true") #h(0.3em) arrow.r.double #h(0.3em) x=y. $

The implication is the only soundness requirement: the predicate may conservatively return false even for equal values. The always-false predicate is therefore valid and yields complete propagation without cutoff. The C++20 witness uses exact signed-integer equality by default and also tests this conservative mode. Hash-only or tolerance tests are not valid unless returning true proves equality in the declared value domain.

The executable witness uses one scalar domain, but the model permits distinct domains.

=== Local definition

#definition([Local definition], [A definition for state $d$ is
$ Delta(d)=((s_1,dots.h,s_k), f_d), $
where the first component is an ordered premise sequence and
$ f_d: V_(s_1) times dots.h.c times V_(s_k) arrow.r V_d $
is a local transformation satisfying the standing finite-kernel assumptions in @sec:assumptions.])

The conclusion is the map key $d$ itself. No separate computation identity, output map, source flag, or producer map is required. Zero-premise definitions represent constant derived states.

Let

$ D = upright("dom")(Delta), #h(1.5em) S_(upright("src")) = S-D. $

States in $D$ are derived. States outside $D$ are sources. Single-producer authority follows from the partial-map representation.

=== Dependency and users

A state $x$ is a direct premise of $d$ when $x$ occurs in the premise sequence of $Delta(d)$. Its transitive closure is dependency order. Users are induced rather than separately declared:

$ upright("users")(x) = {d in D | x in P_d}. $

=== Valuation and satisfaction

A valuation is pointwise typed:

$ nu(s) in V_s union {bot} #h(0.5em) upright("for every") #h(0.5em) s in S, $

where $bot$ means no current materialization. It is not application-level null, deletion, failure, or unknown data; those meanings must be represented explicitly inside the relevant value domain. If $Delta(d)=((s_1,dots.h,s_k),f_d)$, then $d$ is locally satisfied when all premise values exist and

$ nu(d)=f_d(nu(s_1),dots.h,nu(s_k)). $

Local satisfaction uses equality in the declared value domain. The operational cutoff predicate is separate: it may decline to recognize an equality, but it may never claim sameness for unequal values. A quotient or approximate domain must therefore define its value domain and equality first; a heuristic hash or tolerance cannot silently change the semantics.

=== Observation

An observation requests the stable value of a logical state. Observation is an operation on the program, or an access policy outside it, not another component of $G$. The finite rule below is stated for whole-graph epochs. Demand-restricted execution is obtained by applying the same rule to the ancestor-closed induced subprogram of the requested state, with its boundary sources materialized. The C++20 witness conservatively stabilizes the whole finite graph.

== Computational expansion

A local definition may be too coarse to expose useful reuse, parallelism, placement, or repair. Expansion refines granularity without changing boundary meaning.

#definition([Expansion], [If $Delta(d)=(P,f_d)$, an expansion replaces it by a finite pure acyclic DOC subgraph that reads the same boundary premises $P$, publishes to the same boundary state $d$, uses fresh internal identities, and yields $f_d$ for every typed boundary tuple.])

#diagram(96pt, [
  #dnode(15pt, 34pt, [opaque $f_d$], w: 96pt, h: 30pt, fill: warmfill, stroke: warm)
  #dpanel(162pt, 8pt, 294pt, 76pt, [expanded DOC subgraph])
  #dnode(177pt, 36pt, [$g_1$], w: 68pt)
  #dnode(275pt, 36pt, [$g_2$], w: 68pt)
  #dnode(373pt, 36pt, [$g_3$], w: 68pt)
  #darrow(111pt, 49pt, 177pt, 49pt)
  #darrow(245pt, 49pt, 275pt, 49pt)
  #darrow(343pt, 49pt, 373pt, 49pt)
  #dlabel(237pt, 70pt, [fresh internal states; same boundary result $d$], size: 7.7pt)
], [Expansion changes internal visibility and cost, not stable observations at the original boundary.])

An implementation may fuse or batch an expanded region physically while retaining its logical boundaries. Expansion is therefore a semantic granularity choice, not an obligation to schedule every primitive separately.

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
], [Initial materialization and later repair use the same stabilization relation. Retained equality stops the later wave.])

The difference between initial and later stabilization is only what is already retained: initial evaluation begins with $bot$ at every derived state; a later epoch begins with stable values that may remain useful.

== Finite active-set transition system

The finite program and operational configuration are

$ G=(S,Delta), #h(2em) Q=(nu,A), #h(2em) A subset.eq D. $

$nu$ persists across epochs. $A$ is transient and records *repair obligations*: derived states whose definitions may need reconsideration. Membership in $A$ does not assert that the retained value is already known to be unequal; an active state may reevaluate to the same value and stop propagation.

A configuration $Q=(nu,A)$ is *repair-admissible* when every source is materialized and every inactive derived state is materialized and locally satisfied:

$ (forall s in S_(upright("src")): nu(s) != bot) #h(1em) upright("and") #h(1em)
  (forall d in D-A: nu(d) != bot #h(0.35em) upright("and") #h(0.35em) d upright(" is locally satisfied")). $

An active derived state may retain an old materialization or may be $bot$. A configuration is *quiescent* when $A=emptyset$; a repair-admissible quiescent configuration is exactly a stable valuation. Initialization, accepted source repair, compatible graph-version seeds, and reconstruction all enter the same transition relation through this invariant.

=== Ready frontier

Write $e prec d$ when derived state $e$ is a transitive premise of $d$. For an active set $A$, define the dependency-minimal frontier

$ R(A)={d in A | exists.not e in A: e prec d}. $

Every member of $R(A)$ has no active strict ancestor. In a repair-admissible configuration, this implies that all of its premises are materialized: a source is materialized by definition; an inactive derived premise is materialized and satisfied; and an active derived premise, or one below an active ancestor, would prevent readiness. Distinct frontier members cannot depend on one another and have distinct conclusions.

=== Initialization

Let $I$ be a total pointwise-typed initial environment over $S_(upright("src"))$. Initialization constructs

$ nu_0(s)=cases(I(s) & s in S_(upright("src")), bot & s in D), #h(1.2em) A_0=D. $

Stabilization then performs ordinary first evaluation. The initialization configuration is repair-admissible because every derived state is active. More generally, $bot$ may occur only at an active derived state in any repair-admissible configuration.

=== Source update

Let $U_b$ be a finite pointwise-typed partial function whose domain is contained in $S_(upright("src"))$. A runtime accepts it only after validating every target and value. A list representation must also reject duplicate targets before changing any state; that rejection merely enforces that $U_b$ is a function.

Given a repair-admissible configuration $(nu,A)$, define the assignments not proven equal by the source cutoff predicates:

$ X={s in upright("dom")(U_b) | upright("same")_s #h(0.08em) (U_b(s),nu(s)) = upright("false")}. $

The accepted source boundary step is

$ nu_0=nu[s arrow.r.bar U_b(s) #h(0.25em) upright("for") #h(0.25em) s in X], $

$ A_0=A union union_(s in X) upright("users")(s). $

The assignments in $X$ are installed atomically, and the direct users of those sources are added to any obligations already present. The step preserves repair-admissibility: an inactive direct user of a changed source becomes active, while every other inactive state remains locally satisfied until a changed active premise publishes. An empty batch, or a batch whose assignments are all proven equal, yields $X=emptyset$ and leaves $A$ unchanged. With a conservative always-false predicate, an exactly equal assignment may still start harmless repair. Stable-boundary epochs are the common case $A=emptyset$; after an exceptional frontier failure, a later serialized source batch may instead supersede the still-active obligations without discarding them.

=== One frontier-subset transition

Choose any nonempty finite frontier selection

$ emptyset != F subset.eq R(A). $

For each $d in F$ with $Delta(d)=(P_d,f_d)$, evaluate privately from the same pre-transition valuation:

$ v_d=f_d(nu(P_d)). $

Let the propagating-conclusion set be

$ C_F={d in F | nu(d)=bot} union
  {d in F | nu(d) != bot #h(0.3em) upright("and") #h(0.3em) upright("same")_d #h(0.08em) (v_d,nu(d)) = upright("false")}. $

Publish every candidate in $C_F$ as one logical commit and define

$ nu' = nu[d arrow.r.bar v_d #h(0.3em) upright("for") #h(0.3em) d in C_F], $

$ A' = (A-F) union union_(d in C_F) upright("users")(d). $

Then

$ (nu,A) arrow.r (nu',A'). $

This is the sole finite repair rule. A singleton $F$ gives sequential execution. A larger $F$ gives parallel evaluation. All candidates read the same settled pre-state; the complete selected frontier joins before the logical commit. A candidate proven equal to its retained value is removed from $A$ but publishes no replacement and activates no user. If the cutoff predicate conservatively returns false, republishing and downstream activation remain correct but may do more work. The C++20 witness uses the deterministic policy $F=R(A)$ at every step; choosing a smaller eligible subset is allowed by the model but is not required of that witness.

#boundary([Failure before publication], [Typed `Result`, option, or error values are ordinary values when the local function remains total. A thrown host callback violates the finite theorem's totality premise. Defensively, if any candidate in $F$ throws before the barrier, the witness publishes none of that frontier and keeps every state in $F$ active. Accepted source facts remain committed. A realization may treat cancellation before publication the same way, but the witness exposes no cancellation API. Retry, rollback, and irreversible-action policy belong to the effect or recovery boundary rather than to pure stabilization.])

= Central metatheory

#lemma([Frontier materialization and preservation], [In a repair-admissible configuration, every ready definition has materialized premises. An accepted source boundary step and every valid frontier-subset transition preserve repair-admissibility.])

#proof([
Let $Q=(nu,A)$ be repair-admissible. If $d in R(A)$ and a premise $p$ is a source, $p$ is materialized by admissibility. If $p$ is derived and active, then $p prec d$, contradicting readiness; if it is inactive, admissibility makes it materialized and locally satisfied. Thus every candidate in a valid selection is defined.

For a source batch, consider any derived state left inactive after the batch. It was inactive before, and none of its source premises changed; otherwise it would be a direct user of a member of $X$ and would have been activated. Its value and all premises are therefore unchanged, so it remains materialized and satisfied.

For a frontier transition, let $x$ be inactive in $A'$. If $x in F$, all of its premises are outside $F$ and are unchanged by the commit. The candidate $v_x$ therefore satisfies its definition; if $x in.not C_F$, cutoff soundness gives $v_x=nu(x)$, so the retained value is the same satisfying value. If $x in.not F$, then $x$ was already inactive. Any selected premise that changed would place $x$ in the propagated user union, contrary to $x in.not A'$. Hence its conclusion and premises are unchanged and its prior satisfaction is preserved. Materialization follows in the same cases: selected unmaterialized conclusions are published, selected retained conclusions were already materialized, and previously inactive conclusions remain materialized.
])

#lemma([At-most-once selection and finite progress], [Fix one repair episode, meaning a repair-admissible seed followed only by frontier-subset transitions and no intervening accepted source batch. Every derived definition is selected at most once. Consequently every valid transition sequence in that episode is finite, and every maximal sequence ends quiescent.])

#proof([
When $d$ is selected, it has no active strict ancestor. Suppose some strict ancestor of $d$ later became active, and choose the first such activation. Activation can arise only from publication by one of that ancestor's direct premises. That publishing premise is itself a strict ancestor of $d$ and must have been active and selected earlier, contradicting the choice of the first later ancestor activation. Sources do not change inside the fixed episode. Thus no strict ancestor of $d$ can publish after $d$ is selected, its premises cannot later change, and $d$ cannot be reactivated.

At most $|D|$ definitions are therefore selected, while each transition selects a nonempty set, so no valid sequence is infinite. If a finite maximal sequence ended with $A != emptyset$, acyclicity of the finite dependency order would give a minimal member of $A$, hence a nonempty ready frontier and another valid transition. Therefore a maximal sequence ends with $A=emptyset$.
])

#lemma([Canonical stable valuation], [For fixed current source values, there is exactly one stable valuation, namely complete topological reevaluation of every derived definition.])

#proof([
Choose a topological order of $D$. Keep each current source value and define $mu(d)=f_d(mu(P_d))$ in that order. Totality and typing make $mu$ exist. Any stable valuation has the same source values. Inductively, when all premises of $d$ agree with $mu$, local satisfaction and determinism force its conclusion to equal $mu(d)$. Thus every stable valuation equals $mu$, and $mu$ is exactly complete reevaluation.
])

#theorem([Finite stabilization], [For every well-formed finite acyclic DOC program, begin from any repair-admissible configuration and hold sources fixed during the repair episode. Every valid frontier-subset transition sequence is finite. Every maximal sequence ends in the unique stable valuation produced by complete topological reevaluation. The result is independent of the eligible selections and their valid order, and sound exact cutoff does not change that result.])

#proof([
The preservation lemma keeps every reached configuration repair-admissible. The finite-progress lemma makes every valid sequence finite and every maximal sequence quiescent. Quiescence together with repair-admissibility makes every derived state materialized and locally satisfied, so the terminal valuation is stable. The canonical-valuation lemma identifies that terminal valuation uniquely with complete reevaluation. Hence every valid maximal schedule has the same result.

For exact cutoff, if $upright("same")_d(v_d,nu(d))$ is true, soundness gives $v_d=nu(d)$. Retaining the old materialization is therefore observationally identical to publishing the candidate. An inactive direct user was satisfied before the transition and sees no changed premise, so it remains satisfied; an already active user remains active. Omitting activation through that equal conclusion therefore loses no repair obligation. Conservative false negatives may activate additional users, but preservation and uniqueness still force the same terminal valuation.
])

#corollary([Initial/later unity], [First materialization and later reactive repair are the same stabilization relation with different retained valuations.])

#corollary([Semantic caching and work bound], [At a stable boundary, every retained derived value is the unique correct value for its current premises. During one fixed repair episode each definition evaluates at most once. An accepted later source batch starts a new episode and unions its direct users with obligations retained after any exceptional failure.])

#corollary([Independent ready selections commute], [Let $F_1$ and $F_2$ be disjoint subsets of the same ready frontier. No selected conclusion is a premise of another selected conclusion, all candidates read the same settled values, writes target distinct states, and propagated users combine by set union. Evaluating and committing $F_1$ then $F_2$, $F_2$ then $F_1$, or $F_1 union F_2$ therefore yields the same valuation and active set.])

#corollary([Source-update locality], [For a source batch applied at a stable boundary, let $upright("Reach")^*(X)$ be the reflexive-transitive user closure containing the changed sources and every state reachable from them. Initial activation enters only direct users of $X$, and every later activation follows one user edge. No state outside that closure is selected or modified, so it retains its value.])

#corollary([Conservative cutoff], [Any cutoff predicate satisfying only the stated one-way soundness condition is correct. Returning false for equal values can add work inside the reachable region but cannot change the unique stable valuation.])

#theorem([Expansion preservation], [Replacing one definition by a finite acyclic boundary-equivalent expansion preserves every stable observation over the original states.])

#proof([
Fix the source values and compare complete reevaluation of the original and expanded graphs. Every original state upstream of the replaced definition is unchanged. The fresh internal expansion has a unique stable valuation by finite stabilization, and boundary equivalence makes its published value at $d$ equal to $f_d$ on the same boundary premises. A topological induction over the remaining original descendants then gives the same value at every original state. Schedule independence extends the argument from complete reevaluation to every valid stabilization schedule.
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
  #dline(136pt, 64pt, 330pt, 64pt, stroke: 0.7pt + accent)
  #dnode(174pt, 50pt, [same ready frontier], w: 118pt, h: 28pt, fill: white, stroke: accent, size: 8pt)
], [Independent active branches form one ready frontier. The program contains no thread count or concurrency syntax.])

No frontier member transitively depends on another frontier member: if it did, one member would require an active unsettled conclusion as a premise and would not be ready. Distinct frontier members also publish distinct logical conclusions because $Delta$ is a partial map keyed by conclusion state.

A DOC program therefore does not need to spell out `spawn`, `wait`, locks, queues, or a worker count merely to reveal independence. A realization may process a frontier sequentially, on several granted CPU cores, on accelerators, or across placed resources. The realization still needs synchronization: all selected candidates read one settled pre-state, private evaluation completes before the frontier publication barrier, and failed candidates must not leak partial publication. These mechanisms implement the semantic rule; they are not additional concurrency instructions in application code.

#principle([Shared cause], [Change exposes an affected dependency region; the dependency-minimal active frontier identifies necessary independent work. Reactivity, temporal reuse, and parallel readiness arise from the same persistent structure.])

== Reduction optimality and temporal reuse

Avoiding redundant work inside one isolated calculation and reusing results across later change are different objectives. They are compatible rather than mutually exclusive.

#table(
  columns: (1.22fr, 1.72fr, 1.72fr),
  table.header([*Question*], [*Local reduction optimization*], [*DOC temporal reuse*]),
  [Primary waste], [Repeated work within one execution], [Repeating maintained work after later partial change],
  [Boundary], [Inside a local definition or term], [Across persistent states and source-update epochs],
  [Best unit], [Expression, kernel, algorithm], [Affected dependency region and ready frontier],
  [Compatibility], [May optimize any $f_d$], [May retain or expand that optimized $f_d$ as one node],
)

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

#definition([Versioned recurrence], [A recurrent DOC program is a finite acyclic graph template indexed by logical epochs, together with an initial epoch, a demand rule, and a typed partial carry function $K:S_(upright("src"))^E arrow.r S^E$. The meaning $K(s)=x$ is that source $s$ of epoch $t+1$ receives the value of state $x$ from epoch $t$. Thus each next-epoch source has at most one carry authority; its carried value must belong to the source domain. Every uncarried source receives an explicit epoch-local fact or declared fixed default. Demanding epoch $n$ instantiates and stabilizes only the finite prefix through $n$. An observation that continues demanding later epochs without reaching its stopping condition diverges.])

#theorem([Demand-restriction agreement], [Let $T subset.eq S$ be a finite requested set and let $H_T$ be the ancestor-closed induced subprogram containing $T$, with every incoming boundary source materialized to the same fact as in the full program. Stabilizing $H_T$ yields exactly the restriction to $H_T$ of the unique stable valuation obtained by stabilizing the full program from those source facts.])

#proof([
Let $mu$ be the unique full-program stable valuation and let $mu_T$ be the unique stable valuation of $H_T$. Ancestor closure ensures that every premise of each retained derived definition is either retained in $H_T$ or supplied as a boundary source with the same value as in $mu$. Order the retained derived states topologically. The source and boundary cases agree by construction. If every premise of a retained derived state agrees with $mu$, determinism forces its conclusion to agree as well. Induction gives $mu_T=mu|_(H_T)$, including every requested state. Finite stabilization supplies existence and schedule independence on both graphs; demand restriction changes only the induced subprogram, not the transition rule.
])

#theorem([Finite support of requested recurrence prefixes], [For a finite epoch template, total local definitions, a single typed carry authority for each carried next-epoch source, and explicit facts or fixed defaults for every uncarried source, every requested finite prefix $0, dots, n$ requires only finitely many template instances and finitely many finite-kernel transitions. If an absorbing halt state is reached, requesting later epochs may reuse that same terminal meaning without additional machine progress; alternatively demand may stop at halt.])

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

A deterministic two-counter machine has a finite instruction table, a program counter, and two unbounded natural-number registers. Encode a configuration as

$ q_t=(upright("pc")_t,r_(1,t),r_(2,t)). $

One finite local `Step` definition performs the instruction selected by the program counter and yields $q_(t+1)$. Increment, zero test, conditional decrement, and program-counter update simulate one machine transition.

#diagram(66pt, [
  #dnode(18pt, 18pt, [$q_t$], w: 86pt, fill: greenfill, stroke: green)
  #dnode(132pt, 18pt, [`Step`], w: 86pt, fill: warmfill, stroke: warm)
  #dnode(246pt, 18pt, [$q_(t+1)$], w: 92pt, fill: bluefill)
  #dnode(366pt, 18pt, [$q_(t+2)$], w: 92pt, fill: bluefill)
  #darrow(104pt, 32pt, 132pt, 32pt)
  #darrow(218pt, 32pt, 246pt, 32pt)
  #darrow(338pt, 32pt, 366pt, 32pt)
], [Versioned recurrence carries state forward through acyclic epochs rather than introducing a same-epoch dependency cycle.])

#theorem([Universality of versioned recurrence], [DOC with demand-driven unbounded epoch instantiation, unbounded natural values, finite case analysis, increment, zero test, and conditional decrement can simulate every deterministic two-counter machine step for step.])

Map each machine configuration to one epoch state and the finite instruction table to finite case analysis inside `Step`. Define the halt configuration as absorbing, or stop demand before requesting its successor. Induction on $t$ then shows that epoch $t$ denotes the machine configuration after $t$ steps. A halting machine yields a finite observed prefix; a non-halting machine demands an unbounded sequence and diverges.

#boundary([Recurrence evidence], [The witness checks demand-driven finite-prefix materialization, forward carry bindings, bounded stopping predicates, retention windows, and a deterministic two-counter-machine prefix against a direct interpreter. This validates the executable recurrence construction used by the universality argument; it is not a second proof of universality. A finite test cannot complete a non-halting run, and same-epoch fixed points remain a separate semantic problem.])

== Immutable graph-version change

Some programs change not only source values but also which logical states and definitions exist. DOC handles this without mutating the graph beneath active work. Let

$ G_0 arrow.r G_1 arrow.r G_2 arrow.r dots $

be an ordered sequence of immutable, individually well-formed graph versions.

#definition([Graph-version commit], [A commit from $G_k$ to candidate $G_(k+1)$ first stabilizes the current version and validates the candidate before reading any candidate-derived index. A current source fact crosses by stable logical name only when the candidate state remains a source with the same declared value domain and semantic equality. A retained derived value requires the same stable name, the same derived authority role, the same declared value domain and semantic equality, an explicit equivalence-bearing semantic key, identical ordered premise identities, and every ordered premise to be carried or retained compatibly and remain unaffected. If a state domain changes, that state is affected; migration is represented by an explicit candidate transformation rather than implicit value reuse. New states and every source/derived authority-role change are structurally affected. The private candidate seed must be repair-admissible; its affected region is then stabilized by the ordinary finite rule. Numeric runtime state identifiers are local to one immutable version, so cross-version update and observation APIs resolve stable names. The complete candidate graph and valuation replace the prior version atomically, advancing a runtime-scoped graph-generation token.])

An in-flight result captured under graph generation $k$ may publish only while that generation remains current. Retirement removes the old graph's logical roots after active observations release them; ordinary reachability then governs physical reclamation. A newly introduced source uses its declared initial fact and marks its user region affected. A stable name that changes between source and derived authority is likewise affected rather than reused. A newly introduced or structurally changed derived state begins as a repair obligation.

#theorem([Conditional graph-version commit agreement], [Under the stated compatibility contract, every successful commit to $G_(k+1)$ has the same stable values as constructing $G_(k+1)$ from the carried current source facts and evaluating it completely from scratch. Retained compatible values change cost, not meaning.])

#proof([
Let $mu^*$ be complete from-scratch evaluation of $G_(k+1)$ from the carried candidate source facts. Same-role compatible sources have exactly those values in the private candidate seed. Consider an inactive retained derived state in candidate topological order. The compatibility contract permits it to remain inactive only when its authority role, declared domain and equality, equivalence-bearing semantic key, ordered premise identities, and every premise are compatible and unaffected. Its source premises therefore equal $mu^*$, and its earlier retained derived premises equal $mu^*$ by induction. Boundary equivalence of the retained definition then makes its retained conclusion equal $mu^*$ as well. Hence every inactive candidate state is already materialized and locally satisfied; every state not justified by this induction is active. The private seed is repair-admissible.

Finite stabilization on the candidate graph now terminates at its unique stable valuation, which the canonical-valuation lemma identifies with $mu^*$. Atomic generation commit exposes only that stable candidate, and generation rejection prevents an older in-flight result from changing it. Retained compatible values therefore reduce repair work without changing from-scratch meaning.
])

#boundary([Topology identity boundary], [The runtime does not guess whether two arbitrary functions are semantically equivalent. Stable names and semantic keys are explicit compiler or builder contracts. Atomic graph replacement is implemented; distributed agreement on which graph version is authoritative remains a replica and partition policy.])

= Realization contracts and boundaries

Authority, logical availability, and physical lifetime are not extra instructions in the finite repair rule. They are constraints on realizations that preserve the rule's observations.

== Logical availability and safe realization

=== Logical authority and immutable publication

The partial-map representation gives one logical producer to every derived state. Source batches have environmental authority. Placement may move the physical executor or storage location, but it must not create a second logical producer for the same conclusion.

A conforming realization evaluates candidates privately and publishes complete immutable values. A reader observes either the previous complete materialization or the next complete materialization, never a partially mutated object. This distinction between logical authority and physical ownership permits many memory implementations without changing program meaning.

=== Logical availability and physical residency

#definition([Logical availability], [A logical value is available while the program's current state, a permitted observation, retained recurrence policy, active work, or an admitted external root still entitles it to be observed or consumed. A realization preserves that availability by retaining either a usable complete materialization or sufficient authoritative information to reconstruct an observationally equivalent complete value before use.])

A logically available value need not remain resident in its current physical form. A realization may evict, spill, compress, deduplicate, fuse, or discard a reconstructible derived materialization. It may retain current sources, a checkpoint, or another authoritative representation from which the same value can be recovered. Once a value has been pinned by an active observation, evaluation, publication, or transport, that complete physical object remains protected until the use finishes even if its state slot is concurrently evicted or replaced.

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
], [The model determines logical availability. The realization chooses residency, reconstruction, and reclamation while protected uses keep complete physical objects alive.])

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

The logical program does not contain today's machines. For placement, define role-tagged physical entities

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
], [Joining, reassignment, graceful drain, and bounded fail-stop recovery change physical placement, not logical identities or dependency meaning.])

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

#definition([Placed-epoch conformance], [A physical execution of one finite logical epoch is conforming when: (1) transport copies immutable materializations tagged with source epoch, role, and placement generation but does not alter their logical values; (2) every non-discarded derived publication has a conclusion $d$ that is currently active and belongs to $R(A)$, equals $f_d$ applied to the committed logical pre-valuation of that source epoch, and carries a currently admissible role token; (3) join, reassignment, and graceful drain change only $pi_t$, $gamma_t$, and physical copies, never $G$, source facts, or logical definition authority; and (4) after finitely many placement changes, every required transport and active logical role eventually completes.])

#theorem([Failure-free join/drain transparency], [Every conforming placed execution projects, after duplicate and stale physical events are discarded, to a valid sequence of finite frontier-subset transitions. Consequently, after source and placement quiescence, its observable values equal local stabilization.])

A currently admitted publication is either one legal singleton frontier transition or part of a commuting frontier batch: its conclusion is active and ready, it was evaluated from the committed logical pre-valuation of that source epoch, it publishes one distinct logical conclusion, and it cannot be admitted from obsolete authority. Join and drain change where later work occurs, not the logical transition being represented.

=== Bounded fail-stop reconstruction

#definition([Recoverable placed profile], [Source facts acknowledged as recoverable are durably committed by one declared authority. Pure derived materializations are reconstructible caches. After a finite fail-stop loss, the realization invalidates every lost role generation, assigns the roles to surviving or newly joined resources, restores authoritative source facts, marks every lost derived state and its transitive user region as repair obligations, and stabilizes again.])

#theorem([Finite fail-stop reconstruction], [For a finite acyclic pure DOC graph, if authoritative source facts survive and remain fixed during the final recovery interval, at least one valid execution resource eventually remains or joins, generation invalidation rejects late failed work, transport eventually succeeds, and no further failure occurs during that interval, reconstruction reaches the same observable stable valuation as local evaluation from those source facts.])

The replacement execution begins from the same sources as complete reevaluation. Every lost derived state and its transitive user region is active, so the recovery seed is repair-admissible even when a lost premise was previously used by a retained descendant. The finite stabilization theorem gives termination and unique values; placement generations prevent obsolete candidates from replacing them. Checkpoints of expensive derived state may reduce work but are not required for correctness.

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

#principle([Unifying question], [The domains differ, but each asks the same structural question: what conclusion is justified by what current premises, and what must be repaired when those premises change?])

= Runtime conformance

The executable witness is subordinate to the model. Its normative direction is

```text
paper model -> observable obligations -> runtime refinement
```

not the reverse.

#definition([Finite interaction-trace conformance], [Let $eta$ be any finite admissible sequence of committed source batches, stable observations, and immutable graph-version commits beginning from $(G_0,Q_0)$. A physical realization $P$ conforms when

$ upright("Obs")_P(eta)=upright("Obs")_(upright("DOC"))(G_0,Q_0,eta). $

$eta$ is a mathematical test sequence, not retained application history and not a component of $G$ or $Q$. Internal schedules, materializations, cache states, reconstruction steps, placements, and reclamation events may differ.])

This definition unifies repeated source updates, observations, and graph replacement without adding a history calculus to DOC. Recurrent observations are ordinary observations of epoch-indexed logical states within a finite demanded prefix.

== Executed representation

#block[
  #set text(size: 8.8pt)
  #table(
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
  )
]

Application graphs never specify a worker count. Experimental limits are imposed outside the graph through the execution environment. Resource join and removal are likewise realization operations over placement rather than application-level topology instructions.

== Verification scope

The native runtime suite contains 36 named conformance suites and a separate benchmark-generator equivalence test. Its randomized differential component checks 9,600 update epochs against complete reevaluation, including randomized legal frontier-subset schedules. Twenty repeated optimized runs of the two native test executables completed successfully.

Five independent bounded checkers cover complementary state spaces. The ordinary finite checker enumerates 2,520 Boolean DAGs and 40,320 source epochs. The repair checker covers 512 graphs, 59,904 admissible seeds, 239,616 continued source updates, and 521,584 unique explored configurations. The graph-version checker covers 64 graph shapes and 15,360 commits, including source/derived authority transitions. The duplicate-premise checker covers 84 graphs and 2,592 admissible configurations. The demand/recurrence checker covers 364 demand templates, 21,840 demanded subsets, 364 recurrence templates, 17,472 finite prefixes, 2,912 stopping cases, and duplicate-carry rejection.

These finite enumerations check initialization, repair admissibility, continued source batches, every nonempty legal subset of each bounded ready frontier, exact and conservative cutoff, locality, schedule agreement, demand restriction, recurrence support, graph-role changes, graph-local identifier reorderings, and replacement agreement. Bounded checking is executable counterexample search over the stated finite spaces; it is not a proof of universal correctness.

#boundary([Current executable coverage], [The high-performance active-set evaluator remains specialized to scalar values; typed immutable objects, eviction, and reconstruction are checked in a separate safe-realization profile rather than a fully integrated generic evaluator. The placed runtime uses real transport but remains a bounded single-coordinator witness rather than a production multi-host platform. The finite metatheory is mathematically argued and bounded-exhaustively checked, not yet mechanized in a proof assistant. These limits concern evidence and engineering maturity, not hidden additions to the logical core.])

= Evaluation

The benchmark executable checks every DOC result against a complete serial reevaluation oracle. The financial workload also checks a conventional serial dependency-cached repair, and the sorting-network workload checks `std::sort`. The main evaluation rows use twenty fresh processes with alternating scenario order. A later externally limited parallel-capacity follow-up uses paired runs at each participant count, again alternating order. Its table reports median elapsed time and median paired speedup for each externally allowed participant count.

Measurements used an optimized GCC 14.2 build on Linux 6.12.13 with an Intel Xeon Platinum 8573C. Process affinity exposed five CPUs, while the container quota was four CPUs. Participant limits were imposed externally with `DOC_MAX_WORKERS`; application graphs contain no worker count. The complete raw data, medians, standard deviations, confidence intervals, minima, maxima, filter bounds, and executed-command record are provided in the supplementary material.

== Sparse repair, saturation, and negative control

#block[
  #set text(size: 8.5pt)
  #set table(inset: 2.8pt)
  #table(
    columns: (1.68fr, 0.92fr, 0.92fr, 0.82fr),
    table.header([*Scenario*], [*Direct raw mean*], [*DOC raw mean*], [*Evaluations*]),
    [Cold 2,048-leaf reduction], [296.292 ms], [292.741 ms], [4,095],
    [1 changed source], [309.608 ms], [0.350 ms], [12],
    [8 changed sources], [297.049 ms], [1.358 ms], [23],
    [64 changed sources], [330.318 ms], [9.175 ms], [132],
    [512 changed sources], [294.623 ms], [73.310 ms], [1,007],
    [2,048 changed sources], [292.589 ms], [303.648 ms], [4,038],
    [Dense cheap negative control], [0.227 ms], [43.698 ms], [245,730],
  )
]

The count curve is the stable result: sparse updates reconsider only the changed leaves and their ancestors, while dense updates approach complete work. Exact equality cutoff required one producer evaluation and activated no expensive user. Timing follows the same broad shape but is noisy and host-specific. Cold evaluation is near parity; complete change is slightly slower in raw mean; and the deliberately cheap dense graph is decisively worse under DOC because metadata and scheduling cost exceed useful work.

== Externally granted parallel capacity

#block[
  #set text(size: 8.35pt)
  #set table(inset: 2.7pt)
  #table(
    columns: (1.45fr, 1fr, 1.2fr),
    table.header([*Externally allowed participants*], [*Median time*], [*Median paired speedup*]),
    [1], [142.589 ms], [1.000$times$],
    [2], [72.274 ms], [*1.959$times$*],
    [3], [49.605 ms], [*2.853$times$*],
    [4], [37.527 ms], [*3.847$times$*],
  )
]

The same graph and output oracle were used at every externally passed limit. Median time decreases monotonically from one through four participants, while median paired speedup rises to $3.847 times$ at four participants. The four-CPU quota still makes this a bounded single-host result, not a many-core or multi-host scaling claim. It confirms that a coarse ready frontier can consume capacity granted by the environment without embedding capacity in the program.

== Realistic persistent financial projection

The non-synthetic workload models 4,096 business units. Each unit has four source cells and a deterministic 360-period fixed-point cash-flow projection; a balanced tree consolidates unit values. Complete serial reevaluation, a conventional serial cached segment-tree repair, and DOC must produce the same total.

#block[
  #set text(size: 8.45pt)
  #set table(inset: 2.8pt)
  #table(
    columns: (1fr, 1fr, 1fr, 1fr, 0.82fr),
    table.header([*Changed units*], [*Full raw mean*], [*Cached raw mean*], [*DOC raw mean*], [*DOC evals*]),
    [1], [5.316 ms], [0.001 ms], [2.356 ms], [13],
    [64], [4.779 ms], [0.075 ms], [1.942 ms], [133],
    [1,024], [5.214 ms], [1.235 ms], [4.064 ms], [2,049],
  )
]

DOC avoids most of the projection and consolidation graph under sparse change and is faster than complete reevaluation in these runs. The specialized cached baseline is much faster because it encodes exactly the workload's update strategy and has far less generic machinery. This is the honest engineering boundary: DOC supplies reusable semantics and general conformance properties, not a guarantee of beating a domain-specific incremental algorithm.

== Fine-grained graph negative case

A 512-input Batcher sorting network contains 11,520 compare-exchanges represented by 23,040 derived definitions and 23,552 total states. Sparse updates avoid many definitions and expose equality cutoffs, but direct complete network execution remains about two orders of magnitude faster: raw DOC update means range from 9.84 to 10.33 ms, while raw direct update means are below 0.09 ms. At full change, all 23,040 definitions execute and no cutoff remains. The result shows that expansion can expose logical reuse without making node granularity profitable; fusion, batching, or specialized operators would be required for this workload.

#boundary([Evaluation boundary], [These measurements support cost-shape and conformance claims only. They do not establish universal speedup, production distributed scalability, accelerator efficiency, or a hardware-independent constant. Stronger scaling evidence requires rerunning the preserved commands on dedicated many-core and multi-host systems.])

= Limitations

1. *Finite acyclic theorem.* The central theorem covers finite acyclic programs. Versioned recurrence supplies temporal repetition and ordinary partial computation, but same-epoch cyclic equations require a separately stated order, convergence, and observation semantics.
2. *Equality and function contracts.* Sound cutoff, total deterministic definitions, stable-name compatibility, and semantic keys are supplied by a compiler, builder, or application contract; the runtime cannot decide arbitrary function equivalence.
3. *Policy-dependent physical behavior.* Placement, routing, replica authority, partition handling, retention, compaction, checkpoints, quotas, and irreversible-effect recovery are not determined by the logical kernel.
4. *No universal memory or performance bound.* Logically rooted recurrence or audit history may grow without bound. Direct or specialized incremental execution may outperform the generic runtime, especially for dense or fine-grained work.
5. *Evidence limits.* The finite metatheory is not proof-assistant mechanized. Exhaustive checking is bounded. The physical witness is a bounded single-coordinator implementation, and the present scaling measurements are limited to four quota-granted CPUs on one host.

= Related work

Dependency-based evaluation has several established lineages. Kahn gives a deterministic semantic account of process networks whose communication structure constrains execution [1]. Attribute grammars attach semantic values and dependency relations to syntax; Knuth established the framework, and Demers, Reps, and Teitelbaum studied incremental reevaluation for editors [2-4]. Spreadsheets provide a widely used end-user form of dependency-maintained computation, and recent work studies scalable incremental spreadsheet applications [12]. These traditions ground DOC's use of explicit logical dependencies; DOC's finite kernel instead fixes one persistent state graph, one valuation, one repair-obligation set, and one frontier-subset repair relation.

Incremental and self-adjusting computation maintain results across change using recorded dependence, change propagation, memoization, or dynamically discovered dependency graphs [5-7]. Adapton combines demand with incremental maintenance [7]. Static differentiation derives change functions for higher-order languages [8]. Parallel self-adjusting computation develops richer control-dependence machinery and work/span bounds for parallel change propagation [9]. DOC does not claim these ingredients as new. Its contribution is a smaller, language-neutral semantic boundary for persistent logical states: local deterministic definitions, dependency-minimal active repair, an always-correct conservative cutoff profile, and a direct separation between logical metatheory and physical realization contracts.

Other domains organize incremental maintenance around specialized structure. Materialized-view maintenance derives updates for database views [10]. Build-system analysis separates dependency discovery, rebuilding, and scheduling policies [11]. Differential dataflow maintains collections of differences across partially ordered versions and supports iterative data-parallel computation; timely dataflow supplies a distributed cyclic execution substrate [13, 14]. These systems establish that incremental and distributed dependency maintenance can require substantially richer domains, timestamps, operators, or runtime protocols. DOC keeps recurrence, immutable graph succession, placement, recovery, and effects outside the finite nucleus so that each claim is stated at the level actually defined.

Persistent traces also create storage and reclamation concerns; prior self-adjusting-computation work develops explicit memory-management techniques for such traces [15]. DOC's corresponding statement is deliberately semantic rather than algorithmic: the model defines which logical observations remain available, while a conforming runtime chooses storage, reconstruction, pinning, and reclamation policy. Minsky's counter machines provide the classical universality basis used only for the versioned-recurrence construction [16].

The novelty claim is therefore conservative. DOC does not assert historical priority for dependency graphs, incremental repair, demand, parallel frontiers, recurrence, or distributed placement individually. It presents and analyzes their particular factorization around the unchanged nucleus $G=(S,Delta)$ and $Q=(nu,A)$, with one frontier-subset transition and explicit extension and realization boundaries.

= Conclusion

Dependency-Oriented Computation begins with a shift:

#quote(block: true)[
#strong[Do not begin by asking what executes next. Begin by asking what depends on what.]
]

The compact finite representation is

$ G=(S,Delta), #h(2em) Q=(nu,A). $

A program is a family of typed logical states and partial local definitions. A stable valuation agrees with current sources and every required definition. A source change adds induced users to the current repair obligations. One transition selects any subset of the dependency-minimal active frontier, evaluates it from a common settled pre-state, and publishes complete candidates together. Candidates not proven equal propagate; a sound equality proof stops the wave.

The nucleus stays small without hiding implementation reality. Retained values provide semantic reuse; the ready frontier exposes parallel work; versioned recurrence provides temporal unboundedness; immutable graph versions permit dynamic structure without mutating active work; and logical identities permit different memory and resource placements. Publication, reclamation, transport, authority, reconstruction, and effects remain explicit realization obligations rather than hidden primitives.

DOC does not promise universal speedup or erase distributed-systems policy. It gives evaluation, reactive repair, temporal reuse, parallel readiness, versioned recurrence, immutable topology evolution, and bounded elastic reconstruction one shared structural account while keeping its four durable boundaries named and testable.

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

= Appendix B. Terminology

#set text(size: 8.65pt)
#set table(inset: 2.8pt)
#table(
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
)

#set text(size: 10.2pt)
#set table(inset: 5.5pt)

#heading(level: 1, numbering: none, outlined: true)[Declarations]

#strong[Funding.] This research received no specific grant from any funding agency in the public, commercial, or not-for-profit sectors.

#strong[Competing interests.] The author declares no competing interests.

#strong[Code and data availability.] The complete source code, runtime implementation, tests, benchmark data, and verification materials are provided as supplementary material with this submission.

#strong[Generative-AI disclosure.] During the preparation of this work, the author used OpenAI ChatGPT to assist with language refinement, manuscript critique, implementation review, test design, and supporting development tasks. The author reviewed and edited all generated material, independently checked the formal claims, references, implementation, and reported results, and takes full responsibility for the content of the article.

#heading(level: 1, numbering: none, outlined: true)[Bibliography]

#set par(leading: 0.69em, spacing: 0.54em)
#text(size: 9.18pt)[
1. Gilles Kahn. “The Semantics of a Simple Language for Parallel Programming.” In J. L. Rosenfeld (ed.), *Information Processing 74: Proceedings of IFIP Congress 74*. North-Holland, 1974, pp. 471-475. DBLP: conf/ifip/Kahn74.

2. Donald E. Knuth. “Semantics of Context-Free Languages.” *Mathematical Systems Theory*, 2(2), 1968, pp. 127-145. DOI: 10.1007/BF01692511.

3. Donald E. Knuth. “Semantics of Context-Free Languages: Correction.” *Mathematical Systems Theory*, 5, 1971, pp. 95-96. DOI: 10.1007/BF01702865.

4. Alan J. Demers, Thomas W. Reps, and Tim Teitelbaum. “Incremental Evaluation for Attribute Grammars with Application to Syntax-Directed Editors.” *Proceedings of POPL 1981*, pp. 105-116. DOI: 10.1145/567532.567544.

5. Daniel M. Yellin and Robert E. Strom. “INC: A Language for Incremental Computations.” *ACM Transactions on Programming Languages and Systems*, 13(2), 1991, pp. 211-236. DOI: 10.1145/103135.103137.

6. Umut A. Acar. *Self-Adjusting Computation*. PhD thesis, Carnegie Mellon University, 2005. Technical report CMU-CS-05-129.

7. Matthew A. Hammer, Khoo Yit Phang, Michael Hicks, and Jeffrey S. Foster. “Adapton: Composable, Demand-Driven Incremental Computation.” *Proceedings of PLDI 2014*, pp. 156-166. DOI: 10.1145/2666356.2594324.

8. Yufei Cai, Paolo G. Giarrusso, Tillmann Rendel, and Klaus Ostermann. “A Theory of Changes for Higher-Order Languages: Incrementalizing Lambda-Calculi by Static Differentiation.” *Proceedings of PLDI 2014*, pp. 145-155. DOI: 10.1145/2594291.2594304.

9. Daniel Anderson, Guy E. Blelloch, Anubhav Baweja, and Umut A. Acar. “Efficient Parallel Self-Adjusting Computation.” *Proceedings of SPAA 2021*, pp. 59-70. DOI: 10.1145/3409964.3461799.

10. Jose A. Blakeley, Per-Åke Larson, and Frank Wm. Tompa. “Efficiently Updating Materialized Views.” *Proceedings of SIGMOD 1986*, pp. 61-71. DOI: 10.1145/16894.16861.

11. Andrey Mokhov, Neil Mitchell, and Simon Peyton Jones. “Build Systems à la Carte.” *Proceedings of the ACM on Programming Languages*, 2(ICFP), Article 79, 2018, pp. 1-29. DOI: 10.1145/3236774.

12. Sean Hadar and Shachar Itzhaky. “Scalable Spreadsheet-Driven End-User Applications with Incremental Computation.” *Proceedings of Onward! 2023*, pp. 1-14. DOI: 10.1145/3622758.3622887.

13. Frank McSherry, Derek G. Murray, Rebecca Isaacs, and Michael Isard. “Differential Dataflow.” *Proceedings of the 6th Biennial Conference on Innovative Data Systems Research (CIDR 2013)*, 2013. CIDR paper 111.

14. Derek G. Murray, Frank McSherry, Rebecca Isaacs, Michael Isard, Paul Barham, and Martín Abadi. “Naiad: A Timely Dataflow System.” *Proceedings of SOSP 2013*, pp. 439-455. DOI: 10.1145/2517349.2522738.

15. Matthew A. Hammer and Umut A. Acar. “Memory Management for Self-Adjusting Computation.” *Proceedings of ISMM 2008*, pp. 51-60. DOI: 10.1145/1375634.1375642.

16. Marvin L. Minsky. *Computation: Finite and Infinite Machines*. Prentice-Hall, Englewood Cliffs, NJ, 1967. OCLC 523923.
]
