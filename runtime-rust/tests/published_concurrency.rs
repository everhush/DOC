use doc_runtime::{Cutoff,Graph,Value,publication::PublishedRuntime};
use std::sync::{Arc,atomic::{AtomicUsize,Ordering}};
use std::thread;

fn graph()->Graph{
    Graph::parse("source a: int = 1\nsource b: int = 2\n\
                  derive sum: int (a,b) = add(a,b)\n\
                  derive doubled: int (sum) = mul(sum,2)\n").unwrap()
}
#[test]
fn owned_snapshots_never_observe_half_committed_frontiers() {
    let store=Arc::new(PublishedRuntime::new(graph(),4,Cutoff::Exact).unwrap());
    let old=store.read().unwrap();
    let progress=Arc::new(AtomicUsize::new(0));
    thread::scope(|scope|{
        for _ in 0..8 {
            let store=Arc::clone(&store);
            let progress=Arc::clone(&progress);
            let initial=Arc::clone(&old);
            scope.spawn(move||{
                for _ in 0..2000 {
                    assert_eq!(initial.value("a"),Some(&Value::Int(1)));
                    assert_eq!(initial.value("sum"),Some(&Value::Int(3)));
                    assert_eq!(initial.value("doubled"),Some(&Value::Int(6)));
                    let snap=store.read().unwrap();
                    let a=match snap.value("a").unwrap(){Value::Int(n)=>*n,_=>panic!()};
                    let b=match snap.value("b").unwrap(){Value::Int(n)=>*n,_=>panic!()};
                    assert_eq!(snap.value("sum"),Some(&Value::Int(a+b)));
                    assert_eq!(snap.value("doubled"),Some(&Value::Int((a+b)*2)));
                }
                progress.fetch_add(1,Ordering::SeqCst);
            });
        }
        let store=Arc::clone(&store);
        scope.spawn(move||{
            for n in 1..=500 {
                let token=store.read().unwrap().token;
                let next=store.update(token,&[(0,Value::Int(n))]).unwrap();
                assert_eq!(next.graph_generation,0);
            }
        });
    });
    assert_eq!(progress.load(Ordering::SeqCst),8);
    assert_eq!(old.value("sum"),Some(&Value::Int(3)));
    let current=store.read().unwrap();
    assert_eq!(current.value("sum"),Some(&Value::Int(502)));
    assert!(store.update(old.token,&[(0,Value::Int(20))]).is_err());
}
#[test]
fn candidate_errors_and_stale_generation_cannot_publish() {
    let store=PublishedRuntime::new(graph(),2,Cutoff::Exact).unwrap();
    let previous=store.read().unwrap();
    let token=previous.token;
    let bad=store.update(token,&[(0,Value::Int(i64::MAX))]);
    assert!(bad.is_err());
    assert_eq!(store.read().unwrap().as_ref(),previous.as_ref());
    assert!(store.update(token,&[(0,Value::Bool(true))]).is_err());
    assert_eq!(store.read().unwrap().as_ref(),previous.as_ref());
    let changed=Graph::parse(
        "source a: int = 0\nsource b: int = 0\n\
         derive sum: int (a,b) = add(a,b)\n\
         derive doubled: int (sum) = mul(sum,3)\n"
    ).unwrap();
    let next=store.replace_graph(token,changed).unwrap();
    assert_eq!(next.graph_generation,1);
    assert_eq!(store.read().unwrap().value("doubled"),Some(&Value::Int(9)));
    assert!(store.replace_graph(token,graph()).is_err());
    assert_eq!(previous.value("doubled"),Some(&Value::Int(6)));
}
#[test]
fn obsolete_snapshots_are_reclaimed_after_reader_drop() {
    let store=PublishedRuntime::new(graph(),1,Cutoff::Exact).unwrap();
    let held=store.read().unwrap();
    let weak=Arc::downgrade(&held);
    let t=held.token;
    let next=store.update(t,&[(0,Value::Int(7))]).unwrap();
    assert_eq!(store.read().unwrap().value("a"),Some(&Value::Int(7)));
    assert!(weak.upgrade().is_some());
    drop(held);
    assert!(weak.upgrade().is_none());
    assert_eq!(next.source_epoch,1);
}
