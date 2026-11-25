//! Disk checkpoint round trips: typed DOC facts, schema, authority, corruption and confinement.
use doc_runtime::{
    checkpoint::{load_checkpoint,save_checkpoint},
    recurrence::Recurrence,
    Graph,Value,
};
use std::{fs,path::PathBuf};

fn folder(label:&str)->PathBuf {
    let root=std::env::temp_dir().join(format!("doc_checkpoint_{}_{}",std::process::id(),label));
    let _=fs::remove_dir_all(&root);
    fs::create_dir_all(root.join("state")).unwrap();
    root
}
fn carry(g:&Graph)->Vec<(usize,usize)> {
    [("remaining","next_remaining"),("total","next_total")].iter()
        .map(|&(a,b)|(g.id(a).unwrap(),g.id(b).unwrap())).collect()
}
fn source(root:&PathBuf)->String {
    let p=root.join("source.doc");
    fs::write(&p,include_str!("../examples/list_fold.doc")).unwrap();
    p.to_str().unwrap().to_string()
}
fn snapshot(r:&Recurrence,g:&Graph)->Vec<Value> {
    (0..g.states.len()).map(|id|r.value(id).unwrap()).collect()
}
#[test]
fn disk_roundtrip_stable_doc_valuation_all_workers_and_forward_suffix() {
    for workers in [1,2,4,8] {
        let root=folder(&format!("roundtrip_{workers}"));
        let file=source(&root);
        let graph=Graph::parse_file(&file).unwrap();
        let mut live=Recurrence::new_with_retention(
            graph.clone(),carry(&graph),&[],workers,3).unwrap();
        for _ in 0..2 {live.advance(&[]).unwrap();}
        let saved=snapshot(&live,&graph);
        let before=live.snapshot_at(2).unwrap();
        save_checkpoint(&file,"state/checkpoint.chk",&live).unwrap();
        let blob=fs::read_to_string(root.join("state/checkpoint.chk")).unwrap();
        assert!(blob.starts_with("DOC-CHECKPOINT/1\n"));
        assert!(blob.contains("\nchecksum\t"));
        let mut restored=load_checkpoint(
            &file,"state/checkpoint.chk",graph.clone(),carry(&graph),workers,2
        ).unwrap();
        assert_eq!(restored.saved_epoch,2);
        assert_eq!(restored.recurrence.epoch(),0);
        assert_eq!(snapshot(&restored.recurrence,&graph),saved);
        assert_eq!(live.snapshot_at(2).unwrap(),before);
        assert!(restored.recurrence.advance(&[
            (graph.id("total").unwrap(),Value::Int(100))
        ]).is_err(),"recovered carried facts remain protected");
        assert_eq!(restored.recurrence.epoch(),0);
        live.advance(&[]).unwrap();
        restored.recurrence.advance(&[]).unwrap();
        assert_eq!(snapshot(&live,&graph),snapshot(&restored.recurrence,&graph));
        assert_eq!(restored.recurrence.reconstruct_epoch(0).unwrap().unwrap(),
                   restored.recurrence.snapshot_at(0).unwrap());
        fs::remove_dir_all(root).unwrap();
    }
}
#[test]
fn corrupted_truncated_schema_mismatched_and_changed_authority_fail_closed() {
    let root=folder("negative");
    let file=source(&root);
    let graph=Graph::parse_file(&file).unwrap();
    let mut live=Recurrence::new(graph.clone(),carry(&graph),&[],4).unwrap();
    live.advance(&[]).unwrap();
    let stable=live.snapshot_at(live.epoch()).unwrap();
    let checkpoint=root.join("state/checkpoint.chk");
    save_checkpoint(&file,"state/checkpoint.chk",&live).unwrap();
    let good=fs::read(&checkpoint).unwrap();
    let mut altered=good.clone();
    let i=altered.iter().position(|b|*b==b'0').unwrap();
    altered[i]=b'1';
    for bad in [altered,good[..good.len()/2].to_vec(),
                b"DOC-CHECKPOINT/99\n".to_vec(),vec![0xff,0x00]] {
        fs::write(&checkpoint,bad).unwrap();
        assert!(load_checkpoint(
            &file,"state/checkpoint.chk",graph.clone(),carry(&graph),4,2
        ).is_err());
        assert_eq!(live.snapshot_at(live.epoch()).unwrap(),stable);
    }
    fs::write(&checkpoint,&good).unwrap();
    assert!(load_checkpoint(
        &file,"state/checkpoint.chk",graph.clone(),vec![],4,2
    ).is_err(),"different carry authority must be rejected");
    fs::write(&file,"source remaining: ints = [99]\nsource total: int = 0\n").unwrap();
    let new_graph=Graph::parse_file(&file).unwrap();
    assert!(load_checkpoint(
        &file,"state/checkpoint.chk",new_graph,vec![],4,2
    ).is_err(),"changed source schema must be rejected");
    fs::remove_dir_all(root).unwrap();
}
#[test]
fn checkpoint_paths_and_failed_output_are_confined_and_atomic() {
    let root=folder("paths");
    let file=source(&root);
    let graph=Graph::parse_file(&file).unwrap();
    let live=Recurrence::new(graph.clone(),carry(&graph),&[],2).unwrap();
    save_checkpoint(&file,"state/checkpoint.chk",&live).unwrap();
    let original=fs::read(root.join("state/checkpoint.chk")).unwrap();
    for invalid in ["../outside.chk","state/../checkpoint.chk","./checkpoint.chk",
                    "/tmp/escape.chk","state\\escape.chk"] {
        assert!(save_checkpoint(&file,invalid,&live).is_err(),"{invalid}");
        assert!(load_checkpoint(&file,invalid,graph.clone(),carry(&graph),2,2).is_err());
    }
    assert!(save_checkpoint(&file,"nonexistent/checkpoint.chk",&live).is_err());
    assert_eq!(fs::read(root.join("state/checkpoint.chk")).unwrap(),original);
    assert!(load_checkpoint(
        &file,"state/missing.chk",graph.clone(),carry(&graph),2,2
    ).is_err());
    assert!(load_checkpoint(
        &file,"state/checkpoint.chk",graph.clone(),carry(&graph),2,0
    ).is_err(),"invalid retention must reject restore");
    #[cfg(unix)]
    {
        use std::os::unix::fs::symlink;
        let other=folder("outside");
        let outer=other.join("foreign.chk");
        fs::write(&outer,&original).unwrap();
        symlink(&outer,root.join("state/link.chk")).unwrap();
        assert!(load_checkpoint(
            &file,"state/link.chk",graph.clone(),carry(&graph),2,2
        ).is_err(),"symlink escape must be rejected");
        fs::remove_dir_all(other).unwrap();
    }
    fs::remove_dir_all(root).unwrap();
}

#[test]
fn all_six_doc_value_domains_roundtrip_including_utf8_and_extreme_numbers(){
    let root=folder("all_types");
    let file=root.join("source.doc");
    fs::write(&file,concat!(
        "source integer: int = 0\n",
        "source truth: bool = false\n",
        "source natural: nat = 1\n",
        "source numbers: ints = []\n",
        "source optional: maybe_int = none\n",
        "source message: text = \"initial\"\n",
    )).unwrap();
    let path=file.to_str().unwrap();
    let graph=Graph::parse_file(path).unwrap();
    let overrides=vec![
        (graph.id("integer").unwrap(),Value::Int(i64::MIN)),
        (graph.id("truth").unwrap(),Value::Bool(true)),
        (graph.id("natural").unwrap(),Value::Nat("9".repeat(120))),
        (graph.id("numbers").unwrap(),Value::Ints(vec![i64::MIN,0,i64::MAX])),
        (graph.id("optional").unwrap(),Value::MaybeInt(Some(i64::MAX))),
        (graph.id("message").unwrap(),Value::Text("γειά 🌍\nsecond line".into())),
    ];
    let live=Recurrence::new_with_retention(graph.clone(),vec![],&overrides,4,2).unwrap();
    let expected=snapshot(&live,&graph);
    save_checkpoint(path,"state/all.chk",&live).unwrap();
    let disk=fs::read_to_string(root.join("state/all.chk")).unwrap();
    assert!(!disk.contains("γειά"),"UTF-8 literal must be hex encoded");
    let restored=load_checkpoint(path,"state/all.chk",graph.clone(),vec![],1,2)
        .unwrap().recurrence;
    assert_eq!(snapshot(&restored,&graph),expected);
    assert_eq!(restored.epoch(),0);
    fs::remove_dir_all(root).unwrap();
}
