use doc_runtime::{automatic::AutomaticScheduler,Cutoff,Graph,Runtime,Value};
const SOURCE:&str=include_str!("../examples/causal_token.doc");
#[test]
fn dynamic_causal_derivations_are_typed_atomic_and_worker_independent(){
    for workers in [1,2,4,8]{
        let g=Graph::parse(SOURCE).unwrap();let digits=g.id("digits").unwrap();let token=g.id("token").unwrap();let value=g.id("value").unwrap();let limit=g.id("limit").unwrap();let other=g.id("other").unwrap();
        let mut r=Runtime::new(g,workers,Cutoff::Exact);
        r.stabilize().unwrap();
        assert_eq!(r.value(value),Some(Value::Int(123)));
        for (input,expected) in [(vec![],0),(vec![9],9),(vec![4,0,2,5],4025)]{
            r.update(&[(digits,Value::Ints(input.clone()))]).unwrap();
            r.stabilize().unwrap();
            assert_eq!(r.value(token),Some(Value::Ints(vec![input.len() as i64,expected])));
            assert_eq!(r.value(value),Some(Value::Int(expected)));
            assert_eq!(r.snapshot().into_iter().map(Option::unwrap).collect::<Vec<_>>(),r.oracle().unwrap());
        }
        r.update(&[(digits,Value::Ints(vec![9;20])),(limit,Value::Int(11))]).unwrap();
        let before=r.snapshot();let ready=r.ready();
        assert!(r.step(&ready).is_err());assert_eq!(r.snapshot(),before);
        assert_eq!(r.value(other),Some(Value::Int(10)));
        r.update(&[(digits,Value::Ints(vec![7]))]).unwrap();
        let mut scheduler=AutomaticScheduler::new();
        r.stabilize_automatic(&mut scheduler).unwrap();
        assert_eq!(r.value(value),Some(Value::Int(7)));
        assert_eq!(r.value(other),Some(Value::Int(11)));
    }
}
#[test]
fn terminal_predicate_is_lazy_and_budget_is_enforced(){
    for (expression,ok) in [("recur(seed,x,true,add(x,1))",true),("recur(seed,x,false,x)",false)]{
        let g=Graph::parse(&format!("source seed: int = 9223372036854775807\nderive result: int (seed) = {expression}\n")).unwrap();
        let mut r=Runtime::new(g,1,Cutoff::Exact);let before=r.snapshot();
        assert_eq!(r.stabilize().is_ok(),ok);
        if !ok{assert_eq!(before,r.snapshot());}
    }
    let g=Graph::parse("source seed: int = 0\nderive result: int (seed) = recur(seed,x,eq(x,65536),add(x,1))\n").unwrap();
    let id=g.id("result").unwrap();let mut r=Runtime::new(g,1,Cutoff::Exact);r.stabilize().unwrap();assert_eq!(r.value(id),Some(Value::Int(65536)));
}
#[test]
fn reject_ill_typed_or_nested_recurrences_and_export_bound_argument(){
    for expr in ["recur(seed,seed,true,seed)","recur(seed,x,x,x)","recur(seed,x,true,false)","recur(add(seed,1),x,true,x)","if(true,recur(seed,x,true,x),seed)","recur(seed,x,true,recur(seed,y,true,y))"]{
        assert!(Graph::parse(&format!("source seed: int = 0\nderive result: int (seed) = {expr}\n")).is_err(),"{expr}");
    }
    let g=Graph::parse("source seed: int = 0\nsource target: int = 10\nderive result: int (seed,target) = recur(seed,x,eq(x,target),add(x,1))\n").unwrap();
    let ir=doc_runtime::typed_ir::emit_typed_ir_v1(&g,&[]).unwrap();
    assert!(ir.contains("recur(arg(0),eq(arg(2),arg(1)),add(arg(2),lit(int,31)))"));
}
