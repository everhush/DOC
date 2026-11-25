//! Black-box integrated DOC Radar Chase playthrough and process restart.
//! Actual Linux native executable; no mocking game rules or source placement.
use std::{fs,path::PathBuf,process::{Command,Output}};

fn game(path:&str,args:&[&str])->Output{
    Command::new(env!("CARGO_BIN_EXE_doc-game")).arg(path).args(args).output().unwrap()
}
fn game_frames(out:&Output)->Vec<String>{
    String::from_utf8_lossy(&out.stdout).lines()
        .filter(|s|s.starts_with("DOC_GAME_FRAME:") ||
            s.starts_with("DOC_GAME_ENTITIES:") || s.starts_with("DOC_GAME_RADAR:"))
        .map(str::to_owned).collect()
}
#[test]
fn unified_showcase_replay_save_restore_prefab_collision_audio_and_auto_scheduler(){
    let root=std::env::temp_dir().join(format!("doc_radar_{}",std::process::id()));
    let _=fs::remove_dir_all(&root);
    fs::create_dir_all(root.join("levels")).unwrap();
    fs::create_dir_all(root.join("state")).unwrap();
    fs::create_dir_all(root.join("audio")).unwrap();
    let engine=PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../engine");
    for file in ["radar_chase.doc","engine_math.doc","entity_pool.doc",
                 "levels/coin_chase.txt","levels/showcase_xs.txt",
                 "levels/showcase_ys.txt"]{
        fs::copy(engine.join(file),root.join(file)).unwrap();
    }
    let path=root.join("radar_chase.doc");
    let src=path.to_str().unwrap();
    let replay="edsssxwddddsspr";
    let baseline=game(src,&["--headless","--workers=1",&format!("--replay={replay}")]);
    assert!(baseline.status.success(),"{:?}",baseline.stderr);
    let stdout=String::from_utf8_lossy(&baseline.stdout);
    assert!(stdout.contains("DOC_GAME_ENTITIES: count=1 ids=[1]"));
    assert!(stdout.contains("DOC_GAME_ENTITIES: count=0 ids=[]"));
    assert!(stdout.contains("DOC_GAME_RADAR: pre_action_player_cell=9 pre_action_coin_cell=20"));
    assert!(stdout.contains("won=true"),"integrated replay must demonstrate winning");
    assert!(stdout.contains("score=2"),"DOC score must reach the goal");
    assert!(String::from_utf8_lossy(&baseline.stderr).contains("DOC_AUTO_SUMMARY:"));
    for workers in ["2","4","8"]{
        let replay_arg=format!("--replay={replay}");
        let alternative=game(src,&["--headless",&format!("--workers={workers}"),&replay_arg]);
        assert!(alternative.status.success(),"{:?}",alternative.stderr);
        assert_eq!(game_frames(&alternative),game_frames(&baseline),
                   "game semantics must not depend on worker count");
    }
    let prefix=game(src,&["--headless","--replay=edsss","--save=state/level.chk"]);
    assert!(prefix.status.success(),"{:?}",prefix.stderr);
    let suffix=game(src,&["--headless","--load=state/level.chk",
                           "--replay=xwddddsspr"]);
    assert!(suffix.status.success(),"{:?}",suffix.stderr);
    let complete=game_frames(&baseline);
    let prefix_frames=game_frames(&prefix);
    let suffix_frames=game_frames(&suffix);
    // Each tick prints a frame, entity columns and the DOC radar reduction.
    assert_eq!(prefix_frames,complete[..prefix_frames.len()]);
    assert_eq!(suffix_frames,complete[prefix_frames.len()-3..]);
    assert!(String::from_utf8_lossy(&suffix.stdout).contains("DOC_GAME_RESTORED"));
    let audio=game(src,&["--headless","--replay=ddsdd",
                         "--audio-dir=audio"]);
    assert!(audio.status.success(),"{:?}",audio.stderr);
    assert!(fs::read(root.join("audio/cue_5.wav")).unwrap().starts_with(b"RIFF"));
    let corrupt=root.join("state/level.chk");
    fs::write(&corrupt,b"DOC-CHECKPOINT/1\ncorrupt\n").unwrap();
    let failed=game(src,&["--headless","--load=state/level.chk"]);
    assert!(!failed.status.success());
    assert!(game_frames(&failed).is_empty(),"failed restore must publish no frame");
    fs::remove_dir_all(root).unwrap();
}
