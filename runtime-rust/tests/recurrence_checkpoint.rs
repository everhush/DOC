//! Reusable DOC state restore from source-owned typed facts, no game-specific behavior.
use doc_runtime::{recurrence::Recurrence,Graph,Value};

fn graph()->Graph { Graph::parse(include_str!("../examples/list_fold.doc")).unwrap() }
fn new(g:&Graph)->Recurrence {
    let carry=[("remaining","next_remaining"),("total","next_total")].iter()
        .map(|&(a,b)|(g.id(a).unwrap(),g.id(b).unwrap())).collect();
    Recurrence::new_with_retention(g.clone(),carry,&[],4,2).unwrap()
}
#[test]
fn source_checkpoint_and_restarted_recurrence_preserve_logical_state() {
    let g=graph();
    let mut live=new(&g);
    live.advance(&[]).unwrap();
    live.advance(&[]).unwrap();
    let facts=live.current_source_facts().unwrap();
    assert_eq!(facts.len(),2);
    let mut restarted=live.fork_current().unwrap();
    assert_eq!(restarted.epoch(),0,"a fork has a new epoch identity");
    assert_eq!(restarted.current_source_facts().unwrap(),facts);
    for id in 0..g.states.len() {
        assert_eq!(live.value(id),restarted.value(id),"fork changed DOC valuation");
    }
    let restored_snapshot=restarted.snapshot_at(0).unwrap();
    live.advance(&[]).unwrap();
    assert_eq!(restarted.snapshot_at(0).unwrap(),restored_snapshot);
    restarted.advance(&[]).unwrap();
    for id in 0..g.states.len() {
        assert_eq!(live.value(id),restarted.value(id),"suffix diverged after restore");
    }
    assert_eq!(restarted.reconstruct_epoch(0).unwrap().unwrap(),restored_snapshot);
    assert_eq!(live.epoch(),3);
    assert_eq!(restarted.epoch(),1);
}
#[test]
fn restored_carried_authority_still_rejects_mutation_and_retains_snapshot() {
    let g=graph();
    let live=new(&g);
    let mut copy=live.fork_current().unwrap();
    let original=copy.snapshot_at(0).unwrap();
    assert!(copy.advance(&[(g.id("remaining").unwrap(),Value::Ints(vec![5]))]).is_err());
    assert_eq!(copy.epoch(),0);
    assert_eq!(copy.snapshot_at(0).unwrap(),original);
    copy.advance(&[]).unwrap();
    assert_eq!(live.epoch(),0);
    assert_eq!(live.snapshot_at(0).unwrap(),original);
}
