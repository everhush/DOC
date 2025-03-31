#!/usr/bin/env python3
"""Static policy checks for the publication-validation workflow."""
from pathlib import Path
import re
import sys

workflow = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "publication-validation.yml"
errors = []
if not workflow.is_file():
    errors.append("publication-validation.yml is missing")
    text = ""
else:
    text = workflow.read_text(encoding="utf-8")

required = [
    "actions/checkout@v7",
    "actions/setup-python@v7",
    "actions/upload-artifact@v7",
    "retention-days: 1",
    'TYPST_VERSION: "0.15.1"',
    "permissions:",
    "contents: read",
    "verification/check_manuscript.py",
    "verification/check_pdf.sh",
    "verification/check_benchmark_artifact.py",
    "ctest --test-dir",
    "run_all_benchmarks.py",
    "pdftoppm -png",
]
for token in required:
    if token not in text:
        errors.append(f"workflow missing policy token: {token}")

if "secrets." in text:
    errors.append("workflow requires repository/user secrets; publication CI must be credential-free")
if re.search(r"retention-days:\s*(?!1\b)\d+", text):
    errors.append("all uploaded artifacts must use one-day retention")
if "pull_request_target:" in text:
    errors.append("pull_request_target is forbidden for this unprivileged validation workflow")
if "contents: write" in text or "packages: write" in text:
    errors.append("workflow grants write permission unnecessarily")

# Ensure every artifact upload explicitly carries the one-day policy.
uploads = text.split("uses: actions/upload-artifact@v7")
for i, block in enumerate(uploads[1:], start=1):
    segment = block.split("\n      - name:", 1)[0]
    if "retention-days: 1" not in segment:
        errors.append(f"artifact upload #{i} lacks retention-days: 1")

if errors:
    print("CI POLICY: FAIL")
    for error in errors:
        print(f"- {error}")
    sys.exit(1)

print("CI POLICY: PASS")
print("- credential-free read-only workflow")
print("- pinned Typst and current action majors")
print("- every uploaded artifact expires after one day")
