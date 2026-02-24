//! CPU smoke test, not comparable to HVM.
use doc_runtime::{Cutoff, Expr, Graph, Runtime, State, Type, Value};
use std::time::Instant;
fn main() {
    let width = std::env::var("DOC_BENCH_WIDTH").ok().and_then(|v| v.parse::<usize>().ok())
        .unwrap_or(4096).clamp(1, 100_000);
    let workers = std::env::var("DOC_WORKERS").ok().and_then(|v| v.parse::<usize>().ok())
        .unwrap_or(1).clamp(1, 128);
    let mut states = vec![State::source("seed", Value::Int(1))];
    for i in 0..width {
        states.push(State::derived(format!("d{i}"), Type::Int, vec![0],
            Expr::Add(Box::new(Expr::Arg(0)), Box::new(Expr::Lit(Value::Int(i as i64))))));
    }
    let graph = Graph::new(states).expect("graph");
    let start = Instant::now();
    for i in 0..10 {
        let mut rt = Runtime::new(graph.clone(), workers, Cutoff::Exact);
        rt.update(&[(0, Value::Int(i))]).expect("update");
        rt.stabilize().expect("stabilize");
        assert_eq!(rt.value(width), Some(Value::Int(width as i64 - 1 + i)));
        assert_eq!(rt.value(width), Some(rt.oracle().unwrap()[width]));
    }
    println!("width={width} workers={workers} runs=10 elapsed_ms={:.3}", start.elapsed().as_secs_f64()*1000.0);
}
