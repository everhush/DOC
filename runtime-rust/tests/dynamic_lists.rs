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

#[test]
fn long_dynamic_list_carry_reconstructs_evicted_epochs_without_mutating_readers() {
    // Each epoch consumes one element; reconstruction must replay from
    // immutable typed carry rather than borrow a reclaimed list buffer.
    let items=(-32i64..32).collect::<Vec<_>>();
    let literal=items.iter().map(i64::to_string).collect::<Vec<_>>().join(",");
    let source=include_str!("../examples/list_fold.doc").replace(
        "source remaining: ints = [5,-3,9,0]",
        &format!("source remaining: ints = [{literal}]"));
    let graph=Graph::parse(&source).unwrap();
    let remaining=graph.id("remaining").unwrap();
    let total=graph.id("total").unwrap();
    let mut recurrence=Recurrence::new_with_retention(
        graph.clone(),
        vec![(remaining,graph.id("next_remaining").unwrap()),
             (total,graph.id("next_total").unwrap())],&[],4,2).unwrap();
    let pinned=recurrence.snapshot_at(0).unwrap();
    assert!(recurrence.advance_until(graph.id("done").unwrap(),66).unwrap());
    assert_eq!(recurrence.epoch(),64);
    assert_eq!(recurrence.value(remaining),Some(Value::Ints(vec![])));
    assert_eq!(recurrence.value(total),Some(Value::Int(items.iter().sum())));
    assert_eq!(pinned[remaining],Some(Value::Ints(items.clone())));
    assert_eq!(pinned[total],Some(Value::Int(0)));
    assert_eq!(recurrence.retained_epochs(),vec![63,64]);
    for epoch in [0,1,20,63,64] {
        let rebuilt=recurrence.reconstruct_epoch(epoch).unwrap().unwrap();
        assert_eq!(rebuilt[remaining],Some(Value::Ints(items[epoch as usize..].to_vec())));
        assert_eq!(rebuilt[total],Some(Value::Int(items[..epoch as usize].iter().sum())));
    }
    // Replaying an evicted epoch must not overwrite the live generation.
    assert_eq!(recurrence.value(total),Some(Value::Int(items.iter().sum())));
}

#[test]
fn checked_slice_is_immutable_and_bounds_checked() {
    let g=Graph::parse("source xs: ints = [4,9,-1,7]\nsource start: int = 1\nsource count: int = 2\nfn part(a,b,c) = slice(a,b,c)\nderive selected: ints (xs,start,count) = part(xs,start,count)\n").unwrap();
    let ir=doc_runtime::typed_ir::emit_typed_ir_v1(&g,&[]).unwrap();
    assert!(ir.contains("slice(arg(0),arg(1),arg(2))"));
    let xs=g.id("xs").unwrap();let start=g.id("start").unwrap();let count=g.id("count").unwrap();let selected=g.id("selected").unwrap();
    for workers in [1,2,4,8] {
        let mut r=Runtime::new(g.clone(),workers,Cutoff::Exact);
        r.stabilize().unwrap();
        let retained=r.snapshot();
        assert_eq!(retained[selected],Some(Value::Ints(vec![9,-1])));
        for (values,offset,length) in [(vec![8,3],2,0),(vec![],0,0),(vec![1,2,3,4,5],0,5),(vec![-1,7],1,1)] {
            let expected=values[offset as usize..(offset+length) as usize].to_vec();
            r.update(&[(xs,Value::Ints(values)),(start,Value::Int(offset)),(count,Value::Int(length))]).unwrap();
            r.stabilize().unwrap();assert_eq!(r.value(selected),Some(Value::Ints(expected)));
        }
        for (offset,length) in [(-1,0),(0,-1),(3,0),(2,1),(i64::MAX,i64::MAX)] {
            r.update(&[(start,Value::Int(offset)),(count,Value::Int(length))]).unwrap();
            let before=r.snapshot();
            assert!(r.stabilize().is_err());
            assert_eq!(r.snapshot(),before);
        }
        assert_eq!(retained[selected],Some(Value::Ints(vec![9,-1])));
    }
    for expression in ["slice(xs,true,1)","slice(xs,0,true)","slice(1,0,1)"] {
        assert!(Graph::parse(&format!("source xs: ints = [1]\nderive result: ints (xs) = {expression}\n")).is_err());
    }
}
