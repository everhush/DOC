//! The typed resource host adapter is inert until DOC source data is sampled.
use doc_runtime::{resources::DataResources,Cutoff,Graph,Runtime,Type,Value};

#[test]
fn bounded_generation_handles_preserve_types_and_replace_atomically(){
    for _workers in [1usize,2,4,8] {
        let mut assets=DataResources::new(2,128).unwrap();
        let first=assets.insert(Value::Ints(vec![3,-5])).unwrap();
        assert_eq!(assets.get(first,Type::Ints).unwrap(),&Value::Ints(vec![3,-5]));
        assert!(assets.get(first,Type::Int).is_err());
        assert_eq!(assets.live_count(),1);
        assert_eq!(assets.live_payload_bytes(),16);
        assert!(assets.replace(first,Value::Text("wrong".into())).is_err());
        assert!(assets.replace(first,Value::Ints(vec![7;17])).is_err());
        assert_eq!(assets.get(first,Type::Ints).unwrap(),&Value::Ints(vec![3,-5]));
        assert_eq!(assets.live_payload_bytes(),16,"rejected updates must not publish");
        let second=assets.replace(first,Value::Ints(vec![4,5,6])).unwrap();
        assert_eq!(second.slot,first.slot);
        assert_ne!(second.generation,first.generation);
        assert!(assets.get(first,Type::Ints).is_err(),"replaced handle stale");
        assert_eq!(assets.get(second,Type::Ints).unwrap(),&Value::Ints(vec![4,5,6]));
        let separate=assets.insert(Value::Bool(true)).unwrap();
        assert!(assets.insert(Value::Int(999)).is_err(),"bounded slots");
        assert_eq!(assets.allocated_slot_count(),2);
        assert_eq!(assets.live_payload_bytes(),25);
        assets.release(second).unwrap();
        assert!(assets.release(second).is_err(),"double free");
        let recycled=assets.insert(Value::Text("hello".into())).unwrap();
        assert_eq!(recycled.slot,second.slot);
        assert_ne!(recycled.generation,second.generation);
        assert!(assets.get(first,Type::Ints).is_err());
        assert!(assets.get(second,Type::Ints).is_err());
        assert_eq!(assets.live_payload_bytes(),6);
        assets.release(recycled).unwrap();
        assets.release(separate).unwrap();
        assert_eq!(assets.live_count(),0);
        assert_eq!(assets.live_payload_bytes(),0);
        assert_eq!(assets.allocated_slot_count(),2);
        assert!(assets.peak_payload_bytes()>=25);
    }
}
#[test]
fn doc_typed_effect_assets_can_be_loaded_and_released_separately(){
    let file=format!("{}/examples/effect_demo.doc",env!("CARGO_MANIFEST_DIR"));
    let graph=Graph::parse_file(&file).unwrap();
    let mut runtime=Runtime::new(graph.clone(),4,Cutoff::Exact);
    runtime.stabilize().unwrap();
    let amount=runtime.value(graph.id("amount").unwrap()).unwrap();
    let count=runtime.value(graph.id("count").unwrap()).unwrap();
    let mut store=DataResources::new(2,128).unwrap();
    let a=store.insert(amount.clone()).unwrap();
    let b=store.insert(count.clone()).unwrap();
    assert_eq!(store.get(a,Type::Nat).unwrap(),&amount);
    assert_eq!(store.get(b,Type::Int).unwrap(),&Value::Int(-23));
    assert!(store.replace(a,Value::Nat("9".repeat(200))).is_err());
    assert_eq!(store.get(a,Type::Nat).unwrap(),&amount);
    let replacement=store.replace(b,Value::Int(99)).unwrap();
    assert!(store.get(b,Type::Int).is_err());
    assert_eq!(store.get(replacement,Type::Int).unwrap(),&Value::Int(99));
    store.release(a).unwrap();
    store.release(replacement).unwrap();
    assert_eq!(store.live_payload_bytes(),0);
}
#[test]
fn zero_budget_and_excessive_capacity_fail_without_allocating(){
    assert!(DataResources::new(1025,8).is_err());
    let mut no_slots=DataResources::new(0,128).unwrap();
    assert!(no_slots.insert(Value::Int(1)).is_err());
    assert_eq!(no_slots.allocated_slot_count(),0);
    let mut no_bytes=DataResources::new(2,0).unwrap();
    assert!(no_bytes.insert(Value::Bool(true)).is_err());
    assert_eq!(no_bytes.live_count(),0);
    assert!(no_bytes.insert(Value::Ints(Vec::new())).is_ok());
    assert_eq!(no_bytes.live_payload_bytes(),0);
}
