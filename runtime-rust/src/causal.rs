//! Input-dependent causal derivations, not a programmer-controlled loop.
//! The next value depends on the previous value. The terminal predicate
//! is checked first and the successor is evaluated only when necessary.
use crate::{Expr,Result,Type,Value};
pub const MAX_TRANSITIONS:usize=65536;
const MAX_VALUE_ITEMS:usize=65536;
fn bounded(v:&Value)->Result<()>{
    let len=match v{Value::Ints(xs)=>xs.len(),Value::Text(s)|Value::Nat(s)=>s.len(),_=>0};
    if len>MAX_VALUE_ITEMS{return Err("DOC_RECUR: value resource bound".into());}
    Ok(())
}
pub(crate) fn kind(seed:&Expr,done:&Expr,next:&Expr,types:&[Type])->Result<Type>{
    if !matches!(seed,Expr::Arg(_)){return Err("DOC_RECUR: seed must be a named premise".into());}
    let kind=seed.kind(types)?;
    let mut scoped=types.to_vec();scoped.push(kind);
    if done.kind(&scoped)?!=Type::Bool{return Err("DOC_RECUR: terminal predicate must be bool".into());}
    if next.kind(&scoped)?!=kind{return Err("DOC_RECUR: successor type must match seed".into());}
    Ok(kind)
}
pub(crate) fn evaluate(seed:&Expr,done:&Expr,next:&Expr,args:&[Value])->Result<Value>{
    let kind=kind(seed,done,next,&args.iter().map(Value::kind).collect::<Vec<_>>())?;
    let mut current=seed.eval(args)?;
    let mut scoped=args.to_vec();
    for transitions in 0..=MAX_TRANSITIONS{
        bounded(&current)?;
        scoped.push(current);
        match done.eval(&scoped)?{
            Value::Bool(true)=>return Ok(scoped.pop().unwrap()),
            Value::Bool(false)=>{},
            _=>return Err("DOC_RECUR: predicate result type".into()),
        }
        if transitions==MAX_TRANSITIONS{return Err("DOC_RECUR: transition resource bound".into());}
        current=next.eval(&scoped)?;
        scoped.pop();
        if current.kind()!=kind{return Err("DOC_RECUR: successor type mismatch".into());}
    }
    unreachable!("bounded transition loop")
}
