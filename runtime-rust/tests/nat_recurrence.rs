use doc_runtime::{nat,recurrence::Recurrence,Cutoff,Graph,Runtime,Value};

#[test]
fn nat_literals_and_checked_arithmetic_exceed_i64() {
    let g=Graph::parse(include_str!("../examples/nat_recurrence.doc")).unwrap();
    let mut r=Runtime::new(g.clone(),2,Cutoff::Exact);
    r.stabilize().unwrap();
    let next=g.id("next").unwrap();
    let previous=g.id("previous").unwrap();
    assert_eq!(r.value(next).unwrap().to_string(),
               "100000000000000000000000000000000000000000000000000");
    assert_eq!(r.value(previous).unwrap().to_string(),
               "99999999999999999999999999999999999999999999999998");
    assert!(Graph::parse(
        "source a: nat = 0\n derive bad: nat (a) = sub(a,nat(1))\n"
    ).is_ok()); // a dynamic failure; not an ill-typed expression
    assert!(nat::canonical("-1").is_err());
}
#[test]
fn unbounded_nat_is_carried_by_original_doc_recurrence() {
    let g=Graph::parse(
        "source a: nat = 99999999999999999999999999999999999999999999999999\n\
         derive next: nat (a) = add(a,nat(1))\n\
         derive stop: bool (a) = eq(a,nat(10000000000000000000000000000000000000000000000002))\n"
    ).unwrap();
    let a=g.id("a").unwrap();
    let next=g.id("next").unwrap();
    let stop=g.id("stop").unwrap();
    let mut rec=Recurrence::new(g,vec![(a,next)],&[],1).unwrap();
    assert!(rec.advance_until(stop,4).unwrap());
    assert_eq!(rec.epoch(),3);
    assert_eq!(rec.value(a).unwrap().to_string(),
              "10000000000000000000000000000000000000000000000002");
}
#[test]
fn nat_underflow_does_not_publish_failed_candidate() {
    let g=Graph::parse("source a: nat = 0\n\
        derive bad: nat (a) = sub(a,nat(1))\n").unwrap();
    let mut r=Runtime::new(g,1,Cutoff::Exact);
    let before=r.snapshot();
    assert!(r.stabilize().is_err());
    assert_eq!(r.snapshot(),before);
}
