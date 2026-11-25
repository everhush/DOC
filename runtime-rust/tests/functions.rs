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

#[test]
fn lexical_function_specialization_preserves_literals_and_removes_old_arity_limit(){
    let doc=concat!(
        "fn label(x) = concat(text(\"x, café (literal) \"),x)\n",
        "fn total(a,b,c,d,e,f) = add(add(add(a,b),add(c,d)),add(e,f))\n",
        "source suffix: text = \"ok\"\nsource n: int = 1\n",
        "derive message: text (suffix) = label(suffix)\n",
        "derive result: int (n) = total(n,2,3,4,5,6)\n");
    let g=Graph::parse(doc).unwrap();let message=g.id("message").unwrap();let result=g.id("result").unwrap();
    let mut r=Runtime::new(g,4,Cutoff::Exact);r.stabilize().unwrap();
    assert_eq!(r.value(message),Some(Value::Text("x, café (literal) ok".into())));
    assert_eq!(r.value(result),Some(Value::Int(21)));
    let body=(0..100).fold("x".to_string(),|b,_|format!("add(x,{b})"));
    assert!(body.len()>512);
    let g=Graph::parse(&format!("fn many(x) = {body}\nsource n: int = 1\nderive result: int (n) = many(n)\n")).unwrap();
    let result=g.id("result").unwrap();let mut r=Runtime::new(g,2,Cutoff::Exact);r.stabilize().unwrap();assert_eq!(r.value(result),Some(Value::Int(101)));
}
#[test]
fn lexical_function_specialization_limits_expansion_and_rejects_hidden_binders(){
    let mut doc="fn f0(x) = add(x,x)\n".to_owned();
    for i in 1..18{doc.push_str(&format!("fn f{i}(x) = f{}(f{}(x))\n",i-1,i-1));}
    doc.push_str("source n: int = 0\n");
    assert!(Graph::parse(&doc).is_err());
    assert!(Graph::parse("fn hidden(xs) = map_ints(xs,x,x)\nsource xs: ints = [1]\n").is_err());
    assert!(Graph::parse("fn hidden(seed) = recur(seed,x,true,x)\nsource seed: int = 0\n").is_err());
}
