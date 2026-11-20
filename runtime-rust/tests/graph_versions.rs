//! Conservative graph-generation replacement and failure-atomic publication.
use doc_runtime::{Cutoff,Graph,Runtime,Value};

fn original() -> Graph {
    Graph::parse("source amount: int = 2\n\
                  derive total: int (amount) = add(amount,1)\n").unwrap()
}
fn changed_definition() -> Graph {
    Graph::parse("source amount: int = 99\n\
                  source extra: bool = true\n\
                  derive total: int (amount) = mul(amount,2)\n").unwrap()
}

#[test]
fn carries_compatible_source_but_not_outdated_derived_value() {
    for workers in [1,2,4] {
        let mut rt=Runtime::new(original(),workers,Cutoff::Exact);
        rt.stabilize().unwrap();
        rt.update(&[(rt.graph.id("amount").unwrap(),Value::Int(7))]).unwrap();
        rt.stabilize().unwrap();
        assert_eq!(rt.value(rt.graph.id("total").unwrap()),Some(Value::Int(8)));
        let pinned_owned_copy=rt.snapshot();
        rt.replace_graph(changed_definition()).unwrap();
        assert_eq!(rt.generation,1);
        assert_eq!(rt.value(rt.graph.id("amount").unwrap()),Some(Value::Int(7)));
        assert_eq!(rt.value(rt.graph.id("extra").unwrap()),Some(Value::Bool(true)));
        assert_eq!(rt.value(rt.graph.id("total").unwrap()),Some(Value::Int(14)));
        assert_eq!(pinned_owned_copy,vec![Some(Value::Int(7)),Some(Value::Int(8))]);
        assert!(rt.stable());
        assert_eq!(rt.snapshot().into_iter().map(Option::unwrap).collect::<Vec<_>>(),
                   rt.oracle().unwrap());
    }
}

#[test]
fn failed_candidate_preserves_graph_values_generation_and_readers() {
    let mut rt=Runtime::new(original(),2,Cutoff::Exact);
    rt.stabilize().unwrap();
    let before=rt.snapshot();
    let candidate=Graph::parse(
        "source amount: int = 0\n\
         derive broken: int (amount) = add(amount,9223372036854775807)\n"
    ).unwrap();
    assert!(rt.replace_graph(candidate).is_err());
    assert_eq!(rt.generation,0);
    assert_eq!(rt.snapshot(),before);
    assert!(rt.graph.id("total").is_some());
    assert!(rt.graph.id("broken").is_none());
}

#[test]
fn candidate_source_role_and_type_changes_do_not_leak_old_value() {
    let mut rt=Runtime::new(original(),1,Cutoff::Exact);
    rt.stabilize().unwrap();
    let candidate=Graph::parse(
        "source amount: bool = true\n\
         derive total: bool (amount) = if(amount,true,false)\n"
    ).unwrap();
    rt.replace_graph(candidate).unwrap();
    assert_eq!(rt.value(rt.graph.id("amount").unwrap()),Some(Value::Bool(true)));
    assert_eq!(rt.value(rt.graph.id("total").unwrap()),Some(Value::Bool(true)));
    assert_eq!(rt.generation,1);
}

#[test]
fn unstable_replacement_and_stale_tokens_are_rejected() {
    let mut rt=Runtime::new(original(),1,Cutoff::Conservative);
    let before=rt.snapshot();
    assert!(rt.replace_graph(changed_definition()).is_err());
    assert_eq!(rt.snapshot(),before);
    rt.stabilize().unwrap();
    let saved=rt.snapshot_for_generation(0).unwrap();
    rt.replace_graph(changed_definition()).unwrap();
    let current=rt.snapshot();
    assert!(rt.snapshot_for_generation(0).is_none());
    assert!(rt.step_for_generation(0,&[2]).is_err());
    assert_eq!(rt.snapshot(),current);
    assert_eq!(saved,vec![Some(Value::Int(2)),Some(Value::Int(3))]);
}
