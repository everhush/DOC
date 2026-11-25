use doc_runtime::{Value,write_doc_output};
use std::fs;

#[test]
fn only_completed_typed_values_are_exported_to_confined_files() {
    let root=std::env::temp_dir().join(format!("doc_emit_{}",std::process::id()));
    let _=fs::remove_dir_all(&root);
    fs::create_dir_all(root.join("data")).unwrap();
    let src=root.join("source.doc");
    fs::write(&src,"source a: int = 7\n").unwrap();
    let path=src.to_str().unwrap();
    for (output,value,expected) in [
        ("data/int.txt",Value::Int(i64::MIN),format!("{}\n",i64::MIN)),
        ("data/list.txt",Value::Ints(vec![5,-1,0]),"[5,-1,0]\n".into()),
        ("data/nat.txt",Value::Nat("9".repeat(120)),format!("{}\n","9".repeat(120))),
        ("data/none.txt",Value::MaybeInt(None),"none\n".into()),
        ("data/some.txt",Value::MaybeInt(Some(-50)),"some(-50)\n".into()),
    ] {
        write_doc_output(path,output,&value).unwrap();
        assert_eq!(fs::read_to_string(root.join(output)).unwrap(),expected);
    }
    for invalid in ["../escape.txt","data/../escape.txt","./data/file.txt",
                    "/etc/out","C:/blocked.txt","data\\file.txt"] {
        assert!(write_doc_output(path,invalid,&Value::Int(9)).is_err());
    }
    fs::remove_dir_all(&root).unwrap();
}
