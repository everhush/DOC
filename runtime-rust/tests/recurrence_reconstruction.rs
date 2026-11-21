use doc_runtime::{Graph,Value,recurrence::Recurrence};

#[test]
fn authoritative_reconstruction_recovers_evicted_arbitrary_nat_epochs() {
    let graph=Graph::parse(
        "source n: nat = 9999999999999999999999999999999999999999\n\
         source extra: int = 10\n\
         derive next: nat (n) = add(n,nat(1))\n\
         derive view: int (extra) = add(extra,1)\n"
    ).unwrap();
    let n=graph.id("n").unwrap();
    let extra=graph.id("extra").unwrap();
    let next=graph.id("next").unwrap();
    let view=graph.id("view").unwrap();
    let mut recurrence=Recurrence::new_with_retention(
        graph,vec![(n,next)],&[],4,2).unwrap();
    let pinned=recurrence.snapshot_at(0).unwrap();
    for epoch in 1..=100 {
        let facts=if epoch==2 {vec![(extra,Value::Int(40))]}else{vec![]};
        recurrence.advance(&facts).unwrap();
    }
    assert_eq!(recurrence.retained_epochs(),vec![99,100]);
    assert!(recurrence.snapshot_at(2).is_none());
    assert_eq!(pinned[n],Some(Value::Nat(
        "9999999999999999999999999999999999999999".into())));
    let reconstructed0=recurrence.reconstruct_epoch(0).unwrap().unwrap();
    assert_eq!(reconstructed0,pinned);
    let reconstructed2=recurrence.reconstruct_epoch(2).unwrap().unwrap();
    assert_eq!(reconstructed2[view],Some(Value::Int(41)));
    let reconstructed3=recurrence.reconstruct_epoch(3).unwrap().unwrap();
    assert_eq!(reconstructed3[view],Some(Value::Int(11)));
    assert_eq!(reconstructed3[n],Some(Value::Nat(
        "10000000000000000000000000000000000000002".into())));
    let reconstructed100=recurrence.reconstruct_epoch(100).unwrap().unwrap();
    assert_eq!(reconstructed100[n],recurrence.value(n));
    assert!(recurrence.reconstruct_epoch(101).unwrap().is_none());
    assert_eq!(recurrence.epoch(),100);
}
#[test]
fn uncommitted_failed_epoch_cannot_be_reconstructed_or_republished() {
    let graph=Graph::parse(
        "source n: nat = 1\n\
         derive next: nat (n) = sub(n,nat(1))\n"
    ).unwrap();
    let mut recurrence=Recurrence::new_with_retention(
        graph,vec![(0,1)],&[],1,1).unwrap();
    let original=recurrence.snapshot_at(0).unwrap();
    assert!(recurrence.advance(&[]).is_err());
    assert_eq!(recurrence.epoch(),0);
    assert!(recurrence.reconstruct_epoch(1).unwrap().is_none());
    assert_eq!(recurrence.reconstruct_epoch(0).unwrap(),Some(original));
}
