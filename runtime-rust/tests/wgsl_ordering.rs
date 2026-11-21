use doc_runtime::{wgsl,Graph};
use naga::valid::{Capabilities,ValidationFlags,Validator};

#[test]
fn doc_signed_comparisons_lower_to_valid_wgsl() {
    let graph=Graph::parse(include_str!("../examples/integer_ordering.doc")).unwrap();
    for (state,op) in [("less","<"),("less_or_equal","<=")] {
        let shader=wgsl::lower_bool_derived(&graph,graph.id(state).unwrap()).unwrap();
        assert!(shader.contains(&format!("(a0 {op} a1)")));
        assert!(shader.contains("bitcast<i32>"));
        let module=naga::front::wgsl::parse_str(&shader).unwrap();
        Validator::new(ValidationFlags::all(),Capabilities::all())
            .validate(&module).unwrap();
    }
}

#[test]
fn unsound_signed_arithmetic_cannot_be_lowered() {
    let graph=Graph::parse(
        "source a: int = 9\nsource b: int = 3\n         derive no: bool (a,b) = lt(add(a,b),a)\n"
    ).unwrap();
    assert!(wgsl::lower_bool_derived(&graph,graph.id("no").unwrap()).is_err());
}
