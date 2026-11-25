//! Reproducible local Linux CPU measurement, not GPU nor cross-machine comparison.
//! Every trial includes Runtime construction, update, stabilization and oracle.
//! Allocation calls/bytes are CUMULATIVE requests (not retained heap size).
use doc_runtime::{Cutoff, Expr, Graph, Runtime, State, Type, Value};
use std::{
    alloc::{GlobalAlloc,Layout,System},
    sync::atomic::{AtomicU64,Ordering},
    time::Instant,
};
struct CountingAllocator;
static ALLOCATION_CALLS:AtomicU64=AtomicU64::new(0);
static ALLOCATED_BYTES:AtomicU64=AtomicU64::new(0);
#[global_allocator]
static ALLOCATOR:CountingAllocator=CountingAllocator;
unsafe impl GlobalAlloc for CountingAllocator {
    unsafe fn alloc(&self,layout:Layout)->*mut u8{
        ALLOCATION_CALLS.fetch_add(1,Ordering::Relaxed);
        ALLOCATED_BYTES.fetch_add(layout.size() as u64,Ordering::Relaxed);
        System.alloc(layout)
    }
    unsafe fn realloc(&self,ptr:*mut u8,layout:Layout,new_size:usize)->*mut u8{
        ALLOCATION_CALLS.fetch_add(1,Ordering::Relaxed);
        ALLOCATED_BYTES.fetch_add(new_size as u64,Ordering::Relaxed);
        System.realloc(ptr,layout,new_size)
    }
    unsafe fn dealloc(&self,ptr:*mut u8,layout:Layout){System.dealloc(ptr,layout);}
}
fn peak_rss_kib()->Option<u64>{
    let contents=std::fs::read_to_string("/proc/self/status").ok()?;
    contents.lines().find_map(|line|line.strip_prefix("VmHWM:"))
        .and_then(|v|v.split_whitespace().next()?.parse::<u64>().ok())
}
fn main() {
    let width = std::env::var("DOC_BENCH_WIDTH").ok().and_then(|v| v.parse::<usize>().ok())
        .unwrap_or(4096).clamp(1, 100_000);
    let workers = std::env::var("DOC_WORKERS").ok().and_then(|v| v.parse::<usize>().ok())
        .unwrap_or(0);
    let mut states = vec![State::source("seed", Value::Int(1))];
    for i in 0..width {
        states.push(State::derived(format!("d{i}"), Type::Int, vec![0],
            Expr::Add(Box::new(Expr::Arg(0)), Box::new(Expr::Lit(Value::Int(i as i64))))));
    }
    let graph = Graph::new(states).expect("graph");
    const RUNS:usize=10;
    let start = Instant::now();
    let before_calls=ALLOCATION_CALLS.load(Ordering::Relaxed);
    let before_bytes=ALLOCATED_BYTES.load(Ordering::Relaxed);
    let mut per_trial_us=Vec::with_capacity(RUNS);
    for i in 0..RUNS {
        let sample=Instant::now();
        let mut rt = Runtime::new(graph.clone(), workers, Cutoff::Exact);
        rt.update(&[(0, Value::Int(i as i64))]).expect("update");
        rt.stabilize().expect("stabilize");
        assert_eq!(rt.value(width), Some(Value::Int(width as i64 - 1 + i as i64)));
        assert_eq!(rt.value(width), Some(rt.oracle().unwrap()[width].clone()));
        per_trial_us.push(sample.elapsed().as_micros());
    }
    let elapsed_ms=start.elapsed().as_secs_f64()*1000.0;
    let calls=ALLOCATION_CALLS.load(Ordering::Relaxed)-before_calls;
    let allocated_bytes=ALLOCATED_BYTES.load(Ordering::Relaxed)-before_bytes;
    per_trial_us.sort_unstable();
    let p50=per_trial_us[(RUNS*50-1)/100];
    let p95=per_trial_us[(RUNS*95-1)/100];
    let peak=peak_rss_kib().map(|v|v.to_string()).unwrap_or_else(||"unavailable".into());
    println!("width={width} workers={workers} runs={RUNS} elapsed_ms={elapsed_ms:.3}");
    println!("DOC_BENCH_CPU_MEASURED: width={width} workers={workers} runs={RUNS} profile={} p50_us={p50} p95_us={p95} alloc_calls={calls} cumulative_alloc_request_bytes={allocated_bytes} process_peak_rss_kib={peak} measurement=cold_runtime_plus_oracle",
        if cfg!(debug_assertions){"debug"}else{"release"});
}
