use doc_runtime::{Cutoff, Graph, Runtime, Value};

#[test]
fn interlock_matches_truth_table_across_worker_settings() {
    let graph = Graph::parse(include_str!("../examples/boolean_interlock.doc")).unwrap();
    let request = graph.id("a").unwrap();
    let interlock = graph.id("b").unwrap();
    let allowed = graph.id("chosen").unwrap();

    for workers in [1, 4] {
        let mut runtime = Runtime::new(graph.clone(), workers, Cutoff::Exact);
        for (a, b) in [(false, false), (false, true), (true, true), (true, false)] {
            runtime
                .update(&[(request, Value::Bool(a)), (interlock, Value::Bool(b))])
                .unwrap();
            runtime.stabilize().unwrap();
            assert_eq!(runtime.value(allowed), Some(Value::Bool(a && b)));
        }
    }
}
