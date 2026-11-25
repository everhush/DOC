//! Issue #10: bounded DOC-authored entity lifecycle with typed arrays.
use doc_runtime::{recurrence::Recurrence,Graph,Value};
use std::path::PathBuf;
const CARRIES: &[(&str,&str)] = &[
    ("ids","next_ids"),("xs","next_xs"),("ys","next_ys"),
    ("next_id","next_next_id"),
    ("issued_high_water","next_issued_high_water"),
];
fn graph()->Graph {
    let path=PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../engine/entity_scene.doc");
    Graph::parse_file(path.to_str().unwrap()).unwrap()
}
fn game(g:&Graph,workers:usize,initial:&[(usize,Value)])->Recurrence {
    let carry=CARRIES.iter().map(|(src,dst)|(
        g.id(src).unwrap(),g.id(dst).unwrap()
    )).collect();
    Recurrence::new_with_retention(g.clone(),carry,initial,workers,3).unwrap()
}
fn v(g:&Graph,r:&Recurrence,name:&str)->Value {
    r.value(g.id(name).unwrap()).unwrap()
}
fn assert_alignment(g:&Graph,r:&Recurrence) {
    let Value::Ints(ids)=v(g,r,"next_ids") else{panic!("missing ids")};
    let Value::Ints(xs)=v(g,r,"next_xs") else{panic!("missing x")};
    let Value::Ints(ys)=v(g,r,"next_ys") else{panic!("missing y")};
    assert_eq!(ids.len(),xs.len());
    assert_eq!(ids.len(),ys.len());
    assert!(ids.len()<=3,"DOC capacity exceeded");
    for pair in ids.windows(2){assert!(pair[0]<pair[1],"IDs reused or unsorted");}
    assert_eq!(v(g,r,"next_count"),Value::Int(ids.len() as i64));
}

#[test]
fn doc_entity_spawn_capacity_and_fifo_despawn_are_deterministic() {
    let g=graph();
    let input=|name:&str,val:Value|(g.id(name).unwrap(),val);
    for workers in [1,2,4,8,17] {
        let mut r=game(&g,workers,&[]);
        assert_alignment(&g,&r);
        assert_eq!(v(&g,&r,"next_ids"),Value::Ints(vec![1]));
        r.advance(&[input("action",Value::Int(1)),
                    input("spawn_x",Value::Int(5)),
                    input("spawn_y",Value::Int(6))]).unwrap();
        assert_alignment(&g,&r);
        assert_eq!(v(&g,&r,"next_ids"),Value::Ints(vec![1,2]));
        assert_eq!(v(&g,&r,"next_xs"),Value::Ints(vec![1,5]));
        assert_eq!(v(&g,&r,"next_ys"),Value::Ints(vec![1,6]));
        r.advance(&[input("action",Value::Int(1)),
                    input("spawn_x",Value::Int(7)),
                    input("spawn_y",Value::Int(8))]).unwrap();
        assert_eq!(v(&g,&r,"next_ids"),Value::Ints(vec![1,2,3]));
        let epoch2=r.snapshot_at(2).unwrap();
        // Full capacity: no partial insertion into any component column.
        r.advance(&[input("action",Value::Int(1)),
                    input("spawn_x",Value::Int(99)),
                    input("spawn_y",Value::Int(98))]).unwrap();
        assert_alignment(&g,&r);
        assert_eq!(v(&g,&r,"next_ids"),Value::Ints(vec![1,2,3]));
        assert_eq!(v(&g,&r,"next_next_id"),Value::Int(4));
        // Remove the middle entity (index 1), not merely FIFO: columns stay aligned.
        r.advance(&[input("action",Value::Int(2)),
                    input("remove_slot",Value::Int(1))]).unwrap();
        assert_alignment(&g,&r);
        assert_eq!(v(&g,&r,"next_ids"),Value::Ints(vec![1,3]));
        assert_eq!(v(&g,&r,"next_xs"),Value::Ints(vec![1,7]));
        assert_eq!(v(&g,&r,"next_ys"),Value::Ints(vec![1,8]));
        // Removed entity handle 2 is stale; entity 3 occupies shifted slot 1.
        r.advance(&[input("query_slot",Value::Int(1)),
                    input("query_id",Value::Int(2))]).unwrap();
        assert_eq!(v(&g,&r,"queried_alive"),Value::Bool(false));
        assert_eq!(v(&g,&r,"queried_x"),Value::Int(-1));
        r.advance(&[input("query_slot",Value::Int(1)),
                    input("query_id",Value::Int(3))]).unwrap();
        assert_eq!(v(&g,&r,"queried_alive"),Value::Bool(true));
        assert_eq!(v(&g,&r,"queried_x"),Value::Int(7));
        assert_eq!(v(&g,&r,"queried_y"),Value::Int(8));
        // A DOC-authored indexed move updates x/y but preserves the entity ID.
        r.advance(&[input("action",Value::Int(3)),
                    input("move_slot",Value::Int(1)),
                    input("move_x",Value::Int(9)),
                    input("move_y",Value::Int(10))]).unwrap();
        assert_alignment(&g,&r);
        assert_eq!(v(&g,&r,"next_ids"),Value::Ints(vec![1,3]));
        assert_eq!(v(&g,&r,"next_xs"),Value::Ints(vec![1,9]));
        assert_eq!(v(&g,&r,"next_ys"),Value::Ints(vec![1,10]));
        // Invalid move is a no-op, no out-of-bounds collection access.
        r.advance(&[input("action",Value::Int(3)),
                    input("move_slot",Value::Int(-1)),
                    input("move_x",Value::Int(99))]).unwrap();
        assert_eq!(v(&g,&r,"next_xs"),Value::Ints(vec![1,9]));
        // Invalid index is guarded by a lazy conditional before any get().
        r.advance(&[input("query_slot",Value::Int(-1)),
                    input("query_id",Value::Int(2))]).unwrap();
        assert_eq!(v(&g,&r,"queried_alive"),Value::Bool(false));
        assert_eq!(v(&g,&r,"queried_x"),Value::Int(-1));
        assert_eq!(r.reconstruct_epoch(2).unwrap().unwrap(),epoch2);
    }
}
#[test]
fn overflowing_entity_id_aborts_without_advancing_or_evicting_old_epoch() {
    let g=graph();
    let next=g.id("next_id").unwrap();
    let mut r=game(&g,4,&[(next,Value::Int(i64::MAX))]);
    let before=r.snapshot_at(0).unwrap();
    let input=g.id("action").unwrap();
    assert!(r.advance(&[(input,Value::Int(1))]).is_err());
    assert_eq!(r.epoch(),0);
    assert_eq!(r.snapshot_at(0).unwrap(),before);
    assert_eq!(v(&g,&r,"next_ids"),Value::Ints(vec![1]));
    // Idle still succeeds after a failed spawn, and keeps the pinned state.
    r.advance(&[(input,Value::Int(0))]).unwrap();
    assert_eq!(v(&g,&r,"next_ids"),Value::Ints(vec![1]));
}

#[test]
fn strict_collection_indexes_fail_without_publishing_any_candidate() {
    use doc_runtime::{publication::PublishedRuntime,Cutoff};
    use std::sync::Arc;
    let source=concat!(
        "source cells: ints = [1,2,3]\n",
        "source slot: int = 1\n",
        "source value: int = 9\n",
        "derive changed: ints (cells,slot,value) = replace_at(cells,slot,value)\n",
        "derive reduced: ints (cells,slot) = remove_at(cells,slot)\n"
    );
    let store=PublishedRuntime::new(Graph::parse(source).unwrap(),4,Cutoff::Exact).unwrap();
    let first=store.read().unwrap();
    assert_eq!(first.value("changed"),Some(&Value::Ints(vec![1,9,3])));
    assert_eq!(first.value("reduced"),Some(&Value::Ints(vec![1,3])));
    let token=first.token;
    assert!(store.update(token,&[(1,Value::Int(-1))]).is_err());
    assert!(Arc::ptr_eq(&first,&store.read().unwrap()));
    assert!(store.update(token,&[(1,Value::Int(3))]).is_err());
    assert!(Arc::ptr_eq(&first,&store.read().unwrap()));
    let next=store.update(token,&[(1,Value::Int(2))]).unwrap();
    assert_eq!(next.source_epoch,token.source_epoch+1);
    assert_eq!(store.read().unwrap().value("changed"),
               Some(&Value::Ints(vec![1,2,9])));
    assert_eq!(store.read().unwrap().value("reduced"),
               Some(&Value::Ints(vec![1,2])));
}

#[test]
fn externally_requested_budget_and_stale_handle_cannot_escape_scene_invariants() {
    let g=graph();
    let initial=|name:&str,val:Value|(g.id(name).unwrap(),val);
    let action=g.id("action").unwrap();
    let mut oversized=game(&g,4,&[initial("max_entities",Value::Int(i64::MAX))]);
    for _ in 0..8 {
        oversized.advance(&[(action,Value::Int(1))]).unwrap();
        assert_alignment(&g,&oversized);
    }
    assert_eq!(v(&g,&oversized,"next_ids"),Value::Ints(vec![1,2,3]));
    assert_eq!(v(&g,&oversized,"next_next_id"),Value::Int(4));
    let mut stale=game(&g,4,&[initial("next_id",Value::Int(1))]);
    stale.advance(&[(action,Value::Int(1))]).unwrap();
    assert_eq!(v(&g,&stale,"next_ids"),Value::Ints(vec![1]));
    assert_eq!(v(&g,&stale,"next_next_id"),Value::Int(1));
    assert_alignment(&g,&stale);
}

#[test]
fn retired_entity_ids_survive_full_despawn_and_rejected_rewind() {
    let g=graph();
    let action=g.id("action").unwrap();
    let removal=g.id("remove_slot").unwrap();
    let query_slot=g.id("query_slot").unwrap();
    let query_id=g.id("query_id").unwrap();
    let next_id=g.id("next_id").unwrap();
    let high_water=g.id("issued_high_water").unwrap();
    for workers in [1,2,4,8,17] {
        let mut r=game(&g,workers,&[]);
        for _ in 0..2 {
            r.advance(&[(action,Value::Int(1))]).unwrap();
        }
        assert_eq!(v(&g,&r,"next_ids"),Value::Ints(vec![1,2,3]));
        assert_eq!(v(&g,&r,"next_issued_high_water"),Value::Int(3));
        for slot in [2,1,0] {
            r.advance(&[(action,Value::Int(2)),(removal,Value::Int(slot))]).unwrap();
            assert_alignment(&g,&r);
        }
        assert_eq!(v(&g,&r,"next_ids"),Value::Ints(vec![]));
        assert_eq!(v(&g,&r,"next_issued_high_water"),Value::Int(3));
        let epoch=r.epoch();
        let empty_snapshot=r.snapshot_at(epoch).unwrap();
        // Carried allocation authority cannot be reset by an input event.
        assert!(r.advance(&[(next_id,Value::Int(1))]).is_err());
        assert!(r.advance(&[(high_water,Value::Int(0))]).is_err());
        assert_eq!(r.epoch(),epoch);
        assert_eq!(r.snapshot_at(epoch).unwrap(),empty_snapshot);
        // Retired handles 1, 2 and 3 remain invalid after a new entity appears.
        r.advance(&[(action,Value::Int(1)),(query_slot,Value::Int(0)),
                    (query_id,Value::Int(1))]).unwrap();
        assert_alignment(&g,&r);
        assert_eq!(v(&g,&r,"next_ids"),Value::Ints(vec![4]));
        assert_eq!(v(&g,&r,"next_issued_high_water"),Value::Int(4));
        assert_eq!(v(&g,&r,"queried_alive"),Value::Bool(false));
        r.advance(&[(action,Value::Int(0)),(query_id,Value::Int(4))]).unwrap();
        assert_eq!(v(&g,&r,"queried_alive"),Value::Bool(true));
        assert_eq!(v(&g,&r,"queried_x"),Value::Int(0));
    }
}
