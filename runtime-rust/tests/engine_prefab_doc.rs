//! Data-driven DOC prefab composition, typed asset replacement, immutable state, stale-handle safety.
use doc_runtime::{recurrence::Recurrence,Graph,Value};
use std::path::PathBuf;

fn graph()->Graph {
    let path=PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../engine/prefab_scene.doc");
    Graph::parse_file(path.to_str().unwrap()).unwrap()
}
fn scene(g:&Graph,workers:usize,init:&[(usize,Value)])->Recurrence {
    let carries=[("ids","next_ids"),("xs","next_xs"),("ys","next_ys"),
                 ("next_id","next_next_id"),("issued_high_water","next_issued_high_water"),
                 ("prefab_xs","next_prefab_xs"),("prefab_ys","next_prefab_ys")];
    Recurrence::new_with_retention(g.clone(),carries.iter().map(|&(a,b)|
        (g.id(a).unwrap(),g.id(b).unwrap())).collect(),init,workers,3).unwrap()
}
fn v(g:&Graph,r:&Recurrence,name:&str)->Value {
    r.value(g.id(name).unwrap()).unwrap()
}
#[test]
fn typed_prefab_instantiation_replacement_capacity_and_lifetime() {
    let g=graph();
    let f=|name:&str,v:Value|(g.id(name).unwrap(),v);
    for workers in [1,2,4,8,17] {
        let mut r=scene(&g,workers,&[]);
        let initial=r.snapshot_at(0).unwrap();
        assert_eq!(v(&g,&r,"prefab_xs"),Value::Ints(vec![4,9,-2]));
        assert_eq!(v(&g,&r,"prefab_ys"),Value::Ints(vec![2,3,6]));
        r.advance(&[f("action",Value::Int(1)),f("template_slot",Value::Int(0))]).unwrap();
        assert_eq!(v(&g,&r,"next_ids"),Value::Ints(vec![1,2]));
        assert_eq!(v(&g,&r,"next_xs"),Value::Ints(vec![1,4]));
        assert_eq!(v(&g,&r,"next_ys"),Value::Ints(vec![1,2]));
        // A typed asset refresh is an ordinary explicit epoch fact, never hidden pure I/O.
        let first=r.snapshot_at(1).unwrap();
        r.advance(&[f("reload",Value::Bool(true)),
                    f("replacement_xs",Value::Ints(vec![11,12])),
                    f("replacement_ys",Value::Ints(vec![21,22])),
                    f("template_slot",Value::Int(1)),f("action",Value::Int(1))]).unwrap();
        assert_eq!(v(&g,&r,"next_ids"),Value::Ints(vec![1,2,3]));
        assert_eq!(v(&g,&r,"next_xs"),Value::Ints(vec![1,4,12]));
        assert_eq!(v(&g,&r,"next_ys"),Value::Ints(vec![1,2,22]));
        assert_eq!(first[g.id("next_ids").unwrap()],Some(Value::Ints(vec![1,2])));
        // An invalid template index must not access out of bounds or create a partial entity.
        r.advance(&[f("template_slot",Value::Int(i64::MAX)),f("action",Value::Int(1))]).unwrap();
        assert_eq!(v(&g,&r,"next_ids"),Value::Ints(vec![1,2,3]));
        // Replaced assets survive the next epoch because they are carried, not replayed facts.
        assert_eq!(v(&g,&r,"next_prefab_xs"),Value::Ints(vec![11,12]));
        assert_eq!(v(&g,&r,"next_prefab_ys"),Value::Ints(vec![21,22]));
        let epoch=r.epoch();
        let before=r.snapshot_at(epoch).unwrap();
        // An inconsistent typed pair must fail before any state is published.
        assert!(r.advance(&[f("reload",Value::Bool(true)),
                           f("replacement_xs",Value::Ints(vec![1,2])),
                           f("replacement_ys",Value::Ints(vec![1])),
                           f("action",Value::Int(1))]).is_err());
        assert_eq!(r.epoch(),epoch);
        assert_eq!(r.snapshot_at(epoch).unwrap(),before);
        // Typed invalid refresh fails, including changes to another source in the same batch.
        assert!(r.advance(&[f("replacement_ys",Value::Bool(true)),
                            f("reload",Value::Bool(true))]).is_err());
        assert_eq!(r.epoch(),epoch);
        assert_eq!(r.snapshot_at(epoch).unwrap(),before);
        // Fully despawn the scene. The lifetime high-watermark survives.
        for slot in [2,1,0] {
            r.advance(&[f("action",Value::Int(2)),f("remove_slot",Value::Int(slot))]).unwrap();
        }
        assert_eq!(v(&g,&r,"next_ids"),Value::Ints(vec![]));
        assert_eq!(v(&g,&r,"next_issued_high_water"),Value::Int(3));
        assert!(r.advance(&[f("next_id",Value::Int(1))]).is_err());
        r.advance(&[f("reload",Value::Bool(true)),
                    f("replacement_xs",Value::Ints(vec![7])),
                    f("replacement_ys",Value::Ints(vec![8])),
                    f("template_slot",Value::Int(0)),
                    f("action",Value::Int(1))]).unwrap();
        assert_eq!(v(&g,&r,"next_ids"),Value::Ints(vec![4]));
        assert_eq!(v(&g,&r,"next_xs"),Value::Ints(vec![7]));
        assert_eq!(v(&g,&r,"next_ys"),Value::Ints(vec![8]));
        r.advance(&[f("action",Value::Int(0)),f("query_slot",Value::Int(0)),
                    f("query_id",Value::Int(2))]).unwrap();
        assert_eq!(v(&g,&r,"queried_alive"),Value::Bool(false));
        assert_eq!(r.reconstruct_epoch(0).unwrap().unwrap(),initial);
    }
}
#[test]
fn resource_budget_clamps_and_rejects_overflow_atomically() {
    let g=graph();
    let f=|name:&str,v:Value|(g.id(name).unwrap(),v);
    let mut limited=scene(&g,4,&[f("capacity",Value::Int(1))]);
    limited.advance(&[f("action",Value::Int(1)),f("capacity",Value::Int(1))]).unwrap();
    assert_eq!(v(&g,&limited,"next_ids"),Value::Ints(vec![1]));
    let mut over=scene(&g,4,&[f("next_id",Value::Int(i64::MAX))]);
    let initial=over.snapshot_at(0).unwrap();
    assert!(over.advance(&[f("action",Value::Int(1))]).is_err());
    assert_eq!(over.epoch(),0);
    assert_eq!(over.snapshot_at(0).unwrap(),initial);
}
