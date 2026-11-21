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
        _ => Err("WGSL boolean batch subset excludes arithmetic, i64 values, and partial/effectful operations".into()),
    }
}

/// A DOC signed integer is i64, while portable WGSL provides i32. This
/// lowering is *only* observationally equivalent for host-validated i32
/// inputs. It emits equality, never narrowing/overflowing arithmetic.
fn signed_i32_operand(expr: &Expr, formal: &[Type]) -> Result<String> {
    match expr {
        Expr::Arg(i) if formal.get(*i) == Some(&Type::Int) => Ok(format!("a{i}")),
        Expr::Lit(crate::Value::Int(value)) => {
            let value = i32::try_from(*value)
                .map_err(|_| "DOC i64 literal is outside portable WGSL i32 range")?;
            Ok(format!("{value}i"))
        }
        _ => Err("WGSL i32 equality permits only signed i32 premises and constants".into()),
    }
}

fn signed_i32_equality(expr: &Expr, formal: &[Type]) -> Result<String> {
    match expr {
        Expr::Eq(lhs, rhs)
            if lhs.kind(formal)? == Type::Int && rhs.kind(formal)? == Type::Int =>
        {
            Ok(format!(
                "({} == {})",
                signed_i32_operand(lhs, formal)?,
                signed_i32_operand(rhs, formal)?
            ))
        }
        _ => Err("WGSL signed-integer eligibility requires pure equality without arithmetic".into()),
    }
}

/// Emit a typed WebGPU compute shader from an actual DOC derived definition.
///
/// Host input buffers must contain canonical boolean u32 words (only 0 or 1).
/// Input/output buffers must all have the same element count, and the host must
/// validate the size, device limits and completion before any DOC publication.
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
    // Signed i64 comparisons are eligible only under a separate host
    // precondition that every input fits i32. Never silently narrow a DOC
    // integer, or perform a potentially partial DOC i64 operation on WGSL.
    let signed_inputs = !types.is_empty() && types.iter().all(|&kind| kind == Type::Int);
    let bool_inputs = types.iter().all(|&kind| kind == Type::Bool);
    if !signed_inputs && !bool_inputs {
        return Err("WGSL lowering excludes mixed, natural, and unsupported premise types".into());
    }
    let computation = if signed_inputs {
        signed_i32_equality(&definition.expr, &types)?
    } else {
        bool_expr(&definition.expr, &types)?
    };
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
        if signed_inputs {
            wgsl.push_str(&format!(
                "  if (idx >= arrayLength(&input_{index}.data)) {{ return; }}\n  let a{index}: i32 = bitcast<i32>(input_{index}.data[idx]);\n"
            ));
        } else {
            wgsl.push_str(&format!(
                "  if (idx >= arrayLength(&input_{index}.data)) {{ return; }}\n  let a{index}: bool = input_{index}.data[idx] != 0u;\n"
            ));
        }
    }
    wgsl.push_str(&format!(
        "  let value: bool = {computation};\n  result.data[idx] = select(0u, 1u, value);\n}}\n"
    ));
    Ok(wgsl)
}

#[cfg(test)]
mod tests {
    use super::*;

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
    fn rejects_unsupported_integer_and_effectively_partial_computations() {
        let source = "source a: int = 1\nsource b: int = 2\nderive equal: bool (a,b) = eq(a,b)\n";
        let graph = Graph::parse(source).unwrap();
        assert!(lower_bool_derived(&graph, graph.id("equal").unwrap()).is_err());
    }
}
