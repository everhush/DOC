#!/usr/bin/env python3
"""Recover a previously submitted exact notebook after a status transport failure."""
import csv,io,json,os,tarfile,tempfile,time
from pathlib import Path
from dispatch import auth_environment,kaggle,status_from_cli
ORIGINAL="46048894537"
SHA="382318e728f36d83dbf6c3104b97e746c1fa42e7"
def main():
 assert os.environ["GITHUB_REPOSITORY_ID"]=="1471748051"
 out=Path("doc9-pipeline-evidence");local=json.loads((out/"provenance.json").read_text());spec=local["spec"];assert spec["sha"]==SHA and str(spec["run_id"])==ORIGINAL
 meta=json.loads(Path("doc9-pipeline-build/build.json").read_text())
 with tempfile.TemporaryDirectory() as t:
  env,owner=auth_environment(os.environ.get("KAGGLE_DOC_1",""),Path(t)/"config",os.environ.get("DOC_KAGGLE_USERNAME",""))
  name=owner+"/doc-gpu-"+ORIGINAL+"-"+str(spec["attempt"]);errors=0
  while True:
   try:
    state=status_from_cli(kaggle(["kernels","status",name],env));errors=0
   except RuntimeError as e:
    errors+=1;print("READ_ONLY_STATUS_RETRY",errors,str(e),flush=True)
    if errors>=8:raise
    time.sleep(15);continue
   print("DOC9_PIPELINE_RECOVERY_STATUS",state,flush=True)
   if state in ("COMPLETE","FAILED"):break
   time.sleep(20)
  remote=out/"remote";remote.mkdir(exist_ok=True)
  kaggle(["kernels","output",name,"-p",str(remote)],env,timeout=900)
  if state!="COMPLETE":raise RuntimeError("original submitted pipeline notebook failed")
 files=list(remote.rglob("doc9-pipeline-results.tar.gz"));assert len(files)==1
 with tarfile.open(files[0]) as tar:
  rec=json.load(tar.extractfile("provenance.json"));report=json.load(tar.extractfile("measurements/summary.json"));assert rec==dict(sha=SHA,run_id=spec["run_id"],bundle_sha256=spec["bundle_sha256"],physical=True,rows=report["rows"],processes=report["processes"],dispatches=report["dispatches"],result="pass")
  assert report["machine"]["physical"] and report["machine"]["build"]==meta
  rows=list(csv.DictReader(io.TextIOWrapper(tar.extractfile("measurements/samples.csv"))));assert len(rows)==report["rows"] and sum(int(r["dispatch_ns"])>0 for r in rows)==report["dispatches"]
  logs=[m for m in tar.getmembers() if m.name.endswith(".stderr")];assert len(logs)==report["processes"] and sum(b"physical=1 " in tar.extractfile(m).read() for m in logs)==report["dispatches"]//report["machine"]["epochs"]
  (out/"summary.json").write_text(json.dumps(report,indent=2)+"\n")
 print("DOC9_PIPELINE_RECOVERY_PASS",rec,flush=True)
if __name__=="__main__":main()
