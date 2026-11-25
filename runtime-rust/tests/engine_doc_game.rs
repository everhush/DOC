//! End-to-end DOC-authored game state, checked independently from the text host.
use doc_runtime::{recurrence::Recurrence,Cutoff,Graph,Runtime,Value};
use std::path::PathBuf;

const CARRIES: &[(&str,&str)] = &[
    ("frame","next_frame"), ("player_x","next_x"), ("player_y","next_y"),
    ("coin_x","next_coin_x"), ("coin_y","next_coin_y"),
    ("score","next_score"), ("paused","next_paused"), ("won","next_won"),
    ("animation_phase","next_animation_phase"),
];
fn scene()->Graph{
    let file=PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../engine/coin_chase.doc");
    Graph::parse_file(file.to_str().unwrap()).unwrap()
}
fn value(game:&Recurrence,g:&Graph,name:&str)->Value{
    game.value(g.id(name).unwrap()).unwrap()
}
fn new_game(g:Graph,workers:usize,facts:&[(usize,Value)])->Recurrence{
    let carry=CARRIES.iter().map(|&(src,dst)|
        (g.id(src).unwrap(),g.id(dst).unwrap())).collect();
    Recurrence::new_with_retention(g,carry,facts,workers,3).unwrap()
}
fn frame(game:&Recurrence,g:&Graph)->(i64,i64,i64,bool,bool){
    let get=|name|match value(game,g,name){Value::Int(n)=>n,x=>panic!("{name} not int: {x:?}")};
    (get("next_x"),get("next_y"),get("next_score"),
     value(game,g,"next_paused")==Value::Bool(true),
     value(game,g,"next_won")==Value::Bool(true))
}
fn replay(g:Graph,workers:usize,events:&[i64])->Vec<(i64,i64,i64,bool,bool)>{
    let action=g.id("action").unwrap();
    let mut game=new_game(g.clone(),workers,&[]);
    let mut states=vec![frame(&game,&g)];
    for &event in events {
        game.advance(&[(action,Value::Int(event))]).unwrap();
        states.push(frame(&game,&g));
    }
    states
}
#[test]
fn replay_move_wall_coin_win_pause_and_restart_under_different_worker_counts(){
    let g=scene();
    let actions=[4,4,2,4,4,4,4,2,2,4,5,4,5,6,4];
    let baseline=replay(g.clone(),1,&actions);
    assert_eq!(baseline[0],(1,1,0,false,false));
    assert_eq!(baseline[1],(2,1,0,false,false));
    assert_eq!(baseline[2],(2,1,0,false,false),"wall must block movement");
    assert_eq!(baseline[5],(4,2,1,false,false),"first coin collected");
    assert_eq!(baseline[9],(6,4,2,false,true),"second coin wins");
    assert_eq!(baseline[10],baseline[9],"winning is terminal until restart");
    assert!(baseline[11].3,"pause toggles");
    assert_eq!(baseline[12].0,baseline[11].0,"paused game must not move");
    assert!(!baseline[13].3,"unpause");
    assert_eq!(baseline[14],(1,1,0,false,false),"restart resets DOC game");
    assert_eq!(baseline[15],(2,1,0,false,false));
    for workers in [2,4,8,17] {
        assert_eq!(replay(g.clone(),workers,&actions),baseline,
                   "worker count changed DOC-authored game replay");
    }
}
#[test]
fn failed_fixed_step_does_not_commit_or_evict_old_game_epoch(){
    let g=scene();
    let initial_frame=g.id("frame").unwrap();
    let action=g.id("action").unwrap();
    let mut game=new_game(g.clone(),4,&[(initial_frame,Value::Int(i64::MAX-1))]);
    let pinned=game.snapshot_at(0).unwrap();
    assert_eq!(game.epoch(),0);
    assert!(game.advance(&[(action,Value::Int(4))]).is_err(),
        "next_frame must overflow on the prospective epoch");
    assert_eq!(game.epoch(),0);
    assert_eq!(game.snapshot_at(0).unwrap(),pinned);
    assert_eq!(value(&game,&g,"next_x"),Value::Int(1));
    assert!(game.advance(&[(initial_frame,Value::Int(0))]).is_err(),
        "carried state cannot be overridden by host facts");
}
#[test]
fn invalid_effect_and_unknown_source_cannot_replace_game_rules(){
    let g=scene();
    assert!(g.id("next_score").is_some());
    assert!(g.id("next_won").is_some());
    assert!(g.id("wall_hit").is_some());
    assert!(g.id("missing_external_rule").is_none());
    let bad=Graph::parse(concat!(
       "source score: int = 0\n",
       "derive score: int (score) = add(score,1)\n"
    ));
    assert!(bad.is_err(),"game engine must retain DOC graph validation");
}

#[test]
fn typed_level_effect_is_stable_and_reactive_without_reloading_inside_frontier() {
    let g=scene();
    assert!(g.id("level").is_some());
    let mut rt=Runtime::new(g.clone(),4,Cutoff::Exact);
    rt.stabilize().unwrap();
    let id=|name:&str|g.id(name).unwrap();
    assert_eq!(rt.value(id("level")),Some(Value::Ints(vec![8,6,3,1,2])));
    assert_eq!(rt.value(id("width")),Some(Value::Int(8)));
    assert_eq!(rt.value(id("wall_x")),Some(Value::Int(3)));
    assert_eq!(rt.value(id("goal")),Some(Value::Int(2)));
    let before=rt.snapshot();
    rt.update(&[(id("level"),Value::Ints(vec![10,9,5,6,3]))]).unwrap();
    rt.stabilize().unwrap();
    assert_eq!(rt.value(id("width")),Some(Value::Int(10)));
    assert_eq!(rt.value(id("height")),Some(Value::Int(9)));
    assert_eq!(rt.value(id("wall_x")),Some(Value::Int(5)));
    assert_eq!(rt.value(id("wall_y")),Some(Value::Int(6)));
    assert_eq!(rt.value(id("goal")),Some(Value::Int(3)));
    assert_eq!(before[id("wall_x")],Some(Value::Int(3)));
    assert!(rt.oracle().is_ok(),"typed scene source must remain oracle-valid");
}

#[test]
fn doc_authored_animation_phase_loops_and_freezes_while_paused() {
    let g=scene();
    let action=g.id("action").unwrap();
    let mut game=new_game(g.clone(),4,&[]);
    let phase=|r:&Recurrence|value(r,&g,"next_animation_phase");
    assert_eq!(phase(&game),Value::Int(1));
    for expected in 2..=8 {
        game.advance(&[(action,Value::Int(0))]).unwrap();
        assert_eq!(phase(&game),Value::Int(expected));
    }
    game.advance(&[(action,Value::Int(5))]).unwrap();
    assert_eq!(value(&game,&g,"next_paused"),Value::Bool(true));
    assert_eq!(phase(&game),Value::Int(8));
    game.advance(&[(action,Value::Int(0))]).unwrap();
    assert_eq!(phase(&game),Value::Int(8));
    game.advance(&[(action,Value::Int(5))]).unwrap();
    assert_eq!(value(&game,&g,"next_paused"),Value::Bool(false));
    assert_eq!(phase(&game),Value::Int(9));
    game.advance(&[(action,Value::Int(6))]).unwrap();
    assert_eq!(phase(&game),Value::Int(0));
    for _ in 0..16 { game.advance(&[(action,Value::Int(0))]).unwrap(); }
    assert_eq!(phase(&game),Value::Int(0));
    let pinned=game.snapshot_at(game.epoch()).unwrap();
    let phase_id=g.id("next_animation_phase").unwrap();
    assert_eq!(pinned[phase_id],Some(Value::Int(0)));
}
