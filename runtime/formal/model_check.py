#!/usr/bin/env python3
"""Bounded exhaustive checker for the finite DOC active-set rule.

This is deliberately not presented as a proof assistant development. It checks
all 2-source/3-derived acyclic shapes, two Boolean local functions per derived
state, all initial source valuations, all later source valuations, and every
legal nonempty subset of each ready frontier.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, product
from typing import Callable, Iterable

Value = int
Function = Callable[[tuple[Value, ...]], Value]


def xor(values: tuple[Value, ...]) -> Value:
    result = 0
    for value in values:
        result ^= value
    return result


def conjunction(values: tuple[Value, ...]) -> Value:
    return int(all(values))


FUNCTIONS: tuple[Function, ...] = (xor, conjunction)


@dataclass(frozen=True)
class Definition:
    premises: tuple[int, ...]
    function_index: int


@dataclass(frozen=True)
class Graph:
    source_count: int
    definitions: tuple[Definition, ...]

    @property
    def state_count(self) -> int:
        return self.source_count + len(self.definitions)

    def definition(self, state: int) -> Definition:
        return self.definitions[state - self.source_count]

    def users(self) -> tuple[tuple[int, ...], ...]:
        output: list[list[int]] = [[] for _ in range(self.state_count)]
        for state in range(self.source_count, self.state_count):
            for premise in self.definition(state).premises:
                output[premise].append(state)
        return tuple(tuple(users) for users in output)


@dataclass(frozen=True)
class Config:
    values: tuple[Value | None, ...]
    active: frozenset[int]
    evaluated: frozenset[int]


def nonempty_subsets(items: tuple[int, ...]) -> Iterable[tuple[int, ...]]:
    for size in range(1, len(items) + 1):
        yield from combinations(items, size)


def frontier(graph: Graph, active: frozenset[int]) -> tuple[int, ...]:
    blocked = [False] * graph.state_count
    result: list[int] = []
    for state in range(graph.source_count, graph.state_count):
        definition = graph.definition(state)
        blocked[state] = any(
            premise >= graph.source_count and (premise in active or blocked[premise])
            for premise in definition.premises
        )
        if state in active and not blocked[state]:
            result.append(state)
    return tuple(result)


def transition(graph: Graph, users: tuple[tuple[int, ...], ...], config: Config,
               selected: tuple[int, ...], conservative: bool) -> Config:
    current_frontier = frontier(graph, config.active)
    if not selected or any(state not in current_frontier for state in selected):
        raise AssertionError("illegal frontier subset")
    if any(state in config.evaluated for state in selected):
        raise AssertionError("a definition evaluated twice in one epoch")

    candidates: dict[int, Value] = {}
    for state in selected:
        definition = graph.definition(state)
        inputs = tuple(config.values[premise] for premise in definition.premises)
        if any(value is None for value in inputs):
            raise AssertionError("frontier contains unavailable premise")
        candidates[state] = FUNCTIONS[definition.function_index](inputs)  # type: ignore[arg-type]

    values = list(config.values)
    active = set(config.active)
    active.difference_update(selected)
    for state in selected:
        candidate = candidates[state]
        if conservative or values[state] != candidate:
            values[state] = candidate
            active.update(users[state])
    return Config(tuple(values), frozenset(active), config.evaluated.union(selected))


def all_stable_results(graph: Graph, start: Config,
                       conservative: bool) -> set[tuple[Value, ...]]:
    users = graph.users()
    stack = [start]
    visited: set[Config] = set()
    stable: set[tuple[Value, ...]] = set()
    while stack:
        config = stack.pop()
        if config in visited:
            continue
        visited.add(config)
        if not config.active:
            if any(value is None for value in config.values):
                raise AssertionError("stable configuration contains unavailable value")
            stable.add(tuple(int(value) for value in config.values))
            continue
        ready = frontier(graph, config.active)
        if not ready:
            raise AssertionError("active configuration has no ready frontier")
        for selected in nonempty_subsets(ready):
            stack.append(transition(graph, users, config, selected, conservative))
    return stable


def full_evaluate(graph: Graph, sources: tuple[Value, ...]) -> tuple[Value, ...]:
    values: list[Value] = list(sources)
    for state in range(graph.source_count, graph.state_count):
        definition = graph.definition(state)
        inputs = tuple(values[premise] for premise in definition.premises)
        values.append(FUNCTIONS[definition.function_index](inputs))
    return tuple(values)


def descendants(graph: Graph, changed_sources: set[int]) -> set[int]:
    users = graph.users()
    reached = set(changed_sources)
    queue = list(changed_sources)
    while queue:
        state = queue.pop()
        for user in users[state]:
            if user not in reached:
                reached.add(user)
                queue.append(user)
    return reached


def graph_shapes() -> Iterable[Graph]:
    source_count = 2
    premise_options: list[list[tuple[int, ...]]] = []
    for state in range(source_count, source_count + 3):
        previous = tuple(range(state))
        options: list[tuple[int, ...]] = []
        for size in range(1, len(previous) + 1):
            options.extend(combinations(previous, size))
        premise_options.append(options)

    for premises in product(*premise_options):
        for functions in product(range(len(FUNCTIONS)), repeat=3):
            yield Graph(
                source_count,
                tuple(Definition(tuple(premises[i]), functions[i]) for i in range(3)),
            )


def check() -> tuple[int, int]:
    graph_count = 0
    epoch_count = 0
    for graph in graph_shapes():
        graph_count += 1
        for initial_sources in product((0, 1), repeat=graph.source_count):
            initial = Config(
                tuple(initial_sources) + (None,) * len(graph.definitions),
                frozenset(range(graph.source_count, graph.state_count)),
                frozenset(),
            )
            oracle_initial = full_evaluate(graph, tuple(initial_sources))
            for conservative in (False, True):
                initial_results = all_stable_results(graph, initial, conservative)
                if initial_results != {oracle_initial}:
                    raise AssertionError(
                        "initial schedule independence or oracle agreement failed"
                    )

            for later_sources in product((0, 1), repeat=graph.source_count):
                epoch_count += 1
                changed = {
                    index for index, (old, new) in enumerate(zip(initial_sources, later_sources))
                    if old != new
                }
                values = list(oracle_initial)
                active: set[int] = set()
                users = graph.users()
                for source in changed:
                    values[source] = later_sources[source]
                    active.update(users[source])
                update = Config(tuple(values), frozenset(active), frozenset())
                oracle = full_evaluate(graph, tuple(later_sources))
                for conservative in (False, True):
                    results = all_stable_results(graph, update, conservative)
                    if results != {oracle}:
                        raise AssertionError(
                            "update schedule independence or oracle agreement failed"
                        )

                affected = descendants(graph, changed)
                for state in range(graph.state_count):
                    if state not in affected and oracle[state] != oracle_initial[state]:
                        raise AssertionError("locality failed outside the dependency descendants")
    return graph_count, epoch_count


if __name__ == "__main__":
    graphs, epochs = check()
    print(f"bounded model check passed: {graphs} graphs, {epochs} source epochs, all legal frontier subsets, exact and conservative cutoff profiles")
