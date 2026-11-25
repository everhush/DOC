//! Versioned #10 compiler handoff: canonical source-order typed IR and authority.
use doc_runtime::{typed_ir::emit_typed_ir_v1,Graph};

#[test]
fn ir_v1_is_stable_typed_and_uses_explicit_local_premise_indices(){
    let source=concat!(
        "source x: int = 3\n",
        "source y: int = -4\n",
        "derive sum: int (x,y) = add(x,y)\n",
        "derive positive: bool (sum) = lt(0,sum)\n",
        "source label: text = \"Hi\"\n",
    );
    let g=Graph::parse(source).unwrap();
    let ir=emit_typed_ir_v1(&g,&[]).unwrap();
    assert!(ir.starts_with("DOC-TYPED-IR/1\nstates\t5\n"));
    assert!(ir.contains("source\t0\tx\tint\t33\n"));
    assert!(ir.contains("source\t1\ty\tint\t2d34\n"));
    assert!(ir.contains("derive\t2\tsum\tint\t0,1\tadd(arg(0),arg(1))\n"));
    assert!(ir.contains("derive\t3\tpositive\tbool\t2\tlt(lit(int,30),arg(0))\n"));
    assert!(ir.contains("source\t4\tlabel\ttext\t4869\n"));
    assert_eq!(emit_typed_ir_v1(&g,&[]).unwrap(),ir);
    assert!(!ir.contains("HostCall"));
}
#[test]
fn carry_version_contract_accepts_valid_and_rejects_schema_corruption(){
    let g=Graph::parse(concat!(
       "source n: int = 1\n",
       "derive following: int (n) = add(n,1)\n",
    )).unwrap();
    let ir=emit_typed_ir_v1(&g,&[(0,1)]).unwrap();
    assert!(ir.ends_with("carry\t0\t1\n"));
    assert!(emit_typed_ir_v1(&g,&[(0,1),(0,1)]).is_err());
    assert!(emit_typed_ir_v1(&g,&[(1,0)]).is_err());
    assert!(emit_typed_ir_v1(&g,&[(3,0)]).is_err());
    let mut mutated=g.clone();
    mutated.states[0].name="following".into();
    assert!(emit_typed_ir_v1(&mutated,&[]).is_err());
}
#[test]
fn real_engine_ir_is_derived_from_DOC_graph_not_host_game_rules(){
    let file=format!("{}/../engine/coin_chase.doc",env!("CARGO_MANIFEST_DIR"));
    let g=Graph::parse_file(&file).unwrap();
    let a=g.id("frame").unwrap();
    let b=g.id("next_frame").unwrap();
    let ir=emit_typed_ir_v1(&g,&[(a,b)]).unwrap();
    assert!(ir.contains("\tcollected\tbool\t"));
    assert!(ir.contains("\taudio_hz\tint\t"));
    assert!(ir.contains("\taudio_ms\tint\t"));
    assert!(ir.contains("carry\t"));
    assert!(ir.contains("if("));
}
