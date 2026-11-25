//! One actual DOC-authored game exercises entities, prefabs, collision,
//! typed source effects, 128 radar nodes, recurrence, failure and CPU oracle.
//! There are no placement directives in engine/radar_chase.doc.
use doc_runtime::{recurrence::Recurrence,Graph,Value};
use std::path::PathBuf;

const CARRIES:&[(&str,&str)]=&[
    ("frame","next_frame"),("player_x","next_x"),("player_y","next_y"),
    ("coin_x","next_coin_x"),("coin_y","next_coin_y"),
    ("score","next_score"),("paused","next_paused"),("won","next_won"),
    ("animation_phase","next_animation_phase"),
    ("entity_ids","next_entity_ids"),("entity_xs","next_entity_xs"),
    ("entity_ys","next_entity_ys"),("next_entity_id","next_next_entity_id"),
    ("issued_high_water","next_issued_high_water"),
    ("prefab_template_xs","template_next_xs"),
    ("prefab_template_ys","template_next_ys"),
];
fn graph()->Graph{
    let p=PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../engine/radar_chase.doc");
    Graph::parse_file(p.to_str().unwrap()).unwrap()
}
fn carries(g:&Graph)->Vec<(usize,usize)> {
    CARRIES.iter().map(|&(a,b)|(g.id(a).unwrap(),g.id(b).unwrap())).collect()
}
fn view(g:&Graph,r:&Recurrence,name:&str)->Value{
    r.value(g.id(name).unwrap()).unwrap()
}
fn all(g:&Graph,r:&Recurrence)->Vec<Value>{
    (0..g.states.len()).map(|i|r.value(i).unwrap()).collect()
}
#[test]
fn one_showcase_game_covers_actual_entity_radar_collision_replay_and_worker_parity(){
    let g=graph();
    assert_eq!(g.states.iter().filter(|s|s.name.starts_with("radar_") &&
        s.definition.is_some()).count(),148);
    assert_eq!(view(&g,&Recurrence::new(g.clone(),carries(&g),&[],1).unwrap(),
        "prefab_template_xs"),Value::Ints(vec![2,5]));
    let f=|name:&str,value:Value|(g.id(name).unwrap(),value);
    for workers in [1,2,4,8]{
        let mut cpu=Recurrence::new_with_retention(
            g.clone(),carries(&g),&[],workers,3).unwrap();
        let mut auto=Recurrence::new_automatic_with_retention(
            g.clone(),carries(&g),&[],workers,3).unwrap();
        assert_eq!(all(&g,&auto),all(&g,&cpu));
        let initial=auto.snapshot_at(0).unwrap();
        assert_eq!(view(&g,&auto,"radar_player_cell"),Value::Int(9));
        assert_eq!(view(&g,&auto,"radar_coin_cell"),Value::Int(20));
        // e instantiates prefab 1, followed by movement, collision and removal.
        for (i,action) in [7,4,4,2,2,2,8,2,5,5,6].iter().enumerate(){
            let facts=[f("action",Value::Int(*action))];
            cpu.advance(&facts).unwrap();
            auto.advance(&facts).unwrap();
            assert_eq!(all(&g,&auto),all(&g,&cpu),
                "automatic work placement altered DOC game at event {i}");
            for (prefix,x_name,y_name) in [("player","player_x","player_y"),("coin","coin_x","coin_y")]{
                let Value::Int(x)=view(&g,&auto,x_name) else{panic!("invalid radar x")};
                let Value::Int(y)=view(&g,&auto,y_name) else{panic!("invalid radar y")};
                assert_eq!(view(&g,&auto,&format!("radar_{prefix}_cell")),Value::Int(8*y+x));
            }
            if i==0{
                assert_eq!(view(&g,&auto,"next_entity_ids"),Value::Ints(vec![1]));
                assert_eq!(view(&g,&auto,"next_entity_xs"),Value::Ints(vec![2]));
                assert_eq!(view(&g,&auto,"next_entity_ys"),Value::Ints(vec![4]));
                assert_eq!(view(&g,&auto,"queried_alive"),Value::Bool(true));
            }
            if i==5{
                assert_eq!(view(&g,&auto,"next_y"),Value::Int(3),
                           "DOC prefab must block movement into its occupied tile");
            }
            if i==6{
                assert_eq!(view(&g,&auto,"next_entity_ids"),Value::Ints(vec![]));
                assert_eq!(view(&g,&auto,"next_issued_high_water"),Value::Int(1));
            }
            if i==7{
                assert_eq!(view(&g,&auto,"next_y"),Value::Int(4),
                           "after despawn DOC collision permits movement");
            }
            if i==8{
                assert_eq!(view(&g,&auto,"next_paused"),Value::Bool(true));
                assert_eq!(view(&g,&auto,"next_animation_phase"),view(&g,&auto,"animation_phase"));
            }
            if i==9{
                assert_eq!(view(&g,&auto,"next_paused"),Value::Bool(false));
            }
            if i==10{
                assert_eq!(view(&g,&auto,"next_animation_phase"),Value::Int(0));
                assert_eq!(view(&g,&auto,"next_score"),Value::Int(0));
            }
        }
        let stats=auto.automatic_stats().unwrap();
        assert!(stats.cpu_nodes>0);
        assert_eq!(stats.gpu_frontiers>0,stats.gpu_nodes>0);
        assert_eq!(auto.reconstruct_epoch(0).unwrap().unwrap(),initial);
        let stable=auto.snapshot_at(auto.epoch()).unwrap();
        let at=auto.epoch();
        // Source-level typed failure must not publish any part of an epoch.
        assert!(auto.advance(&[
            f("reload",Value::Bool(true)),
            f("replacement_xs",Value::Ints(vec![3,4])),
            f("replacement_ys",Value::Ints(vec![9])),
        ]).is_err());
        assert_eq!(auto.epoch(),at);
        assert_eq!(auto.snapshot_at(at).unwrap(),stable);
        // A legal reload is retained as carried typed data.
        auto.advance(&[
            f("reload",Value::Bool(true)),
            f("replacement_xs",Value::Ints(vec![6])),
            f("replacement_ys",Value::Ints(vec![5])),
        ]).unwrap();
        assert_eq!(view(&g,&auto,"template_next_xs"),Value::Ints(vec![6]));
        let restored=auto.fork_current().unwrap();
        assert_eq!(all(&g,&restored),all(&g,&auto));
    }
}
#[test]
fn unified_game_capacity_and_stale_entity_identity_are_backend_independent(){
    let g=graph();
    let mut cpu=Recurrence::new(g.clone(),carries(&g),&[],1).unwrap();
    let mut auto=Recurrence::new_automatic_with_retention(g.clone(),carries(&g),&[],4,2).unwrap();
    let f=|name:&str,value:Value|(g.id(name).unwrap(),value);
    for i in 0..5{
        let facts=[f("action",Value::Int(7))];
        cpu.advance(&facts).unwrap();
        auto.advance(&facts).unwrap();
        assert_eq!(all(&g,&cpu),all(&g,&auto));
        assert_eq!(view(&g,&auto,"next_entity_count"),Value::Int((i+1).min(4)));
    }
    assert_eq!(view(&g,&auto,"next_entity_ids"),Value::Ints(vec![1,2,3,4]));
    assert_eq!(view(&g,&auto,"next_next_entity_id"),Value::Int(5));
    assert_eq!(view(&g,&auto,"next_issued_high_water"),Value::Int(4));
    let remove=[f("action",Value::Int(8)),f("remove_slot",Value::Int(0))];
    cpu.advance(&remove).unwrap();
    auto.advance(&remove).unwrap();
    assert_eq!(all(&g,&cpu),all(&g,&auto));
    assert_eq!(view(&g,&auto,"next_entity_ids"),Value::Ints(vec![2,3,4]));
    assert_eq!(view(&g,&auto,"queried_alive"),Value::Bool(false));
    let spawn=[f("action",Value::Int(7)),f("query_slot",Value::Int(3)),f("query_id",Value::Int(5))];
    cpu.advance(&spawn).unwrap();
    auto.advance(&spawn).unwrap();
    assert_eq!(all(&g,&cpu),all(&g,&auto));
    assert_eq!(view(&g,&auto,"next_entity_ids"),Value::Ints(vec![2,3,4,5]));
    assert_eq!(view(&g,&auto,"next_issued_high_water"),Value::Int(5));
    assert_eq!(view(&g,&auto,"queried_alive"),Value::Bool(true));
    assert_eq!(view(&g,&auto,"queried_x"),Value::Int(2));
    assert_eq!(view(&g,&auto,"queried_y"),Value::Int(4));
    let stale=[f("query_slot",Value::Int(0)),f("query_id",Value::Int(1))];
    cpu.advance(&stale).unwrap();
    auto.advance(&stale).unwrap();
    assert_eq!(all(&g,&cpu),all(&g,&auto));
    assert_eq!(view(&g,&auto,"queried_alive"),Value::Bool(false));
    assert_eq!(view(&g,&auto,"queried_x"),Value::Int(-1));
}
#[test]
fn showcase_gpu_eligibility_is_detected_from_real_doc_without_annotations(){
    let g=graph();
    let r=doc_runtime::Runtime::new(g.clone(),4,doc_runtime::Cutoff::Exact);
    let ready=r.ready();
    let scalar=ready.iter().filter(|&&id|g.states[id].name.starts_with("radar_"))
        .count();
    assert_eq!(scalar,128,"real game has a sizeable naturally ready radar frontier");
    assert!(ready.iter().any(|id|g.states[*id].name=="next_frame"),
        "CPU gameplay and GPU-eligible radar work share a ready frontier");
    let text=std::fs::read_to_string(
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../engine/radar_chase.doc")
    ).unwrap();
    for forbidden in ["backend=gpu","workers=","gpu_task","cpu_task","@gpu","@cpu"] {
        assert!(!text.contains(forbidden),
            "placement instructions must not leak into the authored DOC game");
    }
}

#[cfg(feature="webgpu")]
#[test]
fn all_radar_definitions_validate_gpu_abi_without_source_hints_or_device(){
    let g=graph();
    let selected=g.states.iter().enumerate()
        .filter(|(_,s)|s.name.starts_with("radar_player_")||
                       s.name.starts_with("radar_coin_"))
        .filter(|(_,s)|s.name.rsplit('_').next()
            .is_some_and(|tail|tail.parse::<usize>().is_ok()))
        .map(|(id,_)|id).collect::<Vec<_>>();
    assert_eq!(selected.len(),128);
    for id in selected{
        doc_runtime::wgsl::validate_gpu_derived(&g,id).unwrap();
        doc_runtime::gpu_abi::encode_derived(&g,id).unwrap();
    }
    assert_eq!(doc_runtime::automatic::AUTO_GPU_MIN_LANES,64);
}
