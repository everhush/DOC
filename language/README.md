# DOC indentation frontend (experimental)

This is a **small syntax adapter**, not a new computation model or a production compiler. It lowers one four-space-indented expression per derived declaration to the existing Rust DOC kernel syntax. The Rust kernel remains responsible for parsing expressions, type-checking, and executing the graph.

```text
source a: int = 2
source b: int = 3

derive sum(a, b): int:
    add(a, b)
```

Try the included example without a Rust toolchain:

```sh
python3 language/indent_frontend.py language/examples/repair.docpy --emit
python3 -m unittest discover -s language -p 'test_*.py' -v
```

With Cargo available, execute and update sources:

```sh
python3 language/indent_frontend.py language/examples/repair.docpy a=4 b=1
```

This frontend deliberately supports only top-level `source NAME: int|bool = LITERAL` and `derive NAME(PREMISES): int|bool:` followed by exactly one expression line indented with four spaces. Blank lines and `#` comments are allowed. Tabs, nested blocks, forward premise references, duplicate names/formals, and arbitrary Python statements are rejected. Expressions use the existing Rust kernel's pure prefix operations (`add`, `sub`, `mul`, `eq`, `if`) and formal premise variables. It is not Python and does not claim to parse arbitrary Python syntax.

The adapter is written in Python to permit standalone syntax validation when Cargo is unavailable; it should eventually be replaced by or integrated into a native Rust frontend after compilation and differential tests. The source format adds no effects, recurrence, graph-version transitions, or new DOC semantics. Overflow remains a failed kernel evaluation, not a total value. **The frontend unit tests have passed locally in Python; native Rust execution has not been tested in this environment.**
