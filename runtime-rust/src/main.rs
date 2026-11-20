use doc_runtime::{recurrence::Recurrence, Cutoff, Graph, Runtime, Value};
use std::{env, fs, process};
fn main() {
    if let Err(e) = run() { eprintln!("DOC: {e}"); process::exit(1); }
}
fn run() -> Result<(), String> {
    let mut args = env::args().skip(1);
    let file = args.next().ok_or("usage: doc FILE.doc [source=value ... | --through=N source=previous ...]")?;
    let src = fs::read_to_string(&file).map_err(|e| format!("{file}: {e}"))?;
    let graph = Graph::parse(&src)?;
    let workers = env::var("DOC_WORKERS").ok().and_then(|v| v.parse().ok())
        .unwrap_or_else(|| std::thread::available_parallelism().map_or(1, |v| v.get()));
    let mut args = args.peekable();
    if let Some(through) = args.peek().and_then(|arg| arg.strip_prefix("--through=")) {
        let through = through.parse::<i64>().map_err(|_| "invalid epoch limit")?;
        let through = u64::try_from(through).map_err(|_| "invalid epoch limit")?;
        args.next();
        let mut carry = Vec::new();
        for binding in args {
            let (source, previous) = binding.split_once('=').ok_or("expected source=previous")?;
            let source = graph.id(source).ok_or("unknown carry source")?;
            let previous = graph.id(previous).ok_or("unknown carry state")?;
            carry.push((source, previous));
        }
        let names: Vec<_> = graph.states.iter().map(|state| state.name.clone()).collect();
        let mut recurrence = Recurrence::new(graph, carry, &[], workers)?;
        loop {
            println!("epoch: {}", recurrence.epoch());
            for (id, name) in names.iter().enumerate() {
                println!("{name}: {}", recurrence.value(id).ok_or("incomplete epoch")?);
            }
            if recurrence.epoch() == through {
                return Ok(());
            }
            recurrence.advance(&[])?;
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
