#!/usr/bin/env python3
"""Read-only, secret-redacted diagnostics for the failed DOC9 attempt 2.
This does not assert artifact integrity, modify visibility or submit a notebook.
"""
import os
import re
import subprocess
import tempfile
from pathlib import Path
from dispatch import auth_environment, cli_failure_category

SLUG = "doc-gpu-46078960477-2-bundle"

def probe(command, env, timeout=60):
    try:
        p = subprocess.run(["kaggle", *command], env=env, capture_output=True,
                           text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return "timeout", ""
    if p.returncode == 0:
        return "ok", p.stdout
    msg = p.stdout + "\n" + p.stderr
    kind = cli_failure_category(msg)
    if kind == "unclassified":
        match = re.search(r"\b(401|403|404|429|500|502|503|504)\b", msg)
        if match:
            kind = "http-" + match.group(1)
        elif re.search(r"forbidden|unauthorized|permission denied|insufficient scope|invalid token", msg, re.I):
            kind = "access-denied"
    return kind, ""

def main():
    with tempfile.TemporaryDirectory(prefix="doc9-access-") as td:
        root = Path(td)
        env, owner = auth_environment(os.environ.get("KAGGLE_DOC_1", ""), root/"config",
                                     os.environ.get("DOC_KAGGLE_USERNAME", ""))
        print("DOC9_AUTH_MODE=" + ("modern-token" if "KAGGLE_API_TOKEN" in env else "legacy-key"))
        status, config = probe(["config", "view"], env)
        print("DOC9_CONFIG_VIEW=" + status)
        match = re.search(r"(?mi)^\s*-?\s*username:\s*([a-z0-9_-]+)\s*$", config)
        if match and match.group(1).lower() != owner:
            raise SystemExit("DOC9_ACCESS_BLOCKED: authenticated owner and configured owner differ")
        print("DOC9_OWNER_BINDING=" + ("match" if match else "unresolved"))
        dataset = owner + "/" + SLUG
        status, owned = probe(["datasets", "list", "--mine", "--search", SLUG, "--csv"], env)
        print("DOC9_OWNED_DATASET_LIST=" + status)
        print("DOC9_PRIOR_DATASET_LISTED=" + ("yes" if dataset.lower() in owned.lower() else "not-confirmed"))
        status, _ = probe(["datasets", "status", dataset, "--format", "json"], env)
        print("DOC9_DATASET_STATUS=" + status)
        listing, files = probe(["datasets", "files", dataset, "--csv"], env)
        print("DOC9_DATASET_FILES=" + listing)
        print("DOC9_BUNDLE_LISTED=" + ("yes" if "doc-gpu-bundle.bin" in files else "not-confirmed"))
        dest = root/"download"
        dest.mkdir()
        retrieved, _ = probe(["datasets", "download", dataset, "-f", "doc-gpu-bundle.bin",
                              "-p", str(dest), "--force", "-q"], env, timeout=120)
        print("DOC9_DATASET_DOWNLOAD=" + retrieved)
        if retrieved != "ok" or not (dest/"doc-gpu-bundle.bin").is_file():
            raise SystemExit("DOC9_ACCESS_BLOCKED: prior private bundle not retrievable")
        print("DOC9_ACCESS_PASS: prior bundle accessible; original dispatch integrity still required")

if __name__ == "__main__":
    main()
