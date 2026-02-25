use doc_runtime::{Cutoff, Expr, Graph, Runtime, State, Type, Value};

// Deterministic generated tests; never interpreted as a formal exhaustive proof.
fn next(seed: &mut u64) -> u64 {
    *seed ^= *seed << 13;
    *seed ^= *seed >> 7;
    *seed ^= *seed << 17;
    *seed
}
#[test]
fn randomized_acyclic_graphs_multiple_frontier_schedules() {
    let mut seed=0xD0C5A1E_u64;
    for graph_case in 0..48 {
        let mut states=vec![
            State::source("s0",Value::Int(2)),
            State::source("s1",Value::Int(3)),
            State::source("s2",Value::Int(4)),
        ];
        for d in 0..40 {
            let p=(next(&mut seed) as usize)%states.len();
            let q=(next(&mut seed) as usize)%states.len();
            let expr=if d%3==0 {
                Expr::Add(Box::new(Expr::Arg(0)),Box::new(Expr::Lit(Value::Int(1))))
            }else {
                Expr::Add(Box::new(Expr::Arg(0)),Box::new(Expr::Arg(1)))
            };
            states.push(State::derived(format!("d{d}"),Type::Int,vec![p,q],expr));
        }
        let graph=Graph::new(states).unwrap();
        for policy in [Cutoff::Exact,Cutoff::Conservative] {
            let mut one=Runtime::new(graph.clone(),1,policy);
            let mut four=Runtime::new(graph.clone(),4,policy);
            let mut subset=Runtime::new(graph.clone(),1,policy);
            for epoch in 0..15 {
                let src=(next(&mut seed)%3) as usize;
                let val=Value::Int((next(&mut seed)%9) as i64);
                for rt in [&mut one,&mut four,&mut subset] {
                    rt.update(&[(src,val)]).unwrap();
                }
                one.stabilize().unwrap();
                four.stabilize().unwrap();
                while !subset.stable() {
                    let ready=subset.ready();
                    let choice=(next(&mut seed) as usize)%ready.len();
                    subset.step(&[ready[choice]]).unwrap();
                }
                let canonical=one.oracle().unwrap();
                let from_snapshot=|r:&Runtime| r.snapshot().into_iter()
                    .map(Option::unwrap).collect::<Vec<_>>();
                assert_eq!(from_snapshot(&one),canonical,"case {graph_case} epoch {epoch}");
                assert_eq!(from_snapshot(&four),canonical,"case {graph_case} epoch {epoch}");
                assert_eq!(from_snapshot(&subset),canonical,"case {graph_case} epoch {epoch}");
            }
        }
    }
}
