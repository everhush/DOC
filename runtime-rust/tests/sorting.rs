use doc_runtime::{Cutoff,Graph,Runtime,Value};

fn run_sort(program:&str, inputs:[Value;4],workers:usize)->Vec<Value>{
    let graph=Graph::parse(program).unwrap();
    let mut runtime=Runtime::new(graph.clone(),workers,Cutoff::Exact);
    let changes=(0..4).map(|i|(graph.id(&"abcd"[i..i+1]).unwrap(),inputs[i].clone()))
        .collect::<Vec<_>>();
    runtime.update(&changes).unwrap();
    runtime.stabilize().unwrap();
    let order=["first","second","third","fourth"];
    order.iter().map(|name|runtime.value(graph.id(name).unwrap()).unwrap()).collect()
}
#[test]
fn signed_four_value_sort_is_deterministic_across_workers() {
    let text=include_str!("../examples/sort4_int.doc");
    for seed in 0..100u64 {
        let mut n=seed*17+3;
        let values=std::array::from_fn(|_|{
            n=n.wrapping_mul(6364136223846793005).wrapping_add(1);
            (n as i64).wrapping_shr((seed%31) as u32)
        });
        let input=values.clone().map(Value::Int);
        let mut want=values;
        want.sort_unstable();
        let want=want.map(Value::Int).to_vec();
        for workers in [1,2,4]{
            assert_eq!(run_sort(text,input.clone(),workers),want);
        }
    }
    let input=[i64::MIN,i64::MAX,0,-1].map(Value::Int);
    assert_eq!(run_sort(text,input,4),
        [i64::MIN,-1,0,i64::MAX].map(Value::Int).to_vec());
}
#[test]
fn arbitrary_nat_sort_is_exact_and_canonical() {
    let text=include_str!("../examples/sort4_nat.doc");
    let huge="9".repeat(200);
    for values in [
        ["0000".to_string(),"00001".to_string(),huge.clone(),"32".into()],
        [huge.clone(), "4".into(),"4".into(), "10000000000000000".into()],
        ["0".into(),"0".into(),"0".into(),"0".into()]
    ]{
        let actual=run_sort(text,values.clone().map(|s|
            Value::Nat(doc_runtime::nat::canonical(&s).unwrap())),2);
        let mut expected=values.map(|s|doc_runtime::nat::canonical(&s).unwrap());
        expected.sort_by(|a,b|a.len().cmp(&b.len()).then_with(||a.cmp(b)));
        assert_eq!(actual,expected.map(Value::Nat).to_vec());
    }
}
#[test]
fn ordering_requires_matching_numeric_types() {
    for text in [
        "source a: int = 1\nsource b: bool = true\nderive bad: bool (a,b) = lt(a,b)\n",
        "derive bad: bool () = le(true,false)\n",
        "derive bad: bool () = lt(nat(1),1)\n",
    ]{assert!(Graph::parse(text).is_err());}
}
