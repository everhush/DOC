use doc_runtime::{recurrence::Recurrence, Graph, Value};

const TEMPLATE: &str = "source cursor: int = 0
source delta: int = 1
derive successor: int (cursor,delta) = add(cursor,delta)
derive halt: bool (cursor) = eq(cursor,4)
";

#[test]
fn demand_stops_at_halt_and_uses_epoch_local_facts() {
    let graph = Graph::parse(TEMPLATE).unwrap();
    let cursor = graph.id("cursor").unwrap();
    let successor = graph.id("successor").unwrap();
    let delta = graph.id("delta").unwrap();
    let halt = graph.id("halt").unwrap();
    let mut recurrence = Recurrence::new(graph, vec![(cursor, successor)], &[], 4).unwrap();
    let mut observed = Vec::new();
    loop {
        observed.push(recurrence.value(cursor).unwrap());
        if recurrence.value(halt) == Some(Value::Bool(true)) {
            break;
        }
        assert!(recurrence.epoch() < 5);
        let facts = if recurrence.epoch() == 0 {
            &[(delta, Value::Int(2))][..]
        } else {
            &[]
        };
        recurrence.advance(facts).unwrap();
    }
    assert_eq!(observed, [0, 1, 3, 4].map(Value::Int));
    assert_eq!(recurrence.epoch(), 3);
}

#[test]
fn conflicts_and_failed_epoch_preserve_the_latest_stable_values() {
    let graph = Graph::parse(TEMPLATE).unwrap();
    let cursor = graph.id("cursor").unwrap();
    let successor = graph.id("successor").unwrap();
    let delta = graph.id("delta").unwrap();
    let halt = graph.id("halt").unwrap();
    assert!(Recurrence::new(
        graph.clone(),
        vec![(cursor, successor), (cursor, delta)],
        &[],
        1
    )
    .is_err());
    assert!(Recurrence::new(graph.clone(), vec![(cursor, halt)], &[], 1).is_err());
    let mut recurrence = Recurrence::new(
        graph,
        vec![(cursor, successor)],
        &[(cursor, Value::Int(i64::MAX - 1))],
        1,
    )
    .unwrap();
    assert!(recurrence.advance(&[(cursor, Value::Int(0))]).is_err());
    assert!(recurrence.advance(&[]).is_err());
    assert_eq!(recurrence.epoch(), 0);
    assert_eq!(recurrence.value(cursor), Some(Value::Int(i64::MAX - 1)));
    recurrence.advance(&[(delta, Value::Int(0))]).unwrap();
    assert_eq!(recurrence.epoch(), 1);
    assert_eq!(recurrence.value(cursor), Some(Value::Int(i64::MAX)));
}
