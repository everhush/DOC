//! DOC-authored reusable half-open collision: deterministic, overflow-free and atomic.
use doc_runtime::{publication::PublishedRuntime,Cutoff,Graph,Value};
use std::{path::PathBuf,sync::Arc};

fn collision() -> Graph {
    let file=PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../engine/collision_2d.doc");
    // Test the imported DOC helper under the same source parser used by the game.
    let source=PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../engine/collision_scene.doc");
    assert!(file.is_file());
    Graph::parse_file(source.to_str().unwrap()).unwrap()
}
fn set(g:&Graph,name:&str,n:i64)->(usize,Value) {
    (g.id(name).unwrap(),Value::Int(n))
}
#[test]
fn half_open_aabb_collision_is_doc_authored_and_worker_deterministic() {
    let g=collision();
    for workers in [1,2,4,8,17] {
        let runtime=PublishedRuntime::new(g.clone(),workers,Cutoff::Exact).unwrap();
        let original=runtime.read().unwrap();
        assert_eq!(original.value("collides"),Some(&Value::Bool(true)));
        let mut token=original.token;
        for (x,expected) in [(2,false),(1,true),(-2,false),(0,true)] {
            token=runtime.update(token,&[set(&g,"bx0",x),set(&g,"bx1",x+1)]).unwrap();
            assert_eq!(runtime.read().unwrap().value("collides"),Some(&Value::Bool(expected)));
        }
        // Touching at x=2 does not collide, including for zero-width rectangles.
        token=runtime.update(token,&[set(&g,"bx0",2),set(&g,"bx1",3)]).unwrap();
        assert_eq!(runtime.read().unwrap().value("collides"),Some(&Value::Bool(false)));
        token=runtime.update(token,&[set(&g,"bx0",0),set(&g,"bx1",0)]).unwrap();
        assert_eq!(runtime.read().unwrap().value("collides"),Some(&Value::Bool(false)));
        // Reversed interval and vertical edge touching must both be false.
        token=runtime.update(token,&[set(&g,"bx0",2),set(&g,"bx1",1)]).unwrap();
        assert_eq!(runtime.read().unwrap().value("collides"),Some(&Value::Bool(false)));
        token=runtime.update(token,&[set(&g,"bx0",0),set(&g,"bx1",1),set(&g,"by0",2),set(&g,"by1",3)]).unwrap();
        assert_eq!(runtime.read().unwrap().value("collides"),Some(&Value::Bool(false)));
        // Type failure rolls back the entire multi-source frame.
        let before=runtime.read().unwrap();
        assert!(runtime.update(token,&[(g.id("bx0").unwrap(),Value::Bool(true)),set(&g,"by0",0)]).is_err());
        assert!(Arc::ptr_eq(&before,&runtime.read().unwrap()));
        assert_eq!(runtime.read().unwrap().token,token);
        let next=runtime.update(token,&[set(&g,"bx0",0),set(&g,"bx1",1),set(&g,"by0",0),set(&g,"by1",1)]).unwrap();
        assert_eq!(runtime.read().unwrap().value("collides"),Some(&Value::Bool(true)));
        assert!(runtime.update(token,&[set(&g,"bx0",1)]).is_err());
        assert_eq!(runtime.read().unwrap().token,next);
        assert_eq!(original.value("collides"),Some(&Value::Bool(true)));
    }
}

#[test]
fn half_open_aabb_extreme_i64_endpoints_need_no_arithmetic_and_remain_atomic() {
    let g = collision();
    for workers in [1, 4, 17] {
        let runtime = PublishedRuntime::new(g.clone(), workers, Cutoff::Exact).unwrap();
        let original = runtime.read().unwrap();
        let mut token = original.token;
        // This deliberately exercises comparisons at both signed endpoints.
        // A collision helper that computes lengths or increments endpoints
        // would overflow here even though these intervals are well-formed.
        token = runtime.update(token, &[
            set(&g, "ax0", i64::MIN), set(&g, "ax1", i64::MAX),
            set(&g, "bx0", i64::MAX - 1), set(&g, "bx1", i64::MAX),
        ]).unwrap();
        assert_eq!(runtime.read().unwrap().value("collides"), Some(&Value::Bool(true)));
        token = runtime.update(token, &[
            set(&g, "bx0", i64::MIN), set(&g, "bx1", i64::MIN + 1),
        ]).unwrap();
        assert_eq!(runtime.read().unwrap().value("collides"), Some(&Value::Bool(true)));
        token = runtime.update(token, &[
            set(&g, "bx0", i64::MAX), set(&g, "bx1", i64::MAX),
        ]).unwrap();
        assert_eq!(runtime.read().unwrap().value("collides"), Some(&Value::Bool(false)));
        let before = runtime.read().unwrap();
        assert!(runtime.update(token, &[
            set(&g, "bx0", i64::MIN),
            (g.id("bx1").unwrap(), Value::Bool(true)),
        ]).is_err());
        assert!(Arc::ptr_eq(&before, &runtime.read().unwrap()));
        assert_eq!(runtime.read().unwrap().token, token);
        assert_eq!(original.value("collides"), Some(&Value::Bool(true)));
    }
}
