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
    if types.iter().any(|&kind| kind != Type::Bool) {
        return Err("WGSL lowering currently supports boolean premises only".into());
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
        wgsl.push_str(&format!(
            "  let a{index}: bool = input_{index}.data[idx] != 0u;\n"
        ));
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
    }

    #[test]
    fn rejects_unsupported_integer_and_effectively_partial_computations() {
        let source = "source a: int = 1\nsource b: int = 2\nderive equal: bool (a,b) = eq(a,b)\n";
        let graph = Graph::parse(source).unwrap();
        assert!(lower_bool_derived(&graph, graph.id("equal").unwrap()).is_err());
    }
}
