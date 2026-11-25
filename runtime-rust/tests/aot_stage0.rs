use std::{fs,path::{Path,PathBuf},process::{Command,Output},sync::atomic::{AtomicUsize,Ordering}};
static NEXT:AtomicUsize=AtomicUsize::new(0);
struct Scratch(PathBuf);
impl Scratch{fn new()->Self{let path=std::env::temp_dir().join(format!("doc-aot-{}-{}",std::process::id(),NEXT.fetch_add(1,Ordering::Relaxed)));fs::create_dir(&path).unwrap();Self(path)}}
impl Drop for Scratch{fn drop(&mut self){let _=fs::remove_dir_all(&self.0);}}
fn run(exe:&Path,args:&[&str])->Output{Command::new(exe).args(args).env_remove("DOC_WORKERS").output().unwrap()}
fn compile(dir:&Path,source:&str)->(PathBuf,PathBuf){
    let doc=dir.join("input.doc");let c=dir.join("output.c");let exe=dir.join("native");let ir=dir.join("output.ir");
    fs::write(&doc,source).unwrap();
    let output=Command::new(env!("CARGO_BIN_EXE_doc-compile")).arg(&doc).arg("--emit-c").arg(&c).arg("--out").arg(&exe).arg("--emit-ir").arg(&ir).output().unwrap();
    assert!(output.status.success(),"{}",String::from_utf8_lossy(&output.stderr));
    assert!(fs::read(&exe).unwrap().starts_with(b"\x7fELF"));
    assert!(fs::read_to_string(ir).unwrap().starts_with("DOC-TYPED-IR/1\n"));
    (doc,exe)
}
fn compare(doc:&Path,exe:&Path,args:&[&str]){
    let reference=Command::new(env!("CARGO_BIN_EXE_doc")).arg(doc).args(args).output().unwrap();
    let actual=run(exe,args);
    assert_eq!(actual.status.success(),reference.status.success(),"{args:?}: {}",String::from_utf8_lossy(&actual.stderr));
    assert_eq!(actual.stdout,reference.stdout,"{args:?}");
}
#[test]
fn standalone_scalar_c_matches_rust_checked_lazy_and_recurrent_semantics(){
    let tmp=Scratch::new();
    let (doc,exe)=compile(&tmp.0,"source a: int = 0\nsource b: int = 1\nsource flag: bool = false\nderive next: int (a,b) = add(a,b)\nderive halt: bool (a) = eq(a,3)\nderive guarded: int (flag,a) = if(flag,mul(a,9223372036854775807),-7)\n");
    for args in [vec![],vec!["a=-9223372036854775808"],vec!["a=2","flag=false"],vec!["a=2","flag=true"],vec!["a=9223372036854775807"],vec!["a=4","a=5"],vec!["next=1"],vec!["flag=1"],vec!["--demand=halt","a=9223372036854775807"],vec!["--through=4","a=next","--fact=2:b=3"],vec!["--until=halt","--max-epochs=7","a=next"],vec!["--through=2","a=next","--fact=1:b=9223372036854775807"],vec!["--through=2","a=next","--fact=1:a=3"]] {compare(&doc,&exe,&args);}
    let result=run(&exe,&["--backend=gpu"]);assert!(!result.status.success());assert!(result.stdout.is_empty());
    // No source file or reference evaluator is needed to run generated code.
    fs::remove_file(&doc).unwrap();
    let empty=tmp.0.join("empty");fs::create_dir(&empty).unwrap();
    let output=Command::new(&exe).current_dir(empty).env_clear().args(["a=2"]).output().unwrap();
    assert!(output.status.success());assert!(String::from_utf8_lossy(&output.stdout).contains("next: 3"));
}
#[test]
fn incremental_demand_cutoff_and_failed_batch_publication(){
    let tmp=Scratch::new();
    let (doc,exe)=compile(&tmp.0,"source x: int = 1\nsource y: int = 0\nderive zero: int (x) = sub(x,x)\nderive stable: int (zero) = add(zero,2)\nderive risky: int (y) = mul(y,9223372036854775807)\n");
    let args=["--demand=stable","--next","--demand=stable","x=2","--next","--demand=stable","x=2","--next","--demand=risky","y=2"];
    let output=run(&exe,&args);assert!(!output.status.success());
    assert_eq!(String::from_utf8_lossy(&output.stdout),"epoch: 0\nstable: 2\nepoch: 1\nstable: 2\nepoch: 2\nstable: 2\n");
    let counts=String::from_utf8_lossy(&output.stderr).lines().filter(|x|x.starts_with("DOC_AOT_EVALUATIONS:")).map(str::to_owned).collect::<Vec<_>>();
    assert_eq!(counts,["DOC_AOT_EVALUATIONS: 2","DOC_AOT_EVALUATIONS: 1","DOC_AOT_EVALUATIONS: 0"]);
    compare(&doc,&exe,&args);
    compare(&doc,&exe,&["--demand=stable","y=2"]);
    // Independent rejection cases retain exactly the already published batch.
    for invalid in ["x=2","unknown=4","stable=4","x=bad"] {
        let args=if invalid=="x=2" {
            vec!["--demand=stable","--next","--demand=stable","x=1",invalid]
        }else{
            vec!["--demand=stable","--next","--demand=stable",invalid]
        };
        compare(&doc,&exe,&args);
        let actual=run(&exe,&args);
        assert!(!actual.status.success());
        assert_eq!(actual.stdout,b"epoch: 0\nstable: 2\n");
    }
    // A demand may change between batches; an unrelated dirty derive
    // remains pending until a full observation is actually requested.
    compare(&doc,&exe,&["--demand=stable","y=2","--next","--demand=zero","x=9","--next"]);
    compare(&doc,&exe,&["x=1","--next","x=2","--next","--demand=stable"]);
}
#[test]
fn actual_parallel_frontier_and_deterministic_c(){
    let tmp=Scratch::new();let mut source="source x: int = 4\n".to_owned();
    for i in 0..128 {source.push_str(&format!("derive n{i}: int (x) = add(x,{i})\n"));}
    source.push_str("derive sum: int (n0,n127) = add(n0,n127)\n");
    let (doc,exe)=compile(&tmp.0,&source);
    let graph=doc_runtime::Graph::parse(&source).unwrap();
    assert_eq!(doc_runtime::aot::emit_c(&graph).unwrap(),fs::read_to_string(tmp.0.join("output.c")).unwrap());
    for w in ["1","2","4","8"]{
        let output=Command::new(&exe).env("DOC_WORKERS",w).arg("x=11").output().unwrap();
        let reference=Command::new(env!("CARGO_BIN_EXE_doc")).arg(&doc).arg("x=11").env("DOC_WORKERS",w).output().unwrap();
        assert!(output.status.success());assert_eq!(output.stdout,reference.stdout);
        let trace=String::from_utf8_lossy(&output.stderr);
        if w=="1"{assert!(!trace.contains("DOC_AOT_PARALLEL_FRONTIER:"));}
        else if std::thread::available_parallelism().unwrap().get()>=2 {assert!(trace.contains("DOC_AOT_PARALLEL_FRONTIER:"));}
    }
}
#[test]
fn unsupported_source_fails_before_outputs(){
    let tmp=Scratch::new();
    for source in ["source label: text = \"unterminated\n","effect a: int = read(\"../escape.txt\")\n","source a: int = 1\nderive b: bool (a) = add(a,1)\n"]{
        let doc=tmp.0.join("input.doc");let c=tmp.0.join("output.c");let exe=tmp.0.join("native");
        fs::write(&doc,source).unwrap();
        let result=Command::new(env!("CARGO_BIN_EXE_doc-compile")).arg(&doc).arg("--emit-c").arg(&c).arg("--out").arg(&exe).output().unwrap();
        assert!(!result.status.success());assert!(!c.exists());assert!(!exe.exists());
    }
}

#[test]
fn native_lists_optional_values_and_owned_transaction_buffers(){
    let tmp=Scratch::new();
    let (doc,exe)=compile(&tmp.0,concat!(
        "source xs: ints = [5,-7]\n",
        "source index: int = 0\n",
        "source choice: bool = false\n",
        "source fallback: maybe_int = some(-3)\n",
        "derive pushed: ints (xs) = append(xs,9)\n",
        "derive removed: ints (pushed,index) = remove_at(pushed,index)\n",
        "derive replaced: ints (pushed,index) = replace_at(pushed,index,-8)\n",
        "derive rest: ints (xs) = tail(xs)\n",
        "derive count: int (pushed) = len(pushed)\n",
        "derive found: maybe_int (xs,index) = try_get(xs,index)\n",
        "derive selected: int (found,fallback) = unwrap_or(found,unwrap_or(fallback,17))\n",
        "derive guarded: int (choice,xs,index) = if(choice,get(xs,index),0)\n",
        "derive same: bool (xs,rest) = eq(xs,rest)\n",
        "derive empty_list: ints () = empty()\n",
        "derive present: maybe_int (count) = some(count)\n",
        "derive absent: maybe_int () = none()\n",
    ));
    for args in [vec![],vec!["xs=[]","index=0"],vec!["xs=[-9223372036854775808, 9223372036854775807]","index=1"],vec!["index=-1"],vec!["--demand=selected","index=-1","fallback=none"],vec!["--demand=guarded","index=-1"],vec!["--demand=guarded","index=-1","choice=true"],vec!["xs=[1,]"],vec!["fallback=some(1x)"],vec!["--through=4","xs=pushed"],vec!["--through=2","fallback=found","--fact=1:index=1"],vec!["--through=1","xs=found"],vec!["--through=2","--fact=1:xs=[]","--fact=2:index=99"]]{compare(&doc,&exe,&args);}
    let out=run(&exe,&["--demand=rest","--next","--demand=rest","xs=[4,5,6]","--next","--demand=rest","xs=[4,5,6]","--next","--demand=guarded","choice=true","index=-1"]);
    assert!(!out.status.success());
    assert_eq!(String::from_utf8_lossy(&out.stdout),"epoch: 0\nrest: [-7]\nepoch: 1\nrest: [5,6]\nepoch: 2\nrest: [5,6]\n");
    // Long recurrence exercises allocation/reclamation; no history held by binary.
    let out=run(&exe,&["--through=1000","xs=rest"]);
    assert!(out.status.success(), "{}",String::from_utf8_lossy(&out.stderr));
}
#[test]
fn existing_radar_chase_graph_compiles_and_replays_cpu_with_frozen_startup_assets(){
    let tmp=Scratch::new();
    let doc=PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../engine/radar_chase.doc");
    let exe=tmp.0.join("native");let c=tmp.0.join("radar.c");
    let result=Command::new(env!("CARGO_BIN_EXE_doc-compile")).arg(&doc).args(["--freeze-startup-assets","--emit-c"]).arg(&c).arg("--out").arg(&exe).output().unwrap();
    assert!(result.status.success(),"{}",String::from_utf8_lossy(&result.stderr));
    assert!(String::from_utf8_lossy(&result.stderr).contains("DOC_AOT_FROZEN_STARTUP_ASSETS"));
    let mut args=vec!["--through=15".to_string()];
    for carry in ["frame=next_frame","player_x=next_x","player_y=next_y","coin_x=next_coin_x","coin_y=next_coin_y","score=next_score","paused=next_paused","won=next_won","animation_phase=next_animation_phase","entity_ids=next_entity_ids","entity_xs=next_entity_xs","entity_ys=next_entity_ys","next_entity_id=next_next_entity_id","issued_high_water=next_issued_high_water","prefab_template_xs=template_next_xs","prefab_template_ys=template_next_ys"]{args.push(carry.into());}
    for (i,c) in "edsssxwddddsspr".chars().enumerate(){
        let action=match c{'w'=>1,'s'=>2,'a'=>3,'d'=>4,'p'=>5,'r'=>6,'e'=>7,'x'=>8,_=>unreachable!()};
        args.push(format!("--fact={}:action={action}",i+1));
    }
    let args=args.iter().map(String::as_str).collect::<Vec<_>>();
    compare(&doc,&exe,&args);
    let out=run(&exe,&args);assert!(out.status.success());
    let stdout=String::from_utf8_lossy(&out.stdout);
    let win=stdout.split("epoch: 13\n").nth(1).unwrap().split("epoch: 14\n").next().unwrap();
    assert!(win.contains("next_won: true\n"));assert!(win.contains("next_score: 2\n"));
    assert!(stdout.contains("epoch: 15\n"));
    // Negative reload: candidate must fail without successor publication.
    let mut invalid=args.clone();
    invalid.extend(["--fact=1:reload=true","--fact=1:replacement_xs=[1]"]);
    compare(&doc,&exe,&invalid);
    eprintln!("DOC_AOT_RADAR_GRAPH_CPU_PARITY_PASS: 16 typed epochs, frozen assets, not full game host/GPU");
}

#[test]
fn all_pure_types_native_text_and_natural_arithmetic(){
    let tmp=Scratch::new();
    let (doc,exe)=compile(&tmp.0,concat!(
        "source a: nat = 99999999999999999999999999999999999999999999\n",
        "source b: nat = 7\nsource enabled: bool = false\n",
        "source left: text = \"世界\"\nsource right: text = \"🙂\"\n",
        "derive total: nat (a,b) = add(a,b)\n",
        "derive product: nat (a,b) = mul(a,b)\n",
        "derive difference: nat (a,b,enabled) = if(enabled,sub(a,b),nat(0))\n",
        "derive order: bool (a,b) = lt(a,b)\n",
        "derive equal: bool (a,b) = eq(a,b)\n",
        "derive leq: bool (a,b) = le(a,b)\n",
        "derive joined: text (left,right) = concat(left,right)\n",
        "derive length: int (joined) = len(joined)\n",
        "derive prefix: bool (joined,left) = starts_with(joined,left)\n",
        "derive selected: text (enabled,joined) = if(enabled,joined,text(\"no\"))\n",
    ));
    for args in [vec![],vec!["a=0000009","b=9","enabled=true"],vec!["a=0","b=2","enabled=true"],vec!["a=0","b=2"],vec!["left=\"\"","right=\"é\""],vec!["a=-1"],vec!["a=12x"],vec!["left=unquoted"],vec!["--through=4","a=total","left=joined"],vec!["--demand=product","a=12345678901234567890","b=98765432109876543210"]]{compare(&doc,&exe,&args);}
    let large=format!("a={}","9".repeat(1000));compare(&doc,&exe,&[&large,"b=1"]);
    let large_text=format!("left=\"{}\"","世界🙂".repeat(2500));compare(&doc,&exe,&[&large_text]);
}
#[test]
fn allocation_failure_sweep_and_long_recurrence_reclaim(){
    let tmp=Scratch::new();
    let (_,exe)=compile(&tmp.0,concat!(
        "source xs: ints = [1,2]\nsource name: text = \"abc\"\nsource n: nat = 19\n",
        "derive more: ints (xs) = append(xs,7)\n",
        "derive next: nat (n) = add(n,nat(1))\n",
        "derive joined: text (name) = concat(name,text(\"x\"))\n",
    ));
    let args=["--through=3","xs=more","n=next","name=joined"];
    let invoke=|fail:Option<usize>|{
        let mut c=Command::new(&exe);c.args(args).env("DOC_WORKERS","1").env("DOC_AOT_MEMORY_TRACE","1");
        if let Some(i)=fail{c.env("DOC_AOT_FAIL_ALLOC_AT",i.to_string());}else{c.env_remove("DOC_AOT_FAIL_ALLOC_AT");}
        c.output().unwrap()
    };
    let baseline=invoke(None);assert!(baseline.status.success());
    let stderr=String::from_utf8_lossy(&baseline.stderr);
    let report=stderr.lines().find(|x|x.starts_with("DOC_AOT_MEMORY: phase=exit ")).unwrap();
    assert!(report.contains("live=0 "));
    let calls:usize=report.rsplit_once("calls=").unwrap().1.parse().unwrap();
    assert!(calls>20);
    for i in 1..=calls{
        let out=invoke(Some(i));assert!(!out.status.success(),"failure {i}");
        let err=String::from_utf8_lossy(&out.stderr);
        assert!(err.contains("DOC_AOT_MEMORY: phase=exit live=0 "),"allocation {i}: {err}");
        assert!(baseline.stdout.starts_with(&out.stdout),"non-prefix publication at {i}");
    }
    let out=Command::new(&exe).args(["--through=2000","n=next"]).env("DOC_WORKERS","1").env("DOC_AOT_MEMORY_TRACE","1").output().unwrap();
    assert!(out.status.success());
    let err=String::from_utf8_lossy(&out.stderr);
    assert!(err.contains("DOC_AOT_MEMORY: phase=exit live=0 "));
    let last=err.lines().find(|x|x.starts_with("DOC_AOT_MEMORY: phase=exit ")).unwrap();
    let field=|key:&str|->usize{last.split_whitespace().find_map(|x|x.strip_prefix(key)).unwrap().parse().unwrap()};
    assert_eq!(field("allocated="),field("freed="));
    assert!(field("allocated=")>field("peak=")*100);
    assert!(field("peak=")<4096);
    eprintln!("DOC_AOT_RECLAMATION_PASS: allocation failure sites={calls}; {last}");
}

#[test]
fn native_startup_assets_are_loaded_at_execution_and_confined(){
    let tmp=Scratch::new();
    let doc=tmp.0.join("source.doc");let c=tmp.0.join("native.c");let exe=tmp.0.join("native");
    fs::write(&doc,concat!("effect xs: ints = read(\"data/list.txt\")\n",
        "effect label: text = read(\"data/label.txt\")\n",
        "derive count: int (xs) = len(xs)\nderive text_bytes: int (label) = len(label)\n")).unwrap();
    // Neither asset exists when the compiler runs.
    let compile=Command::new(env!("CARGO_BIN_EXE_doc-compile")).arg(&doc).arg("--emit-c").arg(&c).arg("--out").arg(&exe).output().unwrap();
    assert!(compile.status.success(),"{}",String::from_utf8_lossy(&compile.stderr));
    let root=format!("--asset-root={}",tmp.0.display());
    let launch=||Command::new(&exe).arg(&root).env("DOC_AOT_MEMORY_TRACE","1").output().unwrap();
    let missing=launch();assert!(!missing.status.success());assert!(missing.stdout.is_empty());
    fs::create_dir(tmp.0.join("data")).unwrap();
    fs::write(tmp.0.join("data/list.txt"),"[4,9]\n").unwrap();
    fs::write(tmp.0.join("data/label.txt"),"世界\n").unwrap();
    let reference=Command::new(env!("CARGO_BIN_EXE_doc")).arg(&doc).output().unwrap();
    let out=launch();assert!(out.status.success());assert_eq!(out.stdout,reference.stdout);
    fs::remove_file(&doc).unwrap();
    fs::write(tmp.0.join("data/list.txt"),"[1,2,3]\n").unwrap();
    let out=launch();assert!(out.status.success());
    assert!(String::from_utf8_lossy(&out.stdout).contains("count: 3\n"));
    fs::write(tmp.0.join("data/list.txt"),"[invalid]").unwrap();
    let out=launch();assert!(!out.status.success());assert!(out.stdout.is_empty());
    assert!(String::from_utf8_lossy(&out.stderr).contains("phase=exit live=0 "));
    fs::remove_file(tmp.0.join("data/list.txt")).unwrap();
    fs::write(tmp.0.join("outside.txt"),"[1]").unwrap();
    std::os::unix::fs::symlink(tmp.0.join("outside.txt"),tmp.0.join("data/list.txt")).unwrap();
    let out=launch();assert!(!out.status.success());assert!(out.stdout.is_empty());
    fs::remove_file(tmp.0.join("data/list.txt")).unwrap();
    fs::write(tmp.0.join("data/list.txt"),"[1]").unwrap();
    fs::write(tmp.0.join("data/label.txt"),[0xff,0xfe]).unwrap();
    let out=launch();assert!(!out.status.success());assert!(out.stdout.is_empty());
}
#[test]
fn actual_radar_graph_runtime_assets_match_frozen_reference_replay(){
    let tmp=Scratch::new();let doc=PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../engine/radar_chase.doc");
    let exe=tmp.0.join("native");let c=tmp.0.join("native.c");
    let compiler=Command::new(env!("CARGO_BIN_EXE_doc-compile")).arg(&doc).arg("--emit-c").arg(&c).arg("--out").arg(&exe).output().unwrap();
    assert!(compiler.status.success(),"{}",String::from_utf8_lossy(&compiler.stderr));
    assert!(String::from_utf8_lossy(&compiler.stderr).contains("DOC_AOT_DEFERRED_STARTUP_ASSETS"));
    let mut args=vec!["--through=15".to_string()];
    for carry in ["frame=next_frame","player_x=next_x","player_y=next_y","coin_x=next_coin_x","coin_y=next_coin_y","score=next_score","paused=next_paused","won=next_won","animation_phase=next_animation_phase","entity_ids=next_entity_ids","entity_xs=next_entity_xs","entity_ys=next_entity_ys","next_entity_id=next_next_entity_id","issued_high_water=next_issued_high_water","prefab_template_xs=template_next_xs","prefab_template_ys=template_next_ys"]{args.push(carry.into());}
    for (i,c) in "edsssxwddddsspr".chars().enumerate(){
        let action=match c{'w'=>1,'s'=>2,'a'=>3,'d'=>4,'p'=>5,'r'=>6,'e'=>7,'x'=>8,_=>unreachable!()};
        args.push(format!("--fact={}:action={action}",i+1));
    }
    let reference=Command::new(env!("CARGO_BIN_EXE_doc")).arg(&doc).args(&args).output().unwrap();
    let root=format!("--asset-root={}",doc.parent().unwrap().display());
    let native=Command::new(&exe).arg(root).args(&args).env("DOC_AOT_MEMORY_TRACE","1").output().unwrap();
    assert!(native.status.success(),"{}",String::from_utf8_lossy(&native.stderr));
    assert_eq!(native.stdout,reference.stdout);
    assert!(String::from_utf8_lossy(&native.stderr).contains("DOC_AOT_ASSET_READ:"));
    assert!(String::from_utf8_lossy(&native.stderr).contains("phase=exit live=0 "));
    let stdout=String::from_utf8_lossy(&native.stdout);
    let win=stdout.split("epoch: 13\n").nth(1).unwrap().split("epoch: 14\n").next().unwrap();
    assert!(win.contains("next_won: true\n"));assert!(win.contains("next_score: 2\n"));
    eprintln!("DOC_AOT_RADAR_RUNTIME_ASSET_CPU_PARITY_PASS: full typed replay, native startup assets, no game host or GPU claim");
}

#[test]
fn native_terminal_game_replay_presentation_and_wav_match_reference(){
    let tmp=Scratch::new();
    let engine=PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../engine");
    let doc=tmp.0.join("radar_chase.doc");
    fs::create_dir(tmp.0.join("levels")).unwrap();
    for file in ["radar_chase.doc","engine_math.doc","entity_pool.doc","levels/coin_chase.txt","levels/showcase_xs.txt","levels/showcase_ys.txt"]{
        fs::copy(engine.join(file),tmp.0.join(file)).unwrap();
    }
    let exe=tmp.0.join("game");let c=tmp.0.join("game.c");
    let result=Command::new(env!("CARGO_BIN_EXE_doc-compile")).arg(&doc).args(["--game","--emit-c"]).arg(&c).arg("--out").arg(&exe).output().unwrap();
    assert!(result.status.success(),"{}",String::from_utf8_lossy(&result.stderr));
    let root=format!("--asset-root={}",tmp.0.display());
    let replay="--replay=edsssxwddddsspr";
    let reference=Command::new(env!("CARGO_BIN_EXE_doc-game")).arg(&doc).args(["--headless",replay]).output().unwrap();
    assert!(reference.status.success(),"{}",String::from_utf8_lossy(&reference.stderr));
    for w in ["1","2","4","8"]{
        let native=Command::new(&exe).arg(&root).args(["--headless",replay]).arg(format!("--workers={w}")).env("DOC_AOT_MEMORY_TRACE","1").output().unwrap();
        assert!(native.status.success(),"{}",String::from_utf8_lossy(&native.stderr));
        assert_eq!(native.stdout,reference.stdout);
        let err=String::from_utf8_lossy(&native.stderr);
        assert!(err.contains("phase=exit live=0 "));
        if w=="1"{assert!(!err.contains("DOC_AOT_PARALLEL_FRONTIER:"));}
        else if std::thread::available_parallelism().unwrap().get()>=2{assert!(err.contains("DOC_AOT_PARALLEL_FRONTIER:"));}
    }
    fs::create_dir(tmp.0.join("reference_audio")).unwrap();fs::create_dir(tmp.0.join("native_audio")).unwrap();
    let reference=Command::new(env!("CARGO_BIN_EXE_doc-game")).arg(&doc).args(["--audio-dir=reference_audio",replay]).output().unwrap();
    assert!(reference.status.success(),"{}",String::from_utf8_lossy(&reference.stderr));
    fs::remove_file(&doc).unwrap();
    let native=Command::new(&exe).arg(&root).args(["--audio-dir=native_audio",replay,"--measure"]).env("DOC_AOT_MEMORY_TRACE","1").output().unwrap();
    assert!(native.status.success(),"{}",String::from_utf8_lossy(&native.stderr));
    let normalize=|bytes:&[u8]|String::from_utf8_lossy(bytes).lines().filter(|s|!s.starts_with("DOC_GAME_CPU_MEASURED:")).map(|s|s.replace("native_audio","reference_audio")).collect::<Vec<_>>();
    assert_eq!(normalize(&native.stdout),normalize(&reference.stdout));
    let mut count=0;
    for file in fs::read_dir(tmp.0.join("reference_audio")).unwrap(){
        let file=file.unwrap();let expected=fs::read(file.path()).unwrap();
        let actual=fs::read(tmp.0.join("native_audio").join(file.file_name())).unwrap();
        assert_eq!(actual,expected,"{}",file.file_name().to_string_lossy());count+=1;
    }
    assert!(count>0);
    let bad=Command::new(&exe).arg(&root).args(["--headless","--replay=ez"]).output().unwrap();
    assert!(!bad.status.success());
    assert_eq!(String::from_utf8_lossy(&bad.stdout).lines().filter(|s|s.starts_with("DOC_GAME_FRAME:")).count(),2);
    eprintln!("DOC_AOT_NATIVE_GAME_CPU_PASS: complete frames/entities/radar/terminal and {count} WAVs, workers 1/2/4/8; no source/evaluator at runtime");
}

#[test]
fn native_dynamic_dependency_family_growth_shrink_and_failure(){
    let tmp=Scratch::new();
    let (doc,exe)=compile(&tmp.0,concat!(
        "source xs: ints = [1,2,3]\nsource bias: int = 2\n",
        "derive ys: ints (xs,bias) = map_ints(xs,item,add(item,bias))\n",
        "derive size: int (ys) = len(ys)\n",
        "derive first: int (ys) = unwrap_or(try_get(ys,0),0)\n",
        "derive next_bias: int (bias) = add(bias,1)\n"));
    for args in [vec![],vec!["xs=[]"],vec!["xs=[-8,9,10,11]","bias=-3"],
                 vec!["xs=[9223372036854775807]"],vec!["--through=2","bias=next_bias","--fact=1:xs=[]","--fact=2:xs=[9,8,7,6]"]]{
        compare(&doc,&exe,&args);
    }
    let big=format!("xs=[{}]",(0..128).map(|i|i.to_string()).collect::<Vec<_>>().join(","));
    for workers in ["1","2","4","8"]{
        let native=Command::new(&exe).env("DOC_WORKERS",workers).arg(&big).output().unwrap();
        let reference=Command::new(env!("CARGO_BIN_EXE_doc")).arg(&doc).arg(&big).env("DOC_WORKERS",workers).output().unwrap();
        assert!(native.status.success());assert_eq!(native.stdout,reference.stdout);
        let log=String::from_utf8_lossy(&native.stderr);
        assert!(log.contains("DOC_AOT_FAMILY: lanes=128 workers="));
        if workers=="1"{assert!(log.contains("lanes=128 workers=1"));}
    }
}

#[test]
fn native_data_dependent_causal_derivations_and_owned_state(){
    let tmp=Scratch::new();
    let (doc,exe)=compile(&tmp.0,include_str!("../examples/causal_token.doc"));
    for args in [vec![],vec!["digits=[]"],vec!["digits=[9,0,8]","limit=100"],
        vec!["digits=[9,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9]"],
        vec!["limit=65537"],vec!["seed=[0]"],vec!["--demand=value","limit=65537"]]{
        compare(&doc,&exe,&args);
    }
    for workers in ["1","2","4","8"]{
        let out=Command::new(&exe).env("DOC_WORKERS",workers).env("DOC_AOT_MEMORY_TRACE","1").output().unwrap();
        assert!(out.status.success(),"{}",String::from_utf8_lossy(&out.stderr));
        assert!(String::from_utf8_lossy(&out.stdout).contains("value: 123"));
        assert!(String::from_utf8_lossy(&out.stderr).contains("live=0"));
    }
    let lazy=Scratch::new();
    let (doc,exe)=compile(&lazy.0,"source seed: int = 9223372036854775807\nderive result: int (seed) = recur(seed,x,true,add(x,1))\n");
    compare(&doc,&exe,&[]);
}

#[test]
fn native_utf8_token_and_exact_word_operations(){
    let tmp=Scratch::new();
    let (doc,exe)=compile(&tmp.0,include_str!("../examples/byte_token.doc"));
    for args in [vec![],vec!["input=\"\""],vec!["input=\"0042\""],vec!["input=\"12a\""],vec!["input=\"é\""],vec!["input=\"9223372036854775807\""],vec!["input=\"9223372036854775808\""]]{compare(&doc,&exe,&args);}
    let words=Scratch::new();
    let (doc,exe)=compile(&words.0,concat!(
        "source x: int = -7\nsource y: int = 3\nsource bytes: ints = [195,169,240,159,153,130]\n",
        "derive q: int (x,y) = quot(x,y)\nderive r: int (x,y) = rem(x,y)\n",
        "derive a: int (x,y) = bit_and(x,y)\nderive o: int (x,y) = bit_or(x,y)\nderive z: int (x,y) = bit_xor(x,y)\n",
        "derive n: int (x) = bit_not(x)\nderive l: int (x,y) = shift_left(x,y)\nderive s: int (x,y) = shift_right(x,y)\n",
        "derive decoded: text (bytes) = utf8_text(bytes)\nderive encoded: ints (decoded) = utf8_bytes(decoded)\n"));
    for args in [vec![],vec!["x=-1","y=63"],vec!["x=1","y=64"],vec!["x=-9223372036854775808","y=-1"],vec!["y=0"],vec!["bytes=[]"],vec!["bytes=[-1]"],vec!["bytes=[256]"],vec!["bytes=[192,128]"],vec!["bytes=[0,65,10]"]]{compare(&doc,&exe,&args);}
}

#[test]
fn native_lexical_functions_preserve_unicode_literals_and_general_formals(){
    let tmp=Scratch::new();
    let (doc,exe)=compile(&tmp.0,concat!(
        "fn label(x) = concat(text(\"x, café (literal) \"),x)\n",
        "fn total(a,b,c,d,e,f) = add(add(add(a,b),add(c,d)),add(e,f))\n",
        "source suffix: text = \"ok\"\nsource n: int = 1\n",
        "derive message: text (suffix) = label(suffix)\n",
        "derive result: int (n) = total(n,2,3,4,5,6)\n"));
    compare(&doc,&exe,&[]);compare(&doc,&exe,&["suffix=\"世界\"","n=9"]);
}

#[test]
#[cfg(all(target_os="linux",target_arch="x86_64"))]
fn native_scalar_object_c_abi_and_freestanding_execution(){
    let tmp=Scratch::new();let root=&tmp.0;
    let source=concat!(
        "source x: int = 1\nsource y: int = 2\nsource enabled: bool = false\n",
        "derive sum: int (x,y) = add(x,y)\n",
        "derive quotient: int (x,y,enabled) = if(enabled,quot(x,y),0)\n",
        "derive shifted: int (x) = shift_right(x,63)\n",
        "derive negative: bool (sum) = lt(sum,0)\n",
        "derive mask: int (x) = bit_not(x)\n");
    let doc=root.join("object.doc");let c=root.join("object.c");
    let h=root.join("object.h");let obj=root.join("object.o");
    fs::write(&doc,source).unwrap();
    let output=Command::new(env!("CARGO_BIN_EXE_doc-compile")).arg(&doc).arg("--emit-c").arg(&c)
        .arg("--object").arg("arithmetic").arg("--emit-header").arg(&h).arg("--out").arg(&obj).output().unwrap();
    assert!(output.status.success(),"{}",String::from_utf8_lossy(&output.stderr));
    let undefined=Command::new("nm").arg("-u").arg(&obj).output().unwrap();
    assert!(undefined.status.success());assert!(undefined.stdout.is_empty(),"{:?}",undefined.stdout);
    let graph=doc_runtime::Graph::parse(source).unwrap();
    let (generated,header)=doc_runtime::aot::emit_scalar_object(&graph,"arithmetic").unwrap();
    assert_eq!(fs::read_to_string(&c).unwrap(),generated);assert_eq!(fs::read_to_string(&h).unwrap(),header);
    // C is used ONLY by this independent ABI conformance fixture, not for
    // implementation of the DOC-authored application. The resulting ELF
    // starts directly at _start with no libc, runtime or dynamic loader.
    let harness=root.join("harness.c");
    fs::write(&harness,r#"
#include "object.h"
static int check(void){
    struct doc_result_arithmetic r;
    if(!doc_export_arithmetic(-7,3,1,&r))return 1;
    if(r.s_sum!=-4||r.s_quotient!=-2||r.s_shifted!=1||r.s_negative!=1||r.s_mask!=6)return 2;
    if(!doc_export_arithmetic(5,0,0,&r)||r.s_quotient!=0)return 3;
    if(doc_export_arithmetic(5,0,1,&r)||r.s_x!=5||r.s_sum!=5||r.s_quotient!=0)return 4;
    if(doc_export_arithmetic(INT64_MAX,1,0,&r)||r.s_sum!=5)return 5;
    if(doc_export_arithmetic(1,2,2,&r)||r.s_sum!=5)return 6;
    if(doc_export_arithmetic(1,2,0,0))return 7;
    /* Reject an aligned result pointer whose byte extent would wrap before
       any dereference. This is a numeric validation, not a pointer sandbox. */
    uintptr_t edge=UINTPTR_MAX-(UINTPTR_MAX%_Alignof(struct doc_result_arithmetic));
    if(doc_export_arithmetic(1,2,0,(struct doc_result_arithmetic*)edge))return 8;
    return 0;
}
__attribute__((force_align_arg_pointer,noreturn)) void _start(void){
    long code=check();
    __asm__ volatile("syscall"::"a"(60L),"D"(code):"rcx","r11","memory");
    __builtin_unreachable();
}
"#).unwrap();
    let exe=root.join("freestanding");
    let build=Command::new("cc").args(["-std=c11","-O2","-ffreestanding","-fno-builtin","-fno-stack-protector","-nostdlib","-static","-no-pie"]).arg(&harness).arg(&obj).arg("-o").arg(&exe).output().unwrap();
    assert!(build.status.success(),"{}",String::from_utf8_lossy(&build.stderr));
    let elf=Command::new("readelf").args(["-l","-d"]).arg(&exe).output().unwrap();
    assert!(elf.status.success());let text=String::from_utf8_lossy(&elf.stdout);
    assert!(!text.contains("INTERP")&&!text.contains("(NEEDED)"),"{text}");
    fs::remove_file(&doc).unwrap();fs::remove_file(&c).unwrap();
    let run=Command::new(&exe).env_clear().output().unwrap();
    assert!(run.status.success(),"freestanding exit {:?}",run.status.code());
}
#[test]
fn native_scalar_object_fails_closed_for_unsupported_values_and_names(){
    let graph=doc_runtime::Graph::parse("source x: int = 1\n").unwrap();
    assert!(doc_runtime::aot::emit_scalar_object(&graph,"bad;name").is_err());
    let graph=doc_runtime::Graph::parse("source xs: ints = [1,2]\n").unwrap();
    assert!(doc_runtime::aot::emit_scalar_object(&graph,"unsupported").is_err());
    let graph=doc_runtime::Graph::parse("source x: int = 1\nderive y: int (x) = unwrap_or(some(x),0)\n").unwrap();
    assert!(doc_runtime::aot::emit_scalar_object(&graph,"unsupported").is_err());
}

#[test]
#[cfg(all(target_os="linux",target_arch="x86_64"))]
fn native_imports_real_socket_and_close_without_handwritten_wrapper(){
    let tmp=Scratch::new();let root=&tmp.0;
    let source=include_str!("../examples/native_socket.doc");
    let doc=root.join("net.doc");let c=root.join("net.c");let h=root.join("net.h");
    let obj=root.join("net.o");let ir=root.join("net.ir");
    fs::write(&doc,source).unwrap();
    let compile=|grants:&[&str]|{
        let mut cmd=Command::new(env!("CARGO_BIN_EXE_doc-compile"));
        cmd.arg(&doc).arg("--object").arg("network").arg("--emit-c").arg(&c)
            .arg("--emit-header").arg(&h).arg("--emit-ir").arg(&ir).arg("--out").arg(&obj);
        for g in grants{cmd.arg("--allow-native-import").arg(g);}
        cmd.output().unwrap()
    };
    assert!(!compile(&["socket"]).status.success());assert!(!c.exists());
    let output=compile(&["socket","close"]);
    assert!(output.status.success(),"{}",String::from_utf8_lossy(&output.stderr));
    let typed=fs::read_to_string(&ir).unwrap();
    assert!(typed.starts_with("DOC-NATIVE-IR/1\n"));
    assert!(typed.contains("import\t0\tsocket\ti32,i32,i32\ti32\n"));
    assert!(typed.contains("call\t3\tfd\tint\t0,1,2\t0\t0,1,2\n"));
    assert!(typed.contains("call\t4\tclosed\tint\t3\t1\t3\n"));
    assert!(!typed.contains("derive\t3\tfd"));
    let undefined=Command::new("nm").arg("-u").arg(&obj).output().unwrap();
    assert!(undefined.status.success());let mut symbols=String::from_utf8_lossy(&undefined.stdout).lines().map(|x|x.split_whitespace().last().unwrap().to_owned()).collect::<Vec<_>>();
    symbols.sort();assert_eq!(symbols,["close","socket"]);
    let harness=root.join("verify.c");fs::write(&harness,r#"
#include "net.h"
#include <fcntl.h>
#include <errno.h>
#include <sys/socket.h>
int main(void){
    struct doc_result_network r;
    if(!doc_export_network(AF_UNIX,SOCK_STREAM,0,&r)||!r.s_success||r.s_fd<0||r.s_closed!=0)return 1;
    if(fcntl((int)r.s_fd,F_GETFD)!=-1||errno!=EBADF)return 2;
    int64_t fd=r.s_fd;
    if(doc_export_network(INT64_MAX,SOCK_STREAM,0,&r)||r.s_fd!=fd||!r.s_success)return 3;
    if(!doc_export_network(-1,SOCK_STREAM,0,&r)||r.s_success||r.s_fd!=-1)return 4;
    return 0;
}
"#).unwrap();
    let exe=root.join("native");let out=Command::new("cc").args(["-std=c11","-O2"]).arg(harness).arg(&obj).arg("-o").arg(&exe).output().unwrap();
    assert!(out.status.success(),"{}",String::from_utf8_lossy(&out.stderr));
    fs::remove_file(doc).unwrap();fs::remove_file(c).unwrap();
    assert!(Command::new(exe).status().unwrap().success());
}
#[test]
fn native_import_authority_types_and_causal_order_fail_closed(){
    use doc_runtime::native_abi::NativeProgram;
    let source=concat!(
        "native import probe(i32) -> i32\nnative import next(i32) -> i32\n",
        "source x: int = 1\n",
        "native call first: int (x) = probe(x)\n",
        "native call second: int (x,first) = next(x)\n");
    let grants=vec!["probe".into(),"next".into()];
    let program=NativeProgram::parse(source,&grants).unwrap();
    let (c,_,ir)=program.emit("ordered").unwrap();
    assert!(c.find("result = doc_import_0").unwrap()<c.find("result = doc_import_1").unwrap());
    assert!(ir.contains("call\t2\tsecond\tint\t0,1\t1\t0"));
    for changed in [
        source.replace("(x,first) = next(x)","(x) = next(x)"),
        source.replace("second: int","second: bool"),
        source.replace("next(x)","next(first, x)"),
        source.replace("next(x)","next(9)"),
        source.replace("native import next","native import probe"),
        source.replace("native import probe(i32)","native import probe(pointer)"),
        source.replace("native import probe(i32)","native import probe(bool8)"),
        source.replace("(x,first) = next(x)","(first) = next(x)"),
    ]{assert!(NativeProgram::parse(&changed,&grants).is_err(),"{changed}");}
    assert!(NativeProgram::parse(source,&["probe".into()]).is_err());
    assert!(NativeProgram::parse(source,&["probe".into(),"next".into(),"unused".into()]).is_err());
    assert!(doc_runtime::Graph::parse(source).is_err());
}

#[test]
#[cfg(all(target_os="linux",target_arch="x86_64"))]
fn native_regions_real_volatile_atomic_and_failure_boundaries(){
    let tmp=Scratch::new();let root=&tmp.0;
    let source=include_str!("../examples/native_regions.doc");
    let doc=root.join("regions.doc");let c=root.join("regions.c");let h=root.join("regions.h");
    let obj=root.join("regions.o");let ir=root.join("regions.ir");
    fs::write(&doc,source).unwrap();
    let output=Command::new(env!("CARGO_BIN_EXE_doc-compile")).arg(&doc).arg("--object").arg("memory")
        .arg("--emit-c").arg(&c).arg("--emit-header").arg(&h).arg("--emit-ir").arg(&ir)
        .arg("--allow-native-region").arg("device").arg("--allow-native-region").arg("counter")
        .arg("--out").arg(&obj).output().unwrap();
    assert!(output.status.success(),"{}",String::from_utf8_lossy(&output.stderr));
    let typed=fs::read_to_string(ir).unwrap();
    assert!(typed.contains("region\t0\tdevice\tu8\tvolatile"));
    assert!(typed.contains("region\t1\tcounter\tu32\tatomic"));
    assert!(typed.contains("region-op\t5\tprevious\tint\t0,2,4\tfetch_add\t1\t0,2"));
    let undef=Command::new("nm").arg("-u").arg(&obj).output().unwrap();
    assert!(undef.status.success());assert!(undef.stdout.is_empty(),"{:?}",undef.stdout);
    let harness=root.join("verify.c");fs::write(&harness,r#"
#include "regions.h"
#include <stdatomic.h>
#include <string.h>
int main(void){
    volatile uint8_t device[2]={0,0};
    _Atomic(uint32_t) counter[2]={10,20};
    struct doc_result_memory r;
    if(!doc_export_memory(1,42,2,(void*)device,2,counter,2,&r))return 1;
    if(device[1]!=42||atomic_load(&counter[1])!=22||r.s_read_back!=42||r.s_previous!=20||r.s_total!=22||!r.s_ordered)return 2;
    if(doc_export_memory(-1,42,2,(void*)device,2,counter,2,&r)||r.s_total!=22||device[0]!=0)return 3;
    if(doc_export_memory(0,256,2,(void*)device,2,counter,2,&r)||r.s_total!=22||device[0]!=0)return 4;
    if(doc_export_memory(0,42,2,(void*)device,2,counter,0,&r)||r.s_total!=22||device[0]!=42||atomic_load(&counter[0])!=10)return 5;
    /* The valid earlier external write persists even though the result
       publication failed on the later zero-length atomic region. */
    if(doc_export_memory(0,43,2,(void*)device,2,(void*)((char*)counter+1),2,&r)||device[0]!=42)return 6;
    if(doc_export_memory(0,43,2,(void*)&r,1,counter,2,&r)||device[0]!=42||r.s_total!=22)return 7;
    if(doc_export_memory(0,43,2,(void*)counter,1,counter,2,&r)||atomic_load(&counter[0])!=10)return 8;
    atomic_store(&counter[0],UINT32_MAX);
    if(!doc_export_memory(0,7,1,(void*)device,2,counter,2,&r)||r.s_previous!=UINT32_MAX||r.s_total!=0)return 9;
    return 0;
}
"#).unwrap();
    let exe=root.join("native");let out=Command::new("cc").args(["-std=c11","-O2"]).arg(harness).arg(&obj).arg("-o").arg(&exe).output().unwrap();
    assert!(out.status.success(),"{}",String::from_utf8_lossy(&out.stderr));
    let output=Command::new(exe).output().unwrap();assert!(output.status.success(),"region proof exit {:?}",output.status.code());
}
#[test]
fn native_region_authority_kind_and_order_are_checked(){
    use doc_runtime::native_abi::NativeProgram;
    let source=include_str!("../examples/native_regions.doc");
    let grants=vec!["device".into(),"counter".into()];
    assert!(NativeProgram::parse_with_regions(source,&[],&grants).is_ok());
    assert!(NativeProgram::parse_with_regions(source,&[],&["device".into()]).is_err());
    for changed in [
        source.replace("u32 atomic","u8 atomic"),
        source.replace("u32 atomic","u32 volatile"),
        source.replace("(index,delta,read_back)","(index,delta)"),
        source.replace("device(index,byte)","device(byte)"),
        source.replace("seq_cst()","relaxed()"),
        source.replace("native region device: u8 volatile","native region device: bool8 plain"),
        source.replace("read_back: int","read_back: bool"),
    ]{assert!(NativeProgram::parse_with_regions(&changed,&[],&grants).is_err(),"{changed}");}
}


#[test]
#[cfg(all(target_os="linux",target_arch="x86_64"))]
fn native_external_sources_are_checked_before_any_effect() {
    let tmp=Scratch::new();let root=&tmp.0;
    let source=concat!(
        "native import touch(i32) -> i32\n",
        "source x: int = 1\n",
        "native call touched: int (x) = touch(x)\n",
        "source enabled: bool = true\n",
        "derive final_value: int (enabled,touched) = if(enabled,touched,0)\n");
    let program=doc_runtime::native_abi::NativeProgram::parse(source,&["touch".into()]).unwrap();
    let (c,h,_)=program.emit("checked").unwrap();
    // The source-validation phase must be explicit even if the current
    // topological implementation happens to visit sources first.
    assert!(c.find("if (in_enabled>1)").unwrap()<c.find("result = doc_import_0").unwrap());
    let generated=root.join("checked.c");let header=root.join("checked.h");
    fs::write(&generated,c).unwrap();fs::write(&header,h).unwrap();
    let harness=root.join("check.c");
    fs::write(&harness,r#"
#include "checked.h"
static int calls;
int32_t touch(int32_t x){++calls;return x+1;}
int main(void){
    struct doc_result_checked r;
    if(!doc_export_checked(1,1,&r)||r.s_final_value!=2||calls!=1)return 1;
    if(doc_export_checked(5,2,&r)||r.s_final_value!=2||calls!=1)return 2;
    uintptr_t edge=UINTPTR_MAX-(UINTPTR_MAX%_Alignof(struct doc_result_checked));
    if(doc_export_checked(5,1,(struct doc_result_checked*)edge)||calls!=1)return 3;
    if(!doc_export_checked(5,0,&r)||r.s_final_value!=0||calls!=2)return 4;
    return 0;
}
"#).unwrap();
    let exe=root.join("native");
    let build=Command::new("cc").args(["-std=c11","-O2","-fno-builtin"])
        .arg(generated).arg(harness).arg("-o").arg(&exe).output().unwrap();
    assert!(build.status.success(),"{}",String::from_utf8_lossy(&build.stderr));
    let run=Command::new(exe).output().unwrap();
    assert!(run.status.success(),"ABI input proof exit {:?}",run.status.code());
}


#[test]
fn compiler_lexical_runs_native_reference_and_independent_oracle() {
    let tmp=Scratch::new();
    let (doc,exe)=compile(&tmp.0,include_str!("../examples/lexical_runs.doc"));
    // An independent oracle, not just two implementations agreeing.
    let oracle=|input:&str| -> Option<Vec<i64>> {
        let mut out=Vec::<i64>::new();
        for (offset,b) in input.bytes().enumerate() {
            let tag=match b {b' '=>0,b'A'..=b'Z'|b'a'..=b'z'|b'_'=>1,b'0'..=b'9'=>2,b'+'=>3,b'='=>4,_=>return None};
            let n=out.len();
            if n>=3&&out[n-3]==tag {out[n-1]+=1;}
            else {out.extend([tag,offset as i64,1]);}
        }
        Some(out)
    };
    for input in ["","abc = 12+z","_Aaa99++= ","0012","a","   ","x1x2","12?","é"] {
        let arg=format!("input=\"{input}\"");
        let args=["--demand=tokens",arg.as_str()];
        compare(&doc,&exe,&args);
        for workers in ["1","2","4","8"] {
            let native=Command::new(&exe).env("DOC_WORKERS",workers).args(args).output().unwrap();
            let reference=Command::new(env!("CARGO_BIN_EXE_doc")).arg(&doc).env("DOC_WORKERS",workers).args(args).output().unwrap();
            assert_eq!(native.status.success(),reference.status.success());
            assert_eq!(native.stdout,reference.stdout);
            match oracle(input) {
                Some(records)=>{
                    assert!(native.status.success(),"{}",String::from_utf8_lossy(&native.stderr));
                    let expected=format!("tokens: [{}]",records.iter().map(i64::to_string).collect::<Vec<_>>().join(","));
                    assert!(String::from_utf8_lossy(&native.stdout).lines().any(|line|line==expected));
                }
                None=>{assert!(!native.status.success());assert!(native.stdout.is_empty());}
            }
        }
    }
    // Source repair grows and shrinks the collection; an invalid successor
    // must publish no new token table, and native ownership must reclaim.
    let args=["--demand=tokens","input=\"a\"","--next","--demand=tokens","input=\"AB12+z\"","--next","--demand=tokens","input=\"\"","--next","--demand=tokens","input=\"?\""];
    compare(&doc,&exe,&args);
    let native=Command::new(&exe).env("DOC_AOT_MEMORY_TRACE","1").args(args).output().unwrap();
    assert!(!native.status.success());
    let output=String::from_utf8_lossy(&native.stdout);
    assert!(output.contains("epoch: 2\ntokens: []\n"));
    assert!(!output.contains("epoch: 3"));
    assert!(String::from_utf8_lossy(&native.stderr).contains("DOC_AOT_MEMORY: phase=exit live=0 "));
}


#[test]
#[cfg(all(target_os="linux",target_arch="x86_64"))]
fn conditional_native_calls_skip_effect_and_narrowing_and_preserve_causal_cleanup(){
    use doc_runtime::native_abi::NativeProgram;
    let tmp=Scratch::new();
    let source=include_str!("../examples/native_conditional.doc");
    let grants=vec!["acquire".into(),"release".into()];
    let (c,h,ir)=NativeProgram::parse(source,&grants).unwrap().emit("conditional").unwrap();
    assert!(ir.lines().any(|line|line.starts_with("call-if\t")&&line.contains("\tacquired\t")));
    assert!(ir.lines().any(|line|line.starts_with("call-if\t")&&line.contains("\treleased\t")));
    for invalid in [
        source.replace("when enabled else absent","when argument else absent"),
        source.replace("when enabled else absent","when enabled else enabled"),
        source.replace("(argument,enabled,absent)","(argument,enabled)"),
        source.replace("when enabled else absent","when enabled"),
        source.replace("when enabled else absent","when unknown else absent"),
        source.replace("when acquired_ok else absent","when enabled else absent").replace("(acquired,acquired_ok,absent)","(argument,enabled,absent)").replace("release(acquired)","release(argument)"),
    ] {assert!(NativeProgram::parse(&invalid,&grants).is_err(),"{invalid}");}
    let generated=tmp.0.join("conditional.c");let header=tmp.0.join("conditional.h");
    fs::write(&generated,c).unwrap();fs::write(&header,h).unwrap();
    let harness=tmp.0.join("check.c");
    fs::write(&harness,r#"
#include "conditional.h"
static int acquires, releases, live;
int32_t acquire(int32_t arg){++acquires;if(arg<0)return -1;++live;return arg;}
int32_t release(int32_t handle){++releases;--live;return handle+1;}
int main(void){
    struct doc_result_conditional r;
    if(!doc_export_conditional(INT64_MAX,0,&r)||r.s_acquired!=-1||r.s_released!=-1||acquires||releases||live)return 1;
    if(!doc_export_conditional(7,1,&r)||r.s_acquired!=7||r.s_released!=8||acquires!=1||releases!=1||live)return 2;
    if(!doc_export_conditional(-1,1,&r)||r.s_acquired!=-1||r.s_released!=-1||acquires!=2||releases!=1||live)return 3;
    if(doc_export_conditional(INT64_MAX,1,&r)||r.s_acquired!=-1||acquires!=2||releases!=1||live)return 4;
    if(doc_export_conditional(0,2,&r)||acquires!=2||releases!=1||live)return 5;
    return 0;
}
"#).unwrap();
    let exe=tmp.0.join("native");
    let out=Command::new("cc").args(["-std=c11","-O2","-fno-builtin"]).arg(generated).arg(harness).arg("-o").arg(&exe).output().unwrap();
    assert!(out.status.success(),"{}",String::from_utf8_lossy(&out.stderr));
    let out=Command::new(exe).output().unwrap();
    assert!(out.status.success(),"conditional effect proof exit {:?}",out.status.code());
}

#[test]
#[cfg(all(target_os="linux",target_arch="x86_64"))]
fn scoped_handles_unwind_on_success_and_checked_failure() {
    use doc_runtime::native_abi::NativeProgram;
    let source = include_str!("../examples/native_scoped.doc");
    let grants = vec!["acquire".into(), "release_handle".into()];
    for invalid in [
        source.replace("cleanup first", "cleanup second"),
        source.replace("cleanup first", "cleanup divisor"),
        source.replace("= release_handle", "= ungranted"),
        source.replace("-> i32", "-> u32"),
    ] {
        assert!(NativeProgram::parse(&invalid, &grants).is_err());
    }
    let (c, h, ir) = NativeProgram::parse(source, &grants).unwrap().emit("scope").unwrap();
    assert_eq!(ir.lines().filter(|l| l.starts_with("cleanup-i32\t")).count(), 2);
    let tmp = Scratch::new();
    fs::write(tmp.0.join("scope.c"), c).unwrap();
    fs::write(tmp.0.join("scope.h"), h).unwrap();
    fs::write(tmp.0.join("fixture.c"), r#"
#include "scope.h"
static int serial, n, closed[2];
int32_t acquire(int32_t x){return x<0 ? -1 : serial++;}
void release_handle(int32_t h){if(n<2)closed[n]=h; ++n;}
int main(void){
    struct doc_result_scope r;
    if(!doc_export_scope(7,1,1,&r)||r.s_quotient!=1||n!=2||closed[0]!=1||closed[1]!=0)return 1;
    n=0;
    if(doc_export_scope(7,1,0,&r)||r.s_second!=1||n!=2||closed[0]!=3||closed[1]!=2)return 2;
    n=0;
    if(!doc_export_scope(7,0,1,&r)||r.s_first!=99||n!=1||closed[0]!=4)return 3;
    n=0;
    if(!doc_export_scope(-1,1,1,&r)||r.s_second!=-1||n!=0)return 4;
    if(doc_export_scope(INT64_MAX,1,1,&r)||n!=0||serial!=5)return 5;
    return 0;
}
"#).unwrap();
    let build = Command::new("cc").current_dir(&tmp.0)
        .args(["-std=c11","-O2","scope.c","fixture.c","-o","fixture"]).output().unwrap();
    assert!(build.status.success(), "{}", String::from_utf8_lossy(&build.stderr));
    let status = Command::new(tmp.0.join("fixture")).status().unwrap();
    assert!(status.success(), "native cleanup fixture: {status}");
}

#[test]
fn native_checked_slice_and_compiler_emission_match_independent_oracle(){
    let tmp=Scratch::new();
    let (doc,exe)=compile(&tmp.0,"source xs: ints = [4,9,-1,7]\nsource start: int = 1\nsource count: int = 2\nderive selected: ints (xs,start,count) = slice(append(xs,8),start,count)\n");
    for args in [vec!["--demand=selected"],vec!["--demand=selected","start=5","count=0"],vec!["--demand=selected","start=6","count=0"],vec!["--demand=selected","start=-1"],vec!["--demand=selected","count=-1"],vec!["--demand=selected","start=9223372036854775807","count=9223372036854775807"]] {
        compare(&doc,&exe,&args);
    }
    let out=run(&exe,&["--demand=selected","start=4","count=1"]);
    assert!(out.status.success());assert!(String::from_utf8_lossy(&out.stdout).contains("selected: [8]"));
    let tmp=Scratch::new();let (doc,exe)=compile(&tmp.0,include_str!("../examples/compiler_emit.doc"));
    let oracle=|input:&str|->Option<String>{
        let mut depth=0usize;let mut code=String::new();
        for c in input.bytes(){match c{
            b' '=>{},
            b'0'..=b'9'=>{depth+=1;code.push('P');code.push(c as char);code.push(';');},
            b'+'|b'*'=>{if depth<2{return None}depth-=1;code.push(if c==b'+'{'A'}else{'M'});code.push(';');},
            _=>return None,
        }}
        if depth==1{Some(code)}else{None}
    };
    for input in ["1","12+3*"," 9 0 * 8 + ","123++","12","1+","+", "", "é","1?"]{
        let assignment=format!("input=\"{input}\"");let args=["--demand=encoded",assignment.as_str()];
        compare(&doc,&exe,&args);
        for workers in ["1","2","4","8"]{
            let actual=Command::new(&exe).env("DOC_WORKERS",workers).args(args).output().unwrap();
            match oracle(input){
                Some(code)=>{assert!(actual.status.success(),"{}",String::from_utf8_lossy(&actual.stderr));let expected=format!("encoded: [{}]",code.bytes().map(|b|b.to_string()).collect::<Vec<_>>().join(","));assert!(String::from_utf8_lossy(&actual.stdout).lines().any(|l|l==expected));},
                None=>{assert!(!actual.status.success());assert!(actual.stdout.is_empty());}
            }
        }
    }
    let args=["--demand=code","input=\"12+\"","--next","--demand=code","input=\"7\"","--next","--demand=code","input=\"123++\"","--next","--demand=code","input=\"12\""];
    compare(&doc,&exe,&args);
    let actual=Command::new(&exe).env("DOC_AOT_MEMORY_TRACE","1").args(args).output().unwrap();
    assert!(!actual.status.success());assert!(String::from_utf8_lossy(&actual.stdout).contains("epoch: 2\n"));assert!(!String::from_utf8_lossy(&actual.stdout).contains("epoch: 3"));
    assert!(String::from_utf8_lossy(&actual.stderr).contains("DOC_AOT_MEMORY: phase=exit live=0 "));
}


#[test]
fn native_tagged_graph_type_checker_matches_independent_oracle(){
    let tmp=Scratch::new();
    let (doc,exe)=compile(&tmp.0,include_str!("../examples/compiler_type_graph.doc"));
    let oracle=|rows:&[i64]|->Option<Vec<i64>>{
        if rows.len()%3!=0{return None;}
        let mut types=Vec::new();
        for r in rows.chunks_exact(3){
            let [op,a,b]=[r[0],r[1],r[2]];
            let ty=match op{
                0 if b==0=>0,
                1 if b==0&&(a==0||a==1)=>1,
                2..=4=>{
                    let x=*types.get(usize::try_from(a).ok()?)?;
                    let y=*types.get(usize::try_from(b).ok()?)?;
                    match op{2 if x==0&&y==0=>0,3 if x==0&&y==0=>1,4 if x==y=>1,_=>return None}
                },
                _=>return None,
            };
            types.push(ty);
        }
        Some(types)
    };
    let cases: &[&[i64]]=&[
        &[], &[0,-7,0], &[1,1,0],
        &[0,17,0,0,3,0,2,0,1,3,1,2,1,1,0,4,3,4],
        &[1,0,0,1,1,0,4,0,1],
        &[1,2,0], &[0,1,2], &[0,1], &[5,0,0],
        &[2,0,0], &[0,1,0,2,-1,0], &[0,1,0,2,0,1],
        &[1,1,0,2,0,0], &[0,1,0,1,1,0,4,0,1],
    ];
    for rows in cases{
        let assignment=format!("records=[{}]",rows.iter().map(i64::to_string).collect::<Vec<_>>().join(","));
        let args=["--demand=types",assignment.as_str()];
        compare(&doc,&exe,&args);
        for workers in ["1","2","4","8"]{
            let output=Command::new(&exe).env("DOC_WORKERS",workers).args(args).output().unwrap();
            match oracle(rows){
                Some(types)=>{
                    assert!(output.status.success(),"{}",String::from_utf8_lossy(&output.stderr));
                    let expected=format!("types: [{}]",types.iter().map(i64::to_string).collect::<Vec<_>>().join(","));
                    assert!(String::from_utf8_lossy(&output.stdout).lines().any(|l|l==expected));
                },
                None=>{assert!(!output.status.success());assert!(output.stdout.is_empty());}
            }
        }
    }
    let args=["--demand=types","records=[0,7,0]","--next","--demand=types","records=[0,1,0,0,2,0,2,0,1]","--next","--demand=types","records=[]","--next","--demand=types","records=[2,0,0]"];
    compare(&doc,&exe,&args);
    let output=Command::new(&exe).env("DOC_AOT_MEMORY_TRACE","1").args(args).output().unwrap();
    assert!(!output.status.success());
    let stdout=String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains("epoch: 2\ntypes: []\n"));
    assert!(!stdout.contains("epoch: 3"));
    assert!(String::from_utf8_lossy(&output.stderr).contains("DOC_AOT_MEMORY: phase=exit live=0 "));
}


#[test]
#[cfg(all(target_os="linux",target_arch="x86_64"))]
fn native_byte_views_drive_real_posix_io_with_checked_ranges(){
    use doc_runtime::native_abi::NativeProgram;
    let source=include_str!("../examples/native_buffer.doc");
    let grants=vec!["read".into(),"write".into()];
    let regions=vec!["buffer".into()];
    for invalid in [
        source.replace("u8 plain","u8 volatile"),
        source.replace("u8 plain","i64 plain"),
        source.replace("read(input_fd,buffer,offset,requested)","read(input_fd,unknown,offset,requested)"),
        source.replace("read(input_fd,buffer,offset,requested)","read(input_fd,buffer,enabled,requested)"),
        source.replace("read(input_fd,buffer,offset,requested)","read(input_fd,buffer,offset)"),
        source.replace("-> i64","-> bytes"),
        source.replace("read(i32,bytes)","read(i32,bytes,bytes)").replace("read(input_fd,buffer,offset,requested)","read(input_fd,buffer,offset,requested,buffer,offset,requested)"),
    ]{assert!(NativeProgram::parse_with_regions(&invalid,&grants,&regions).is_err(),"{invalid}");}
    assert!(NativeProgram::parse_with_regions(source,&grants,&[]).is_err());
    assert!(NativeProgram::parse_with_regions(source,&["read".into()],&regions).is_err());
    let tmp=Scratch::new();
    let (c,h,ir)=NativeProgram::parse_with_regions(source,&grants,&regions).unwrap().emit("transfer").unwrap();
    assert!(ir.contains("read\ti32,bytes\ti64"));
    assert!(ir.contains("write\ti32,const_bytes\ti64"));
    assert!(ir.lines().filter(|l|l.starts_with("call-if\t")).all(|l|l.contains("r:0:")));
    fs::write(tmp.0.join("transfer.c"),c).unwrap();
    fs::write(tmp.0.join("transfer.h"),h).unwrap();
    fs::write(tmp.0.join("fixture.c"),r#"
#include "transfer.h"
#include <unistd.h>
#include <string.h>
#include <fcntl.h>
int main(void){
    int in[2],out[2];
    if(pipe(in)||pipe(out))return 1;
    if(write(in[1],"ABC",3)!=3||close(in[1]))return 2;
    if(fcntl(out[0],F_SETFL,O_NONBLOCK)<0)return 3;
    uint8_t buf[8];memset(buf,0x55,sizeof buf);
    struct doc_result_transfer r;
    /* An external event source can call a typed exported DOC entry directly. */
    int (*event)(int64_t,int64_t,int64_t,int64_t,uint8_t,int64_t,void*,size_t,struct doc_result_transfer*)=doc_export_transfer;
    if(!event(in[0],out[1],2,5,1,-1,buf,8,&r))return 4;
    if(r.s_received!=3||r.s_sent!=3||!r.s_complete||memcmp(buf+2,"ABC",3)||buf[1]!=0x55||buf[5]!=0x55)return 5;
    char observed[8];if(read(out[0],observed,8)!=3||memcmp(observed,"ABC",3))return 6;
    /* Invalid range fails before dispatch and preserves previous result. */
    if(event(in[0],out[1],7,2,1,-1,buf,8,&r)||r.s_received!=3)return 7;
    if(event(in[0],out[1],-1,1,1,-1,buf,8,&r)||r.s_received!=3)return 8;
    if(event(in[0],out[1],1,-1,1,-1,buf,8,&r)||r.s_received!=3)return 9;
    if(event(in[0],out[1],INT64_MAX,INT64_MAX,1,-1,buf,8,&r)||r.s_received!=3)return 10;
    if(event(in[0],out[1],0,1,1,-1,&r,1,&r)||r.s_received!=3)return 11;
    if(event(in[0],out[1],0,1,2,-1,buf,8,&r)||r.s_received!=3)return 12;
    if(!event(INT64_MAX,INT64_MAX,-1,-1,0,-1,buf,8,&r)||r.s_received!=-1||r.s_sent!=-1||r.s_complete)return 13;
    if(!event(in[0],out[1],8,0,1,-1,buf,8,&r)||r.s_received!=0||r.s_sent!=0||!r.s_complete)return 14;
    if(!event(in[0],out[1],0,0,1,-1,0,0,&r)||!r.s_complete)return 15;
    if(read(out[0],observed,8)!=-1)return 16;
    if(!event(-1,out[1],0,1,1,-1,buf,8,&r)||r.s_received!=-1||r.s_sent!=-1||r.s_complete)return 17;
    close(in[0]);close(out[0]);close(out[1]);return 0;
}
"#).unwrap();
    let build=Command::new("cc").current_dir(&tmp.0).args(["-std=c11","-O2","-Werror=incompatible-pointer-types","-fno-builtin","transfer.c","fixture.c","-o","fixture"]).output().unwrap();
    assert!(build.status.success(),"{}",String::from_utf8_lossy(&build.stderr));
    let run=Command::new(tmp.0.join("fixture")).output().unwrap();
    assert!(run.status.success(),"byte-view proof exit {:?}",run.status.code());
}

#[test]
fn nested_tagged_data_native_and_reference_match_recursive_oracle(){
    let tmp=Scratch::new();
    let (doc,exe)=compile(&tmp.0,include_str!("../examples/nested_data.doc"));
    fn parse(rows:&[i64],p:&mut usize)->Option<i64>{
        let tag=*rows.get(*p)?;*p+=1;
        match tag{
            0=>{rows.get(*p)?;*p+=1;Some(1)},
            1=>{let v=*rows.get(*p)?;*p+=1;if v==0||v==1{Some(1)}else{None}},
            2=>{let n=usize::try_from(*rows.get(*p)?).ok()?;*p+=1;let end=p.checked_add(n)?;let bytes=rows.get(*p..end)?.iter().map(|&b|u8::try_from(b)).collect::<std::result::Result<Vec<_>,_>>().ok()?;std::str::from_utf8(&bytes).ok()?;*p=end;Some(1)},
            3=>{let n=usize::try_from(*rows.get(*p)?).ok()?;*p+=1;if n>65536{return None}let mut total=1;for _ in 0..n{total+=parse(rows,p)?;}Some(total)},
            4=>Some(1),
            5=>Some(1+parse(rows,p)?),
            _=>None,
        }
    }
    let cases: &[&[i64]]=&[
        &[0,i64::MIN], &[1,0], &[1,1], &[2,0], &[2,2,195,169], &[3,0], &[4], &[5,4],
        &[3,3,0,42,5,2,2,195,169,4], &[3,2,3,2,1,1,0,-7,5,3,1,2,1,65],
        &[], &[0], &[1,2], &[2,-1], &[2,2,65], &[2,1,255], &[2,1,256], &[2,1,-1],
        &[2,i64::MAX], &[3,-1], &[3,65537], &[3,2,4], &[5], &[6], &[4,4],
    ];
    for rows in cases{
        let mut p=0;let expected=parse(rows,&mut p).filter(|_|p==rows.len());
        let assignment=format!("encoded=[{}]",rows.iter().map(i64::to_string).collect::<Vec<_>>().join(","));
        let args=["--demand=summary",assignment.as_str()];
        compare(&doc,&exe,&args);
        let out=run(&exe,&args);
        match expected{
            Some(n)=>{assert!(out.status.success(),"{}",String::from_utf8_lossy(&out.stderr));let line=format!("summary: [{},0,{n}]",rows.len());assert!(String::from_utf8_lossy(&out.stdout).lines().any(|l|l==line));},
            None=>{assert!(!out.status.success());assert!(out.stdout.is_empty());},
        }
    }
    let args=["--demand=summary","encoded=[4]","--next","--demand=summary","encoded=[3,2,5,0,8,2,1,65]","--next","--demand=summary","encoded=[3,0]","--next","--demand=summary","encoded=[3,1]"];
    compare(&doc,&exe,&args);
    let out=Command::new(&exe).env("DOC_AOT_MEMORY_TRACE","1").args(args).output().unwrap();
    assert!(!out.status.success());
    let stdout=String::from_utf8_lossy(&out.stdout);
    assert!(stdout.contains("epoch: 2\nsummary: [2,0,1]\n"));assert!(!stdout.contains("epoch: 3"));
    assert!(String::from_utf8_lossy(&out.stderr).contains("DOC_AOT_MEMORY: phase=exit live=0 "));
}


#[test]
#[cfg(all(target_os="linux",target_arch="x86_64"))]
fn native_recurrence_drives_stream_and_scoped_cleanup_without_host_policy(){
    use doc_runtime::native_abi::NativeProgram;
    let source=include_str!("../examples/native_stream.doc");
    let grants=vec!["read".into(),"write".into()];
    let regions=vec!["buffer".into()];
    for invalid in [
        source.replace("until stopped","until total"),
        source.replace("until stopped","until send_missing"),
        source.replace("carry total=next_total","carry total=complete"),
        source.replace("carry total=next_total","carry total=chunk"),
        source.replace("carry total=next_total","carry next_total=received"),
        source.replace("carry total=next_total","carry total=next_total,total=sent"),
        source.replace("carry total=next_total","carry "),
    ]{assert!(NativeProgram::parse_with_regions(&invalid,&grants,&regions).is_err(),"{invalid}");}
    let tmp=Scratch::new();
    let (c,h,ir)=NativeProgram::parse_with_regions(source,&grants,&regions).unwrap().emit("stream").unwrap();
    assert!(ir.lines().any(|l|l.starts_with("repeat\t")));
    fs::write(tmp.0.join("stream.c"),c).unwrap();
    fs::write(tmp.0.join("stream.h"),h).unwrap();
    let source=concat!(
        "native import acquire(i32) -> i32\n",
        "native cleanup owned = release_handle\n",
        "native repeat until halt carry step=next\n",
        "source step: int = 0\n",
        "source stop: int = 3\n",
        "source fail: int = -1\n",
        "native call owned: int (step) = acquire(step)\n",
        "derive next: int (step,owned) = add(step,1)\n",
        "derive checked: int (next,fail) = quot(1,sub(fail,next))\n",
        "derive halt: bool (next,stop,checked) = le(stop,next)\n");
    let grants=vec!["acquire".into(),"release_handle".into()];
    assert!(NativeProgram::parse(&source.replace("step=next","step=owned"),&grants).is_err());
    let (c,h,_)=NativeProgram::parse(source,&grants).unwrap().emit("repeat_scope").unwrap();
    fs::write(tmp.0.join("repeat.c"),c).unwrap();
    fs::write(tmp.0.join("repeat.h"),h).unwrap();
    fs::write(tmp.0.join("fixture.c"),r#"
#include "stream.h"
#include "repeat.h"
#include <unistd.h>
#include <string.h>
#include <stdlib.h>
static int calls,released,live;
int32_t acquire(int32_t x){if(live)abort();calls++;live++;return x;}
void release_handle(int32_t x){(void)x;if(live!=1)abort();released++;live--;}
int main(void){
    int in[2],out[2];if(pipe(in)||pipe(out))return 1;
    if(write(in[1],"ABCDEFG",7)!=7||close(in[1]))return 2;
    uint8_t buffer[3]={0};struct doc_result_stream s;
    if(!doc_export_stream(in[0],out[1],2,0,0,-1,buffer,3,&s))return 3;
    if(s.s_next_total!=7||s.s_received!=0||!s.s_stopped||close(out[1]))return 4;
    char bytes[8];if(read(out[0],bytes,8)!=7||memcmp(bytes,"ABCDEFG",7)||read(out[0],bytes,8)!=0)return 5;
    close(in[0]);close(out[0]);
    struct doc_result_repeat_scope r;
    if(!doc_export_repeat_scope(0,3,-1,&r)||r.s_next!=3||calls!=3||released!=3||live)return 6;
    calls=released=0;
    if(doc_export_repeat_scope(0,3,2,&r)||r.s_next!=3||calls!=2||released!=2||live)return 7;
    calls=released=0;
    if(doc_export_repeat_scope(0,70000,-1,&r)||r.s_next!=3||calls!=65536||released!=65536||live)return 8;
    return 0;
}
"#).unwrap();
    let build=Command::new("cc").current_dir(&tmp.0).args(["-std=c11","-O2","-fno-builtin","stream.c","repeat.c","fixture.c","-o","fixture"]).output().unwrap();
    assert!(build.status.success(),"{}",String::from_utf8_lossy(&build.stderr));
    let run=Command::new(tmp.0.join("fixture")).output().unwrap();
    assert!(run.status.success(),"native repeat proof exit {:?}",run.status.code());
}

#[test]
#[cfg(all(target_os="linux",target_arch="x86_64"))]
fn native_region_extent_supports_doc_authored_allocation_policy(){
    use doc_runtime::native_abi::NativeProgram;
    let source=include_str!("../examples/native_arena.doc");
    let regions=vec!["arena".into()];
    for invalid in [
        source.replace("capacity: int","capacity: bool"),
        source.replace("= arena()","= arena(used)"),
        source.replace("= arena()","= unknown()"),
    ]{assert!(NativeProgram::parse_with_regions(&invalid,&[],&regions).is_err(),"{invalid}");}
    assert!(NativeProgram::parse_with_regions(source,&[],&[]).is_err());
    let tmp=Scratch::new();
    let (c,h,ir)=NativeProgram::parse_with_regions(source,&[],&regions).unwrap().emit("arena").unwrap();
    assert!(ir.lines().any(|l|l.starts_with("region-op\t")&&l.contains("\textent\t")));
    fs::write(tmp.0.join("arena.c"),c).unwrap();
    fs::write(tmp.0.join("arena.h"),h).unwrap();
    fs::write(tmp.0.join("fixture.c"),r#"
#include "arena.h"
int main(void){
    _Alignas(16) uint8_t memory[16]={0};
    struct doc_result_arena r;
    if(!doc_export_arena(1,3,4,7,memory,16,&r)||r.s_start!=4||r.s_next!=7||r.s_capacity!=16||memory[6]!=7)return 1;
    if(!doc_export_arena(r.s_next,8,8,9,memory,16,&r)||r.s_start!=8||r.s_next!=16||memory[15]!=9)return 2;
    if(doc_export_arena(16,1,1,7,memory,16,&r)||r.s_next!=16||memory[15]!=9)return 3;
    if(doc_export_arena(0,1,3,7,memory,16,&r)||r.s_next!=16)return 4;
    if(doc_export_arena(0,0,1,7,memory,16,&r)||r.s_next!=16)return 5;
    if(doc_export_arena(-1,1,1,7,memory,16,&r)||r.s_next!=16)return 6;
    if(doc_export_arena(INT64_MAX,1,8,7,memory,16,&r)||r.s_next!=16)return 7;
    if(doc_export_arena(0,1,1,7,0,0,&r)||r.s_next!=16)return 8;
    if(doc_export_arena(0,1,1,256,memory,16,&r)||memory[0])return 9;
    if(doc_export_arena(0,1,1,7,&r,1,&r)||r.s_next!=16)return 10;
    for(int i=0;i<16;i++)if(i!=6&&i!=15&&memory[i])return 11;
    return 0;
}
"#).unwrap();
    let build=Command::new("cc").current_dir(&tmp.0).args(["-std=c11","-O2","-fno-builtin","arena.c","fixture.c","-o","fixture"]).output().unwrap();
    assert!(build.status.success(),"{}",String::from_utf8_lossy(&build.stderr));
    let run=Command::new(tmp.0.join("fixture")).output().unwrap();
    assert!(run.status.success(),"arena policy proof exit {:?}",run.status.code());
}


#[test]
fn generated_worker_policy_uses_grain_and_hardware_not_fixed_ceiling(){
    let tmp=Scratch::new();
    let graph=doc_runtime::Graph::parse("source x: int = 2\nderive y: int (x) = add(x,1)\n").unwrap();
    let generated=doc_runtime::aot::emit_c(&graph).unwrap();
    fs::write(tmp.0.join("policy.c"),generated).unwrap();
    fs::write(tmp.0.join("fixture.c"),r#"
#define main doc_original_main
#include "policy.c"
#undef main
int main(void){
    if(doc_worker_count(63,256,256)!=1) return 1;
    if(doc_worker_count(64,256,256)!=2) return 2;
    if(doc_worker_count(4096,96,0)!=96) return 3;
    if(doc_worker_count(4096,256,256)!=128) return 4;
    if(doc_worker_count(4096,80,65)!=65) return 5;
    if(doc_worker_count(4096,8,256)!=8) return 6;
    if(doc_worker_count(4096,0,0)!=1) return 7;
    if(doc_workers(1)!=1) return 8;
    return 0;
}
"#).unwrap();
    let status=Command::new("cc").current_dir(&tmp.0)
        .args(["-std=c11","-O2","-pthread","fixture.c","-o","policy"]).status().unwrap();
    assert!(status.success());
    assert!(Command::new(tmp.0.join("policy")).status().unwrap().success());
}
