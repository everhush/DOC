#set page(paper: "a4", margin: (x: 26mm, y: 25mm))
#set text(font: "Libertinus Serif", size: 10.5pt)
#set par(justify: true)
#set heading(numbering: "1.")

#align(center)[
  #text(size: 17pt, weight: "bold")[A Finite Calculus of Dependency-Oriented Repair]
  #v(5pt)
  #text(size: 11pt)[Typed expressions, frontier-subset reduction, and observational refinement]
  #v(6pt)
  Rituraj Basak \
  Kolkata, India
]
#v(10pt)

*Status.* This is a standalone research draft defining a minimal source language and an
executable restriction of the finite DOC kernel. It is not a revision of the submitted
Dependency-Oriented Computation paper. A separate finite-family elaboration is included below; recurrence, general graph-version replacement,
placement, storage, and effects retain their separate conditional status.

= Abstract

Dependency-Oriented Computation (DOC) defines a persistent finite acyclic family
of typed logical states and deterministic local definitions. This note gives the
kernel an explicit, first-order, pure expression language and a small-step
frontier-subset operational calculus. A program is independent of its evaluation
order and physical placement. State changes enter through atomic source batches;
changed conclusions propagate through dependency edges, while sound equality
cutoffs can suppress downstream work. The calculus intentionally expresses
neither user-visible memory management nor actors, API calls, network effects,
or database operations. We give arguments for expression type safety, preservation of repair admissibility,
finite termination, unique stable observation, and sound expansion under the existing DOC assumptions. A conditional elaboration of input-dependent finite families leaves the finite repair rules unchanged. Executable reference and independent native checks are not mechanized proofs.

= Scope and relationship to DOC

The normative model remains the finite kernel of Dependency-Oriented
Computation. The new language supplies concrete, inspectable definitions
to replace opaque pure host callbacks. It is an *instance* of the general
model, not an alternative mathematical definition of the model.

The present calculus is not universal by itself: it has a finite graph,
a finite number of expression nodes, and no recursion, unbounded iteration,
or effectful instructions. Versioned recurrence and finite-prefix
universality, as discussed in the original model, must be incorporated as
a separately defined extension before making any universality claim.

= Typed expression fragment

The illustrative ground domains are signed integers and booleans.
The language admits constants, premise variables, addition, subtraction,
multiplication, equality, and a conditional. In the abstract calculus,
integer operators are interpreted over their declared *total* domains
(for example mathematical integers, or an explicit result-valued bounded
domain). A machine interpreter using checked 64-bit integers reports
overflow as a failed evaluation; that failure is not covered by
the total-transformation theorem.

For a premise type context Gamma, the typing judgment Gamma |- e : T
uses the following syntax-directed rules. A premise variable has the type assigned by Gamma.
Arithmetic requires two integer expressions and returns an integer.
Equality requires matching argument domains and returns a boolean.
A conditional requires a boolean guard and equally typed branches;
only the selected branch is evaluated. Every permitted expression is
pure, deterministic, and total under its declared semantic domain.

*Expression type safety.* Under a well-typed premise environment, evaluation of a well-typed expression terminates with a value in its declared domain, provided each primitive is total and closed over its declared domain. Proof by structural induction: constants and variables have their assigned types; the inductive hypotheses give typed operands for each arithmetic or equality primitive, whose interpretation returns a typed result. For a conditional the guard evaluates to a boolean and the selected branch terminates with the common branch type by induction. The finite expression tree has no recursive calls. A checked machine overflow is an exceptional implementation outcome unless an explicit result-valued primitive and type are modeled; it is not a counterexample to the total-domain statement.

The surface implementation uses named source declarations and derived
definitions with an explicit ordered list of premises. The order of
declarations in its text format is topological. That parser restriction
is not part of the general graph calculus: the abstract graph may be
declared in any order provided it is finite and acyclic.

= Programs, states, and configurations

Let S be a finite family of stable state identifiers. Each state s has
a declared value domain V_s. A partial definition map Delta assigns
each derived state d an ordered premise sequence P_d and a pure
well-typed expression e_d. The sources are S minus dom(Delta).
Each derived state has exactly one logical producer.

A graph is well formed if all premises exist, every expression's
declared type agrees with its conclusion domain, and the induced
dependency relation is acyclic. A valuation nu maps each state either
to a value of its domain or to an absent-materialization marker.
Absence is not an application-level null value. A transient active
set A contains derived states whose conclusions may require repair.

A configuration Q = (nu, A) is *repair-admissible* when all sources
have values and every inactive derived state is materialized and
satisfies its definition in the current valuation.

= Source-batch transition

A batch U assigns typed new values to a finite subset of source states.
Batch validity is checked before logical mutation, including the
single-assignment requirement within a batch. Let same_s(x,y)
be a cutoff predicate for state s satisfying the one-way law:

#align(center)[
  #box(inset: 6pt, stroke: .5pt + gray)[
    same_s(x,y) = true implies x = y.
  ]
]

The changed-source set X consists of assignments not proven equal.
The entire set X is installed at one source boundary. The next active
set is the prior active set union the direct derived users of X.
An always-false cutoff is valid; it may perform additional work.
A hash collision or approximate comparison cannot prove equality
unless equality soundness is established for the stated value domain.

= Frontier-subset reduction

For derived states e and d, write e precedes d when e is a transitive
strict premise of d. The ready frontier R(A) consists exactly of
active states with no active strict derived predecessor. Choose any
nonempty finite subset F of R(A). Because the graph is acyclic,
a nonempty active set has a nonempty ready frontier.

Each d in F evaluates its expression from the same settled
pre-transition valuation nu, producing private candidate v_d.
No selected state reads a candidate from a peer selected in the
same step. Let C_F consist of those d whose previous value is absent,
or whose candidate is not proven equal by the sound cutoff.

The logical transition publishes all candidates in C_F as one
atomic frontier publication, removes F from A, and activates
the direct users of every state in C_F. Candidates proven equal are
removed from the active set without downstream activation.
If an evaluation is partial or fails before the barrier, the
implementation must publish none of that step's candidates;
the total finite-kernel theorem does not apply to the failing
local transformation.

= Fundamental metatheory

*Lemma 1: Frontier materialization.* Every ready derived state in a
repair-admissible configuration has materialized premises.
Reason: an unmaterialized derived premise must be active under
repair admissibility; every ready state has no active ancestor.

*Lemma 2: Preservation.* A legal frontier-subset transition preserves
repair admissibility. Selected definitions become satisfied because their premises are unchanged within the frontier and equal candidates retain equal values. An unselected inactive definition can lose satisfaction only if a direct premise changes; all such users are activated. Other inactive definitions retain their satisfaction. The analogous source-boundary argument uses validation and activation of direct users of the changed-source set.

*Lemma 3: At most once per episode.* Within a fixed graph version
and a repair episode between source boundaries, each derived state
is selected at most once. When a state is selected, no active derived strict predecessor remains. If a strict predecessor were first activated later, the publishing premise responsible for that activation would itself be a strict predecessor active immediately before the transition, contradicting the absence of any active predecessor up to that point. Sources are fixed within the episode. Consequently no later publication can reactivate the selected state.

*Theorem 1: Finite stabilization.* For a finite acyclic well-formed
program, a repair-admissible seed, and total local definitions,
every maximal legal sequence of frontier-subset transitions
terminates at an empty active set. By Lemma 3 each step selects
at least one previously unselected state, so there are no more
than |dom(Delta)| selected definitions in an episode.

*Theorem 2: Stable uniqueness and schedule independence.*
For each fixed source environment, acyclicity and determinism
define a unique valuation by topological evaluation. By
repair admissibility, a quiescent configuration satisfies
every derived definition. Therefore every legal maximal
schedule terminates at that unique valuation and agrees
with complete topological reevaluation.

*Corollary: Dependency locality.* After a source batch applied at a stable boundary, definitions
outside the forward dependency cone of changed source facts
cannot be newly activated through this transition rule.
Sound cutoff can reduce the activated subset further.

*Corollary: Conservative cutoff correctness.* Always returning
false from the cutoff does not affect the unique stable
valuation, but may increase evaluations.

These statements are subject to the finite DOC assumptions.
The proof sketches are explanatory, not machine-checked proof objects.

= Computational expansion and granularity

One definition may be replaced by a finite acyclic subgraph with
fresh internal identities, the same boundary premises, and the same
boundary result for every legal typed input. Such a replacement is
a boundary-observational refinement. Expansion makes additional
independent work visible, but does not require each instruction
to be scheduled separately. Fusion or batching may be necessary
for performance; expansion without a cost model is not guaranteed
to improve runtime.

= Conditional finite-family elaboration

A runtime-sized family is a small example of dynamic dependency computation: an input determines how many independent definitions are needed. This is not an unrestricted graph-rewriting rule.

Fix a settled input snapshot containing a natural number n, a collection of n typed elements, and any other fixed typed premises. For an admitted n, a family constructor has the abstract form `family(n, items, f)`, where f is a pure total expression template from the element and fixed premises to T. Extend the boundary value domain with finite ordered sequences of T; this is an explicitly separate extension of the ground domains, not a primitive in the original int/bool calculus. The admission judgment requires a finite n, agreement with the collection length, and the ordinary expression typing judgment for f under a context containing the element and fixed premises.

The elaboration creates fresh distinct internal identities (family identity, index) for indices 0 through n minus 1, each with its own element and fixed premises. A fresh collection constructor reads all n results in index order and publishes to the declared boundary. For n = 0 it publishes the empty collection. Element and shape facts are obtained from the settled snapshot; no candidate reads its own unsettled output. The candidate graph is acyclic, since edges run from input facts to member results to the collection. If admission fails, no candidate is installed. No bound on physical resources follows from this abstract finiteness.

*Conditional elaboration agreement.* Given an admitted snapshot, evaluating the elaboration from scratch yields the same ordered sequence as pointwise application of f. Each member has a typed result by expression type safety, and the collector returns the ordered sequence of precisely those results. Theorem 1 and Theorem 2 therefore establish finite stabilization and schedule independence for this fixed elaboration. This is a boundary-observational refinement for the given snapshot, not a claim that the internal identities persist across lengths or that every member is individually cached.

When the input changes, a new elaboration may be constructed privately. Reusing materializations between elaborations requires the separate graph-version compatibility contract of the computation-model paper; otherwise initialize the candidate from scratch. Atomic successful publication and rejection of obsolete generations are required realization boundaries. The theorem does not cover a generator that fails to terminate, an evolving graph during a repair episode, or unbounded recursive family creation.

= Extensions outside the finite kernel

Versioned recurrence requires epoch indexes, finite demand prefixes,
carry authority, and retention rules. Immutable graph replacement
requires private validation and compatibility of retained values
before atomic commit. Physical reclamation, pinning, and reconstruction
are realization obligations, not rewriting rules of the finite calculus.
Placement, resource-fabric admission, actor supervision, and transport
must not be inferred from the ready-frontier law. Nondeterministic
external effects occur at explicit boundaries whose recorded outcomes
may subsequently become source facts.

Bounded realizations of several of these contracts exist, but their implementation tests do not extend the finite calculus theorem. Each additional formal extension requires its own semantics and validation. No
shared-memory cluster, exactly-once external side effects,
consensus, partition tolerance, or production failover is
established by this paper.

= Executable interpretation and evidence boundary

The accompanying Rust crate implements a closed int/bool fragment,
parses pure definitions, checks graph types and acyclicity, performs
atomic source updates, and evaluates legal frontier subsets.
Independent definition evaluations may use multiple local threads.
The separate topological evaluator acts as an executable oracle.

The supplied tests are finite examples and differential checks,
not exhaustive verification of arbitrary programs. Checked i64
overflow is an explicit runtime error, not a theorem-preserving
ordinary value. The original manuscript's C++20 benchmark results
remain evidence for that distinct C++ witness and hardware campaign;
they are not evidence about the Rust reference or the later independent native realization. The accepted native evidence includes typed recurrence and bounded independent-family evaluation, graph replacement and failure isolation; these are executable checks of supported profiles, not a proof of this elaboration for every typed input. The main paper and its DOC-only reproducibility supplement record the exact revisions and measurements.

= Open obligations

The finite proofs and conditional elaboration are mathematical arguments rather than proof-assistant objects. Mechanization, arbitrary typed graph-generating recursion, general graph-version transition syntax, and richer type domains require separate formal work. Resource admission and failure paths must remain explicit, and executable conformance tests are bounded. Performance and broader application evidence belong in the computation-model paper rather than being repeated here.

= Conclusion

A typed pure calculus provides a concrete entry point for programming
the finite dependency-oriented repair relation without redefining DOC
as an actor platform, database, cloud API, or deployment system.
The formal model remains independent of runtime memory layout and
physical worker topology. The finite family elaboration illustrates how input-dependent work can refine the unchanged kernel under explicit assumptions. General completeness and production readiness are outside this calculus; unrestricted graph generation and recurrence remain separate extensions.

= Reference

Basak, R. Dependency-Oriented Computation: Persistent-Graph Semantics
for Incremental Repair. Research manuscript, revised preprint source. The present calculus draft follows the assumptions and scope boundaries of the finite DOC model; the earlier submitted version remains identifiable separately.
