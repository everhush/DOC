use doc_runtime::{Cutoff,Graph,Runtime,Value};

#[test]
fn explicit_native_module_reuses_pure_functions_without_transpilation() {
    let g=Graph::parse_file(&format!("{}/examples/module_clamp.doc",env!("CARGO_MANIFEST_DIR"))).unwrap();
    assert_eq!(g.states.len(),5);
    for workers in [1,2,4] {
        let mut rt=Runtime::new(g.clone(),workers,Cutoff::Exact);
        rt.stabilize().unwrap();
        assert_eq!(rt.value(g.id("bounded").unwrap()),Some(Value::Int(11)));
        assert_eq!(rt.value(g.id("amplified").unwrap()),Some(Value::Int(44)));
        rt.update(&[(g.id("x").unwrap(),Value::Int(-100))]).unwrap();
        rt.stabilize().unwrap();
        assert_eq!(rt.value(g.id("bounded").unwrap()),Some(Value::Int(-13)));
        assert_eq!(rt.value(g.id("amplified").unwrap()),Some(Value::Int(-52)));
    }
}

#[test]
fn same_native_library_is_parametric_over_arbitrary_natural_values() {
    let g=Graph::parse_file(&format!("{}/examples/module_clamp_nat.doc",env!("CARGO_MANIFEST_DIR"))).unwrap();
    let mut rt=Runtime::new(g.clone(),4,Cutoff::Exact);
    rt.stabilize().unwrap();
    let capped=format!("1{}","0".repeat(80));
    assert_eq!(rt.value(g.id("bounded").unwrap()),Some(Value::Nat(capped)));
    assert_eq!(rt.value(g.id("amplified").unwrap()),
        Some(Value::Nat(format!("4{}","0".repeat(80)))));
}
