use doc_runtime::{Cutoff,Graph,Runtime,Type,Value};

#[test]
fn safe_index_option_values_are_typed_and_immutable() {
    let graph=Graph::parse(include_str!("../examples/safe_index.doc")).unwrap();
    let mut rt=Runtime::new(graph.clone(),4,Cutoff::Exact);
    rt.stabilize().unwrap();
    assert_eq!(rt.value(graph.id("looked").unwrap()),
        Some(Value::MaybeInt(Some(-5))));
    assert_eq!(rt.value(graph.id("value").unwrap()),Some(Value::Int(-5)));
    assert_eq!(rt.value(graph.id("absent").unwrap()),Some(Value::Bool(false)));
    let old=rt.snapshot();
    rt.update(&[(graph.id("index").unwrap(),Value::Int(-17))]).unwrap();
    rt.stabilize().unwrap();
    assert_eq!(rt.value(graph.id("looked").unwrap()),
        Some(Value::MaybeInt(None)));
    assert_eq!(rt.value(graph.id("value").unwrap()),Some(Value::Int(42)));
    assert_eq!(rt.value(graph.id("absent").unwrap()),Some(Value::Bool(true)));
    assert_eq!(rt.value(graph.id("actual").unwrap()),Some(Value::Int(-1)));
    assert_eq!(old[graph.id("looked").unwrap()],
        Some(Value::MaybeInt(Some(-5))));
    rt.update(&[(graph.id("prior").unwrap(),Value::MaybeInt(Some(11)))]).unwrap();
    rt.stabilize().unwrap();
    assert_eq!(rt.value(graph.id("preferred").unwrap()),
        Some(Value::MaybeInt(Some(11))));
    assert_eq!(rt.value(graph.id("actual").unwrap()),Some(Value::Int(11)));
}
#[test]
fn options_parse_and_reject_invalid_payloads() {
    assert_eq!(Value::parse_for_type("some(-9223372036854775808)",Type::MaybeInt)
        .unwrap(),Value::MaybeInt(Some(i64::MIN)));
    assert_eq!(Value::parse_for_type("none",Type::MaybeInt).unwrap(),
        Value::MaybeInt(None));
    for invalid in ["some()","some(1.2)","some(9223372036854775808)","nil","some(x)"]{
        assert!(Value::parse_for_type(invalid,Type::MaybeInt).is_err(),"{invalid}");
    }
    for doc in [
        "source a: ints = [1]\nderive bad: maybe_int (a) = some(a)\n",
        "source a: ints = []\nderive bad: int (a) = unwrap_or(a,0)\n",
        "source a: bool = true\nderive bad: maybe_int (a) = try_get(a,0)\n",
    ]{
        assert!(Graph::parse(doc).is_err());
    }
}
