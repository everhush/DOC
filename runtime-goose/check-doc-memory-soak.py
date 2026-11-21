#!/usr/bin/env python3
"""Resource smoke on SAME DOC churn source; not a formal no-leak proof."""
import csv,json,os,platform,subprocess,sys,time
from pathlib import Path
rust,goose,logdir=sys.argv[1:]
out=Path(logdir);out.mkdir(parents=True,exist_ok=True)
src="runtime-rust/examples/memory_soak.doc"
workers=(1,4)
counts=(250,1000,5000)
records=[]
for name,binary in (("rust",rust),("goose",goose)):
    preview=subprocess.run(
        [binary,src,"--through=3","counter=next_counter",
         "list=next_list","label=next_label"],
        capture_output=True,text=True,timeout=30)
    if preview.returncode or not all(s in preview.stdout for s in
        ("epoch: 3","counter: 1","label: b","list: [3,4,7]")):
        raise AssertionError(f"{name} DOC typed churn invalid: {preview.stdout}\n{preview.stderr}")
    for number_workers in workers:
        for epochs in counts:
            command=[binary,src,f"--through={epochs}",
                     "counter=next_counter","list=next_list","label=next_label"]
            env={**os.environ,"DOC_WORKERS":str(number_workers),
                 "DOC_GOOSE_WORKERS":str(number_workers)}
            # Streaming output goes directly to /dev/null; Python's own
            # resident set cannot hide growth in the native child.
            with open(os.devnull,"wb") as sink:
                started=time.perf_counter_ns()
                process=subprocess.Popen(command,stdout=sink,
                                         stderr=subprocess.PIPE,env=env)
                pid,code,usage=os.wait4(process.pid,0)
                elapsed=(time.perf_counter_ns()-started)/1_000_000
                if pid!=process.pid or os.waitstatus_to_exitcode(code)!=0:
                    msg=process.stderr.read().decode(errors="replace")
                    raise AssertionError(f"{name} epochs={epochs} failed {msg}")
            if usage.ru_maxrss > 400_000:
                raise AssertionError(
                    f"{name}/{number_workers} peak RSS exceeds 400MB smoke threshold")
            records.append({
                "runtime":name,"workers_setting":number_workers,
                "epochs":epochs,"wall_ms":round(elapsed,3),
                "user_ms":round(usage.ru_utime*1000,3),
                "sys_ms":round(usage.ru_stime*1000,3),
                "maxrss_kib":usage.ru_maxrss,
                "sha":os.environ.get("GITHUB_SHA","local"),
                "command":json.dumps(command)
            })
for name in ("rust","goose"):
    for nworkers in workers:
        group={r["epochs"]:r for r in records
               if r["runtime"]==name and r["workers_setting"]==nworkers}
        # Fairly permissive guard: a monotonically growing lost-materialization
        # leak should exceed this with sufficient churn. This does NOT prove
        # a hard memory bound or absence of smaller leaks.
        lower=group[250]["maxrss_kib"]
        higher=group[5000]["maxrss_kib"]
        if higher > lower*2.5+60_000:
            raise AssertionError(
                f"{name}/{nworkers} large RSS increase {lower}->{higher}KiB")
with (out/"doc-churn-memory-samples.csv").open("w",newline="") as f:
    writer=csv.DictWriter(f,fieldnames=list(records[0]))
    writer.writeheader();writer.writerows(records)
summary={"count":len(records),"method":"per-child wait4 RSS, streamed output, "
         "250/1000/5000 epochs, CPU workers setting 1/4, no steady-state proof",
         "host":platform.platform(),"samples":records}
(out/"doc-churn-memory-summary.json").write_text(
    json.dumps(summary,indent=2)+"\n")
print(f"DOC_TYPED_CHURN_MEMORY_SMOKE_PASS: {len(records)} bounded-memory samples")
