"""Offline percentile regression: GPU benchmark statistics are not mislabeled maxima."""
import ast
from pathlib import Path
import unittest

source = Path(__file__).with_name("doc_kaggle_gpu.py").read_text()
tree = ast.parse(source.replace("__DOC_KAGGLE_RUN_SPEC__", "{}"))
function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name == "nearest_rank_p95")
namespace = {}
exec(compile(ast.Module(body=[function], type_ignores=[]), "<p95>", "exec"), namespace)
p95 = namespace["nearest_rank_p95"]

class PercentileOracle(unittest.TestCase):
    def test_nearest_rank_exact_boundaries(self):
        self.assertEqual(p95([7]), 7)
        self.assertEqual(p95(list(range(1, 10))), 9)
        self.assertEqual(p95(list(range(1, 21))), 19)
        self.assertEqual(p95(list(range(1, 101))), 95)
        self.assertEqual(p95(list(range(100, 0, -1))), 95)
    def test_empty_is_explicit_error(self):
        with self.assertRaises(ValueError):
            p95([])
    def test_benchmark_uses_percentile_not_maximum(self):
        benchmark = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                         and node.name == "benchmark_hardware_gpu")
        calls = [node for node in ast.walk(benchmark) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == "nearest_rank_p95"]
        self.assertEqual(len(calls), 1)

if __name__ == "__main__":
    unittest.main()
