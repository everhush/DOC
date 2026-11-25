"""Prepare an exact-SHA native DOC GPU runtime bundle on GitHub's CPU runner.

No Kaggle GPU minutes are spent by this build/artifact/dataset preparation.
Only the active Rust wgpu native runtime is compiled in the successful
Rust-only Linux CI job; Kaggle executes those SHA-pinned binaries.
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

ARTIFACT_NAMES = ("doc-rust-wgpu-validation",)
GPU_EXECUTABLES = {
    "bin/webgpu_bool":("rust","gpu-binaries/webgpu_bool"),
    "bin/webgpu_integer_eq":("rust","gpu-binaries/webgpu_integer_eq"),
    "bin/doc-rust-gpu":("rust","gpu-binaries/doc-rust-gpu"),
    "bin/doc-game":("rust","gpu-binaries/doc-game"),
    "bin/doc-scene3d":("rust","gpu-binaries/doc-scene3d"),
    "bin/scene3d_gpu_proof":("rust","gpu-binaries/scene3d_gpu_proof"),
    "bin/dependency_family_proof":("rust","gpu-binaries/dependency_family_proof"),
}
SOURCE_FILES = (
    "runtime-rust/examples/boolean_conditional.doc",
    "runtime-rust/examples/boolean_staged.doc",
    "runtime-rust/examples/mixed_comparison.doc",
    "runtime-rust/examples/gpu_arithmetic_chain.doc",
    "runtime-rust/examples/gpu_nested_arithmetic.doc",
    "runtime-rust/examples/parallel_frontier.doc",
    "runtime-rust/examples/dependency_family.doc",
    "runtime-rust/examples/typed_arithmetic.doc",
    "runtime-rust/examples/integer_equality.doc",
    "runtime-rust/examples/integer_ordering.doc",
    "engine/radar_chase.doc",
    "engine/radar_chase_3d.doc",
    "engine/graphics/arena_vertex.doc",
    "engine/graphics/mesh_fragment.doc",
    "engine/levels/arena_vertices.txt",
    "engine/levels/arena_indices.txt",
    "engine/engine_math.doc",
    "engine/entity_pool.doc",
    "engine/levels/coin_chase.txt",
    "engine/levels/showcase_xs.txt",
    "engine/levels/showcase_ys.txt",
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
            run.get("name")!="DOC Rust Linux validation":
        raise RuntimeError("GPU binaries must come from a successful exact-SHA DOC native CI run")
    return str(run["id"])

def download_binaries(repo,run_id,dest,token):
    # gh is preinstalled on ubuntu-latest and handles artifact ZIP redirects
    # without propagating the GitHub API bearer token into Kaggle.
    if not shutil.which("gh"):
        raise RuntimeError("GitHub CLI required on CPU controller; Kaggle never receives token")
    env={**os.environ,"GH_TOKEN":token}
    for name in ARTIFACT_NAMES:
        folder = dest / "rust"
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
    manifest={"sha":sha,"standard_ci_run_id":run_id,"backend":["Rust wgpu"],
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
        # Kaggle removes/expands a .tar.gz input dataset file during indexing.
        # Gzip-compressed TAR bytes are therefore stored with a neutral .bin
        # name: verified live private create/files/download/sha probe.
        bundle=destination/"doc-gpu-bundle.bin"
        with tarfile.open(bundle,"w:gz") as archive:
            for file in sorted(root.rglob("*")):
                if file.is_file():
                    archive.add(file,arcname=str(file.relative_to(root)))
    return bundle,hashlib.sha256(bundle.read_bytes()).hexdigest(),manifest

def _api_denied(completed):
    # Only classified status is retained: Kaggle output may contain private
    # notebook, account or dataset details.
    message=(completed.stderr+"\n"+completed.stdout).lower()
    return any(label in message for label in (
        "401", "403", "forbidden", "unauthorized", "permission denied",
        "insufficient scope", "invalid token"))


def verify_private_bundle_download(dataset, expected_archive, env):
    """Fallback for Kaggle's status endpoint: fetch and hash real private bytes.

    Only the authenticated owner's newly created dataset is accepted. Download
    failure during Kaggle's indexing period is retryable, but permanent
    read/auth denial fails closed and no notebook is submitted.
    """
    with tempfile.TemporaryDirectory(prefix="doc-kaggle-retrieval-") as td:
        remote=Path(td)
        proc=subprocess.run([
            "kaggle","datasets","download",dataset,
            "-f",expected_archive.name,"-p",str(remote),
            "--force","-q"],
            env=env,capture_output=True,text=True,timeout=120)
        if proc.returncode:
            if _api_denied(proc):
                raise RuntimeError(
                    "Kaggle private dataset status AND bundle retrieval denied")
            return False
        downloaded=remote/expected_archive.name
        if not downloaded.is_file():
            # A successful CLI return without the requested archive is never
            # an authenticated dataset-byte integrity witness.
            raise RuntimeError("Kaggle download returned no expected bundle")
        local_hash=hashlib.sha256(expected_archive.read_bytes()).digest()
        remote_hash=hashlib.sha256(downloaded.read_bytes()).digest()
        if local_hash!=remote_hash:
            raise RuntimeError("Kaggle private dataset bytes mismatch exact-SHA bundle")
        return True


def create_private_dataset(folder, owner,run_id,attempt,env):
    slug=f"doc-gpu-{run_id}-{attempt}-bundle"
    if not re.fullmatch(r"doc-gpu-[0-9]+-[0-9]+-bundle",slug):
        raise ValueError("Invalid private GPU binary dataset ID")
    dataset=owner+"/"+slug
    metadata={
        "title":slug,"id":dataset,
        "description":"Private, SHA-pinned native Rust wgpu DOC executables "
                      "compiled and tested by exact GitHub Linux Rust CI. "
                      "DOC source retains its own license; native device drivers are supplied by the host.",
        "licenses":[{"name":"other"}],
    }
    (folder/"dataset-metadata.json").write_text(json.dumps(metadata,indent=2)+"\n")
    archive=folder/"doc-gpu-bundle.bin"
    if not archive.is_file():
        raise RuntimeError("Missing exact-SHA native DOC bundle before Kaggle upload")
    # The unique new dataset is private by default; no GPU session begins here.
    p=subprocess.run(["kaggle","datasets","create","-p",str(folder),"-q"],
         env=env,capture_output=True,text=True,timeout=180)
    if p.returncode:
        raise RuntimeError("Kaggle private native GPU binary dataset upload failed")
    # Primary: Kaggle dataset-version status. The archive is named .bin
    # because Kaggle filters .tar.gz from dataset file listings/downloads.
    # Some accounts report 403 only
    # on the status endpoint despite valid create, quota and own-dataset APIs.
    # Alternative: require ACTUAL authenticated retrieval and a byte-for-byte
    # hash match of the private SHA-pinned bundle, never a listing alone.
    while True:
        status=subprocess.run(["kaggle","datasets","status",dataset,
            "--format","json"],env=env,capture_output=True,text=True,timeout=25)
        if status.returncode:
            if _api_denied(status):
                if verify_private_bundle_download(dataset,archive,env):
                    print("DOC_KAGGLE_PRIVATE_BUNDLE_INTEGRITY_PASS: authenticated exact bytes")
                    return dataset
                # The dataset may still be indexing. We do not give up solely
                # because the status endpoint is forbidden and download is 404.
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
            # Kaggle can return COMPLETE before indexing the actual input
            # filename. Status alone is NOT proof the private notebook can
            # mount our SHA-pinned native bundle.
            if verify_private_bundle_download(dataset,archive,env):
                print("DOC_KAGGLE_PRIVATE_BUNDLE_INTEGRITY_PASS: authenticated exact bytes")
                return dataset
            time.sleep(8)
            continue
        if any(word in state for word in ("ERROR","FAIL","CANCEL")):
            raise RuntimeError("Kaggle private GPU binary dataset failed processing")
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
