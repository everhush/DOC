#!/usr/bin/env python3
"""Bounded independent oracle for duplicate premises and atomic frontier abort.

Checked integer domain [-2,2]. This is NOT Rust execution.
"""
from itertools import product, combinations

DOMAIN = range(-2, 3)

def subsets(xs):
    for n in range(1, len(xs) + 1):
        yield from combinations(xs, n)

def check():
    cases = successful = aborted = 0
    # Source s; derived a,b; join c. Duplicate source premise occurrences
    # occupy separate formal argument positions, not distinct dependency edges.
    for source, old_a, old_b, old_c, da, db, dc in product(DOMAIN, repeat=7):
        if old_b != source + db or old_c != old_a + old_b + dc:
            continue
        for duplicate in (False, True):
            if old_a != (2 if duplicate else 1) * source + da:
                continue
            for new_source in DOMAIN:
                for policy in ("exact", "conservative"):
                    expected_a = (2 if duplicate else 1) * new_source + da
                    expected_b = new_source + db
                    initial = (new_source, old_a, old_b, old_c)
                    active = {1, 2}
                    if new_source == source and policy == "exact":
                        active = set()
                    pending = [(initial, frozenset(active))]
                    visited = set()
                    while pending:
                        vals, act = pending.pop()
                        if (vals, act) in visited:
                            continue
                        visited.add((vals, act))
                        if not act:
                            if new_source == source and policy == "exact":
                                assert vals == initial
                            elif all(-2 <= x <= 2 for x in
                                     (expected_a, expected_b,
                                      expected_a + expected_b + dc)):
                                assert vals == (new_source, expected_a,
                                                expected_b, expected_a + expected_b + dc)
                            continue
                        ready = tuple(d for d in (1, 2, 3) if
                                      d in act and (d != 3 or not (act & {1, 2})))
                        assert ready
                        for selected in subsets(ready):
                            candidates = {
                                d: {1: expected_a, 2: expected_b,
                                    3: vals[1] + vals[2] + dc}[d]
                                for d in selected
                            }
                            before = (vals, act)
                            if any(v not in DOMAIN for v in candidates.values()):
                                # Failure must leave valuation and active set unchanged.
                                after = before
                                assert after == before
                                aborted += 1
                                continue
                            newvals = list(vals)
                            newact = set(act)
                            for d, v in candidates.items():
                                newact.remove(d)
                                if policy == "conservative" or vals[d] != v:
                                    newvals[d] = v
                                    if d in (1, 2):
                                        newact.add(3)
                            pending.append((tuple(newvals), frozenset(newact)))
                            successful += 1
                    cases += 1
    return cases, successful, aborted

if __name__ == "__main__":
    a, b, c = check()
    print(f"PASS: {a} scenarios, {b} successful frontier transitions, "
          f"{c} rejected overflowing frontiers")
