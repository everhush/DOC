use doc_runtime::{recurrence::Recurrence, Cutoff, Graph, Runtime, Value};
use std::{env, fs, process};
fn main() {
    if let Err(e) = run() { eprintln!("DOC: {e}"); process::exit(1); }
}
fn run() -> Result<(), String> {
    let mut args = env::args().skip(1);
    let file = args.next().ok_or("usage: doc FILE.doc [source=value ... | --through=N source=previous ... | --until=BOOL --max-epochs=N source=previous ...]")?;
    let src = fs::read_to_string(&file).map_err(|e| format!("{file}: {e}"))?;
    let graph = Graph::parse(&src)?;
    let workers = env::var("DOC_WORKERS").ok().and_then(|v| v.parse().ok())
        .unwrap_or_else(|| std::thread::available_parallelism().map_or(1, |v| v.get()));
    let mut args = args.peekable();
    let recurrence_command = if let Some(first) = args.peek() {
        if let Some(limit) = first.strip_prefix("--through=") {
            Some((false, limit.to_string()))
        } else {
            first.strip_prefix("--until=").map(|name| (true, name.to_string()))
        }
    } else {
        None
    };
    if let Some((until, first_value)) = recurrence_command {
        args.next();
        let (end_epoch, halt_name) = if until {
            let halt_name = first_value;
            let cap = args.next().ok_or("--until requires --max-epochs=N")?;
            let cap = cap.strip_prefix("--max-epochs=")
                .ok_or("--until requires --max-epochs=N")?;
            (cap.parse::<u64>().map_err(|_| "invalid epoch cap")?, Some(halt_name))
        } else {
            (first_value.parse::<u64>().map_err(|_| "invalid epoch limit")?, None)
        };
        // Source facts are independent of carry and are scoped to their
        // requested successor epoch. Validate the whole request before output.
        let mut carry = Vec::new();
        let mut facts = std::collections::BTreeMap::<u64, Vec<(usize, Value)>>::new();
        for binding in args {
            if let Some(rest) = binding.strip_prefix("--fact=") {
                let (epoch_text, assignment) = rest.split_once(':')
                    .ok_or("epoch fact requires --fact=EPOCH:name=value")?;
                let epoch = epoch_text.parse::<u64>()
                    .map_err(|_| "invalid fact epoch")?;
                if epoch == 0 || epoch > end_epoch {
                    return Err("epoch fact must target a requested successor epoch".into());
                }
                let (name, text) = assignment.split_once('=')
                    .ok_or("epoch fact requires name=value")?;
                let source = graph.id(name).ok_or("unknown epoch fact source")?;
                if graph.states[source].definition.is_some() {
                    return Err("epoch fact cannot target a derived state".into());
                }
                let value = Value::parse(text)?;
                if value.kind() != graph.states[source].kind {
                    return Err("epoch fact type mismatch".into());
                }
                let target = facts.entry(epoch).or_default();
                if target.iter().any(|(id, _)| *id == source) {
                    return Err("duplicate source fact in one epoch".into());
                }
                target.push((source, value));
            } else {
                let (source, previous) = binding.split_once('=')
                    .ok_or("expected source=previous or --fact=EPOCH:name=value")?;
                let source = graph.id(source).ok_or("unknown carry source")?;
                let previous = graph.id(previous).ok_or("unknown carry state")?;
                carry.push((source, previous));
            }
        }
        for assignments in facts.values() {
            if assignments.iter().any(|(id, _)| carry.iter().any(|(source, _)| source == id)) {
                return Err("epoch fact conflicts with a carried source".into());
            }
        }
        let halt = if let Some(name) = &halt_name {
            let id = graph.id(name).ok_or("unknown recurrent halt state")?;
            if graph.states[id].kind != doc_runtime::Type::Bool {
                return Err("halt predicate must name a Boolean state".into());
            }
            Some(id)
        } else {
            None
        };
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
    let mut rt = Runtime::new(graph, workers, Cutoff::Exact);
    let mut changes = Vec::new();
    for arg in args {
        let (name, raw) = arg.split_once('=').ok_or("expected source=value")?;
        let id = rt.graph.id(name).ok_or_else(|| format!("unknown state {name}"))?;
        changes.push((id, Value::parse(raw)?));
    }
    rt.update(&changes)?;
    rt.stabilize()?;
    for (id, s) in rt.graph.states.iter().enumerate() {
        println!("{}: {}", s.name, rt.value(id).ok_or("incomplete value")?);
    }
    eprintln!("stats: {:?}", rt.stats);
    Ok(())
}
