use doc_runtime::Graph;
use std::fs;

#[test]
fn imports_and_sampled_effects_reject_lexical_traversal_and_absolute_paths() {
    let root=std::env::temp_dir().join(format!("doc_path_policy_{}",std::process::id()));
    let _=fs::remove_dir_all(&root);
    fs::create_dir_all(root.join("example")).unwrap();
    fs::write(root.join("secret.txt"),"42").unwrap();
    for (index,expression) in [
        "import ../secret.doc",
        "import lib/../secret.doc",
        "import ./secret.doc",
        "import /etc/passwd.doc",
        "import C:/private/stolen.doc",
        "effect value: int = read(\"../secret.txt\")",
        "effect value: int = read(\"./secret.txt\")",
        "effect value: int = read(\"bad\\\\path.txt\")",
        "effect value: int = read(\"//etc/passwd\")",
    ].iter().enumerate() {
        let path=root.join("example").join(format!("case_{index}.doc"));
        fs::write(&path,format!("{expression}\nsource a: int = 1\n")).unwrap();
        assert!(Graph::parse_file(path.to_str().unwrap()).is_err(),"{expression}");
    }
    fs::write(root.join("example").join("data.txt"),"-23\n").unwrap();
    let good=root.join("example").join("good.doc");
    fs::write(&good,"effect value: int = read(\"data.txt\")\n").unwrap();
    assert!(Graph::parse_file(good.to_str().unwrap()).is_ok());
    fs::remove_dir_all(&root).unwrap();
}


#[test]
fn confined_reads_reject_nonregular_and_oversized_files_and_symlink_components(){
    use doc_runtime::{audio::write_tone_wav,checkpoint::load_checkpoint,write_doc_output,Value};
    use std::{ffi::CString,os::unix::{ffi::OsStrExt,fs::symlink}};
    let root=std::env::temp_dir().join(format!("doc_descriptor_policy_{}",std::process::id()));
    let _=fs::remove_dir_all(&root);
    fs::create_dir_all(root.join("data")).unwrap();
    let src=root.join("main.doc");
    let fifo=root.join("data/pipe");
    let name=CString::new(fifo.as_os_str().as_bytes()).unwrap();
    assert_eq!(unsafe{libc::mkfifo(name.as_ptr(),0o600)},0);
    fs::write(root.join("data/large"),vec![b' ';1_048_577]).unwrap();
    fs::write(root.join("data/big.doc"),vec![b' ';65_537]).unwrap();
    fs::write(root.join("data/value"),"42").unwrap();
    symlink(root.join("data"),root.join("alias")).unwrap();
    symlink(root.join("data/value"),root.join("data/link")).unwrap();
    for program in [
        "effect x: int = read(\"data/pipe\")",
        "effect x: int = read(\"data/large\")",
        "effect x: int = read(\"data\")",
        "effect x: int = read(\"alias/value\")",
        "effect x: int = read(\"data/link\")",
        "import data/big.doc",
    ] {
        fs::write(&src,program).unwrap();
        assert!(Graph::parse_file(src.to_str().unwrap()).is_err(),"{program}");
    }
    assert!(Graph::parse_file(fifo.to_str().unwrap()).is_err());
    fs::write(&src,"effect x: int = read(\"data/value\")").unwrap();
    let graph=Graph::parse_file(src.to_str().unwrap()).unwrap();
    assert!(load_checkpoint(src.to_str().unwrap(),"data/pipe",graph,vec![],1,1).is_err());
    assert!(write_doc_output(src.to_str().unwrap(),"alias/out",&Value::Int(7)).is_err());
    assert!(write_tone_wav(src.to_str().unwrap(),"alias/tone.wav",440,10).is_err());
    assert!(!root.join("data/out").exists());
    assert!(!root.join("data/tone.wav").exists());
    // A leaf symlink is replaced as a directory entry, never followed.
    write_doc_output(src.to_str().unwrap(),"data/link",&Value::Int(7)).unwrap();
    assert_eq!(fs::read_to_string(root.join("data/value")).unwrap(),"42");
    assert_eq!(fs::read_to_string(root.join("data/link")).unwrap(),"7\n");
    assert!(!fs::symlink_metadata(root.join("data/link")).unwrap().file_type().is_symlink());
    assert!(write_doc_output(src.to_str().unwrap(),"data/link",&Value::Nat("00".into())).is_err());
    assert_eq!(fs::read_to_string(root.join("data/link")).unwrap(),"7\n");
    fs::remove_dir_all(root).unwrap();
}


#[test]
fn compiler_and_selected_gpu_share_bounded_source_snapshot_admission(){
    use std::{ffi::CString,os::unix::ffi::OsStrExt,process::Command};
    use doc_runtime::Value;
    let root=std::env::temp_dir().join(format!("doc_snapshot_policy_{}",std::process::id()));
    let _=fs::remove_dir_all(&root);
    fs::create_dir_all(&root).unwrap();
    let src=root.join("input.doc");
    let fifo=root.join("pipe.doc");
    let name=CString::new(fifo.as_os_str().as_bytes()).unwrap();
    assert_eq!(unsafe{libc::mkfifo(name.as_ptr(),0o600)},0);
    let oversized=root.join("large.doc");
    fs::write(&oversized,vec![b' ';1_048_577]).unwrap();
    for path in [&fifo,&oversized]{
        assert!(Graph::parse_pure_gpu_file(path.to_str().unwrap()).is_err());
        let out=Command::new(env!("CARGO_BIN_EXE_doc-compile"))
            .arg(path).arg("--emit-c").arg(root.join("out.c"))
            .arg("--out").arg(root.join("out")).output().unwrap();
        assert!(!out.status.success());
        assert!(!root.join("out.c").exists());
        assert!(!root.join("out").exists());
    }
    fs::write(&src,"source x: int = 7\nderive y: int (x) = add(x,1)\n").unwrap();
    let file=src.to_str().unwrap();
    let snapshot=Graph::read_source_file(file).unwrap();
    let pure=Graph::parse_pure_gpu_file(file).unwrap();
    assert_eq!(pure.states[0].initial,Some(Value::Int(7)));
    // Changing the file after the snapshot cannot change AOT source admission.
    fs::write(&src,"effect x: int = read(\"pipe.doc\")\n").unwrap();
    let error=Graph::parse_pure_gpu_file(file).unwrap_err();
    assert!(error.contains("DOC_GPU_UNSUPPORTED: source imports and effects"));
    let (aot,assets)=Graph::parse_aot_snapshot(file,&snapshot,false).unwrap();
    assert!(assets.is_empty());
    assert_eq!(aot.states[0].initial,Some(Value::Int(7)));
    assert!(aot.id("y").is_some());
    fs::write(&src,"import missing.doc\n").unwrap();
    assert!(Graph::parse_pure_gpu_file(file).unwrap_err().contains("DOC_GPU_UNSUPPORTED"));
    fs::remove_dir_all(root).unwrap();
}
