use doc_runtime::{Cutoff,Graph,ObservationToken,Runtime,Value};

fn graph() -> Graph {
    Graph::parse("source a: int = 1\nsource b: int = 2\n\
                  derive sum: int (a,b) = add(a,b)\n").unwrap()
}
#[test]
fn source_updates_invalidate_prior_gpu_observation_tokens_once_per_batch() {
    let mut rt=Runtime::new(graph(),2,Cutoff::Exact);
    rt.stabilize().unwrap();
    let original=rt.observation_token();
    assert_eq!(original.source_epoch,0);
    let a=rt.graph.id("a").unwrap();
    let b=rt.graph.id("b").unwrap();
    rt.update(&[(a,Value::Int(5)),(b,Value::Int(7))]).unwrap();
    assert_eq!(rt.source_epoch,1);
    assert!(rt.validate_observation_token(original).is_err());
    let second=rt.observation_token();
    rt.update(&[(a,Value::Int(5)),(b,Value::Int(7))]).unwrap();
    assert_eq!(rt.observation_token(),second);
    rt.update(&[]).unwrap();
    assert_eq!(rt.observation_token(),second);
    assert!(rt.update(&[(a,Value::Int(8)),(a,Value::Int(9))]).is_err());
    assert!(rt.update(&[(a,Value::Bool(true))]).is_err());
    assert_eq!(rt.observation_token(),second);
    rt.stabilize().unwrap();
    assert_eq!(rt.value(rt.graph.id("sum").unwrap()),Some(Value::Int(12)));
    rt.validate_observation_token(second).unwrap();
}
#[test]
fn graph_replacement_invalidates_candidate_tokens_even_if_source_values_equal() {
    let mut rt=Runtime::new(graph(),1,Cutoff::Exact);
    rt.stabilize().unwrap();
    let previous=rt.observation_token();
    rt.replace_graph(graph()).unwrap();
    assert_eq!(rt.generation,1);
    assert_eq!(rt.source_epoch,1);
    assert!(rt.validate_observation_token(previous).is_err());
    rt.validate_observation_token(rt.observation_token()).unwrap();
}
#[test]
fn source_epoch_overflow_fails_without_any_partial_batch_mutation() {
    let mut rt=Runtime::new(graph(),1,Cutoff::Exact);
    rt.stabilize().unwrap();
    rt.source_epoch=u64::MAX;
    let before=rt.snapshot();
    let old=rt.observation_token();
    let a=rt.graph.id("a").unwrap();
    assert!(rt.update(&[(a,Value::Int(3))]).is_err());
    assert_eq!(before,rt.snapshot());
    assert_eq!(old,rt.observation_token());
    assert!(rt.replace_graph(graph()).is_err());
    assert_eq!(old,rt.observation_token());
}
#[test]
fn distinct_tokens_rejected_without_exposing_partially_evaluated_frontier() {
    let mut rt=Runtime::new(graph(),4,Cutoff::Exact);
    rt.stabilize().unwrap();
    let t=rt.observation_token();
    let forged=ObservationToken{source_epoch:t.source_epoch+1,..t};
    assert!(rt.validate_observation_token(forged).is_err());
    assert_eq!(rt.value(rt.graph.id("sum").unwrap()),Some(Value::Int(3)));
}
