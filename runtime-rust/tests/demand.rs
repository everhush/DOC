use doc_runtime::{Cutoff, Graph, Runtime, Value};

#[test]
fn only_ancestor_closed_demand_is_evaluated_and_failure_is_isolated() {
    let graph=Graph::parse(include_str!("../examples/demand_lazy.doc")).unwrap();
    let target=graph.id("target").unwrap();
    let broken=graph.id("broken").unwrap();
    let copy=graph.id("copy").unwrap();
    let a=graph.id("a").unwrap();
    for workers in [1,2,4] {
        let mut rt=Runtime::new(graph.clone(),workers,Cutoff::Exact);
        assert!(rt.stabilize_requested(&[]).is_err());
        assert!(rt.stabilize_requested(&[graph.states.len()]).is_err());
        rt.stabilize_requested(&[target]).unwrap();
        assert_eq!(rt.value(target),Some(Value::Int(3)));
        assert_eq!(rt.value(broken),None);
        assert_eq!(rt.value(copy),None);
        rt.stabilize_requested(&[copy]).unwrap();
        assert_eq!(rt.value(copy),Some(Value::Int(4)));
        assert!(rt.stabilize_requested(&[broken]).is_err());
        assert_eq!(rt.value(copy),Some(Value::Int(4)));
        rt.update(&[(a,Value::Int(7))]).unwrap();
        rt.stabilize_requested(&[copy]).unwrap();
        assert_eq!(rt.value(copy),Some(Value::Int(10)));
        assert_eq!(rt.value(broken),None);
    }
}

#[test]
fn demanded_observation_matches_complete_oracle_when_total() {
    let program="source a: int = 2\nsource b: int = 5\n\
                 derive sum: int (a,b) = add(a,b)\n\
                 derive diff: int (a,b) = sub(a,b)\n\
                 derive result: int (sum) = mul(sum,3)\n";
    let graph=Graph::parse(program).unwrap();
    let sum=graph.id("sum").unwrap();
    let result=graph.id("result").unwrap();
    let mut partial=Runtime::new(graph.clone(),4,Cutoff::Exact);
    partial.stabilize_requested(&[result]).unwrap();
    let mut complete=Runtime::new(graph,1,Cutoff::Exact);
    complete.stabilize().unwrap();
    assert_eq!(partial.value(result),complete.value(result));
    assert_eq!(partial.value(sum),complete.value(sum));
    assert_eq!(partial.value(3),None);
    assert!(!partial.stable());
    partial.stabilize().unwrap();
    assert_eq!(partial.snapshot(),complete.snapshot());
}
