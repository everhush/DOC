//! General-purpose source-authored finite search, unrelated to game-specific host code.
use doc_runtime::{recurrence::Recurrence,Graph,Value};

fn graph() -> Graph { Graph::parse(include_str!("../examples/search_list.doc")).unwrap() }
fn run(list: &[i64], target: i64, workers: usize) -> (Option<i64>,u64) {
    let g=graph();
    let carry=[("remaining","next_remaining"),("index","next_index"),("found_at","next_found_at"),("needle","next_needle")]
        .iter().map(|&(source,derived)|(g.id(source).unwrap(),g.id(derived).unwrap()))
        .collect();
    let initial=[(g.id("remaining").unwrap(),Value::Ints(list.to_vec())),
                 (g.id("needle").unwrap(),Value::Int(target))];
    let mut sequence=Recurrence::new_with_retention(g.clone(),carry,&initial,workers,2).unwrap();
    let old=sequence.snapshot_at(0).unwrap();
    assert!(sequence.advance_until(g.id("done").unwrap(),list.len() as u64+1).unwrap());
    assert_eq!(old[g.id("remaining").unwrap()],Some(Value::Ints(list.to_vec())));
    let result=sequence.value(g.id("next_found_at").unwrap()).unwrap();
    let Value::MaybeInt(found)=result else {panic!("DOC search result type changed")};
    assert_eq!(sequence.reconstruct_epoch(0).unwrap().unwrap(),old);
    (found,sequence.epoch())
}
#[test]
fn doc_search_first_occurrence_empty_missing_duplicates_and_extremes() {
    let cases: &[(&[i64],i64,Option<i64>)]=&[
        (&[],0,None),
        (&[9],9,Some(0)),
        (&[9,9],9,Some(0)),
        (&[4,9,-2,9],9,Some(1)),
        (&[0,-2,4],100,None),
        (&[i64::MIN,0,i64::MAX],i64::MAX,Some(2)),
    ];
    for &(items,needle,expected) in cases {
        let one=run(items,needle,1);
        assert_eq!(one.0,expected,"DOC result differs from independent search oracle");
        assert_eq!(one.0,items.iter().position(|&x|x==needle).map(|x|x as i64));
        for workers in [2,4,8,17] {
            assert_eq!(run(items,needle,workers),one,"worker count changed search");
        }
    }
}
#[test]
fn doc_search_rejects_illegal_carried_fact_and_keeps_retained_state() {
    let g=graph();
    let carry=[("remaining","next_remaining"),("index","next_index"),("found_at","next_found_at"),("needle","next_needle")]
        .iter().map(|&(src,dst)|(g.id(src).unwrap(),g.id(dst).unwrap())).collect();
    let mut r=Recurrence::new_with_retention(g.clone(),carry,&[],4,3).unwrap();
    let before=r.snapshot_at(0).unwrap();
    assert!(r.advance(&[(g.id("remaining").unwrap(),Value::Ints(vec![1]))]).is_err());
    assert_eq!(r.epoch(),0);
    assert_eq!(r.snapshot_at(0).unwrap(),before);
    // An attempted override of a carried search argument must also fail atomically.
    assert!(r.advance(&[(g.id("needle").unwrap(),Value::Bool(true))]).is_err());
    assert_eq!(r.epoch(),0);
    assert_eq!(r.snapshot_at(0).unwrap(),before);
    r.advance(&[]).unwrap();
    assert_eq!(r.epoch(),1);
}
