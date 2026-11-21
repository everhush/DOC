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
        "import C:/Windows/System32/stolen.doc",
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
