use doc_runtime::{Cutoff,Graph,Runtime,Value,recurrence::Recurrence};

fn template()->Graph{
    Graph::parse(include_str!("../examples/list_fold.doc")).unwrap()
}
#[test]
fn typed_dynamic_collections_are_immutable_and_exact() {
    let graph=template();
    let mut rt=Runtime::new(graph.clone(),4,Cutoff::Exact);
    rt.stabilize().unwrap();
    assert_eq!(rt.value(graph.id("count").unwrap()),Some(Value::Int(4)));
    assert_eq!(rt.value(graph.id("next_total").unwrap()),Some(Value::Int(5)));
    assert_eq!(rt.value(graph.id("next_remaining").unwrap()),
        Some(Value::Ints(vec![-3,9,0])));
    assert_eq!(rt.value(graph.id("singleton").unwrap()),
        Some(Value::Ints(vec![0])));
    let old=rt.snapshot();
    rt.update(&[(graph.id("remaining").unwrap(),
        Value::Ints(vec![i64::MIN,i64::MAX]))]).unwrap();
    rt.stabilize().unwrap();
    assert_eq!(old[graph.id("remaining").unwrap()],
        Some(Value::Ints(vec![5,-3,9,0])));
    assert_eq!(rt.value(graph.id("count").unwrap()),Some(Value::Int(2)));
}
#[test]
fn list_fold_through_forward_carry_halts_and_retains_immutable_snapshots() {
    let graph=template();
    let source=graph.id("remaining").unwrap();
    let total=graph.id("total").unwrap();
    let mut rt=Recurrence::new_with_retention(
        graph.clone(),
        vec![(source,graph.id("next_remaining").unwrap()),
             (total,graph.id("next_total").unwrap())],&[],4,2
    ).unwrap();
    let old=rt.snapshot_at(0).unwrap();
    assert!(rt.advance_until(graph.id("done").unwrap(),10).unwrap());
    assert_eq!(rt.epoch(),4);
    assert_eq!(rt.value(source),Some(Value::Ints(vec![])));
    assert_eq!(rt.value(total),Some(Value::Int(11)));
    assert_eq!(rt.retained_epochs(),vec![3,4]);
    assert_eq!(old[source],Some(Value::Ints(vec![5,-3,9,0])));
}
#[test]
fn collection_bounds_and_types_are_checked() {
    for program in [
        "source a: ints = [0]\nderive bad: int (a) = get(a,-1)\n",
        "source a: ints = []\nderive bad: int (a) = get(a,0)\n",
        "source a: bool = true\nderive bad: int (a) = len(a)\n",
        "source a: ints = [1,2]\nderive bad: ints (a) = append(a,true)\n",
        "source a: ints = [1]\nderive bad: int (a) = get(a,nat(0))\n"
    ]{
        match Graph::parse(program){
            Err(_)=>{},
            Ok(g)=>assert!(Runtime::new(g,1,Cutoff::Exact).stabilize().is_err())
        }
    }
    assert!(Value::parse_for_type("[1,x]",doc_runtime::Type::Ints).is_err());
    assert!(Value::parse_for_type("[,1]",doc_runtime::Type::Ints).is_err());
    assert!(Value::parse_for_type("[0,0,0]",doc_runtime::Type::Ints).is_ok());
    assert!(Value::parse_for_type(
        &format!("[{}]",vec!["1";4097].join(",")),
        doc_runtime::Type::Ints).is_ok());
}

#[test]
fn dynamic_collections_extend_beyond_previous_fixed_cap() {
    let values=(0..4097i64).collect::<Vec<_>>();
    let list=format!("[{}]",values.iter().map(i64::to_string)
        .collect::<Vec<_>>().join(","));
    let source=format!("source items: ints = {list}\n\
        derive expanded: ints (items) = append(items,777)\n\
        derive count: int (expanded) = len(expanded)\n");
    let graph=Graph::parse(&source).unwrap();
    let mut runtime=Runtime::new(graph.clone(),4,Cutoff::Exact);
    runtime.stabilize().unwrap();
    assert_eq!(runtime.value(graph.id("count").unwrap()),Some(Value::Int(4098)));
    let mut expected=values;
    expected.push(777);
    assert_eq!(runtime.value(graph.id("expanded").unwrap()),
               Some(Value::Ints(expected)));
}
