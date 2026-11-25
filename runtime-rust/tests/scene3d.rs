use doc_runtime::{scene3d::Scene3d,Value};
fn file()->String{format!("{}/../engine/radar_chase_3d.doc",env!("CARGO_MANIFEST_DIR"))}
#[test]
fn scene_3d_replay_is_doc_authored_and_worker_independent(){
    let mut reference=Vec::new();
    for workers in [1,2,4,8]{
        let mut scene=Scene3d::open(&file(),workers,false).unwrap();
        let mut reports=vec![scene.report().unwrap()];let mut win=false;let mut jumped=false;let mut landed=false;let mut spawned=false;
        for key in "jedsssxwddddsspr".chars(){
            scene.advance(key).unwrap();let frame=scene.frame().unwrap();reports.push(scene.report().unwrap());
            let elevation=match scene.value("next_elevation").unwrap(){Value::Int(n)=>n,_=>panic!("elevation")};
            jumped|=elevation>0;landed|=jumped&&elevation==0;
            win|=scene.value("next_won").unwrap()==Value::Bool(true);
            spawned|=scene.value("next_entity_count").unwrap()==Value::Int(1);
            assert_eq!(frame.vertices.len(),28);assert_eq!(frame.indices.len(),42);
            assert_eq!(frame.draws.last().unwrap().params[1],elevation as i32);
            assert!(frame.draws.len()>=3);
        }
        assert!(win&&jumped&&landed&&spawned);
        if reference.is_empty(){reference=reports;}else{assert_eq!(reference,reports);}
        assert!(scene.advance('q').is_err());
    }
}
#[test]
fn scene_graph_compiles_generated_mesh_shaders(){
    let scene=Scene3d::open(&file(),1,false).unwrap();
    let module=naga::front::wgsl::parse_str(&scene.program.wgsl).unwrap();
    naga::valid::Validator::new(naga::valid::ValidationFlags::all(),naga::valid::Capabilities::all()).validate(&module).unwrap();
}

fn temp_scene(label:&str)->std::path::PathBuf{
    let root=std::env::temp_dir().join(format!("doc-3d-{label}-{}-{}",std::process::id(),std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()));
    let engine=std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../engine");
    for relative in ["radar_chase_3d.doc","engine_math.doc","entity_pool.doc","graphics/arena_vertex.doc","graphics/mesh_fragment.doc","levels/coin_chase.txt","levels/showcase_xs.txt","levels/showcase_ys.txt","levels/arena_vertices.txt","levels/arena_indices.txt"]{
        let dst=root.join(relative);std::fs::create_dir_all(dst.parent().unwrap()).unwrap();
        std::fs::copy(engine.join(relative),dst).unwrap();
    }
    std::fs::create_dir(root.join("audio")).unwrap();
    root
}
#[test]
fn invalid_scene_projection_does_not_publish_successor(){
    let root=temp_scene("invalid");
    let file=root.join("radar_chase_3d.doc");
    let source=std::fs::read_to_string(&file).unwrap().replace("shift_y:draw:1:-20:150","shift_y:draw:1:-20:10");
    std::fs::write(&file,source).unwrap();
    let mut scene=Scene3d::open(file.to_str().unwrap(),1,false).unwrap();
    let before=scene.report().unwrap();assert_eq!(scene.epoch(),0);
    assert!(scene.advance('j').is_err());assert_eq!(scene.epoch(),0);assert_eq!(before,scene.report().unwrap());
    std::fs::remove_dir_all(root).unwrap();
}

#[test]
fn scene_checkpoint_audio_and_restore_preserve_gameplay(){
    let root=temp_scene("checkpoint");
    let file=root.join("radar_chase_3d.doc");let file=file.to_str().unwrap();
    let mut scene=Scene3d::open(file,2,false).unwrap();
    for key in "jedss".chars(){scene.advance(key).unwrap();}
    scene.save("game.chk").unwrap();
    let mut restored=Scene3d::open(file,4,false).unwrap();
    assert_eq!(restored.restore("game.chk").unwrap(),5);
    let state=|s:&Scene3d|s.report().unwrap().split_once(' ').unwrap().1.split_once(' ').unwrap().1.to_owned();
    assert_eq!(state(&scene),state(&restored));
    for key in "sxwddddsspr".chars(){
        scene.advance(key).unwrap();restored.advance(key).unwrap();
        assert_eq!(state(&scene),state(&restored));scene.emit_audio("audio").unwrap();
    }
    let wavs=std::fs::read_dir(root.join("audio")).unwrap().map(|e|e.unwrap().path()).collect::<Vec<_>>();
    assert_eq!(wavs.len(),2);for p in wavs{let bytes=std::fs::read(p).unwrap();assert_eq!(&bytes[..4],b"RIFF");assert_eq!(&bytes[8..12],b"WAVE");}
    let before=restored.report().unwrap();
    std::fs::write(root.join("bad.chk"),b"broken").unwrap();
    assert!(restored.restore("bad.chk").is_err());assert_eq!(before,restored.report().unwrap());
    std::fs::remove_dir_all(root).unwrap();
}

#[test]
fn scene_shader_stage_uses_confined_regular_bounded_source(){
    use std::os::unix::fs::symlink;
    use std::os::unix::ffi::OsStrExt;
    let root=temp_scene("stage-boundary");
    let scene=root.join("radar_chase_3d.doc");
    let stage=root.join("graphics/arena_vertex.doc");
    let original=std::fs::read(&stage).unwrap();
    assert!(Scene3d::open(scene.to_str().unwrap(),1,false).is_ok());
    std::fs::rename(&stage,root.join("graphics/real_vertex.doc")).unwrap();
    symlink("real_vertex.doc",&stage).unwrap();
    assert!(Scene3d::open(scene.to_str().unwrap(),1,false).is_err());
    std::fs::remove_file(&stage).unwrap();
    let path=std::ffi::CString::new(stage.as_os_str().as_bytes()).unwrap();
    assert_eq!(unsafe{libc::mkfifo(path.as_ptr(),0o600)},0);
    assert!(Scene3d::open(scene.to_str().unwrap(),1,false).is_err());
    std::fs::remove_file(&stage).unwrap();
    std::fs::write(&stage,vec![b' ';65_537]).unwrap();
    assert!(Scene3d::open(scene.to_str().unwrap(),1,false).is_err());
    std::fs::write(&stage,&original).unwrap();
    assert!(Scene3d::open(scene.to_str().unwrap(),1,false).is_ok());
    std::fs::remove_dir_all(root).unwrap();
}
