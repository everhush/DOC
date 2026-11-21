"""Prepare an exact-SHA native DOC GPU runtime bundle on GitHub's CPU runner.

No Kaggle GPU minutes are spent by this build/artifact/dataset preparation.
The two DOC implementations are compiled independently in the normal CI jobs:
Rust with wgpu, Goose with SDL3. Kaggle only dispatches their native binaries.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import time
import tempfile
import urllib.request

ARTIFACT_NAMES = ("doc-rust-wgpu-validation", "doc-goose-sdl3-native-gpu")
GPU_EXECUTABLES = {
    "bin/webgpu_bool":("rust","gpu-binaries/webgpu_bool"),
    "bin/webgpu_integer_eq":("rust","gpu-binaries/webgpu_integer_eq"),
    "bin/vulkaninfo":("rust","gpu-binaries/vulkaninfo"),
    "lib/libvulkan.so.1":("rust","gpu-binaries/libvulkan.so.1"),
    "bin/doc-goose-sdl3":("goose","doc-goose-sdl3"),
    "bin/Xvfb":("goose","gpu-platform-bin/Xvfb"),
    "bin/xvfb-run":("goose","gpu-platform-bin/xvfb-run"),
    "bin/xauth":("goose","gpu-platform-bin/xauth"),
}
SOURCE_FILES = (
    "runtime-rust/examples/boolean_conditional.doc",
    "runtime-rust/examples/boolean_staged.doc",
    "runtime-rust/examples/integer_equality.doc",
    "runtime-rust/examples/integer_ordering.doc",
    "runtime-goose/check-doc-sdl3-gpu.py",
    "runtime-goose/check-dual-gpu-parity.py",
    "LICENSE",
)

def github_json(repo, token, path):
    if not token:
        raise ValueError("GITHUB_TOKEN required to verify native binary build provenance")
    req = urllib.request.Request(
        "https://api.github.com/repos/" + repo + "/" + path,
        headers={"Authorization":"Bearer " + token,
                 "Accept":"application/vnd.github+json",
                 "X-GitHub-Api-Version":"2022-11-28"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)

def find_native_run(repo, token, sha, requested_id):
    if not re.fullmatch(r"[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+", repo):
        raise ValueError("Invalid GitHub repository")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("Expected immutable git commit SHA")
    if requested_id:
        if not re.fullmatch(r"[1-9][0-9]{0,19}", str(requested_id)):
            raise ValueError("Invalid GitHub run ID")
        run = github_json(repo,token,"actions/runs/"+str(requested_id))
    else:
        candidates = github_json(repo,token,
            "actions/workflows/doc-validation.yml/runs?per_page=50&head_sha="+sha)
        runs = candidates.get("workflow_runs",[])
        run = next((x for x in runs
                    if x.get("head_sha")==sha and x.get("conclusion")=="success"),None)
        if run is None:
            raise RuntimeError("No successful exact-SHA native DOC build for GPU offload")
    if run.get("head_sha")!=sha or run.get("conclusion")!="success" or \
            run.get("name")!="DOC dual-runtime validation":
        raise RuntimeError("GPU binaries must come from a successful exact-SHA DOC native CI run")
    return str(run["id"])

def download_binaries(repo,run_id,dest,token):
    # gh is preinstalled on ubuntu-latest and handles artifact ZIP redirects
    # without propagating the GitHub API bearer token into Kaggle.
    if not shutil.which("gh"):
        raise RuntimeError("GitHub CLI required on CPU controller; Kaggle never receives token")
    env={**os.environ,"GH_TOKEN":token}
    for name in ARTIFACT_NAMES:
        folder = dest / ("rust" if name.startswith("doc-rust") else "goose")
        folder.mkdir(parents=True,exist_ok=True)
        p=subprocess.run([
            "gh","run","download",run_id,"--repo",repo,
            "--name",name,"--dir",str(folder)],
            env=env,capture_output=True,text=True,timeout=180)
        if p.returncode:
            raise RuntimeError("Cannot download verified native CI artifact: "+name)
    return dest

def bundle_source(repo,sha,run_id,checkout,artifacts,destination):
    """Pack only reviewed native binaries, exact DOC source and test oracles."""
    destination.mkdir(parents=True,exist_ok=False)
    manifest={"sha":sha,"standard_ci_run_id":run_id,"backend":["Rust wgpu","Goose SDL3"],
              "files":{}}
    with tempfile.TemporaryDirectory(prefix="doc-gpu-bundle-") as temp:
        root=Path(temp)
        for dst,(component,src) in GPU_EXECUTABLES.items():
            source=artifacts/component/src
            if not source.is_file() or source.stat().st_size==0:
                raise RuntimeError("Native DOC GPU binary missing in exact-SHA CI: "+src)
            target=root/dst
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source,target)
            target.chmod(0o755)
        for path in SOURCE_FILES:
            source=checkout/path
            if not source.is_file():
                raise RuntimeError("DOC shared-source fixture missing: "+path)
            target=root/"DOC"/path
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source,target)
        for file in sorted(root.rglob("*")):
            if file.is_file():
                manifest["files"][str(file.relative_to(root))]=hashlib.sha256(
                    file.read_bytes()).hexdigest()
        (root/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
        bundle=destination/"doc-gpu-bundle.tar.gz"
        with tarfile.open(bundle,"w:gz") as archive:
            for file in sorted(root.rglob("*")):
                if file.is_file():
                    archive.add(file,arcname=str(file.relative_to(root)))
    return bundle,hashlib.sha256(bundle.read_bytes()).hexdigest(),manifest

def create_private_dataset(folder, owner,run_id,attempt,env):
    slug=f"doc-gpu-{run_id}-{attempt}-bundle"
    if not re.fullmatch(r"doc-gpu-[0-9]+-[0-9]+-bundle",slug):
        raise ValueError("Invalid private GPU binary dataset ID")
    dataset=owner+"/"+slug
    metadata={
        "title":slug,"id":dataset,
        "description":"Private, SHA-pinned Rust wgpu and native Goose SDL3 executables "
                      "compiled and tested by a prior GitHub CPU CI run. Native DOC source is CC-BY-4.0; "
                      "precompiled third-party Xvfb/Vulkan tools retain upstream licenses.",
        "licenses":[{"name":"other"}],
    }
    (folder/"dataset-metadata.json").write_text(json.dumps(metadata,indent=2)+"\n")
    # Kaggle datasets are private by default. No GPU session is started here.
    p=subprocess.run(["kaggle","datasets","create","-p",str(folder),"-q"],
         env=env,capture_output=True,text=True,timeout=180)
    if p.returncode:
        raise RuntimeError("Kaggle private native GPU binary dataset upload failed")
    # Kaggle controls dataset indexing; DOC has no fixed readiness deadline.
    # Permanent permission failure is still actionable; transient delays retry.
    polls=0
    while True:
        polls+=1
        status=subprocess.run(["kaggle","datasets","status",dataset,
            "--format","json"],env=env,capture_output=True,text=True,timeout=25)
        if status.returncode:
            # Avoid printing CLI stderr, which may contain account metadata.
            error=(status.stderr+"\n"+status.stdout).lower()
            if any(term in error for term in (
                    "401","403","forbidden","unauthorized","permission denied",
                    "insufficient scope","invalid token")):
                raise RuntimeError(
                    "Kaggle private dataset status denied by API permissions")
            time.sleep(8)
            continue
        try:
            state=json.loads(status.stdout)
            if isinstance(state,dict):
                state=state.get("status",state.get("currentStatus",""))
        except json.JSONDecodeError:
            state=status.stdout
        state=str(state).upper()
        if "COMPLETE" in state or "READY" in state:
            return dataset
        if any(word in state for word in ("ERROR","FAIL","CANCEL")):
            raise RuntimeError("Kaggle private GPU binary dataset failed processing")
        # Back off between polls without imposing a DOC-defined time limit.
        time.sleep(8)

def prepare_native_gpu_dataset(repo, token, spec, checkout, workdir, kaggle_env, owner):
    run_id=find_native_run(repo,token,spec["sha"],
                           os.environ.get("DOC_SOURCE_WORKFLOW_RUN_ID",""))
    with tempfile.TemporaryDirectory(prefix="doc-gpu-artifacts-") as temp:
        artifacts=download_binaries(repo,run_id,Path(temp),token)
        output=workdir/"native-gpu-dataset"
        bundle,checksum,manifest=bundle_source(
            repo,spec["sha"],run_id,checkout,artifacts,output)
    name=create_private_dataset(output,owner,spec["run_id"],spec["attempt"],kaggle_env)
    return {"bundle_dataset":name,
            "bundle_sha256":checksum,
            "standard_ci_run_id":run_id,
            "bundle_bytes":bundle.stat().st_size,
            "native_files":len(manifest["files"])}
