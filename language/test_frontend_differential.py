"""Deterministic bounded differential and mutation checks for the DOC syntax adapter.

The reference emitter is intentionally independent of the frontend parser. These
checks validate lowering only; they do not execute the Rust kernel.
"""
import importlib.util
import itertools
import pathlib
import unittest

spec = importlib.util.spec_from_file_location(
    'indent_frontend', pathlib.Path(__file__).with_name('indent_frontend.py'))
frontend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frontend)


class LoweringDifferentialTests(unittest.TestCase):
    def test_generated_graphs_and_independent_emitter(self):
        # Three topologically ordered nodes, two types, and all legal premise
        # subsets. Every generated expression is a formal or a typed literal.
        checked = 0
        for types in itertools.product(('int', 'bool'), repeat=3):
            for first in (0, 1, -1):
                for p1 in ((), ('a',)):
                    for p2 in ((), ('a',), ('b',), ('a', 'b')):
                        src = [f'source a: {types[0]} = ' +
                               (str(first) if types[0] == 'int' else 'true')]
                        legacy = [src[0]]
                        for name, ps, kind in (('b', p1, types[1]),
                                               ('c', p2, types[2])):
                            expr = ps[0] if ps else ('0' if kind == 'int' else 'false')
                            src.extend((f'derive {name}({", ".join(ps)}): {kind}:',
                                        f'    {expr}'))
                            legacy.append(f'derive {name}: {kind} ({",".join(ps)}) = {expr}')
                        self.assertEqual(frontend.lower('\n'.join(src) + '\n'),
                                         '\n'.join(legacy) + '\n')
                        checked += 1
        self.assertEqual(checked, 192)

    def test_integer_boundary_neighbors_both_positions(self):
        values = [-(2**63)-1, -(2**63), -(2**63)+1,
                  -1, 0, 1, 2**63-2, 2**63-1, 2**63]
        for value in values:
            valid = -(2**63) <= value <= 2**63-1
            for program in (f'source a: int = {value}\n',
                            f'derive a(): int:\n    {value}\n'):
                with self.subTest(value=value, program=program[:12]):
                    if valid:
                        self.assertIn(str(value), frontend.lower(program))
                    else:
                        with self.assertRaisesRegex(frontend.SyntaxErrorDOC,
                                                    'signed 64-bit range'):
                            frontend.lower(program)

    def test_mutations_reject_forward_refs_duplicates_and_indentation(self):
        programs = (
            'derive b(a): int:\n    a\nsource a: int = 1\n',
            'source a: int = 1\nsource a: int = 2\n',
            'source a: int = 1\nderive b(a,a): int:\n    a\n',
            'source a: int = 1\nderive b(a): int:\n  a\n',
            'source a: int = 1\nderive b(a): int:\n\ta\n',
            'source a: int = 1\nderive b(a): int:\n    a\n    a\n',
        )
        for program in programs:
            with self.subTest(program=program):
                with self.assertRaises(frontend.SyntaxErrorDOC):
                    frontend.lower(program)


if __name__ == '__main__':
    unittest.main()
