//! Canonical textual DOC-TYPED-IR/1 export: the stable #10 -> #11 handoff.
//! This emits fully checked typed graph/effect-free expression structure; it
//! does NOT compile to C or claim a binary ABI. File effects have already
//! been sampled into source facts, never embedded as executable host calls.

use std::collections::HashSet;
use crate::{Expr,Graph,Result,StateId,Type,Value};

const MAX_EXPORT_BYTES:usize=16*1024*1024;
const MAX_EXPR_DEPTH:usize=128;

fn kind(kind:Type)->&'static str {
    match kind{
        Type::Int=>"int",Type::Bool=>"bool",Type::Nat=>"nat",
        Type::Ints=>"ints",Type::MaybeInt=>"maybe_int",Type::Text=>"text",
    }
}
fn hex(bytes:&[u8])->String{
    let mut out=String::with_capacity(bytes.len().saturating_mul(2));
    for byte in bytes{out.push_str(&format!("{byte:02x}"));}
    out
}
fn literal(value:&Value)->String{
    let raw=match value{Value::Text(s)=>s.clone(),other=>other.to_string()};
    format!("{},{}",kind(value.kind()),hex(raw.as_bytes()))
}
fn unary(name:&str,operand:&Expr,depth:usize)->Result<String>{
    Ok(format!("{name}({})",expr(operand,depth+1)?))
}
fn binary(name:&str,left:&Expr,right:&Expr,depth:usize)->Result<String>{
    Ok(format!("{name}({},{})",expr(left,depth+1)?,expr(right,depth+1)?))
}
fn ternary(name:&str,a:&Expr,b:&Expr,c:&Expr,depth:usize)->Result<String>{
    Ok(format!("{name}({},{},{})",expr(a,depth+1)?,
        expr(b,depth+1)?,expr(c,depth+1)?))
}
fn expr(value:&Expr,depth:usize)->Result<String>{
    if depth>MAX_EXPR_DEPTH {return Err("DOC typed IR expression depth exceeded".into());}
    Ok(match value{
        Expr::Lit(v)=>format!("lit({})",literal(v)),
        Expr::Arg(i)=>format!("arg({i})"),
        Expr::Empty=>"empty".into(),
        Expr::NoInt=>"none".into(),
        Expr::SomeInt(x)=>unary("some",x,depth)?,
        Expr::Length(x)=>unary("len",x,depth)?,
        Expr::Tail(x)=>unary("tail",x,depth)?,
        Expr::Add(a,b)=>binary("add",a,b,depth)?,
        Expr::Sub(a,b)=>binary("sub",a,b,depth)?,
        Expr::Mul(a,b)=>binary("mul",a,b,depth)?,
        Expr::Eq(a,b)=>binary("eq",a,b,depth)?,
        Expr::Lt(a,b)=>binary("lt",a,b,depth)?,
        Expr::Le(a,b)=>binary("le",a,b,depth)?,
        Expr::Append(a,b)=>binary("append",a,b,depth)?,
        Expr::RemoveAt(a,b)=>binary("remove_at",a,b,depth)?,
        Expr::Get(a,b)=>binary("get",a,b,depth)?,
        Expr::TryGet(a,b)=>binary("try_get",a,b,depth)?,
        Expr::UnwrapOr(a,b)=>binary("unwrap_or",a,b,depth)?,
        Expr::MapInts(a,b)=>binary("map_ints",a,b,depth)?,
        Expr::Recur(a,b,c)=>ternary("recur",a,b,c,depth)?,
        Expr::WordBinary(op,a,b)=>binary(op.name(),a,b,depth)?,
        Expr::BitNot(a)=>unary("bit_not",a,depth)?,
        Expr::Utf8Bytes(a)=>unary("utf8_bytes",a,depth)?,
        Expr::Utf8Text(a)=>unary("utf8_text",a,depth)?,
        Expr::Concat(a,b)=>binary("concat",a,b,depth)?,
        Expr::StartsWith(a,b)=>binary("starts_with",a,b,depth)?,
        Expr::ReplaceAt(a,b,c)=>ternary("replace_at",a,b,c,depth)?,
        Expr::Slice(a,b,c)=>ternary("slice",a,b,c,depth)?,
        Expr::If(a,b,c)=>ternary("if",a,b,c,depth)?,
    })
}
/// Deterministic, source-order, tab-delimited typed IR. Literal bytes are
/// encoded as lowercase hex; no user bytes can inject a row or delimiter.
/// Row grammar is versioned in docs/DOC-TYPED-IR-V1.md.
pub fn emit_typed_ir_v1(
    graph:&Graph,carry:&[(StateId,StateId)]
)->Result<String>{
    // Public Rust Graph fields may have been mutated: always revalidate.
    let graph=Graph::new(graph.states.clone())?;
    let mut used=HashSet::new();
    for &(source,previous) in carry{
        let s=graph.states.get(source).ok_or("DOC IR unknown carry source")?;
        let p=graph.states.get(previous).ok_or("DOC IR unknown previous state")?;
        if s.definition.is_some() || s.kind!=p.kind || !used.insert(source){
            return Err("DOC IR invalid or duplicate typed carry authority".into());
        }
    }
    let mut out=format!("DOC-TYPED-IR/1\nstates\t{}\n",graph.states.len());
    for (id,s) in graph.states.iter().enumerate(){
        match (&s.initial,&s.definition){
            (Some(v),None)=>{
                out.push_str(&format!("source\t{id}\t{}\t{}\t{}\n",
                    s.name,kind(s.kind),hex(match v {
                        Value::Text(s)=>s.as_bytes().to_vec(),
                        other=>other.to_string().into_bytes(),
                    }.as_slice())));
            },
            (None,Some(d))=>{
                let premises=d.premises.iter().map(|i|i.to_string())
                    .collect::<Vec<_>>().join(",");
                out.push_str(&format!("derive\t{id}\t{}\t{}\t{}\t{}\n",
                    s.name,kind(s.kind),premises,expr(&d.expr,0)?));
            },
            _=>return Err("DOC IR invalid graph state".into()),
        }
        if out.len()>MAX_EXPORT_BYTES{
            return Err("DOC IR output exceeds resource bound".into());
        }
    }
    for &(source,previous) in carry{
        out.push_str(&format!("carry\t{source}\t{previous}\n"));
        if out.len()>MAX_EXPORT_BYTES{
            return Err("DOC IR output exceeds resource bound".into());
        }
    }
    Ok(out)
}
