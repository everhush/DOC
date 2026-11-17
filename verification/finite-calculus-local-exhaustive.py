#!/usr/bin/env python3
"""Independent finite DOC bool-domain exhaustive semantics verifier.

Validates the finite calculus, NOT compiled Rust or physical realization.
"""
from itertools import product, combinations

FUNCS = (lambda xs: sum(xs) % 2, lambda xs: int(all(xs)))

def subsets(xs):
    for n in range(1, len(xs) + 1):
        yield from combinations(xs, n)

def families():
    for a, b, c in product(range(2), range(4), range(8)):
        pre = tuple(tuple(j for j in range(i) if mask & (1 << j))
                    for i, mask in zip((1, 2, 3), (a, b, c)))
        for choices in product((0, 1), repeat=3):
            yield pre, choices

def users(pre):
    u = [set() for _ in range(4)]
    for d, ps in enumerate(pre, 1):
        for p in ps:
            u[p].add(d)
    return tuple(tuple(sorted(s)) for s in u)

def ready_reference(pre, active):
    out = []
    for d in sorted(active):
        visited, stack, blocked = set(), list(pre[d - 1]), False
        while stack:
            p = stack.pop()
            if p in visited:
                continue
            visited.add(p)
            if p in active:
                blocked = True
                break
            if p:
                stack.extend(pre[p - 1])
        if not blocked:
            out.append(d)
    return tuple(out)

def ready_linear(pre, active):
    ancestor = [False] * 4
    out = []
    for d in range(1, 4):
        blocked = any(ancestor[p] or p in active for p in pre[d - 1])
        ancestor[d] = blocked
        if d in active and not blocked:
            out.append(d)
    return tuple(out)

def satisfied(pre, fs, vals, d):
    if vals[d] is None:
        return False
    xs = [vals[p] for p in pre[d - 1]]
    return None not in xs and FUNCS[fs[d - 1]](xs) == vals[d]

def admissible(pre, fs, vals, active):
    return vals[0] is not None and all(
        d in active or satisfied(pre, fs, vals, d) for d in range(1, 4)
    )

def oracle(pre, fs, vals):
    out = list(vals)
    for d in range(1, 4):
        out[d] = FUNCS[fs[d - 1]]([out[p] for p in pre[d - 1]])
    return tuple(out)

def step(pre, fs, u, cfg, selected, conservative):
    vals, active, done = cfg
    assert selected and set(selected).issubset(ready_reference(pre, active))
    assert not set(selected).intersection(done)
    candidates = {
        d: FUNCS[fs[d - 1]]([vals[p] for p in pre[d - 1]])
        for d in selected
    }
    new_vals, new_active = list(vals), set(active) - set(selected)
    for d, candidate in candidates.items():
        if conservative or vals[d] is None or vals[d] != candidate:
            new_vals[d] = candidate
            new_active.update(u[d])
    result = (tuple(new_vals), frozenset(new_active), done | frozenset(selected))
    assert admissible(pre, fs, result[0], result[1])
    return result

def verify(pre, fs, u, seed, conservative):
    pending, seen, finals = [seed], set(), set()
    maximum = 0
    while pending:
        cfg = pending.pop()
        if cfg in seen:
            continue
        seen.add(cfg)
        vals, active, done = cfg
        assert admissible(pre, fs, vals, active)
        maximum = max(maximum, len(done))
        assert len(done) <= 3
        if not active:
            finals.add(vals)
            continue
        ready = ready_reference(pre, active)
        assert ready == ready_linear(pre, active)
        assert ready
        for selected in subsets(ready):
            pending.append(step(pre, fs, u, cfg, selected, conservative))
    assert finals == {oracle(pre, fs, seed[0])}
    return len(seen), maximum

def main():
    graphs = seeds = checks = explored = updates = max_selection = 0
    for pre, fs in families():
        graphs += 1
        u = users(pre)
        cache = {}
        def check(seed, conservative):
            nonlocal checks, explored, max_selection
            key = (seed, conservative)
            if key not in cache:
                size, depth = verify(pre, fs, u, seed, conservative)
                cache[key] = (size, depth)
                checks += 1
                explored += size
                max_selection = max(max_selection, depth)

        for vals_tail in product((0, 1, None), repeat=3):
            for source in (0, 1):
                vals = (source,) + vals_tail
                for mask in range(8):
                    active = frozenset(
                        d for d in range(1, 4) if mask & (1 << (d - 1))
                    )
                    if not admissible(pre, fs, vals, active):
                        continue
                    seeds += 1
                    seed = (vals, active, frozenset())
                    for conservative in (False, True):
                        check(seed, conservative)
                        for new_source in (0, 1):
                            changed = conservative or vals[0] != new_source
                            new_vals = (new_source,) + vals[1:] if changed else vals
                            next_active = (active | frozenset(u[0])) if changed else active
                            next_seed = (new_vals, next_active, frozenset())
                            assert admissible(pre, fs, next_seed[0], next_seed[1])
                            check(next_seed, conservative)
                            updates += 1

    print(f"PASS: {graphs} graphs, {seeds} admissible seeds, "
          f"{updates} source updates, {checks} schedule/profile explorations, "
          f"{explored} explored configurations, max {max_selection} selections")

if __name__ == "__main__":
    main()
