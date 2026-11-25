use doc_runtime::{Cutoff, Expr, Graph, Runtime, State, Type, Value};
fn example() -> Graph {
    Graph::parse("source a: int = 2\nsource b: int = 3\n\
        derive sum: int (a,b) = add(a,b)\n\
        derive doubled: int (sum) = mul(sum,2)\n").unwrap()
}
#[test] fn initialization_and_cutoff() {
    let mut rt = Runtime::new(example(), 1, Cutoff::Exact);
    rt.stabilize().unwrap();
    assert_eq!(rt.value(2), Some(Value::Int(5)));
    assert_eq!(rt.value(3), Some(Value::Int(10)));
    rt.update(&[(0,Value::Int(4)),(1,Value::Int(1))]).unwrap();
    rt.stabilize().unwrap();
    assert_eq!(rt.value(3), Some(Value::Int(10)));
    assert_eq!(rt.stats.cutoffs, 1);
    assert_eq!(rt.stats.evaluations, 3);
}
#[test] fn conservative_propagates() {
    let mut rt = Runtime::new(example(), 1, Cutoff::Conservative);
    rt.stabilize().unwrap();
    rt.update(&[(0,Value::Int(4)),(1,Value::Int(1))]).unwrap();
    rt.stabilize().unwrap();
    assert_eq!(rt.stats.evaluations, 4);
    assert_eq!(rt.stats.cutoffs, 0);
}
#[test] fn failed_batch_is_atomic() {
    let mut rt = Runtime::new(example(), 1, Cutoff::Exact);
    let before = rt.snapshot();
    assert!(rt.update(&[(0,Value::Int(99)),(2,Value::Int(1))]).is_err());
    assert_eq!(rt.snapshot(), before);
    assert!(rt.update(&[(0,Value::Int(5)),(0,Value::Int(6))]).is_err());
}
#[test] fn subset_schedules_agree_with_oracle() {
    let mut rt = Runtime::new(Graph::parse(
        "source a: int = 2\n\
         derive b: int (a) = add(a,1)\n\
         derive c: int (a) = mul(a,3)\n\
         derive d: int (b,c) = add(b,c)\n").unwrap(), 2, Cutoff::Exact);
    assert_eq!(rt.ready(), vec![1,2]);
    assert!(rt.step(&[1,3]).is_err());
    rt.step(&[2]).unwrap();
    rt.step(&[1]).unwrap();
    rt.step(&[3]).unwrap();
    assert!(rt.stable());
    assert_eq!(rt.value(3), Some(Value::Int(9)));
    assert_eq!(rt.snapshot().into_iter().map(Option::unwrap).collect::<Vec<_>>(), rt.oracle().unwrap());
}
#[test] fn failed_frontier_does_not_publish() {
    let mut rt = Runtime::new(Graph::parse(
        "source a: int = 2\n\
         derive good: int (a) = add(a,1)\n\
         derive overflow: int (a) = add(a,9223372036854775807)\n"
    ).unwrap(),4,Cutoff::Exact);
    let before=rt.snapshot();
    assert!(rt.stabilize().is_err());
    assert_eq!(before,rt.snapshot());
    assert_eq!(rt.ready(),vec![1,2]);
}
#[test] fn invalid_programs_are_rejected() {
    assert!(Graph::new(vec![
        State::derived("a",Type::Int,vec![1],Expr::Arg(0)),
        State::derived("b",Type::Int,vec![0],Expr::Arg(0))
    ]).is_err());
    assert!(Graph::parse("source a: bool = 4").is_err());
    assert!(Graph::parse("source a: int = 1\nsource a: int = 2").is_err());
}
#[test] fn parallel_matches_sequential() {
    let mut states=vec![State::source("seed",Value::Int(1))];
    for i in 0..1000 {
        states.push(State::derived(format!("item{i}"),Type::Int,vec![0],
            Expr::Add(Box::new(Expr::Arg(0)),Box::new(Expr::Lit(Value::Int(i))))));
    }
    let graph=Graph::new(states).unwrap();
    let mut a=Runtime::new(graph.clone(),1,Cutoff::Exact);
    let mut b=Runtime::new(graph,4,Cutoff::Exact);
    for n in 1..10 {
        a.update(&[(0,Value::Int(n))]).unwrap();
        b.update(&[(0,Value::Int(n))]).unwrap();
        a.stabilize().unwrap();
        b.stabilize().unwrap();
        assert_eq!(a.snapshot(),b.snapshot());
        assert_eq!(a.snapshot().into_iter().map(Option::unwrap).collect::<Vec<_>>(),a.oracle().unwrap());
    }
}


#[test]
fn host_constructed_naturals_cannot_bypass_typed_admission(){
    use doc_runtime::resources::DataResources;
    let graph=Graph::parse("source n: nat = 0012\nsource flag: bool = false\nderive next: nat (n) = add(n,nat(1))\n").unwrap();
    let mut rt=Runtime::new(graph.clone(),1,Cutoff::Exact);
    rt.stabilize().unwrap();
    let before=rt.snapshot();
    let token=rt.observation_token();
    let mut resources=DataResources::new(2,128).unwrap();
    let handle=resources.insert(Value::Nat("12".into())).unwrap();
    for raw in ["","00","012","-1","abc","/","é"] {
        let invalid=Value::Nat(raw.into());
        assert!(Graph::new(vec![State::source("bad",invalid.clone())]).is_err());
        assert!(Graph::new(vec![State::derived("bad",Type::Nat,vec![],Expr::Lit(invalid.clone()))]).is_err());
        assert!(Expr::Lit(invalid.clone()).eval(&[]).is_err());
        assert!(Expr::Arg(0).eval(&[invalid.clone()]).is_err());
        assert!(rt.update(&[(1,Value::Bool(true)),(0,invalid.clone())]).is_err());
        assert_eq!(rt.snapshot(),before);
        assert_eq!(rt.observation_token(),token);
        assert!(rt.stable());
        assert!(resources.insert(invalid.clone()).is_err());
        assert!(resources.replace(handle,invalid).is_err());
        assert_eq!(resources.get(handle,Type::Nat).unwrap(),&Value::Nat("12".into()));
        assert_eq!(resources.live_payload_bytes(),2);
        assert_eq!(resources.live_count(),1);
    }
    assert_eq!(Value::parse_for_type("00012",Type::Nat).unwrap(),Value::Nat("12".into()));
    rt.update(&[(0,Value::Nat("99".into()))]).unwrap();
    rt.stabilize().unwrap();
    assert_eq!(rt.value(2),Some(Value::Nat("100".into())));
}
