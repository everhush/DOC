use doc_runtime::{wgsl,Graph};
use naga::valid::{Capabilities,ValidationFlags,Validator};

#[test]
fn signed_i32_equality_is_lowered_from_actual_doc_source() {
    let graph=Graph::parse(include_str!("../examples/integer_equality.doc")).unwrap();
    let shader=wgsl::lower_bool_derived(&graph,graph.id("equal").unwrap()).unwrap();
    assert!(shader.contains("bitcast<i32>(input_0.data[idx])"));
    assert!(shader.contains("bitcast<i32>(input_1.data[idx])"));
    assert!(shader.contains("(a0 == a1)"));
    let parsed=naga::front::wgsl::parse_str(&shader).unwrap();
    Validator::new(ValidationFlags::all(),Capabilities::all()).validate(&parsed).unwrap();
}

#[test]
fn unsupported_i64_math_or_wide_literals_never_silently_narrow() {
    for program in [
        "source a: int = 1\nderive reject: bool (a) = eq(add(a,1),0)\n",
        "source a: int = 1\nderive reject: bool (a) = eq(a,9223372036854775807)\n",
        "source a: nat = 1\nderive reject: bool (a) = eq(a,nat(1))\n",
    ] {
        let graph=Graph::parse(program).unwrap();
        assert!(wgsl::lower_bool_derived(&graph,graph.id("reject").unwrap()).is_err());
    }
}
