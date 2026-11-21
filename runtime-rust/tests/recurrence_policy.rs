use doc_runtime::{recurrence::Recurrence, Graph, Value};

const HALTING: &str = include_str!("../examples/recurrence_halt.doc");

fn make(retention: usize) -> Recurrence {
    let graph = Graph::parse(HALTING).unwrap();
    let index = graph.id("index").unwrap();
    let successor = graph.id("successor").unwrap();
    Recurrence::new_with_retention(
        graph, vec![(index, successor)], &[], 2, retention
    ).unwrap()
}

#[test]
fn finite_demand_and_explicit_boolean_halt_are_distinct() {
    let mut r = make(3);
    r.demand_through(2).unwrap();
    assert_eq!(r.epoch(), 2);
    assert_eq!(r.value(0), Some(Value::Int(2)));
    assert_eq!(r.advance_until(3, 2).unwrap(), false);
    assert_eq!(r.epoch(), 2);
    assert_eq!(r.advance_until(3, 100).unwrap(), true);
    assert_eq!(r.epoch(), 3);
    assert_eq!(r.advance_until(3, 100).unwrap(), true);
    assert_eq!(r.epoch(), 3);
}

#[test]
fn retention_drops_old_epochs_but_owned_copies_survive() {
    let mut r = make(3);
    let epoch_zero_copy = r.snapshot_at(0).unwrap();
    r.demand_through(5).unwrap();
    assert_eq!(r.retained_epochs(), vec![3, 4, 5]);
    assert_eq!(r.snapshot_at(2), None);
    let old_three = r.snapshot_at(3).unwrap();
    assert_eq!(old_three[0], Some(Value::Int(3)));
    assert_eq!(r.snapshot_at(5).unwrap()[0], Some(Value::Int(5)));
    assert_eq!(epoch_zero_copy[0], Some(Value::Int(0)));
}

#[test]
fn invalid_retention_and_halt_type_fail_safely() {
    let g = Graph::parse(HALTING).unwrap();
    assert!(Recurrence::new_with_retention(g.clone(), vec![], &[], 1, 0).is_err());
    let mut r = make(2);
    let before = r.snapshot_at(0).unwrap();
    assert!(r.advance_until(0, 100).is_err());
    assert_eq!(r.snapshot_at(0), Some(before));
    assert_eq!(r.epoch(), 0);
}

#[test]
fn failed_epoch_cannot_publish_or_evict_previous_snapshots() {
    let graph = Graph::parse(
        "source counter: int = 9223372036854775806\n\
         derive successor: int (counter) = add(counter,1)\n"
    ).unwrap();
    let counter = graph.id("counter").unwrap();
    let successor = graph.id("successor").unwrap();
    let mut r=Recurrence::new_with_retention(graph,vec![(counter,successor)],&[],1,2).unwrap();
    let initial=r.snapshot_at(0).unwrap();
    assert!(r.advance(&[]).is_err());
    assert_eq!(r.epoch(),0);
    assert_eq!(r.retained_epochs(),vec![0]);
    assert_eq!(r.snapshot_at(0),Some(initial));
}

#[test]
fn explicit_facts_keep_epoch_local_authority() {
    let graph=Graph::parse(
        "source a: int = 2\nsource factor: int = 1\n\
         derive out: int (a,factor) = add(a,factor)\n"
    ).unwrap();
    let a=graph.id("a").unwrap();
    let factor=graph.id("factor").unwrap();
    let out=graph.id("out").unwrap();
    let mut r=Recurrence::new_with_retention(graph,vec![(a,out)],&[],1,2).unwrap();
    r.advance(&[(factor,Value::Int(7))]).unwrap();
    assert_eq!(r.value(out),Some(Value::Int(10)));
    r.advance(&[]).unwrap();
    assert_eq!(r.value(out),Some(Value::Int(11)));
    assert_eq!(r.retained_epochs(),vec![1,2]);
}
