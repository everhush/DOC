use doc_runtime::{Cutoff,Graph,Runtime,Value};

#[test]
fn explicit_effect_sources_are_typed_and_pure_derived_evaluation_is_separate(){
    let graph=Graph::parse_file(
        &format!("{}/examples/effect_demo.doc",env!("CARGO_MANIFEST_DIR"))
    ).unwrap();
    let mut runtime=Runtime::new(graph.clone(),4,Cutoff::Exact);
    runtime.stabilize().unwrap();
    assert_eq!(runtime.value(graph.id("count").unwrap()),Some(Value::Int(-23)));
    assert_eq!(runtime.value(graph.id("incremented").unwrap()),Some(Value::Int(-22)));
    assert_eq!(runtime.value(graph.id("enabled").unwrap()),Some(Value::Bool(true)));
    let hundred="9".repeat(100);
    assert_eq!(runtime.value(graph.id("amount").unwrap()),
        Some(Value::Nat(hundred.clone())));
    assert_eq!(runtime.value(graph.id("next_amount").unwrap()),
        Some(Value::Nat(format!("1{}","0".repeat(100)))));
    assert_eq!(runtime.value(graph.id("selected").unwrap()),
        Some(Value::Nat(format!("1{}2","0".repeat(99)))));
    runtime.update(&[(graph.id("enabled").unwrap(),Value::Bool(false))]).unwrap();
    runtime.stabilize().unwrap();
    assert_eq!(runtime.value(graph.id("selected").unwrap()),
        Some(Value::Nat("0".into())));
}
