//! Issue #10 first deterministic engine slice: DOC-authored fixed-step state transition.
//! The Rust host advances ticks and commits effects; the game rules are DOC expressions.
//! This is a headless simulation proof, not a renderer or a finished engine.
use doc_runtime::{publication::PublishedRuntime,Cutoff,Graph,Value};
use std::sync::Arc;

const GAME: &str = r#"
source tick: int = 0
source player_x: int = 0
source velocity: int = 2
source wall: int = 7
derive candidate: int (player_x,velocity) = add(player_x,velocity)
derive next_x: int (candidate,wall,player_x) = if(lt(candidate,wall),candidate,player_x)
derive blocked: bool (candidate,wall) = if(lt(candidate,wall),false,true)
derive score: int (tick) = mul(tick,10)
"#;

fn integer(value: Option<&Value>) -> i64 {
    match value { Some(Value::Int(n))=>*n, other=>panic!("expected DOC int: {other:?}") }
}

#[test]
fn fixed_step_doc_game_is_deterministic_and_snapshot_safe() {
    let graph=Graph::parse(GAME).unwrap();
    for workers in [1,2,4,8] {
        let game=PublishedRuntime::new(graph.clone(),workers,Cutoff::Exact).unwrap();
        let original=game.read().unwrap();
        let mut trace=Vec::new();
        for step in 1..=8_i64 {
            let before=game.read().unwrap();
            let x=integer(before.value("next_x"));
            let token=before.token;
            // The host is a narrow clock/effect adapter; DOC computes next_x.
            let next=game.update(token,&[(0,Value::Int(step)),(1,Value::Int(x))]).unwrap();
            assert_eq!(next.source_epoch,token.source_epoch+1);
            let after=game.read().unwrap();
            assert_eq!(after.token,next);
            trace.push((integer(after.value("player_x")),
                        integer(after.value("next_x")),
                        integer(after.value("score")),
                        after.value("blocked").cloned()));
            assert!(game.update(token,&[(1,Value::Int(999))]).is_err(),
                    "stale frame must never overwrite a committed frame");
        }
        let expected=(1..=8_i64).map(|step| {
            let x=if step<=3 {2*step} else {6};
            (x,if x<6 {x+2} else {x},step*10,
             Some(Value::Bool(x>=6)))
        }).collect::<Vec<_>>();
        assert_eq!(trace,expected);
        assert_eq!(original.value("player_x"),Some(&Value::Int(0)));
        assert_eq!(original.value("score"),Some(&Value::Int(0)));
        assert!(!Arc::ptr_eq(&original,&game.read().unwrap()));
    }
}

#[test]
fn rejected_engine_frame_preserves_publication_and_recovers() {
    let game=PublishedRuntime::new(Graph::parse(GAME).unwrap(),4,Cutoff::Exact).unwrap();
    let initial=game.read().unwrap();
    let token=initial.token;
    // Overflow in a derived DOC node must not publish tick or component changes.
    assert!(game.update(token,&[(0,Value::Int(1)),
        (1,Value::Int(i64::MAX))]).is_err());
    let unchanged=game.read().unwrap();
    assert!(Arc::ptr_eq(&initial,&unchanged));
    assert_eq!(unchanged.token,token);
    let committed=game.update(token,&[(0,Value::Int(1)),
        (1,Value::Int(2))]).unwrap();
    assert_eq!(committed.source_epoch,token.source_epoch+1);
    assert_eq!(game.read().unwrap().value("next_x"),Some(&Value::Int(4)));
    assert!(game.update(token,&[(0,Value::Int(2))]).is_err());
}
