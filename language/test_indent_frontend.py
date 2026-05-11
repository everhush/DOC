"""Regression tests for the bounded indentation-based DOC frontend."""
import importlib.util
import pathlib
import unittest

spec = importlib.util.spec_from_file_location('indent_frontend', pathlib.Path(__file__).with_name('indent_frontend.py'))
frontend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frontend)

class FrontendTests(unittest.TestCase):
    def test_repair_example(self):
        src = """# source declarations
source a: int = 2
source b: int = 3
source flag: bool = true

derive sum(a, b): int:
    add(a, b)
derive doubled(sum): int:
    mul(sum, 2)
derive chosen(flag, doubled): int:
    if(flag, doubled, 0)
"""
        expected = """source a: int = 2
source b: int = 3
source flag: bool = true
derive sum: int (a,b) = add(a, b)
derive doubled: int (sum) = mul(sum, 2)
derive chosen: int (flag,doubled) = if(flag, doubled, 0)
"""
        self.assertEqual(frontend.lower(src), expected)

    def test_empty_premises(self):
        self.assertEqual(frontend.lower('derive answer(): int:\n    42\n'), 'derive answer: int () = 42\n')

    def test_comments(self):
        self.assertEqual(frontend.lower('source a: int = -2 # initial\nderive b(a): int: # note\n    add(a,1) # body\n'), 'source a: int = -2\nderive b: int (a) = add(a,1)\n')

    def test_i64_source_boundaries(self):
        for value in (-(1 << 63), (1 << 63) - 1):
            with self.subTest(value=value):
                self.assertEqual(frontend.lower(f'source a: int = {value}\n'),
                                 f'source a: int = {value}\n')
        for value in (-(1 << 63) - 1, 1 << 63, 10 ** 100):
            with self.subTest(value=value):
                with self.assertRaisesRegex(frontend.SyntaxErrorDOC, 'signed 64-bit range'):
                    frontend.lower(f'source a: int = {value}\n')

    def test_derived_i64_literal_boundaries(self):
        for value in (-(1 << 63), (1 << 63) - 1):
            with self.subTest(value=value):
                self.assertIn(str(value), frontend.lower(f'derive x(): int:\n    {value}\n'))
        for value in (-(1 << 63) - 1, 1 << 63):
            with self.subTest(value=value):
                with self.assertRaisesRegex(frontend.SyntaxErrorDOC, 'signed 64-bit range'):
                    frontend.lower(f'derive x(): int:\n    {value}\n')
        with self.assertRaisesRegex(frontend.SyntaxErrorDOC, 'signed 64-bit range'):
            frontend.lower('derive x(): int:\n    ' + '9' * 10000 + '\n')

    def test_derived_zero_padded_i64_literals(self):
        # Rust accepts leading zeros in expression integer tokens.
        for literal in ('000', '-000', '0' * 10000 + '1',
                        '-' + '0' * 10000 + '1',
                        '0' * 10000 + str((1 << 63) - 1),
                        '-' + '0' * 10000 + str(1 << 63)):
            with self.subTest(prefix=literal[:24], length=len(literal)):
                self.assertIn(literal, frontend.lower(
                    f'derive x(): int:\n    {literal}\n'))
        for literal in ('0' * 10000 + str(1 << 63),
                        '-' + '0' * 10000 + str((1 << 63) + 1)):
            with self.subTest(prefix=literal[:24], length=len(literal)):
                with self.assertRaisesRegex(frontend.SyntaxErrorDOC, 'signed 64-bit range'):
                    frontend.lower(f'derive x(): int:\n    {literal}\n')

    def test_invalid(self):
        bad = [
            'derive x(): int:', ' source x: int = 1',
            'source x: bool = 2', 'source x: int = true',
            'source x: int = 1\nsource x: int = 2',
            'source x: int = 1\nderive y(x,x): int:\n    add(x,x)',
            'derive y(x): int:\n    x',
            'source x: int = 1\nderive y(x): int:\n  x',
            'source x: int = 1\nderive y(x): int:\n\tx',
            'source x: int = 1\nderive y(x): int:\n    x\n    x',
            'source x: int = 1\nderive y(x): int:\n    x+1',
            'source x: int = 1\nderive y(x): int:\n    x\n  source z: int = 2',
        ]
        for case in bad:
            with self.subTest(case=case):
                with self.assertRaises(frontend.SyntaxErrorDOC):
                    frontend.lower(case)

if __name__ == '__main__':
    unittest.main()
