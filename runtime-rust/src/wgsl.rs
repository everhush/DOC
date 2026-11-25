//! Preliminary DOC-to-WGSL lowering for a *deliberately restricted* pure subset.
//! Each dispatch lane independently evaluates ONE existing DOC derived definition.
//! This is a boundary-equivalent batch expansion, not general GPU placement.
use crate::{Expr, Graph, Result, StateId, Type};

fn bool_expr(expr: &Expr, formals: &[Type]) -> Result<String> {
    match expr {
        Expr::Lit(crate::Value::Bool(value)) => Ok(value.to_string()),
        Expr::Arg(index) if formals.get(*index) == Some(&Type::Bool) => {
            Ok(format!("a{index}"))
        }
        Expr::Eq(left, right)
            if left.kind(formals)? == Type::Bool && right.kind(formals)? == Type::Bool =>
        {
            Ok(format!(
                "({} == {})",
                bool_expr(left, formals)?,
                bool_expr(right, formals)?
            ))
        }
        Expr::Eq(_, _) | Expr::Lt(_, _) | Expr::Le(_, _) =>
            signed_i32_equality(expr, formals),
        Expr::If(condition, yes, no)
            if condition.kind(formals)? == Type::Bool
                && yes.kind(formals)? == Type::Bool
                && no.kind(formals)? == Type::Bool =>
        {
            // DOC's pure, total boolean fragment makes select's eager operands safe.
            Ok(format!(
                "select({}, {}, {})",
                bool_expr(no, formals)?,
                bool_expr(yes, formals)?,
                bool_expr(condition, formals)?
            ))
        }
        _ => Err("WGSL Boolean batch subset permits only total Boolean conditions and host-validated i32 comparisons; no arithmetic or effects".into()),
    }
}

/// A DOC signed integer is i64, while portable WGSL provides i32. This
/// lowering is *only* observationally equivalent for host-validated i32
/// inputs. It emits comparisons, never narrowing/overflowing arithmetic.
fn signed_i32_operand(expr: &Expr, formal: &[Type]) -> Result<String> {
    match expr {
        Expr::Arg(i) if formal.get(*i) == Some(&Type::Int) => Ok(format!("a{i}")),
        Expr::Lit(crate::Value::Int(value)) => {
            let value = i32::try_from(*value)
                .map_err(|_| "DOC i64 literal is outside portable WGSL i32 range")?;
            Ok(format!("{value}i"))
        }
        Expr::If(condition, yes, no)
            if condition.kind(formal)? == Type::Bool
                && yes.kind(formal)? == Type::Int
                && no.kind(formal)? == Type::Int =>
        {
            // Both branches are total i32 expressions. DOC's lazy if and
            // WGSL's eager select therefore have identical observations.
            Ok(format!(
                "select({}, {}, {})",
                signed_i32_operand(no, formal)?,
                signed_i32_operand(yes, formal)?,
                bool_expr(condition, formal)?
            ))
        }
        _ => Err("WGSL signed comparisons permit only total i32 premises, constants and conditional selections".into()),
    }
}

fn signed_i32_equality(expr: &Expr, formal: &[Type]) -> Result<String> {
    let (left,right,operator)=match expr {
        Expr::Eq(a,b)=>(a,b,"=="),
        Expr::Lt(a,b)=>(a,b,"<"),
        Expr::Le(a,b)=>(a,b,"<="),
        _=>return Err("WGSL signed eligibility requires pure eq/lt/le".into())
    };
    if left.kind(formal)?!=Type::Int || right.kind(formal)?!=Type::Int {
        return Err("WGSL signed operands must be DOC integers".into());
    }
    Ok(format!("({} {operator} {})",
        signed_i32_operand(left,formal)?,
        signed_i32_operand(right,formal)?))
}

/// Emit a typed WebGPU compute shader from an actual DOC derived definition.
///
/// Boolean premise buffers must contain canonical u32 words (only 0 or 1).
/// Signed integer premises must be proven to fit portable WGSL i32, preserving
/// their original bit patterns. Typed input buffers may mix bool and int, and
/// nested signed comparisons are permitted inside total Boolean conditionals.
/// A host must validate each premise's type/range, equal lane count, device
/// limits and complete readback before publishing any DOC result.
/// A failed/lost device dispatch must not publish partial results.
///
/// This is *not* a claim that an arbitrary DOC program is GPU-executable.
pub fn lower_bool_derived(graph: &Graph, state_id: StateId) -> Result<String> {
    let state = graph.states.get(state_id).ok_or("unknown DOC state")?;
    let definition = state.definition.as_ref().ok_or("not a derived DOC state")?;
    if state.kind != Type::Bool {
        return Err("WGSL lowering currently requires a boolean derived result".into());
    }
    if definition.premises.len() > 4 {
        return Err("WGSL lowering currently supports at most four premises".into());
    }
    let types: Result<Vec<Type>> = definition
        .premises
        .iter()
        .map(|&id| graph.states.get(id).map(|s| s.kind).ok_or("unknown DOC premise".into()))
        .collect();
    let types = types?;
    // Int equality/order over host-validated i32 values is exact for DOC's
    // i64 comparison semantics. Do not lower arithmetic, partial operations,
    // text/nat/list premises, or unchecked i64->i32 conversion.
    if types.iter().any(|kind| !matches!(kind, Type::Int | Type::Bool)) {
        return Err("WGSL lowering supports only typed Boolean and host-validated signed i32 premises".into());
    }
    let computation = bool_expr(&definition.expr, &types)?;
    let mut wgsl = String::from("struct Storage { data: array<u32>, }\n");
    for index in 0..types.len() {
        wgsl.push_str(&format!(
            "@group(0) @binding({index}) var<storage, read> input_{index}: Storage;\n"
        ));
    }
    wgsl.push_str(&format!(
        "@group(0) @binding({}) var<storage, read_write> result: Storage;\n",
        types.len()
    ));
    wgsl.push_str(
        "@compute @workgroup_size(64)\nfn main(@builtin(global_invocation_id) gid: vec3<u32>) {\n  let idx: u32 = gid.x;\n  if (idx >= arrayLength(&result.data)) { return; }\n",
    );
    for index in 0..types.len() {
        // A malformed host binding must not cause an out-of-bounds premise read.
        // The host must still reject length mismatches rather than publish a
        // partially written candidate buffer.
        match types[index] {
            Type::Int => wgsl.push_str(&format!(
                "  if (idx >= arrayLength(&input_{index}.data)) {{ return; }}\n  let a{index}: i32 = bitcast<i32>(input_{index}.data[idx]);\n"
            )),
            Type::Bool => wgsl.push_str(&format!(
                "  if (idx >= arrayLength(&input_{index}.data)) {{ return; }}\n  let a{index}: bool = input_{index}.data[idx] != 0u;\n"
            )),
            _ => unreachable!("unsupported GPU premise type was rejected"),
        }
    }
    wgsl.push_str(&format!(
        "  let value: bool = {computation};\n  result.data[idx] = select(0u, 1u, value);\n}}\n"
    ));
    Ok(wgsl)
}

/// Count authored integer operations without evaluating any DOC result on CPU.
pub fn arithmetic_operation_count(expr: &Expr) -> usize {
    match expr {
        Expr::Add(a,b) | Expr::Sub(a,b) | Expr::Mul(a,b) =>
            1usize.saturating_add(arithmetic_operation_count(a))
                .saturating_add(arithmetic_operation_count(b)),
        Expr::Eq(a,b) | Expr::Lt(a,b) | Expr::Le(a,b) =>
            arithmetic_operation_count(a).saturating_add(arithmetic_operation_count(b)),
        Expr::If(c,a,b) =>
            arithmetic_operation_count(c)
                .saturating_add(arithmetic_operation_count(a))
                .saturating_add(arithmetic_operation_count(b)),
        _ => 0,
    }
}

/// Compile total nested arithmetic while conservatively proving signed-i32
/// safety. One arithmetic operator permits leaves within [-32767,32767].
/// For 2..=12 operators we require *every* numeric leaf and every runtime
/// integer premise within [-4,4]. A binary tree with at most 13 leaves
/// then stays within 4^13 = 67,108,864 under +,-,* in all branch paths.
fn conservative_arithmetic_operand(expr:&Expr,formals:&[Type],bound:i64)->Result<String> {
    match expr {
        Expr::Arg(index) if formals.get(*index)==Some(&Type::Int) =>
            Ok(format!("a{index}")),
        Expr::Lit(crate::Value::Int(value)) => {
            if !(-bound..=bound).contains(value) {
                return Err("DOC_GPU_UNSUPPORTED: arithmetic literal exceeds proved i32 range".into());
            }
            Ok(format!("{value}i"))
        }
        Expr::Add(a,b) | Expr::Sub(a,b) | Expr::Mul(a,b)
            if a.kind(formals)?==Type::Int && b.kind(formals)?==Type::Int =>
        {
            let op=match expr {
                Expr::Add(_,_)=>"+",Expr::Sub(_,_)=>"-",Expr::Mul(_,_)=>"*",
                _=>unreachable!(),
            };
            Ok(format!("({} {op} {})",
                conservative_arithmetic_operand(a,formals,bound)?,
                conservative_arithmetic_operand(b,formals,bound)?))
        }
        Expr::If(condition,yes,no)
            if condition.kind(formals)?==Type::Bool
                && yes.kind(formals)?==Type::Int
                && no.kind(formals)?==Type::Int =>
        {
            Ok(format!("select({}, {}, {})",
                conservative_arithmetic_operand(no,formals,bound)?,
                conservative_arithmetic_operand(yes,formals,bound)?,
                bool_expr(condition,formals)?))
        }
        _ => Err("DOC_GPU_UNSUPPORTED: nested arithmetic requires total i32 scalar expressions".into()),
    }
}

/// Lower a pure authored DOC integer state; all accepted operators execute on
/// the selected GPU, with host admission only and no CPU-derived fallback.
pub fn lower_int_derived(graph:&Graph,state_id:StateId)->Result<String> {
    let state=graph.states.get(state_id).ok_or("unknown DOC state")?;
    let definition=state.definition.as_ref().ok_or("not a derived DOC state")?;
    if state.kind!=Type::Int {
        return Err("DOC_GPU_UNSUPPORTED: this lowering requires an integer derived state".into());
    }
    if definition.premises.len()>4 {
        return Err("DOC_GPU_UNSUPPORTED: too many integer-stage premises".into());
    }
    let types:Result<Vec<Type>>=definition.premises.iter().map(|&id| {
        graph.states.get(id).map(|s|s.kind).ok_or("unknown DOC premise".into())
    }).collect();
    let types=types?;
    if types.iter().any(|t|!matches!(t,Type::Bool|Type::Int)) {
        return Err("DOC_GPU_UNSUPPORTED: integer stage requires Boolean/i32 premises".into());
    }
    let operations=arithmetic_operation_count(&definition.expr);
    if operations>12 {
        return Err("DOC_GPU_UNSUPPORTED: nested arithmetic exceeds proved operation bound".into());
    }
    let computation=if operations==0 {
        signed_i32_operand(&definition.expr,&types)?
    }else{
        conservative_arithmetic_operand(&definition.expr,&types,
            if operations>1 {4}else{32767})?
    };
    let mut shader = String::from("struct Storage { data: array<u32>, }\n");
    for index in 0..types.len() {
        shader.push_str(&format!(
            "@group(0) @binding({index}) var<storage, read> input_{index}: Storage;\n"
        ));
    }
    shader.push_str(&format!(
        "@group(0) @binding({}) var<storage, read_write> result: Storage;\n",
        types.len()
    ));
    shader.push_str(
        "@compute @workgroup_size(64)\nfn main(@builtin(global_invocation_id) gid: vec3<u32>) {\n  let idx: u32 = gid.x;\n  if (idx >= arrayLength(&result.data)) { return; }\n",
    );
    for (index,kind) in types.iter().enumerate() {
        match kind {
            Type::Int => shader.push_str(&format!(
                "  if (idx >= arrayLength(&input_{index}.data)) {{ return; }}\n  let a{index}: i32 = bitcast<i32>(input_{index}.data[idx]);\n"
            )),
            Type::Bool => shader.push_str(&format!(
                "  if (idx >= arrayLength(&input_{index}.data)) {{ return; }}\n  let a{index}: bool = input_{index}.data[idx] != 0u;\n"
            )),
            _ => unreachable!("prevalidated scalar types"),
        }
    }
    shader.push_str(&format!(
        "  let value: i32 = {computation};\n  result.data[idx] = bitcast<u32>(value);\n}}\n"
    ));
    Ok(shader)
}

/// One validation/lowering path for GPU frontiers. A DOC state passes
/// admission without constructing an unused standalone WGSL shader.
fn validated_frontier_expr(graph:&Graph,state_id:StateId)->Result<(Vec<Type>,String)> {
    let state=graph.states.get(state_id).ok_or("unknown DOC GPU frontier state")?;
    let d=state.definition.as_ref().ok_or("DOC GPU frontier includes source")?;
    if d.premises.len()>4 {
        return Err("DOC_GPU_UNSUPPORTED: too many premises in GPU frontier".into());
    }
    let types:Result<Vec<Type>>=d.premises.iter().map(|&id|
        graph.states.get(id).map(|s|s.kind).ok_or("unknown GPU premise".into())
    ).collect();
    let types=types?;
    if types.iter().any(|k|!matches!(k,Type::Bool|Type::Int)){
        return Err("DOC_GPU_UNSUPPORTED: only bool/i32 GPU frontier inputs".into());
    }
    let expression=match state.kind {
        Type::Bool=>bool_expr(&d.expr,&types)?,
        Type::Int=>{
            let ops=arithmetic_operation_count(&d.expr);
            if ops>12 {
                return Err("DOC_GPU_UNSUPPORTED: GPU arithmetic operation budget exceeded".into());
            }
            if ops==0 {signed_i32_operand(&d.expr,&types)?}
            else {conservative_arithmetic_operand(&d.expr,&types,
                if ops>1 {4}else{32767})?}
        }
        _=>return Err("DOC_GPU_UNSUPPORTED: non-scalar GPU frontier state".into()),
    };
    Ok((types,expression))
}
pub fn validate_gpu_derived(graph:&Graph,state_id:StateId)->Result<()> {
    validated_frontier_expr(graph,state_id).map(|_|())
}

/// Compile one dependency-independent ready frontier into a single shader.
/// Each invocation evaluates ONE authored DOC derived expression; multiple
/// lanes/workgroups can execute without crossing the dependency barrier.
/// No host-side evaluation substitutes for any GPU-derived result.
pub fn lower_parallel_frontier(
    graph: &Graph, ready: &[StateId], workgroup_size: u32,
) -> Result<String> {
    if ready.is_empty() || workgroup_size == 0 {
        return Err("DOC_GPU_UNSUPPORTED: empty GPU frontier or zero workgroup size".into());
    }
    let mut shader=String::from(
        "struct Storage { data: array<u32>, }\n\
         @group(0) @binding(0) var<storage, read> inputs: Storage;\n\
         @group(0) @binding(1) var<storage, read_write> results: Storage;\n");
    shader.push_str(&format!(
        "@compute @workgroup_size({workgroup_size})\n\
         fn main(@builtin(global_invocation_id) gid: vec3<u32>) {{\n\
         let idx: u32 = gid.x;\n\
         if (idx >= arrayLength(&results.data) || arrayLength(&inputs.data)==0u) {{ return; }}\n\
         switch(idx) {{\n"
    ));
    let mut base=0usize;
    for (lane,&state_id) in ready.iter().enumerate() {
        let state=graph.states.get(state_id).ok_or("unknown DOC GPU frontier state")?;
        let definition=state.definition.as_ref().ok_or("GPU frontier includes source")?;
        let (types,computation)=validated_frontier_expr(graph,state_id)?;
        shader.push_str(&format!("case {lane}u: {{\n"));
        for (k,kind) in types.iter().enumerate() {
            let index=base.checked_add(k).ok_or("DOC GPU premise offset overflow")?;
            match kind {
                Type::Bool => shader.push_str(&format!(
                    "let a{k}: bool = inputs.data[{index}u] != 0u;\n")),
                Type::Int => shader.push_str(&format!(
                    "let a{k}: i32 = bitcast<i32>(inputs.data[{index}u]);\n")),
                _ => unreachable!(),
            }
        }
        match state.kind {
            Type::Bool => shader.push_str(&format!(
                "let value: bool = {computation};\n\
                 results.data[idx] = select(0u,1u,value);\n")),
            Type::Int => shader.push_str(&format!(
                "let value: i32 = {computation};\n\
                 results.data[idx] = bitcast<u32>(value);\n")),
            _ => unreachable!(),
        }
        shader.push_str("}\n");
        base=base.checked_add(definition.premises.len().max(1))
            .ok_or("DOC GPU packed premise overflow")?;
    }
    shader.push_str("default: {}\n}\n}\n");
    Ok(shader)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn rust_owned_reusable_wgsl_parses_and_validates() {
        // DOC authored shader source stays WGSL; wgpu owns any provider translation.
        let source=include_str!("../shaders/doc_reusable.wgsl");
        let module=naga::front::wgsl::parse_str(source)
            .expect("Rust DOC reusable WGSL must parse");
        naga::valid::Validator::new(
            naga::valid::ValidationFlags::all(),naga::valid::Capabilities::all())
            .validate(&module)
            .expect("Rust DOC reusable WGSL must be valid");
    }


    #[test]
    fn independent_ready_frontier_emits_one_wgsl_invocation_per_doc_state() {
        let graph=Graph::parse(include_str!("../examples/parallel_frontier.doc")).unwrap();
        let ids:Vec<_>=graph.topo.iter().copied()
            .filter(|&id|graph.states[id].name.starts_with('p')).collect();
        assert_eq!(ids.len(),128);
        let shader=lower_parallel_frontier(&graph,&ids,32).unwrap();
        assert_eq!(shader.matches("case ").count(),128);
        assert!(shader.contains("@workgroup_size(32)"));
        let module=naga::front::wgsl::parse_str(&shader).unwrap();
        naga::valid::Validator::new(naga::valid::ValidationFlags::all(),
            naga::valid::Capabilities::all()).validate(&module).unwrap();
    }
    #[test]
    fn independent_mixed_arithmetic_gpu_frontier_validates() {
        let graph=Graph::parse(include_str!("../examples/gpu_nested_arithmetic.doc")).unwrap();
        let ids=[graph.id("sum").unwrap(),graph.id("branched").unwrap()];
        let shader=lower_parallel_frontier(&graph,&ids,2).unwrap();
        let module=naga::front::wgsl::parse_str(&shader).unwrap();
        naga::valid::Validator::new(naga::valid::ValidationFlags::all(),
            naga::valid::Capabilities::all()).validate(&module).unwrap();
        assert!(shader.contains("mul") || shader.contains(" * "));
        assert!(shader.contains("bitcast<u32>(value)"));
    }


    #[test]
    fn integer_arithmetic_chain_is_valid_wgsl_without_host_evaluation() {
        let graph = Graph::parse(include_str!("../examples/gpu_arithmetic_chain.doc")).unwrap();
        for name in ["sum","twice","diff"] {
            let shader=lower_int_derived(&graph, graph.id(name).unwrap()).unwrap();
            let module=naga::front::wgsl::parse_str(&shader).unwrap();
            let mut validator=naga::valid::Validator::new(
                naga::valid::ValidationFlags::all(), naga::valid::Capabilities::all());
            validator.validate(&module).unwrap();
            assert!(shader.contains("result.data[idx] = bitcast<u32>(value)"));
        }
        let sum=lower_int_derived(&graph, graph.id("sum").unwrap()).unwrap();
        assert!(sum.contains("a0 + a1"));
        assert!(lower_int_derived(&graph, graph.id("chosen").unwrap()).is_err());
        let full=Graph::parse(include_str!("../examples/typed_arithmetic.doc")).unwrap();
        let selected=lower_int_derived(&full,full.id("chosen").unwrap()).unwrap();
        assert!(selected.contains("select("));
        let module=naga::front::wgsl::parse_str(&selected).unwrap();
        naga::valid::Validator::new(naga::valid::ValidationFlags::all(),
            naga::valid::Capabilities::all()).validate(&module).unwrap();
    }

    #[test]
    fn nested_arithmetic_wgsl_preserves_safe_integer_semantics() {
        let graph=Graph::parse(include_str!("../examples/gpu_nested_arithmetic.doc")).unwrap();
        for state in ["sum","branched"] {
            let id=graph.id(state).unwrap();
            let wgsl=lower_int_derived(&graph,id).unwrap();
            let module=naga::front::wgsl::parse_str(&wgsl).unwrap();
            naga::valid::Validator::new(naga::valid::ValidationFlags::all(),
                naga::valid::Capabilities::all()).validate(&module).unwrap();
            assert!(wgsl.contains("result.data[idx] = bitcast<u32>(value)"));
        }
        let huge=Graph::parse(concat!(
            "source a: int = 2\n",
            "derive total: int (a) = add(a,32768)\n"
        )).unwrap();
        assert!(lower_int_derived(&huge,huge.id("total").unwrap()).is_err());
        let unsafe_literal=Graph::parse(concat!(
            "source a: int = 2\n",
            "derive total: int (a) = add(a,mul(a,5))\n"
        )).unwrap();
        assert!(lower_int_derived(&unsafe_literal,
            unsafe_literal.id("total").unwrap()).is_err());
        let mut expr="a".to_string();
        for _ in 0..13 {expr=format!("add(a,{expr})");}
        let deep=Graph::parse(&format!(
            "source a: int = 2\nderive total: int (a) = {expr}\n")).unwrap();
        assert!(lower_int_derived(&deep,deep.id("total").unwrap()).is_err());
    }
    #[test]
    fn nested_pure_boolean_doc_is_valid_wgsl() {
        let source = "source a: bool = true\nsource b: bool = false\nderive chosen: bool (a,b) = if(eq(a,b),true,eq(a,false))\n";
        let graph = Graph::parse(source).unwrap();
        let wgsl = lower_bool_derived(&graph, graph.id("chosen").unwrap()).unwrap();
        let module = naga::front::wgsl::parse_str(&wgsl).unwrap();
        let mut validator = naga::valid::Validator::new(
            naga::valid::ValidationFlags::all(),
            naga::valid::Capabilities::all(),
        );
        validator.validate(&module).unwrap();
        assert!(wgsl.contains("select("));
        assert!(wgsl.contains("arrayLength(&result.data)"));
        assert!(wgsl.contains("arrayLength(&input_0.data)"));
        assert!(wgsl.contains("arrayLength(&input_1.data)"));
    }

    #[test]
    fn boolean_conditional_cpu_truth_table_and_wgsl_validation() {
        use crate::{Cutoff, Runtime, Value};
        let source = include_str!("../examples/boolean_conditional.doc");
        let graph = Graph::parse(source).unwrap();
        let target = graph.id("chosen").unwrap();
        let shader = lower_bool_derived(&graph, target).unwrap();
        let module = naga::front::wgsl::parse_str(&shader).unwrap();
        naga::valid::Validator::new(
            naga::valid::ValidationFlags::all(),
            naga::valid::Capabilities::all(),
        ).validate(&module).unwrap();
        for a in [false, true] {
            for b in [false, true] {
                let mut runtime = Runtime::new(graph.clone(), 1, Cutoff::Exact);
                runtime.update(&[
                    (graph.id("a").unwrap(), Value::Bool(a)),
                    (graph.id("b").unwrap(), Value::Bool(b)),
                ]).unwrap();
                runtime.stabilize().unwrap();
                // Independently simplify: if a == b then true, otherwise !a.
                let oracle = a == b || !a;
                assert_eq!(runtime.value(target), Some(Value::Bool(oracle)));
            }
        }
    }

    #[test]
    fn mixed_bool_and_signed_comparison_nested_doc_validates_wgsl() {
        use crate::{Cutoff, Runtime, Value};
        // This is a genuinely mixed-typed DOC expression rather than
        // a fixed two-source comparison kernel. The host must still prove
        // all signed lane inputs fit i32 and dispatch the emitted shader.
        let source = include_str!("../examples/mixed_comparison.doc");
        let graph = Graph::parse(source).unwrap();
        let target = graph.id("chosen").unwrap();
        let shader = lower_bool_derived(&graph, target).unwrap();
        let module = naga::front::wgsl::parse_str(&shader).unwrap();
        naga::valid::Validator::new(
            naga::valid::ValidationFlags::all(),
            naga::valid::Capabilities::all(),
        ).validate(&module).unwrap();
        assert!(shader.contains("let a0: bool"));
        assert!(shader.contains("let a1: i32"));
        assert!(shader.contains("let a2: i32"));
        assert!(shader.contains("select("));
        assert!(shader.contains("=="));
        assert!(shader.contains("<"));
        let values = [
            i64::from(i32::MIN), -1, 0, 1, i64::from(i32::MAX),
        ];
        for gate in [true, false] {
            for a in values {
                for b in values {
                    let mut runtime = Runtime::new(graph.clone(), 1, Cutoff::Exact);
                    runtime.update(&[
                        (graph.id("gate").unwrap(), Value::Bool(gate)),
                        (graph.id("a").unwrap(), Value::Int(a)),
                        (graph.id("b").unwrap(), Value::Int(b)),
                    ]).unwrap();
                    runtime.stabilize().unwrap();
                    assert_eq!(
                        runtime.value(target),
                        Some(Value::Bool(if gate { a == b } else { a < b }))
                    );
                }
            }
        }
    }

    #[test]
    fn signed_conditional_comparison_is_validated_and_matches_cpu() {
        use crate::{Cutoff, Runtime, Value};
        let source = concat!(
            "source gate: bool = true\n",
            "source a: int = 1\n",
            "source b: int = 2\n",
            "derive chosen: bool (gate,a,b) = lt(if(gate,a,b),if(gate,b,a))\n",
        );
        let graph = Graph::parse(source).unwrap();
        let target = graph.id("chosen").unwrap();
        let shader = lower_bool_derived(&graph, target).unwrap();
        let module = naga::front::wgsl::parse_str(&shader).unwrap();
        naga::valid::Validator::new(
            naga::valid::ValidationFlags::all(),
            naga::valid::Capabilities::all(),
        ).validate(&module).unwrap();
        assert!(shader.matches("select(").count() >= 2);
        for gate in [false, true] {
            for a in [i64::from(i32::MIN), -1, 0, 1, i64::from(i32::MAX)] {
                for b in [i64::from(i32::MIN), -1, 0, 1, i64::from(i32::MAX)] {
                    let mut runtime = Runtime::new(graph.clone(), 1, Cutoff::Exact);
                    runtime.update(&[
                        (graph.id("gate").unwrap(), Value::Bool(gate)),
                        (graph.id("a").unwrap(), Value::Int(a)),
                        (graph.id("b").unwrap(), Value::Int(b)),
                    ]).unwrap();
                    runtime.stabilize().unwrap();
                    assert_eq!(runtime.value(target),
                        Some(Value::Bool(if gate { a < b } else { b < a })));
                }
            }
        }
    }

    #[test]
    fn signed_conditional_rejects_out_of_range_branch_literal() {
        let source = concat!(
            "source gate: bool = true\n",
            "source a: int = 1\n",
            "derive chosen: bool (gate,a) = lt(if(gate,a,2147483648),a)\n",
        );
        let graph = Graph::parse(source).unwrap();
        assert!(lower_bool_derived(&graph, graph.id("chosen").unwrap()).is_err());
    }

    #[test]
    fn mixed_typed_lowering_rejects_out_of_range_i64_literals() {
        let source = concat!(
            "source gate: bool = true\n",
            "source a: int = 1\n",
            "derive chosen: bool (gate,a) = if(gate,eq(a,2147483648),true)\n",
        );
        let graph = Graph::parse(source).unwrap();
        assert!(lower_bool_derived(&graph, graph.id("chosen").unwrap()).is_err());
    }

    #[test]
    fn rejects_unsupported_integer_arithmetic_while_allowing_safe_equality() {
        let source = "source a: int = 1\nsource b: int = 2\nderive equal: bool (a,b) = eq(a,b)\nderive unsafe: bool (a,b) = eq(add(a,1),b)\n";
        let graph = Graph::parse(source).unwrap();
        assert!(lower_bool_derived(&graph, graph.id("equal").unwrap()).is_ok());
        assert!(lower_bool_derived(&graph, graph.id("unsafe").unwrap()).is_err());
    }
}
