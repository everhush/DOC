use doc_runtime::{recurrence::Recurrence,Graph,Value};

#[test]
fn nat_snapshots_remain_owned_and_readable_across_long_automatic_eviction() {
    // 120 decimal digits exceed the representable i64 and preserve the exact
    // value when a prior published generation is retained by an active reader.
    let seed="9".repeat(120);
    let program=format!(
        "source a: nat = {seed}\n\
         derive next: nat (a) = add(a,nat(1))\n"
    );
    let g=Graph::parse(&program).unwrap();
    let a=g.id("a").unwrap();
    let next=g.id("next").unwrap();
    let mut recurrence=Recurrence::new_with_retention(
        g,vec![(a,next)],&[],4,4
    ).unwrap();
    let protected=recurrence.snapshot_at(0).unwrap();
    let pinned=&protected;
    std::thread::scope(|scope| {
        let reader=scope.spawn(move || {
            for _ in 0..1000 {
                assert_eq!(pinned[a],Some(Value::Nat(seed.clone())));
            }
        });
        recurrence.demand_through(400).unwrap();
        reader.join().unwrap();
    });
    assert_eq!(recurrence.epoch(),400);
    assert_eq!(recurrence.retained_epochs(),vec![397,398,399,400]);
    assert!(recurrence.snapshot_at(0).is_none());
    assert_eq!(protected[a],Some(Value::Nat("9".repeat(120))));
    let expected=format!("1{}399","0".repeat(117));
    assert_eq!(recurrence.value(a),Some(Value::Nat(expected)));
    assert_eq!(recurrence.snapshot_at(400).unwrap()[a],recurrence.value(a));
}

#[test]
fn failed_nat_epoch_cannot_replace_or_evict_stable_owned_generation() {
    let graph=Graph::parse(
        "source a: nat = 0\n\
         derive next: nat (a) = sub(a,nat(1))\n"
    ).unwrap();
    // The invalid candidate happens in the original epoch, and no published
    // recurrence is created. A failed constructor has no published snapshot.
    assert!(Recurrence::new_with_retention(
        graph,vec![(0,1)],&[],2,2
    ).is_err());
    let graph=Graph::parse(
        "source a: nat = 1\n\
         derive next: nat (a) = sub(a,nat(1))\n"
    ).unwrap();
    let mut recurrence=Recurrence::new_with_retention(
        graph,vec![(0,1)],&[],2,2
    ).unwrap();
    let before=recurrence.snapshot_at(0).unwrap();
    assert_eq!(recurrence.epoch(),0);
    assert!(recurrence.advance(&[]).is_err());
    assert_eq!(recurrence.epoch(),0);
    assert_eq!(recurrence.retained_epochs(),vec![0]);
    assert_eq!(recurrence.snapshot_at(0),Some(before));
}
