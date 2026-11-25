use doc_runtime::{automatic::AutomaticScheduler,Cutoff,Graph,Runtime,Value};
const SOURCE:&str=include_str!("../examples/dependency_family.doc");
#[test]
fn runtime_sized_families_repair_and_publish_atomically(){
    for workers in [1,2,4,8]{
        let g=Graph::parse(SOURCE).unwrap();let xs=g.id("xs").unwrap();let ys=g.id("ys").unwrap();let count=g.id("count").unwrap();let unrelated=g.id("unrelated").unwrap();
        let mut r=Runtime::new(g,workers,Cutoff::Exact);
        r.stabilize().unwrap();assert_eq!(r.value(ys),Some(Value::Ints(vec![6,7,8])));
        for n in [128,0,3,256,1]{
            let input=(0..n).map(i64::from).collect::<Vec<_>>();
            r.update(&[(xs,Value::Ints(input.clone()))]).unwrap();r.stabilize().unwrap();
            assert_eq!(r.value(ys),Some(Value::Ints(input.into_iter().map(|v|v+5).collect())));
            assert_eq!(r.value(count),Some(Value::Int(n.into())));
            assert_eq!(r.snapshot().into_iter().map(Option::unwrap).collect::<Vec<_>>(),r.oracle().unwrap());
        }
        let flag=r.graph.id("flag").unwrap();
        r.update(&[(xs,Value::Ints(vec![i64::MAX])),(flag,Value::Bool(true))]).unwrap();
        let before=r.snapshot();let ready=r.ready();
        assert!(r.step(&ready).is_err());assert_eq!(r.snapshot(),before);
        assert_eq!(r.value(unrelated),Some(Value::Bool(true)));
    }
}
#[test]
fn family_automatic_expands_real_ready_lanes(){
    let g=Graph::parse(SOURCE).unwrap();let xs=g.id("xs").unwrap();let ys=g.id("ys").unwrap();
    let mut r=Runtime::new(g,4,Cutoff::Exact);let mut scheduler=AutomaticScheduler::new();
    r.update(&[(xs,Value::Ints((0..128).collect()))]).unwrap();
    r.stabilize_automatic(&mut scheduler).unwrap();
    assert_eq!(r.value(ys),Some(Value::Ints((5..133).collect())));
    assert!(scheduler.stats().cpu_nodes+scheduler.stats().gpu_nodes>=130);
    if scheduler.gpu_kind()!="none"{
        assert_eq!(scheduler.stats().gpu_nodes,128);
        assert!(scheduler.stats().mixed_frontiers>=1);
    }
    let before=r.snapshot();r.update(&[(xs,Value::Ints(vec![i64::MAX]))]).unwrap();
    assert!(r.stabilize_automatic(&mut scheduler).is_err());
    assert_eq!(r.value(ys),before[ys]);
}
#[test]
fn family_type_admission_and_canonical_ir(){
    for body in ["map_ints(xs,bias,add(bias,1))","map_ints(xs,item,eq(item,0))","map_ints(xs,item,len(xs))","if(true,map_ints(xs,item,item),xs)","map_ints(xs,item,map_ints(xs,other,other))"]{
        let source=format!("source xs: ints = [1]\nsource bias: int = 2\nderive ys: ints (xs,bias) = {body}\n");
        assert!(Graph::parse(&source).is_err(),"{body}");
    }
    let g=Graph::parse(SOURCE).unwrap();
    let ir=doc_runtime::typed_ir::emit_typed_ir_v1(&g,&[]).unwrap();
    assert!(ir.contains("map_ints(arg(0),add(arg(2),arg(1)))"));
    let mut r=Runtime::new(g,1,Cutoff::Exact);let xs=r.graph.id("xs").unwrap();
    r.update(&[(xs,Value::Ints(vec![0;4097]))]).unwrap();let before=r.snapshot();
    assert!(r.stabilize().is_err());assert_eq!(r.snapshot(),before);
}
