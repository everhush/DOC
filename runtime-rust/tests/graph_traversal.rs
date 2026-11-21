use doc_runtime::{Graph,Value,recurrence::Recurrence};

#[test]
fn graph_traversal_is_executed_by_the_doc_recurrence_not_host_code() {
    let graph=Graph::parse(include_str!("../examples/graph_walk.doc")).unwrap();
    let node=graph.id("node").unwrap();
    let hops=graph.id("hops").unwrap();
    let halt=graph.id("halt").unwrap();
    for workers in [1,2,4] {
        let mut rt=Recurrence::new_with_retention(
            graph.clone(),vec![(node,graph.id("next_node").unwrap()),
                (hops,graph.id("next_hops").unwrap())],
            &[],workers,2
        ).unwrap();
        let snapshot=rt.snapshot_at(0).unwrap();
        assert!(rt.advance_until(halt,10).unwrap());
        assert_eq!(rt.epoch(),2);
        assert_eq!(rt.value(node),Some(Value::Int(-1)));
        assert_eq!(rt.value(hops),Some(Value::Int(2)));
        assert_eq!(snapshot[node],Some(Value::Int(0)));
        assert_eq!(rt.retained_epochs(),vec![1,2]);
    }
}
#[test]
fn finite_demand_cap_does_not_claim_nontermination_or_halt_on_cycle() {
    let src=include_str!("../examples/graph_walk.doc")
        .replace("[2,4,-1,1,3]","[0]");
    let graph=Graph::parse(&src).unwrap();
    let node=graph.id("node").unwrap();
    let hops=graph.id("hops").unwrap();
    let halt=graph.id("halt").unwrap();
    let mut rt=Recurrence::new(graph.clone(),
        vec![(node,graph.id("next_node").unwrap()),
             (hops,graph.id("next_hops").unwrap())],&[],1).unwrap();
    assert!(!rt.advance_until(halt,100).unwrap());
    assert_eq!(rt.epoch(),100);
    assert_eq!(rt.value(node),Some(Value::Int(0)));
    assert_eq!(rt.value(hops),Some(Value::Int(100)));
}
