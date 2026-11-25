//! Lexical, AST-level pure-function specialization. No text replacement,
//! literal corruption, hidden host evaluation, or accidental binder capture.
use crate::{Expr,Result};
pub(crate) const MAX_EXPR_NODES:usize=65536;
pub(crate) const MAX_FORMALS:usize=256;
pub(crate) fn instantiate(e:&Expr,actuals:Option<&[Expr]>,depth:usize,budget:&mut usize)->Result<Expr>{
    if depth>128||*budget==0{return Err("DOC function specialization exceeds expression resource bound".into());}
    *budget-=1;
    use Expr::*;
    fn copy(e:&Expr,a:Option<&[Expr]>,d:usize,b:&mut usize)->Result<Box<Expr>>{
        Ok(Box::new(instantiate(e,a,d+1,b)?))
    }
    let mut binary=|x:&Expr,y:&Expr,op:fn(Box<Expr>,Box<Expr>)->Expr|->Result<Expr>{
        Ok(op(copy(x,actuals,depth,budget)?,copy(y,actuals,depth,budget)?))
    };
    match e{
        Lit(v)=>Ok(Lit(v.clone())),
        Arg(i)=>if let Some(a)=actuals{
            instantiate(a.get(*i).ok_or("DOC function invalid formal index")?,None,depth,budget)
        }else{Ok(Arg(*i))},
        Empty=>Ok(Empty),NoInt=>Ok(NoInt),
        Add(a,b)=>binary(a,b,Add),Sub(a,b)=>binary(a,b,Sub),Mul(a,b)=>binary(a,b,Mul),
        Eq(a,b)=>binary(a,b,Eq),Lt(a,b)=>binary(a,b,Lt),Le(a,b)=>binary(a,b,Le),
        Append(a,b)=>binary(a,b,Append),RemoveAt(a,b)=>binary(a,b,RemoveAt),Get(a,b)=>binary(a,b,Get),
        TryGet(a,b)=>binary(a,b,TryGet),UnwrapOr(a,b)=>binary(a,b,UnwrapOr),
        Concat(a,b)=>binary(a,b,Concat),StartsWith(a,b)=>binary(a,b,StartsWith),
        WordBinary(op,a,b)=>Ok(WordBinary(*op,copy(a,actuals,depth,budget)?,copy(b,actuals,depth,budget)?)),
        SomeInt(a)=>Ok(SomeInt(copy(a,actuals,depth,budget)?)),
        Length(a)=>Ok(Length(copy(a,actuals,depth,budget)?)),
        Tail(a)=>Ok(Tail(copy(a,actuals,depth,budget)?)),
        BitNot(a)=>Ok(BitNot(copy(a,actuals,depth,budget)?)),
        Utf8Bytes(a)=>Ok(Utf8Bytes(copy(a,actuals,depth,budget)?)),
        Utf8Text(a)=>Ok(Utf8Text(copy(a,actuals,depth,budget)?)),
        If(a,b,c)=>Ok(If(copy(a,actuals,depth,budget)?,copy(b,actuals,depth,budget)?,copy(c,actuals,depth,budget)?)),
        ReplaceAt(a,b,c)=>Ok(ReplaceAt(copy(a,actuals,depth,budget)?,copy(b,actuals,depth,budget)?,copy(c,actuals,depth,budget)?)),
        Slice(a,b,c)=>Ok(Slice(copy(a,actuals,depth,budget)?,copy(b,actuals,depth,budget)?,copy(c,actuals,depth,budget)?)),
        MapInts(..)|Recur(..)=>Err("DOC function body may not introduce an unnamed dynamic derive".into()),
    }
}
