//! Concurrent real-world lifetime stress for complete immutable DOC publication.
//! This is bounded adversarial evidence, NOT a proof of all memory safety,
//! garbage-collection policy, or a claim of zero leaks in arbitrary workloads.
use doc_runtime::{Cutoff,Graph,ObservationToken,Value};
use doc_runtime::publication::{PublishedRuntime,PublishedSnapshot};
use std::sync::{Arc,Barrier};
use std::sync::atomic::{AtomicBool,Ordering};

fn paired_graph()->Graph {
    Graph::parse(concat!(
        "source left: int = 0\n",
        "source right: int = 0\n",
        "derive total: int (left,right) = add(left,right)\n",
        "derive equal: bool (left,right) = eq(left,right)\n",
    )).unwrap()
}

fn check_full_batch(s:&PublishedSnapshot)->ObservationToken {
    let left=match s.value("left") {
        Some(Value::Int(v))=>*v,
        other=>panic!("incomplete left publication: {other:?}")
    };
    let right=match s.value("right") {
        Some(Value::Int(v))=>*v,
        other=>panic!("incomplete right publication: {other:?}")
    };
    assert_eq!(left,right,"observed a half-published source batch");
    assert_eq!(s.value("total"),Some(&Value::Int(left*2)));
    assert_eq!(s.value("equal"),Some(&Value::Bool(true)));
    assert_eq!(s.token.graph_generation,0);
    // Exactly one new source epoch is issued per distinct two-source batch.
    assert_eq!(s.token.source_epoch,left as u64);
    s.token
}

#[test]
fn concurrent_source_batches_cannot_publish_torn_values_or_tokens() {
    const UPDATES:i64=300;
    const READERS:usize=6;
    let engine=Arc::new(PublishedRuntime::new(
        paired_graph(),4,Cutoff::Exact).unwrap());
    let oldest=engine.read().unwrap();
    let old_weak=Arc::downgrade(&oldest);
    check_full_batch(&oldest);

    let start=Arc::new(Barrier::new(READERS+2));
    let finished=Arc::new(AtomicBool::new(false));
    std::thread::scope(|scope|{
        for _ in 0..READERS {
            let runtime=Arc::clone(&engine);
            let barrier=Arc::clone(&start);
            let done=Arc::clone(&finished);
            let retained=Arc::clone(&oldest);
            scope.spawn(move||{
                barrier.wait();
                let mut last_epoch=0;
                let mut count=0;
                loop {
                    let published=runtime.read().unwrap();
                    let token=check_full_batch(&published);
                    assert!(token.source_epoch>=last_epoch,
                        "single reader observed source epoch regression");
                    last_epoch=token.source_epoch;
                    // Held pinned observation must remain valid after hundreds
                    // of later, concurrently committed source updates.
                    assert_eq!(retained.value("total"),Some(&Value::Int(0)));
                    count+=1;
                    if done.load(Ordering::Acquire) && count>=1_000 {
                        break;
                    }
                    if count%37==0 {std::thread::yield_now();}
                }
                assert_eq!(check_full_batch(&runtime.read().unwrap()).source_epoch,
                           UPDATES as u64);
            });
        }
        let runtime=Arc::clone(&engine);
        let barrier=Arc::clone(&start);
        let done=Arc::clone(&finished);
        scope.spawn(move||{
            barrier.wait();
            for i in 1..=UPDATES {
                let previous=runtime.read().unwrap().token;
                let token=runtime.update(previous,&[
                    (0,Value::Int(i)),(1,Value::Int(i))
                ]).unwrap();
                assert_eq!(token.source_epoch,i as u64);
                if i%11==0 {std::thread::yield_now();}
            }
            done.store(true,Ordering::Release);
        });
        start.wait();
    });
    let final_snapshot=engine.read().unwrap();
    assert_eq!(check_full_batch(&final_snapshot).source_epoch,UPDATES as u64);
    // Readers and the writer have released the original Arc. It must be
    // actually reclaimable, not merely logically marked as retired.
    assert!(old_weak.upgrade().is_some());
    drop(oldest);
    assert!(old_weak.upgrade().is_none());
}

#[test]
fn invalid_batch_cannot_poison_current_generation_or_pinned_reader() {
    let runtime=PublishedRuntime::new(paired_graph(),2,Cutoff::Exact).unwrap();
    let retained=runtime.read().unwrap();
    let original_token=retained.token;
    let invalid=[
        vec![(0,Value::Int(5)),(0,Value::Int(6))], // duplicate ID
        vec![(0,Value::Int(5)),(1,Value::Bool(true))], // type mismatch
        vec![(0,Value::Int(5)),(2,Value::Int(7))], // derived output
        vec![(0,Value::Int(5)),(999,Value::Int(7))], // invalid ID
    ];
    for batch in invalid {
        assert!(runtime.update(original_token,&batch).is_err());
        let current=runtime.read().unwrap();
        assert!(Arc::ptr_eq(&retained,&current));
        assert_eq!(current.token,original_token);
        check_full_batch(&current);
    }
    let new_token=runtime.update(original_token,&[
        (0,Value::Int(8)),(1,Value::Int(8))]).unwrap();
    assert_eq!(new_token.source_epoch,original_token.source_epoch+1);
    assert_eq!(runtime.read().unwrap().value("total"),Some(&Value::Int(16)));
    assert_eq!(retained.value("total"),Some(&Value::Int(0)));
    assert!(runtime.update(original_token,&[(0,Value::Int(100))]).is_err());
}
