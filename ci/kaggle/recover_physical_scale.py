#!/usr/bin/env python3
"""Read-only recovery of the completed exact physical benchmark; never submit GPU work."""
import csv,hashlib,json,math,os,re,tempfile
from pathlib import Path
from dispatch import auth_environment,kaggle,status_from_cli
ORIGINAL="46032762791"
SHA="ef06a32f0c0504784e15ea0db4b6ca5ab9cf8838"
def main():
 if os.environ.get("GITHUB_REPOSITORY_ID")!="1471748051":raise ValueError("private CI fork only")
 out=Path("doc9-physical-scale-evidence");local=json.loads((out/"provenance.json").read_text());spec=local["spec"];assert spec["sha"]==SHA and str(spec["run_id"])==ORIGINAL
 build=Path("doc9-scale-build");meta=json.loads((build/"build.json").read_text());expected={w:meta[w]["bench"] for w in ("add","poly")}
 for w in expected:assert hashlib.sha256((build/w/"bench").read_bytes()).hexdigest()==expected[w]
 remote=out/"remote";base=remote/"doc9-gpu-scale";raw=base/"measurements/raw"
 with tempfile.TemporaryDirectory(prefix="doc9-recovery-") as t:
  env,owner=auth_environment(os.environ.get("KAGGLE_DOC_1",""),Path(t)/"config",os.environ.get("DOC_KAGGLE_USERNAME",""));name=owner+"/doc-gpu-"+ORIGINAL+"-"+str(spec["attempt"])
  assert status_from_cli(kaggle(["kernels","status",name],env))=="COMPLETE"
  tags=[f"{s:02d}-{w}-{n}-{m}" for s in range(1,11) for w in ("add","poly") for n in (1,31,32,63,64,128,256,512,1024,2048,4096) for m in ("cpu1","cpu-auto","auto","gpu")]
  missing=[f"{tag}.{ext}" for tag in tags for ext in ("stdout","stderr") if not (raw/f"{tag}.{ext}").is_file()]
  # Only retrieve missing read-only outputs from the already completed run.
  files=["doc9-gpu-scale/provenance.json","doc9-gpu-scale/measurements/summary.json"]+[f"doc9-gpu-scale/measurements/raw/{p}" for p in missing]
  for i in range(0,len(files),60):
   group=files[i:i+60];pattern=".*(?:"+"|".join(re.escape(p) for p in group)+")$"
   try:kaggle(["kernels","output",name,"-p",str(remote),"--file-pattern",pattern],env,timeout=300)
   except RuntimeError:
    # The CLI may time out after writing files; check, then do a read-only retry.
    group=[p for p in group if not (remote/p).is_file()]
    if group:kaggle(["kernels","output",name,"-p",str(remote),"--file-pattern",".*(?:"+"|".join(re.escape(p) for p in group)+")$"],env,timeout=300)
  # If CLI patterns vary by version, retry ordinary non-forced output, skipping existing files.
  if any(not (remote/p).is_file() for p in files):kaggle(["kernels","output",name,"-p",str(remote)],env,timeout=1200)
 rec=json.loads((base/"provenance.json").read_text());assert rec==dict(sha=SHA,run_id=spec["run_id"],bundle_sha256=spec["bundle_sha256"],physical=True,result="pass",binaries=expected)
 report=json.loads((base/"measurements/summary.json").read_text());assert report["physical"] and report["binaries"]==expected and report["epoch_count"]==14960 and report["dispatch_count"]==6120
 rows=list(csv.DictReader((base/"measurements/epochs.csv").open()));dispatch=list(csv.DictReader((base/"measurements/dispatches.csv").open()));assert len(rows)==14960 and len(dispatch)==6120
 nphys=0
 for tag in tags:
  stdout=(raw/(tag+".stdout")).read_bytes();stderr=(raw/(tag+".stderr")).read_bytes();assert b"live=0 " in stdout
  mode=tag.split("-",3)[3];nphys+=int(b"physical=1 " in stderr)
  assert (b"physical=1 " in stderr)==(not mode.startswith("cpu"))
 assert nphys==440 and len(list(raw.glob("*.stderr")))==880 and len(list(raw.glob("*.stdout")))==880
 print("DOC9_PHYSICAL_SCALING_RECOVERED: 14960 verified epochs; 6120 actual dispatches; 440 physical sessions; 880 complete raw process pairs",flush=True)
if __name__=="__main__":main()
