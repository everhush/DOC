//! Publication contract: immutable readers, generation ABA rejection,
//! one committed writer, rollback on failed replacement, eventual retirement.
use doc_runtime::{Cutoff, Graph, Value};
use doc_runtime::publication::PublishedRuntime;
use std::sync::{Arc, Barrier};

fn base_graph()->Graph {
    Graph::parse(concat!(
        "source n: nat = 99999999999999999999999999999999999999999999999999\n",
        "source items: ints = [1,2,3]\n",
        "derive next: nat (n) = add(n,nat(1))\n",
        "derive size: int (items) = len(items)\n"
    )).unwrap()
}
fn changed_graph()->Graph {
    Graph::parse(concat!(
        "source items: ints = [8]\n",
        "source n: nat = 3\n",
        "derive size: int (items) = len(items)\n",
        "derive next: nat (n) = add(n,nat(2))\n",
        "derive zero: bool (size) = eq(size,0)\n"
    )).unwrap()
}

#[test]
fn concurrent_pinned_observers_survive_reordered_graph_and_later_reclamation() {
    let engine=Arc::new(PublishedRuntime::new(base_graph(),4,Cutoff::Exact).unwrap());
    let pinned=engine.read().unwrap();
    let weak_old=Arc::downgrade(&pinned);
    let old_token=pinned.token;
    let saved_n=pinned.value("n").cloned().unwrap();
    let saved_next=pinned.value("next").cloned().unwrap();
    let reader_ready=Arc::new(Barrier::new(5));
    let reader_release=Arc::new(Barrier::new(5));
    std::thread::scope(|scope| {
        for _ in 0..4 {
            let reader=Arc::clone(&pinned);
            let ready=reader_ready.clone();
            let release=reader_release.clone();
            let n=saved_n.clone();
            let next=saved_next.clone();
            scope.spawn(move||{
                ready.wait();
                release.wait();
                // This reader is still holding the *old* immutable graph
                // even after the writer has replaced its source order,
                // derived expressions and newly inserted states.
                for _ in 0..1000 {
                    assert_eq!(reader.token,old_token);
                    assert_eq!(reader.value("n"),Some(&n));
                    assert_eq!(reader.value("next"),Some(&next));
                    assert_eq!(reader.value("items"),Some(&Value::Ints(vec![1,2,3])));
                }
            });
        }
        reader_ready.wait();
        let next_token=engine.replace_graph(old_token,changed_graph()).unwrap();
        assert_eq!(next_token.graph_generation,old_token.graph_generation+1);
        assert_eq!(next_token.source_epoch,old_token.source_epoch+1);
        let current=engine.read().unwrap();
        assert!(!Arc::ptr_eq(&current,&pinned));
        assert_eq!(current.token,next_token);
        assert_eq!(current.value("n"),Some(&saved_n)); // compatible named carry
        assert_eq!(current.value("items"),Some(&Value::Ints(vec![1,2,3])));
        assert_eq!(current.value("size"),Some(&Value::Int(3)));
        assert_eq!(current.value("zero"),Some(&Value::Bool(false)));
        assert!(engine.update(old_token,&[(0,Value::Ints(vec![0]))]).is_err());
        assert!(engine.replace_graph(old_token,base_graph()).is_err());
        assert_eq!(engine.read().unwrap().token,next_token);
        reader_release.wait();
    });
    // A detached reader can retain an evicted graph; after the last reader
    // releases it, the old materialization is actually reclaimable.
    assert!(weak_old.upgrade().is_some());
    drop(pinned);
    assert!(weak_old.upgrade().is_none());
}

#[test]
fn failed_candidate_has_no_partial_publish_or_reader_invalidation() {
    let engine=PublishedRuntime::new(base_graph(),2,Cutoff::Exact).unwrap();
    let protected=engine.read().unwrap();
    let token=protected.token;
    let broken=Graph::parse(concat!(
        "source n: nat = 1\n",
        "source items: ints = [7]\n",
        "derive next: nat (n) = add(n,nat(1))\n",
        "derive size: int (items) = get(items,-1)\n"
    )).unwrap();
    assert!(engine.replace_graph(token,broken).is_err());
    let after=engine.read().unwrap();
    assert!(Arc::ptr_eq(&protected,&after));
    assert_eq!(after.token,token);
    assert!(engine.update(token,&[(0,Value::Int(1))]).is_err());
    assert!(Arc::ptr_eq(&after,&engine.read().unwrap()));
    let next=engine.update(token,&[(1,Value::Ints(vec![3,5,8]))]).unwrap();
    assert_ne!(next,token);
    assert_eq!(protected.value("items"),Some(&Value::Ints(vec![1,2,3])));
    assert_eq!(engine.read().unwrap().value("size"),Some(&Value::Int(3)));
}

#[test]
fn simultaneous_writers_with_same_token_cannot_both_commit() {
    let engine=Arc::new(PublishedRuntime::new(base_graph(),2,Cutoff::Exact).unwrap());
    let token=engine.read().unwrap().token;
    let barrier=Arc::new(Barrier::new(3));
    let (left,right)=std::thread::scope(|scope|{
        let workers=(0..2).map(|n|{
            let rt=engine.clone();
            let ready=barrier.clone();
            scope.spawn(move||{
                ready.wait();
                rt.update(token,&[(1,Value::Ints(vec![n, n+1]))])
            })
        }).collect::<Vec<_>>();
        barrier.wait();
        (workers[0].join().unwrap(),workers[1].join().unwrap())
    });
    assert_eq!(usize::from(left.is_ok())+usize::from(right.is_ok()),1);
    let new_token=engine.read().unwrap().token;
    assert_eq!(new_token.source_epoch,token.source_epoch+1);
    assert_eq!(new_token.graph_generation,token.graph_generation);
    assert!(engine.update(token,&[(1,Value::Ints(vec![0]))]).is_err());
}
