use doc_runtime::{Cutoff,Graph,Runtime,Type,Value,recurrence::Recurrence};

#[test]
fn utf8_literals_concat_and_prefix_preserve_exact_bytes() {
    let graph=Graph::parse(include_str!("../examples/text_program.doc")).unwrap();
    let mut rt=Runtime::new(graph.clone(),4,Cutoff::Exact);
    rt.stabilize().unwrap();
    assert_eq!(rt.value(graph.id("joined").unwrap()),
               Some(Value::Text("Hello, 世界".into())));
    assert_eq!(rt.value(graph.id("byte_count").unwrap()),
               Some(Value::Int("Hello, 世界".len() as i64)));
    assert_eq!(rt.value(graph.id("is_greeting").unwrap()),Some(Value::Bool(true)));
    assert_eq!(rt.value(graph.id("is_cjk").unwrap()),Some(Value::Bool(true)));
    let prior=rt.snapshot();
    rt.update(&[(graph.id("name").unwrap(),Value::Text("🙂".into()))]).unwrap();
    rt.stabilize().unwrap();
    assert_eq!(rt.value(graph.id("joined").unwrap()),
               Some(Value::Text("Hello, 🙂".into())));
    assert_eq!(prior[graph.id("joined").unwrap()],
               Some(Value::Text("Hello, 世界".into())));
}
#[test]
fn utf8_recurrence_preserves_owned_text_snapshots_under_eviction() {
    let graph=Graph::parse(include_str!("../examples/text_recurrence.doc")).unwrap();
    let text=graph.id("text_value").unwrap();
    let next=graph.id("next").unwrap();
    let mut rt=Recurrence::new_with_retention(
        graph,vec![(text,next)],&[],2,3).unwrap();
    let old=rt.snapshot_at(0).unwrap();
    rt.demand_through(150).unwrap();
    assert_eq!(rt.value(text),Some(Value::Text("🙂".repeat(151))));
    assert_eq!(old[text],Some(Value::Text("🙂".into())));
    assert_eq!(rt.reconstruct_epoch(20).unwrap().unwrap()[text],
               Some(Value::Text("🙂".repeat(21))));
}
#[test]
fn text_literals_reject_invalid_escapes() {
    for source in [
        "source a: text = \"unterminated\n",
        "source a: text = \"x\\\\y\"\n",
        "source a: text = \"x\\\"y\"\n",
        "source a: int = 1\nderive bad: text (a) = concat(a,text(\"x\"))\n",
    ]{
        assert!(Graph::parse(source).is_err(),"{source}");
    }
    assert!(Value::parse_for_type(
        &format!("\"{}\"","x".repeat(16385)),Type::Text).is_ok());
}

#[test]
fn utf8_source_and_concat_can_exceed_old_fixed_text_ceiling() {
    let large="世界🙂".repeat(2500);
    let source=format!("source payload: text = \"{large}\"\n\
        derive expanded: text (payload) = concat(payload,text(\"!\"))\n\
        derive bytes: int (expanded) = len(expanded)\n");
    let graph=Graph::parse(&source).unwrap();
    let mut runtime=Runtime::new(graph.clone(),4,Cutoff::Exact);
    runtime.stabilize().unwrap();
    let expanded=format!("{large}!");
    assert_eq!(runtime.value(graph.id("expanded").unwrap()),
               Some(Value::Text(expanded.clone())));
    assert_eq!(runtime.value(graph.id("bytes").unwrap()),
               Some(Value::Int(expanded.len() as i64)));
}
