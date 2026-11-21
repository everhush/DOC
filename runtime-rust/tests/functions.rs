use doc_runtime::{Cutoff,Graph,Runtime,Value};

#[test]
fn nested_pure_functions_are_typed_in_the_original_doc_graph() {
    let doc=include_str!("../examples/functions_int.doc");
    for worker_count in [1,2,4] {
        let graph=Graph::parse(doc).unwrap();
        let clamped=graph.id("clamped").unwrap();
        let quad=graph.id("quadruple").unwrap();
        let at_low=graph.id("at_low").unwrap();
        let mut runtime=Runtime::new(graph.clone(),worker_count,Cutoff::Exact);
        runtime.stabilize().unwrap();
        assert_eq!(runtime.value(clamped),Some(Value::Int(-7)));
        assert_eq!(runtime.value(quad),Some(Value::Int(-28)));
        assert_eq!(runtime.value(at_low),Some(Value::Bool(true)));
        runtime.update(&[(graph.id("x").unwrap(),Value::Int(100))]).unwrap();
        runtime.stabilize().unwrap();
        assert_eq!(runtime.value(clamped),Some(Value::Int(11)));
        assert_eq!(runtime.value(quad),Some(Value::Int(44)));
        assert_eq!(runtime.value(at_low),Some(Value::Bool(false)));
    }
}
#[test]
fn same_functions_are_parametrically_safe_for_very_large_nat() {
    let graph=Graph::parse(include_str!("../examples/functions_nat.doc")).unwrap();
    let mut rt=Runtime::new(graph.clone(),2,Cutoff::Exact);
    rt.stabilize().unwrap();
    assert_eq!(rt.value(graph.id("clamped").unwrap()),
        Some(Value::Nat(format!("1{}","0".repeat(70)))));
    assert_eq!(rt.value(graph.id("quadruple").unwrap()),
        Some(Value::Nat(format!("4{}","0".repeat(70)))));
}
#[test]
fn functions_reject_arity_type_cycles_and_reserved_identifiers() {
    let prelude="fn twice(x) = add(x,x)\nsource x: int = 1\n";
    for failure in [
        format!("{prelude}derive bad: int (x) = twice(x,x)\n"),
        format!("{prelude}derive bad: int (x) = twice()\n"),
        "fn foo(x,x) = add(x,x)\nsource x: int = 1\n".into(),
        "fn add(x,y) = mul(x,y)\nsource x: int = 1\n".into(),
        "fn looped(x) = looped(x)\nsource x: int = 1\nderive bad: int (x) = looped(x)\n".into(),
        "fn invalid(x) = add(x,1)\nsource a: bool = true\nderive bad: bool (a) = invalid(a)\n".into()
    ]{
        assert!(Graph::parse(&failure).is_err(),"{failure}");
    }
}
