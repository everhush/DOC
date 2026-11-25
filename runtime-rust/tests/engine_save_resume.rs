//! Black-box Linux DOC game save/resume, with independent replay oracle.
use std::{fs,path::PathBuf,process::{Command,Output}};

fn run(src:&str,args:&[&str])->Output{
    let mut command=Command::new(env!("CARGO_BIN_EXE_doc-game"));
    command.arg(src).args(args);
    command.output().unwrap()
}
fn frames(out:&Output)->Vec<String>{
    String::from_utf8(out.stdout.clone()).unwrap().lines()
        .filter(|s|s.starts_with("DOC_GAME_FRAME:"))
        .map(str::to_string).collect()
}
#[test]
fn saved_doc_game_resume_matches_uninterrupted_replay_and_rejects_corruption(){
    let root=std::env::temp_dir().join(format!("doc_game_save_{}",std::process::id()));
    let _=fs::remove_dir_all(&root);
    fs::create_dir_all(root.join("levels")).unwrap();
    fs::create_dir_all(root.join("state")).unwrap();
    fs::create_dir_all(root.join("audio")).unwrap();
    let original=PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../engine");
    for file in ["coin_chase.doc","engine_math.doc","levels/coin_chase.txt"]{
        let dest=root.join(file);
        fs::copy(original.join(file),dest).unwrap();
    }
    let path=root.join("coin_chase.doc");
    let path=path.to_str().unwrap();
    let baseline=run(path,&["--headless","--workers=1","--replay=ddsddddsspr"]);
    assert!(baseline.status.success(),"{:?}",baseline.stderr);
    let prefix=run(path,&["--headless","--workers=1","--replay=dds",
        "--save=state/run.chk"]);
    assert!(prefix.status.success(),"{:?}",prefix.stderr);
    assert_eq!(frames(&prefix),frames(&baseline)[..4]);
    let saved=fs::read(root.join("state/run.chk")).unwrap();
    let resumed=run(path,&["--headless","--workers=4","--load=state/run.chk",
        "--replay=ddddsspr"]);
    assert!(resumed.status.success(),"{:?}",resumed.stderr);
    assert_eq!(frames(&resumed),frames(&baseline)[3..],
               "DOC prefix+suffix must equal uninterrupted exact state transitions");
    assert!(String::from_utf8_lossy(&resumed.stdout)
        .contains("DOC_GAME_RESTORED: saved_epoch=3 new_epoch=0"));
    let mut broken=saved.clone();
    broken[0]=b'X';
    fs::write(root.join("state/run.chk"),broken).unwrap();
    let error=run(path,&["--headless","--load=state/run.chk","--replay=d"]);
    assert!(!error.status.success());
    assert!(frames(&error).is_empty(),"rejected restore must not display a frame");
    assert!(String::from_utf8_lossy(&error.stderr).contains("DOC_GAME_ERROR:"));
    fs::write(root.join("state/run.chk"),saved).unwrap();
    let blocked=run(path,&["--headless","--load=../outside.chk"]);
    assert!(!blocked.status.success());
    assert!(frames(&blocked).is_empty());
    // The first collected coin generates a genuine WAV effect from DOC cue facts.
    let tone=run(path,&["--headless","--workers=4","--replay=ddsdd",
        "--audio-dir=audio"]);
    assert!(tone.status.success(),"{:?}",tone.stderr);
    assert!(String::from_utf8_lossy(&tone.stdout)
        .contains("DOC_GAME_AUDIO_WAV: epoch=5 path=audio/cue_5.wav"));
    let wav=fs::read(root.join("audio/cue_5.wav")).unwrap();
    assert_eq!(&wav[0..4],b"RIFF");
    assert_eq!(&wav[8..12],b"WAVE");
    fs::remove_dir_all(root).unwrap();
}
