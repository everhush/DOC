//! Test-only proof, same authored graph on every admitted device.
use doc_runtime::{automatic::AutomaticScheduler,Cutoff,Graph,Runtime,Value};
fn main(){
    let path=std::env::args().nth(1).expect("usage: dependency_family_proof FILE.doc");
    let required=std::env::args().nth(2).expect("expected device kind");
    let g=Graph::parse_file(&path).unwrap();
    let xs=g.id("xs").unwrap();let ys=g.id("ys").unwrap();let bias=g.id("bias").unwrap();let flag=g.id("flag").unwrap();
    let mut r=Runtime::new(g.clone(),4,Cutoff::Exact);
    let mut cpu=Runtime::new(g,1,Cutoff::Exact);
    let mut scheduler=AutomaticScheduler::new();
    assert_eq!(scheduler.gpu_kind(),required);
    let mut gpu_lanes=0;
    for (n,b) in [(128,5),(0,5),(256,6),(3,7),(128,8)]{
        let changes=[(xs,Value::Ints((0..n).map(i64::from).collect())),(bias,Value::Int(b))];
        cpu.update(&changes).unwrap();cpu.stabilize().unwrap();
        r.update(&changes).unwrap();
        let before=scheduler.stats().gpu_nodes;
        r.stabilize_automatic(&mut scheduler).unwrap();
        assert_eq!(r.snapshot(),cpu.snapshot());
        assert_eq!(r.value(ys),Some(Value::Ints((0..n).map(|v|i64::from(v)+b).collect())));
        let actual=scheduler.stats().gpu_nodes-before;
        assert_eq!(actual,if required!="none"&&n>=64{n as u64}else{0});
        gpu_lanes+=actual;
        println!("DOC_FAMILY_EPISODE: lanes={n} gpu_lanes={actual}");
    }
    // An ineligible wide value must fail checked CPU arithmetic; no lane
    // or unrelated result from that same parent frontier may publish.
    let changes=[(xs,Value::Ints(vec![i64::MAX])),(flag,Value::Bool(true))];
    r.update(&changes).unwrap();let before=r.snapshot();
    assert!(r.stabilize_automatic(&mut scheduler).is_err());assert_eq!(r.snapshot(),before);
    assert_eq!(scheduler.gpu_kind(),required);
    if required!="none"{assert_eq!(scheduler.stats().mixed_frontiers,3);}
    println!("{}",scheduler.report());
    println!("DOC_FAMILY_PROOF_PASS: device={} gpu_lanes={gpu_lanes} episodes=5 rollback=true",scheduler.gpu_kind());
}
