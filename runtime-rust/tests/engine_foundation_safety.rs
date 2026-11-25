//! Minimal engine-foundation safety gate for DOC Rust.
//! Covers source batches, generation replacement, immutable reader pinning,
//! exact cutoff, and all-or-nothing failure on a wide ready frontier.
//! This is bounded regression evidence, not a claim of general device-loss
//! recovery, unbounded memory safety, or production game-engine completion.
use doc_runtime::{publication::{PublishedRuntime,PublishedSnapshot},Cutoff,Graph,Runtime,Value};
use std::sync::{Arc,Barrier};
use std::sync::atomic::{AtomicBool,Ordering};

fn scene_graph(multiply:bool)->Graph {
    let operation=if multiply {"mul"} else {"add"};
    Graph::parse(&format!(
        "source x: int = 1\nsource y: int = 1\n\
         derive score: int (x,y) = {operation}(x,y)\n\
         derive stable: bool (score) = eq(score,score)\n"
    )).unwrap()
}
fn assert_scene(s:&PublishedSnapshot) {
    let x=match s.value("x"){Some(Value::Int(v))=>*v,other=>panic!("missing x {other:?}")};
    let y=match s.value("y"){Some(Value::Int(v))=>*v,other=>panic!("missing y {other:?}")};
    assert_eq!(x,y,"observed a torn two-source batch");
    let expected=if s.token.graph_generation%2==0{x.checked_add(y).unwrap()}
                 else{x.checked_mul(y).unwrap()};
    assert_eq!(s.value("score"),Some(&Value::Int(expected)));
    assert_eq!(s.value("stable"),Some(&Value::Bool(true)));
}

#[test]
fn concurrent_readers_repeated_source_and_graph_commits_are_generation_atomic() {
    const READERS:usize=5;
    const LAST:i64=128;
    let engine=Arc::new(PublishedRuntime::new(scene_graph(false),4,Cutoff::Exact).unwrap());
    let retained=engine.read().unwrap();
    let old_weak=Arc::downgrade(&retained);
    assert_scene(&retained);
    let start=Arc::new(Barrier::new(READERS+2));
    let finished=Arc::new(AtomicBool::new(false));
    std::thread::scope(|scope|{
        for _ in 0..READERS {
            let runtime=Arc::clone(&engine);
            let start=Arc::clone(&start);
            let finished=Arc::clone(&finished);
            let pinned=Arc::clone(&retained);
            scope.spawn(move||{
                start.wait();
                let mut previous=pinned.token;
                let mut observations=0;
                loop {
                    let current=runtime.read().unwrap();
                    assert_scene(&current);
                    assert!(current.token.graph_generation>=previous.graph_generation);
                    assert!(current.token.source_epoch>=previous.source_epoch);
                    previous=current.token;
                    assert_eq!(pinned.value("x"),Some(&Value::Int(1)));
                    assert_eq!(pinned.value("score"),Some(&Value::Int(2)));
                    observations+=1;
                    if finished.load(Ordering::Acquire) && observations>=512 {break;}
                    if observations%31==0 {std::thread::yield_now();}
                }
                assert_eq!(runtime.read().unwrap().value("x"),Some(&Value::Int(LAST)));
            });
        }
        let runtime=Arc::clone(&engine);
        let writer_start=Arc::clone(&start);
        let finished=Arc::clone(&finished);
        scope.spawn(move||{
            writer_start.wait();
            for n in 2..=LAST {
                let previous=runtime.read().unwrap();
                let token=previous.token;
                let next=runtime.update(token,&[
                    (0,Value::Int(n)),(1,Value::Int(n))
                ]).unwrap();
                assert!(next.source_epoch>token.source_epoch);
                assert!(runtime.update(token,&[(0,Value::Int(999))]).is_err());
                if n%11==0 {
                    let before=runtime.read().unwrap();
                    let current=before.token;
                    let invalid=Graph::parse(
                        "source x: int = 0\nsource y: int = 0\n\
                         derive score: int (x) = add(x,9223372036854775807)\n"
                    ).unwrap();
                    assert!(runtime.replace_graph(current,invalid).is_err());
                    assert!(Arc::ptr_eq(&before,&runtime.read().unwrap()));
                    assert_eq!(runtime.read().unwrap().token,current);
                    let next_graph=scene_graph((current.graph_generation+1)%2==1);
                    let next=runtime.replace_graph(current,next_graph).unwrap();
                    assert_eq!(next.graph_generation,current.graph_generation+1);
                    assert_eq!(next.source_epoch,current.source_epoch+1);
                    assert!(runtime.replace_graph(current,scene_graph(false)).is_err());
                }
                if n%7==0 {std::thread::yield_now();}
            }
            finished.store(true,Ordering::Release);
        });
        start.wait();
    });
    let final_view=engine.read().unwrap();
    assert_scene(&final_view);
    assert_eq!(final_view.value("x"),Some(&Value::Int(LAST)));
    assert_eq!(retained.value("score"),Some(&Value::Int(2)));
    assert!(old_weak.upgrade().is_some());
    drop(retained);
    assert!(old_weak.upgrade().is_none(),
        "obsolete immutable generation retained after last reader released");
}

#[test]
fn exact_cutoff_preserves_downstream_while_conservative_recomputes() {
    let graph=Graph::parse(concat!(
        "source x: int = 1\n",
        "derive invariant: bool (x) = eq(x,x)\n",
        "derive downstream: bool (invariant) = eq(invariant,true)\n"
    )).unwrap();
    for workers in [1,2,4,8] {
        for cutoff in [Cutoff::Exact,Cutoff::Conservative] {
            let mut rt=Runtime::new(graph.clone(),workers,cutoff);
            rt.stabilize().unwrap();
            let before=rt.stats;
            let old_token=rt.observation_token();
            rt.update(&[(0,Value::Int(2))]).unwrap();
            assert_ne!(old_token,rt.observation_token());
            rt.stabilize().unwrap();
            let increment=rt.stats.evaluations-before.evaluations;
            assert_eq!(increment,if cutoff==Cutoff::Exact{1}else{2});
            if cutoff==Cutoff::Exact {
                assert_eq!(rt.stats.cutoffs-before.cutoffs,1);
            }
            assert_eq!(rt.value(2),Some(Value::Bool(true)));
            assert_eq!(
                rt.snapshot().into_iter().map(Option::unwrap).collect::<Vec<_>>(),
                rt.oracle().unwrap()
            );
        }
    }
}

fn wide_failure_graph()->Graph {
    let mut source="source x: int = 0\n".to_string();
    for i in 1..=128 {
        source.push_str(&format!("derive good{i}: int (x) = add(x,{i})\n"));
    }
    source.push_str("derive failing: int (x) = add(x,9223372036854775807)\n");
    Graph::parse(&source).unwrap()
}

#[test]
fn one_failed_candidate_in_wide_ready_frontier_never_partially_publishes() {
    for workers in [1,2,4,8] {
        let store=PublishedRuntime::new(wide_failure_graph(),workers,Cutoff::Exact).unwrap();
        let previous=store.read().unwrap();
        let token=previous.token;
        assert_eq!(previous.value("good128"),Some(&Value::Int(128)));
        assert_eq!(previous.value("failing"),Some(&Value::Int(i64::MAX)));
        assert!(store.update(token,&[(0,Value::Int(1))]).is_err(),
            "overflow in last frontier member must abort entire update");
        let after=store.read().unwrap();
        assert!(Arc::ptr_eq(&previous,&after),
            "failed candidate changed published Arc");
        assert_eq!(after.token,token);
        assert_eq!(after.value("good128"),Some(&Value::Int(128)));
        assert!(store.update(token,&[
            (0,Value::Int(-1)),(0,Value::Int(0))
        ]).is_err());
        assert!(Arc::ptr_eq(&previous,&store.read().unwrap()));
        let committed=store.update(token,&[(0,Value::Int(-1))]).unwrap();
        assert_eq!(committed.source_epoch,token.source_epoch+1);
        assert_eq!(store.read().unwrap().value("good128"),Some(&Value::Int(127)));
        assert_eq!(store.read().unwrap().value("failing"),
                   Some(&Value::Int(i64::MAX-1)));
        assert_eq!(previous.value("good128"),Some(&Value::Int(128)));
        assert!(store.update(token,&[(0,Value::Int(0))]).is_err());
    }
}
