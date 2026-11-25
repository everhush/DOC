use doc_runtime::{recurrence::Recurrence, Cutoff, Graph, Runtime, Value};
use std::{env, process};
// One typed recurrence request/authority preflight for BOTH native Rust
// executors. Only the plan is shared: CPU and wgpu still independently
// evaluate the DOC source on their explicitly selected execution backend.
struct RecurrencePlan {
    end_epoch:u64,
    halt_id:Option<usize>,
    carry:Vec<(usize,usize)>,
    facts:std::collections::BTreeMap<u64,Vec<(usize,Value)>>,
}
fn parse_recurrence_plan(
    graph:&Graph,args:&mut impl Iterator<Item=String>,
)->Result<RecurrencePlan,String>{
    let command=args.next().ok_or("missing recurrence command")?;
    let (end_epoch,halt_id)=if let Some(raw)=command.strip_prefix("--through=") {
        (raw.parse::<u64>().map_err(|_|"invalid recurrence epoch limit")?,None)
    }else if let Some(raw)=command.strip_prefix("--until="){
        let cap=args.next().ok_or("--until requires --max-epochs=N")?;
        let cap=cap.strip_prefix("--max-epochs=")
            .ok_or("--until requires --max-epochs=N")?;
        let end=cap.parse::<u64>().map_err(|_|"invalid recurrence epoch cap")?;
        let halt=graph.id(raw).ok_or("unknown recurrent halt state")?;
        if graph.states[halt].kind!=doc_runtime::Type::Bool {
            return Err("halt predicate must name a Boolean state".into());
        }
        (end,Some(halt))
    }else{return Err("expected --through=N or --until=STATE".into());};
    let mut carry:Vec<(usize,usize)>=Vec::new();
    let mut facts=std::collections::BTreeMap::<u64,Vec<(usize,Value)>>::new();
    for binding in args.by_ref(){
        if let Some(raw)=binding.strip_prefix("--fact="){
            let (epoch_text,assignment)=raw.split_once(':')
                .ok_or("epoch fact requires --fact=EPOCH:name=value")?;
            let epoch=epoch_text.parse::<u64>()
                .map_err(|_|"invalid epoch fact index")?;
            if epoch==0||epoch>end_epoch{
                return Err("epoch fact must target a requested successor epoch".into());
            }
            let (name,raw)=assignment.split_once('=')
                .ok_or("epoch fact requires source=value")?;
            let source=graph.id(name).ok_or("unknown epoch fact source")?;
            if graph.states[source].definition.is_some(){
                return Err("epoch fact cannot target a derived state".into());
            }
            let value=Value::parse_for_type(raw,graph.states[source].kind)?;
            if value.kind()!=graph.states[source].kind{
                return Err("epoch fact type mismatch".into());
            }
            let same=facts.entry(epoch).or_default();
            if same.iter().any(|(id,_)|*id==source){
                return Err("duplicate source fact in one epoch".into());
            }
            same.push((source,value));
        }else{
            let (name,previous)=binding.split_once('=')
                .ok_or("expected source=previous or --fact=EPOCH:name=value")?;
            let source=graph.id(name).ok_or("unknown carry source")?;
            let previous=graph.id(previous).ok_or("unknown carried state")?;
            if graph.states[source].definition.is_some()||
                graph.states[source].kind!=graph.states[previous].kind {
                return Err("carry requires source of the previous state's type".into());
            }
            if carry.iter().any(|(id,_)|*id==source) {
                return Err("duplicate recurrence carry authority".into());
            }
            carry.push((source,previous));
        }
    }
    if facts.values().any(|list|list.iter().any(|(source,_)|
        carry.iter().any(|(id,_)|source==id))){
        return Err("epoch fact conflicts with a carried source".into());
    }
    Ok(RecurrencePlan {end_epoch,halt_id,carry,facts})
}
// Reference counterpart of the generated native --next batch driver.
// Each successful batch emits exactly one observation; a failed batch
// terminates without emitting a partial successor. The invocation-local
// Runtime is dropped on error, so no failed state escapes this CLI.
fn run_repair_batches(graph:Graph, workers:usize, args:&[String])->Result<(),String>{
    let mut rt=Runtime::new(graph,workers,Cutoff::Exact);
    for (epoch,batch) in args.split(|arg|arg=="--next").enumerate(){
        let (target,assignments)=if let Some(name)=batch.first().and_then(|arg|arg.strip_prefix("--demand=")){
            (Some(rt.graph.id(name).ok_or("unknown DOC demand target")?), &batch[1..])
        }else{(None,batch)};
        let mut changes=Vec::new();
        for assignment in assignments{
            let (name,raw)=assignment.split_once('=').ok_or("expected source=value in repair batch")?;
            let id=rt.graph.id(name).ok_or("unknown DOC source")?;
            changes.push((id,Value::parse_for_type(raw,rt.graph.states[id].kind)?));
        }
        rt.update(&changes)?;
        if let Some(id)=target{
            rt.stabilize_requested(&[id])?;
        }else{
            rt.stabilize()?;
        }
        // Preflight the entire requested observation before printing an epoch.
        let mut lines=Vec::new();
        for (id,state) in rt.graph.states.iter().enumerate(){
            if target.is_none()||target==Some(id){
                let value=rt.value(id).ok_or("incomplete repair observation")?;
                lines.push(format!("{}: {}",state.name,value));
            }
        }
        println!("epoch: {epoch}");
        for line in lines{println!("{line}");}
        use std::io::Write;
        std::io::stdout().flush().map_err(|e|format!("repair output: {e}"))?;
    }
    Ok(())
}
fn main() {
    if let Err(e) = run() { eprintln!("DOC: {e}"); process::exit(1); }
}
fn run() -> Result<(), String> {
    let mut args = env::args().skip(1);
    let file = args.next().ok_or("usage: doc FILE.doc [--backend=cpu|gpu] [source=value ... | --through=N source=previous ... | --until=BOOL --max-epochs=N source=previous ... | --demand=STATE source=value ... [--next ...]]")?;
    // Explicit placement policy: no automatic selection or CPU fallback.
    let mut gpu_selected = false;
    let mut args = args.peekable();
    if let Some(backend) = args.peek().and_then(|a| a.strip_prefix("--backend=")).map(str::to_owned) {
        args.next();
        match backend.as_str() {
            "cpu" => {},
            "gpu" => gpu_selected = true,
            _ => return Err("DOC_BACKEND_INVALID: expected --backend=cpu or --backend=gpu (no auto mode)".into()),
        }
    }
    // A binary built without wgpu retains strict fail-closed admission and
    // rejects GPU even if FILE does not exist (no source effects or fallback).
    #[cfg(not(feature = "webgpu"))]
    if gpu_selected {
        return Err("DOC_GPU_UNSUPPORTED: rebuild with --features webgpu; no CPU fallback".into());
    }
    // Strict GPU checks and parses one bounded pure snapshot without effects.
    // The CPU file frontend remains the explicitly effectful boundary.
    let graph=if gpu_selected{Graph::parse_pure_gpu_file(&file)?}else{Graph::parse_file(&file)?};
    #[cfg(feature = "webgpu")]
    if gpu_selected {
        // Every accepted derived state runs on wgpu; host recurrence controls
        // only epoch authority/carry. Each epoch is a separately stable,
        // completely GPU-evaluated publication (no CPU evaluator fallback).
        if args.peek().is_some_and(|a|
            a.starts_with("--through=")||a.starts_with("--until=")) {
            let RecurrencePlan {end_epoch,halt_id,carry,facts}=
                parse_recurrence_plan(&graph,&mut args)?;
            let mut current=doc_runtime::gpu::evaluate(&graph,&[])?;
            for epoch in 0..=end_epoch {
                println!("epoch: {epoch}");
                for (state,value) in graph.states.iter().zip(current.iter()) {
                    println!("{}: {}",state.name,value);
                }
                if let Some(halt)=halt_id {
                    if matches!(current.get(halt),Some(Value::Bool(true))) {
                        println!("DOC_RECURRENCE_HALT: {epoch}");
                        return Ok(());
                    }
                }
                if epoch==end_epoch {
                    if halt_id.is_some() {
                        return Err("DOC recurrence did not halt within the requested epoch cap".into());
                    }
                    return Ok(());
                }
                let next=epoch.checked_add(1).ok_or("GPU recurrence epoch exhausted")?;
                let mut inputs:Vec<(usize,Value)>=carry.iter()
                    .map(|(source,previous)|(*source,current[*previous].clone())).collect();
                if let Some(extra)=facts.get(&next) {inputs.extend(extra.iter().cloned());}
                current=doc_runtime::gpu::evaluate(&graph,&inputs)?;
            }
            unreachable!("bounded GPU recurrence must terminate at its cap");
        }
        // Other graph policies, graph replacement, demand and effects remain
        // explicitly unsupported instead of silently running a CPU evaluator.
        let mut changes = Vec::new();
        for assignment in args {
            if assignment.starts_with("--") {
                return Err("DOC_GPU_UNSUPPORTED: selected GPU currently accepts only finite source=value updates".into());
            }
            let (name, raw) = assignment.split_once('=')
                .ok_or("DOC_GPU_UNSUPPORTED: GPU expects source=value assignments")?;
            let id = graph.id(name).ok_or_else(|| format!("unknown DOC GPU source {name}"))?;
            changes.push((id, Value::parse_for_type(raw, graph.states[id].kind)?));
        }
        let values = doc_runtime::gpu::evaluate(&graph, &changes)?;
        for (state, value) in graph.states.iter().zip(values.iter()) {
            println!("{}: {}", state.name, value);
        }
        return Ok(());
    }
    let workers = env::var("DOC_WORKERS").ok().and_then(|v| v.parse().ok())
        .unwrap_or_else(|| std::thread::available_parallelism().map_or(1, |v| v.get()));
    if args.peek().is_some_and(|a|
        a.starts_with("--through=")||a.starts_with("--until=")) {
        let RecurrencePlan {end_epoch,halt_id:halt,carry,facts}=
            parse_recurrence_plan(&graph,&mut args)?;
        let names: Vec<_> = graph.states.iter().map(|state| state.name.clone()).collect();
        let mut recurrence = Recurrence::new(graph, carry, &[], workers)?;
        loop {
            println!("epoch: {}", recurrence.epoch());
            for (id, name) in names.iter().enumerate() {
                println!("{name}: {}", recurrence.value(id).ok_or("incomplete epoch")?);
            }
            if let Some(halt_id) = halt {
                match recurrence.value(halt_id) {
                    Some(Value::Bool(true)) => {
                        println!("DOC_RECURRENCE_HALT: {}", recurrence.epoch());
                        return Ok(());
                    }
                    Some(Value::Bool(false)) => {}
                    _ => return Err("halt predicate must name a Boolean state".into()),
                }
            }
            if recurrence.epoch() == end_epoch {
                if halt.is_some() {
                    return Err("DOC recurrence did not halt within the requested epoch cap".into());
                }
                return Ok(());
            }
            let next = recurrence.epoch().checked_add(1).ok_or("epoch index exhausted")?;
            let requested = facts.get(&next).map(Vec::as_slice).unwrap_or(&[]);
            recurrence.advance(requested)?;
        }
    }
    let remaining:Vec<String>=args.collect();
    if remaining.iter().any(|arg|arg=="--next"){
        return run_repair_batches(graph,workers,&remaining);
    }
    let mut args=remaining.into_iter().peekable();
    if let Some(target_name) = args.peek().and_then(|arg|
        arg.strip_prefix("--demand=")).map(str::to_owned) {
        args.next();
        let target = graph.id(&target_name).ok_or("unknown DOC demand target")?;
        let mut requested = Runtime::new(graph, workers, Cutoff::Exact);
        let mut changes = Vec::new();
        for assignment in args {
            let (name, text) = assignment.split_once('=')
                .ok_or("expected source=value after --demand")?;
            let source = requested.graph.id(name).ok_or("unknown DOC source")?;
            changes.push((source, Value::parse_for_type(text, requested.graph.states[source].kind)?));
        }
        requested.update(&changes)?;
        requested.stabilize_requested(&[target])?;
        println!("{target_name}: {}", requested.value(target).ok_or("missing demanded value")?);
        return Ok(());
    }
    if let Some(spec)=args.peek()
        .and_then(|arg|arg.strip_prefix("--emit=")).map(str::to_owned) {
        args.next();
        if args.next().is_some(){return Err("DOC emit accepts one name:path".into());}
        let (name,relative)=spec.split_once(':')
            .ok_or("DOC emit expects --emit=STATE:relative/path")?;
        let target=graph.id(name).ok_or("unknown DOC emit state")?;
        let mut rt=Runtime::new(graph,workers,Cutoff::Exact);
        rt.stabilize_requested(&[target])?;
        let value=rt.value(target).ok_or("DOC emit value unavailable")?;
        doc_runtime::write_doc_output(&file,relative,&value)?;
        println!("DOC_EFFECT_WRITE_PASS: {name}: {value}");
        return Ok(());
    }
    if let Some(next_file)=args.peek()
        .and_then(|arg|arg.strip_prefix("--replace=")).map(str::to_owned) {
        args.next();
        if args.next().is_some(){return Err("graph replacement accepts one path".into());}
        let mut rt=Runtime::new(graph,workers,Cutoff::Exact);
        rt.stabilize()?;
        println!("DOC_GRAPH_GENERATION: 0");
        for (i,state) in rt.graph.states.iter().enumerate(){
            println!("{}: {}",state.name,rt.value(i).ok_or("missing old value")?);
        }
        // The new generation is constructed and stabilized privately:
        // an invalid candidate cannot publish a partial replacement.
        let next_graph=Graph::parse_file(&next_file)?;
        rt.replace_graph(next_graph)?;
        println!("DOC_GRAPH_GENERATION: 1");
        for (i,state) in rt.graph.states.iter().enumerate(){
            println!("{}: {}",state.name,rt.value(i).ok_or("missing new value")?);
        }
        return Ok(());
    }
    let mut rt = Runtime::new(graph, workers, Cutoff::Exact);
    let mut changes = Vec::new();
    for arg in args {
        let (name, raw) = arg.split_once('=').ok_or("expected source=value")?;
        let id = rt.graph.id(name).ok_or_else(|| format!("unknown state {name}"))?;
        changes.push((id, Value::parse_for_type(raw, rt.graph.states[id].kind)?));
    }
    rt.update(&changes)?;
    rt.stabilize()?;
    for (id, s) in rt.graph.states.iter().enumerate() {
        println!("{}: {}", s.name, rt.value(id).ok_or("incomplete value")?);
    }
    eprintln!("stats: {:?}", rt.stats);
    Ok(())
}

#[cfg(test)]
mod recurrence_cli_plan_tests {
    use super::*;
    fn plan(args:&[&str])->Result<RecurrencePlan,String>{
        let graph=Graph::parse(include_str!("../examples/recurrence_halt.doc"))?;
        let mut argv=args.iter().map(|s|s.to_string())
            .collect::<Vec<_>>().into_iter().peekable();
        parse_recurrence_plan(&graph,&mut argv)
    }
    #[test]
    fn shared_typed_recurrence_plan_accepts_exact_carry_and_epoch_facts(){
        let plan=plan(&[
            "--until=halt","--max-epochs=7","index=successor","--fact=2:step=3",
        ]).unwrap();
        assert_eq!(plan.end_epoch,7);
        assert_eq!(plan.halt_id,Some(3));
        assert_eq!(plan.carry.len(),1);
        assert_eq!(plan.facts.get(&2).unwrap().len(),1);
    }
    #[test]
    fn shared_typed_recurrence_plan_rejects_conflicting_and_invalid_authority(){
        for invalid in [
            vec!["--until=successor","--max-epochs=3"],
            vec!["--through=3","step=halt"],
            vec!["--through=3","index=successor","index=index"],
            vec!["--through=3","index=successor","--fact=1:index=2"],
            vec!["--through=3","--fact=0:step=1"],
            vec!["--through=3","--fact=4:step=1"],
            vec!["--through=3","--fact=1:halt=true"],
            vec!["--through=3","--fact=1:step=1","--fact=1:step=1"],
            vec!["--until=halt","--max-epochs=invalid"],
        ]{
            assert!(plan(&invalid).is_err(),"accepted invalid {invalid:?}");
        }
    }
}
