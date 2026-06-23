use doc_runtime::{wgsl, Graph};
use naga::valid::{Capabilities, ValidationFlags, Validator};

fn validate(shader: &str) {
    let module = naga::front::wgsl::parse_str(shader).expect("WGSL must parse");
    Validator::new(ValidationFlags::all(), Capabilities::all())
        .validate(&module)
        .expect("WGSL must be semantically valid");
}

#[test]
fn doc_boolean_equalities_lower_to_valid_wgsl() {
    let graph = Graph::parse(
        "source a: bool = true\nsource b: bool = false\nderive xor: bool (a,b) = if(eq(a,b),false,true)\n",
    )
    .expect("valid DOC source");
    let shader = wgsl::lower_bool_derived(&graph, graph.id("xor").unwrap()).unwrap();
    assert!(shader.contains("@compute"));
    assert!(shader.contains("input_0"));
    assert!(shader.contains("select"));
    validate(&shader);
}

#[test]
fn zero_input_boolean_literal_has_valid_shader() {
    let graph = Graph::parse("derive constant: bool () = true\n").unwrap();
    let shader = wgsl::lower_bool_derived(&graph, graph.id("constant").unwrap()).unwrap();
    validate(&shader);
}

#[test]
fn unsupported_integer_math_is_rejected_not_miscompiled() {
    let graph = Graph::parse(
        "source a: int = 1\nsource b: int = 2\nderive sum: int (a,b) = add(a,b)\n",
    )
    .unwrap();
    assert!(wgsl::lower_bool_derived(&graph, graph.id("sum").unwrap()).is_err());
    assert!(wgsl::lower_bool_derived(&graph, graph.id("a").unwrap()).is_err());
    assert!(wgsl::lower_bool_derived(&graph, 999).is_err());
}
