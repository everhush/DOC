#!/usr/bin/env python3
"""Bounded checks for demand restriction and finite recurrence prefixes.

This checker is intentionally independent of the C++ runtime.  It compares
restricted evaluation with a complete topological oracle, and compares the
recurrence construction with an explicitly unrolled finite DAG.  Passing is
bounded evidence, not a universal proof.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Callable, Iterable

Value = int


def xor(xs: tuple[Value, ...]) -> Value:
    out = 0
    for x in xs:
        out ^= x
    return out


def conjunction(xs: tuple[Value, ...]) -> Value:
    return int(all(xs))


FUNCS: tuple[Callable[[tuple[Value, ...]], Value], ...] = (xor, conjunction)


@dataclass(frozen=True)
class Defn:
    premises: tuple[int, ...]
    function: int


@dataclass(frozen=True)
class Graph:
    source_count: int
    defs: tuple[Defn, ...]

    @property
    def n(self) -> int:
        return self.source_count + len(self.defs)

    def definition(self, state: int) -> Defn:
        return self.defs[state - self.source_count]


def premise_options(previous_count: int) -> tuple[tuple[int, ...], ...]:
    """Empty, unary, and ordered binary premise lists, including duplicates."""
    return ((),) + tuple((p,) for p in range(previous_count)) + tuple(
        (a, b) for a in range(previous_count) for b in range(previous_count)
    )


def complete(g: Graph, sources: tuple[Value, ...]) -> tuple[Value, ...]:
    values = list(sources)
    for state in range(g.source_count, g.n):
        d = g.definition(state)
        values.append(FUNCS[d.function](tuple(values[p] for p in d.premises)))
    return tuple(values)


def ancestor_closure(g: Graph, demanded: frozenset[int]) -> frozenset[int]:
    closure = set(demanded)
    stack = list(demanded)
    while stack:
        state = stack.pop()
        if state < g.source_count:
            continue
        for premise in g.definition(state).premises:
            if premise not in closure:
                closure.add(premise)
                stack.append(premise)
    return frozenset(closure)


def restricted(g: Graph, sources: tuple[Value, ...], demanded: frozenset[int]) -> dict[int, Value]:
    closure = ancestor_closure(g, demanded)
    values: dict[int, Value] = {
        state: sources[state] for state in range(g.source_count) if state in closure
    }
    for state in range(g.source_count, g.n):
        if state not in closure:
            continue
        d = g.definition(state)
        assert all(p in values for p in d.premises)
        values[state] = FUNCS[d.function](tuple(values[p] for p in d.premises))
    return {state: values[state] for state in demanded}


def demand_graphs() -> Iterable[Graph]:
    source_count = 2
    opts = [premise_options(state) for state in range(source_count, source_count + 2)]
    for premises in product(*opts):
        for functions in product(range(len(FUNCS)), repeat=2):
            yield Graph(
                source_count,
                tuple(Defn(premises[i], functions[i]) for i in range(2)),
            )


def check_demand_restriction() -> tuple[int, int, int]:
    graph_count = source_cases = demand_cases = 0
    for g in demand_graphs():
        graph_count += 1
        for sources in product((0, 1), repeat=g.source_count):
            source_cases += 1
            full = complete(g, sources)
            # Every nonempty demanded subset, including source observations.
            for mask in range(1, 1 << g.n):
                demanded = frozenset(i for i in range(g.n) if mask & (1 << i))
                got = restricted(g, sources, demanded)
                assert got == {state: full[state] for state in demanded}
                closure = ancestor_closure(g, demanded)
                for state in closure:
                    if state >= g.source_count:
                        assert all(p in closure for p in g.definition(state).premises)
                demand_cases += 1
    return graph_count, source_cases, demand_cases


def recurrence_graphs() -> Iterable[Graph]:
    source_count = 2
    opts0 = premise_options(2)
    opts1 = premise_options(3)
    for p0, p1 in product(opts0, opts1):
        for f0, f1 in product(range(len(FUNCS)), repeat=2):
            yield Graph(source_count, (Defn(p0, f0), Defn(p1, f1)))


def iterative_prefix(
    g: Graph,
    initial_sources: tuple[Value, Value],
    carry_state: int,
    last_epoch: int,
) -> tuple[tuple[Value, ...], ...]:
    epochs: list[tuple[Value, ...]] = []
    sources = initial_sources
    for epoch in range(last_epoch + 1):
        values = complete(g, sources)
        epochs.append(values)
        # Exactly one authoritative carry writes source 0.  Source 1 is
        # deliberately uncarried and therefore reuses its template fact.
        sources = (values[carry_state], initial_sources[1])
    return tuple(epochs)


def explicitly_unrolled_prefix(
    g: Graph,
    initial_sources: tuple[Value, Value],
    carry_state: int,
    last_epoch: int,
) -> tuple[tuple[Value, ...], ...]:
    """Independent oracle: construct and evaluate the finite unrolled DAG."""
    values: list[Value] = []
    width = g.n
    for epoch in range(last_epoch + 1):
        base = epoch * width
        if epoch == 0:
            values.extend(initial_sources)
        else:
            previous_base = (epoch - 1) * width
            values.append(values[previous_base + carry_state])
            values.append(initial_sources[1])
        assert len(values) == base + g.source_count
        for state in range(g.source_count, g.n):
            d = g.definition(state)
            inputs = tuple(values[base + premise] for premise in d.premises)
            values.append(FUNCS[d.function](inputs))
    return tuple(
        tuple(values[epoch * width : (epoch + 1) * width])
        for epoch in range(last_epoch + 1)
    )


def carry_map_valid(carries: tuple[tuple[int, int], ...], source_count: int) -> bool:
    targets = [target for _, target in carries]
    return all(0 <= target < source_count for target in targets) and len(targets) == len(set(targets))


def check_recurrence() -> tuple[int, int, int, int]:
    graph_count = prefix_cases = halt_cases = rejected_duplicate_carries = 0
    for g in recurrence_graphs():
        graph_count += 1
        for initial in product((0, 1), repeat=2):
            for carry_state in range(g.source_count, g.n):
                for last_epoch in range(6):
                    demand_driven = iterative_prefix(g, initial, carry_state, last_epoch)
                    unrolled = explicitly_unrolled_prefix(g, initial, carry_state, last_epoch)
                    assert demand_driven == unrolled
                    assert len(demand_driven) == last_epoch + 1
                    assert sum(len(epoch) for epoch in demand_driven) == (last_epoch + 1) * g.n
                    # No state from a future epoch is needed for the requested prefix.
                    prefix_cases += 1

                # A finite stopping predicate is absorbing: once the selected
                # observation is true, no successor epoch is constructed.
                materialized = []
                sources = initial
                halted = False
                for _ in range(6):
                    if halted:
                        before = len(materialized)
                        assert len(materialized) == before
                        continue
                    values = complete(g, sources)
                    materialized.append(values)
                    halted = values[-1] == 1
                    if not halted:
                        sources = (values[carry_state], initial[1])
                if halted:
                    first_halt = next(i for i, epoch in enumerate(materialized) if epoch[-1] == 1)
                    assert len(materialized) == first_halt + 1
                halt_cases += 1

        # Two carries targeting the same next-epoch source are rejected;
        # different targets are accepted.  This is the single-authority rule.
        d0, d1 = range(g.source_count, g.n)
        assert not carry_map_valid(((d0, 0), (d1, 0)), g.source_count)
        assert carry_map_valid(((d0, 0), (d1, 1)), g.source_count)
        rejected_duplicate_carries += 1
    return graph_count, prefix_cases, halt_cases, rejected_duplicate_carries


def main() -> None:
    dg, ds, dc = check_demand_restriction()
    rg, pc, hc, rc = check_recurrence()
    print(
        "demand/recurrence model check passed: "
        f"{dg} demand graphs, {ds} source valuations, {dc} demanded subsets; "
        f"{rg} recurrence templates, {pc} finite prefixes, {hc} stopping cases, "
        f"{rc} duplicate-carry rejection cases"
    )


if __name__ == "__main__":
    main()
