//! Finite DOC locality, repeated-premise and batch-oracle conformance.
//! No recurrence, physical memory, or placement claims follow from these tests.
use doc_runtime::{Cutoff, Graph, Runtime, Value};

fn graph() -> Graph {
    Graph::parse(
        "source a: int = 2\n\
         source b: int = 7\n\
         derive twice: int (a) = add(a,a)\n\
         derive unrelated: int (b) = mul(b,3)\n\
         derive output: int (twice,unrelated) = add(twice,unrelated)\n",
    ).unwrap()
}

#[test]
fn duplicate_occurrences_and_unrelated_reuse() {
    for workers in [1, 2, 4] {
        for cutoff in [Cutoff::Exact, Cutoff::Conservative] {
            let mut rt = Runtime::new(graph(), workers, cutoff);
            rt.stabilize().unwrap();
            assert_eq!(rt.value(2), Some(Value::Int(4)));
            assert_eq!(rt.value(3), Some(Value::Int(21)));
            assert_eq!(rt.value(4), Some(Value::Int(25)));
            let before = rt.stats.evaluations;
            rt.update(&[(0, Value::Int(5))]).unwrap();
            rt.stabilize().unwrap();
            assert_eq!(rt.value(2), Some(Value::Int(10)));
            assert_eq!(rt.value(3), Some(Value::Int(21)));
            assert_eq!(rt.value(4), Some(Value::Int(31)));
            assert_eq!(rt.stats.evaluations - before, 2);
            assert_eq!(
                rt.snapshot().into_iter().map(Option::unwrap).collect::<Vec<_>>(),
                rt.oracle().unwrap()
            );
        }
    }
}

#[test]
fn same_value_exact_cutoff_prevents_downstream_recomputation() {
    for workers in [1, 2, 4] {
        let mut rt = Runtime::new(graph(), workers, Cutoff::Exact);
        rt.stabilize().unwrap();
        let before = rt.stats.evaluations;
        rt.update(&[(0, Value::Int(2))]).unwrap();
        rt.stabilize().unwrap();
        assert_eq!(rt.stats.evaluations, before);
        assert_eq!(rt.value(4), Some(Value::Int(25)));
    }
}

#[test]
fn invalid_multi_source_batch_is_all_or_nothing() {
    for workers in [1, 2, 4] {
        let mut rt = Runtime::new(graph(), workers, Cutoff::Exact);
        rt.stabilize().unwrap();
        let before = rt.snapshot();
        let ready = rt.ready();
        assert!(rt.update(&[
            (0, Value::Int(9)),
            (1, Value::Bool(false)),
        ]).is_err());
        assert_eq!(rt.snapshot(), before);
        assert_eq!(rt.ready(), ready);
        rt.update(&[(0, Value::Int(9)), (1, Value::Int(1))]).unwrap();
        rt.stabilize().unwrap();
        assert_eq!(rt.value(4), Some(Value::Int(21)));
        assert_eq!(
            rt.snapshot().into_iter().map(Option::unwrap).collect::<Vec<_>>(),
            rt.oracle().unwrap()
        );
    }
}
