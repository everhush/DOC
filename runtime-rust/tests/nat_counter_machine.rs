use doc_runtime::{Graph,Value,recurrence::Recurrence};
#[test]
fn a_real_doc_program_simulates_the_two_counter_transfer_machine() {
    let graph=Graph::parse(include_str!("../examples/nat_counter_machine.doc")).unwrap();
    let pc=graph.id("pc").unwrap();
    let a=graph.id("a").unwrap();
    let b=graph.id("b").unwrap();
    let next_pc=graph.id("pc_next").unwrap();
    let next_a=graph.id("a_next").unwrap();
    let next_b=graph.id("b_next").unwrap();
    let halt=graph.id("halt").unwrap();
    for workers in [1,2,4] {
        let mut recurrence=Recurrence::new(graph.clone(),
            vec![(pc,next_pc),(a,next_a),(b,next_b)],&[],workers).unwrap();
        assert!(recurrence.advance_until(halt,8).unwrap());
        assert_eq!(recurrence.epoch(),7);
        assert_eq!(recurrence.value(pc),Some(Value::Nat("2".into())));
        assert_eq!(recurrence.value(a),Some(Value::Nat("0".into())));
        assert_eq!(recurrence.value(b),Some(Value::Nat("3".into())));
    }
}
#[test]
fn large_natural_counter_prefix_is_finite_and_exact() {
    let program=include_str!("../examples/nat_counter_machine.doc")
        .replace("source a: nat = 3","source a: nat = 9999999999999999999999999999999999999999");
    let graph=Graph::parse(&program).unwrap();
    let a=graph.id("a").unwrap();
    let next_a=graph.id("a_next").unwrap();
    let pc=graph.id("pc").unwrap();
    let next_pc=graph.id("pc_next").unwrap();
    let b=graph.id("b").unwrap();
    let next_b=graph.id("b_next").unwrap();
    let mut rt=Recurrence::new(graph,vec![(a,next_a),(pc,next_pc),(b,next_b)],&[],1).unwrap();
    rt.demand_through(20).unwrap();
    assert_eq!(rt.epoch(),20);
    assert_eq!(rt.value(a),Some(Value::Nat(
        "9999999999999999999999999999999999999989".into())));
    assert_eq!(rt.value(b),Some(Value::Nat("10".into())));
}
