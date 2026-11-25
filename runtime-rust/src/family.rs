//! Runtime-sized dependency families. Each lane is an ordinary checked
//! scalar derivation; the parent publishes the ordered collection only
//! after every member of the expanded ready frontier succeeds.
use crate::{Expr,Graph,Runtime,State,StateId,Type,Value,Result};
use std::collections::HashMap;
pub const MAX_FAMILY_LANES:usize=4096;
const MAX_EXPANDED_STATES:usize=65536;

// A family is a top-level derive, not a nested effect or an implicit loop.
// This initial scalar family subset uses the existing typed expression
// semantics and compact actual captures, so the existing GPU admission
// does not accidentally see the input list as a scalar premise.
fn compact(e:&Expr,used:&mut Vec<usize>,types:&[Type])->Result<Expr>{
    use Expr::*;
    let mut binary=|a:&Expr,b:&Expr,op:fn(Box<Expr>,Box<Expr>)->Expr|->Result<Expr>{
        Ok(op(Box::new(compact(a,used,types)?),Box::new(compact(b,used,types)?)))
    };
    match e{
        Lit(v) if matches!(v,Value::Int(_)|Value::Bool(_))=>Ok(Lit(v.clone())),
        Arg(i)=>{
            if !matches!(types.get(*i),Some(Type::Int|Type::Bool)){
                return Err("DOC_FAMILY: body captures must be scalar int/bool".into());
            }
            let local=if let Some(n)=used.iter().position(|x|x==i){n}else{used.push(*i);used.len()-1};
            Ok(Arg(local))
        },
        Add(a,b)=>binary(a,b,Add),Sub(a,b)=>binary(a,b,Sub),Mul(a,b)=>binary(a,b,Mul),
        Eq(a,b)=>binary(a,b,Eq),Lt(a,b)=>binary(a,b,Lt),Le(a,b)=>binary(a,b,Le),
        WordBinary(op,a,b)=>Ok(WordBinary(*op,Box::new(compact(a,used,types)?),Box::new(compact(b,used,types)?))),
        BitNot(a)=>Ok(BitNot(Box::new(compact(a,used,types)?))),
        If(c,a,b)=>Ok(If(Box::new(compact(c,used,types)?),Box::new(compact(a,used,types)?),Box::new(compact(b,used,types)?))),
        _=>Err("DOC_FAMILY: initial map body supports pure int/bool scalar expressions".into())
    }
}
pub(crate) fn prepare(body:&Expr,types:&[Type])->Result<(Expr,Vec<usize>)>{
    let mut scoped=types.to_vec();scoped.push(Type::Int);
    let mut captures=Vec::new();
    let expr=compact(body,&mut captures,&scoped)?;
    if expr.kind(&captures.iter().map(|&i|scoped[i]).collect::<Vec<_>>())?!=Type::Int{
        return Err("DOC_FAMILY: map_ints body must produce int".into());
    }
    Ok((expr,captures))
}
pub(crate) fn kind(list:&Expr,body:&Expr,types:&[Type])->Result<Type>{
    if !matches!(list,Expr::Arg(_))||list.kind(types)?!=Type::Ints{
        return Err("DOC_FAMILY: map_ints requires an ints premise".into());
    }
    prepare(body,types)?;Ok(Type::Ints)
}
pub(crate) fn placement(e:&Expr,root:bool)->Result<()>{
    use Expr::*;
    match e{
        MapInts(a,b)=>{if !root{return Err("DOC_FAMILY: use a separate named derive for each map_ints".into());}
            placement(a,false)?;placement(b,false)},
        Recur(seed,done,next)=>{if !root{return Err("DOC_RECUR: use a separate named derive for causal recurrence".into());}
            placement(seed,false)?;placement(done,false)?;placement(next,false)},
        Lit(_)|Arg(_)|Empty|NoInt=>Ok(()),
        SomeInt(x)|Length(x)|Tail(x)|BitNot(x)|Utf8Bytes(x)|Utf8Text(x)=>placement(x,false),
        Add(a,b)|Sub(a,b)|Mul(a,b)|Eq(a,b)|Lt(a,b)|Le(a,b)|Append(a,b)|RemoveAt(a,b)|Get(a,b)|
        TryGet(a,b)|UnwrapOr(a,b)|Concat(a,b)|StartsWith(a,b)|WordBinary(_,a,b)=>{placement(a,false)?;placement(b,false)},
        ReplaceAt(a,b,c)|Slice(a,b,c)|If(a,b,c)=>{placement(a,false)?;placement(b,false)?;placement(c,false)}
    }
}
fn input(list:&Expr,args:&[Value])->Result<Vec<i64>>{
    let Value::Ints(xs)=list.eval(args)? else{return Err("DOC_FAMILY: ints input required".into())};
    if xs.len()>MAX_FAMILY_LANES{return Err("DOC_FAMILY: runtime lane resource bound exceeded".into());}
    Ok(xs)
}
// Independent sequential oracle; actual Runtime frontiers expand below.
pub(crate) fn evaluate(list:&Expr,body:&Expr,args:&[Value])->Result<Value>{
    let (expr,captures)=prepare(body,&args.iter().map(Value::kind).collect::<Vec<_>>())?;
    let mut output=Vec::new();
    for x in input(list,args)?{
        let lane=captures.iter().map(|&i|if i==args.len(){Value::Int(x)}else{args[i].clone()}).collect::<Vec<_>>();
        let Value::Int(n)=expr.eval(&lane)? else{return Err("DOC_FAMILY: lane result kind".into())};
        output.push(n);
    }Ok(Value::Ints(output))
}
pub(crate) fn has_map(rt:&Runtime,ready:&[StateId])->bool{
    ready.iter().any(|&id|matches!(rt.graph.states[id].definition.as_ref().map(|d|&d.expr),Some(Expr::MapInts(..))))
}
pub(crate) struct Expanded{
    pub graph:Graph,
    outputs:Vec<(StateId,bool,Vec<StateId>)>,
}
fn premise(rt:&Runtime,states:&mut Vec<State>,sources:&mut HashMap<StateId,StateId>,id:StateId)->Result<StateId>{
    if let Some(&local)=sources.get(&id){return Ok(local);}
    let local=states.len();
    states.push(State::source(format!("parent_{id}"),rt.value(id).ok_or("DOC_FAMILY: unsettled premise")?));
    sources.insert(id,local);Ok(local)
}
pub(crate) fn expand(rt:&Runtime,ready:&[StateId])->Result<Expanded>{
    let mut states=Vec::new();let mut sources=HashMap::new();let mut outputs=Vec::new();
    let mut lanes=0usize;
    for &id in ready{
        let state=&rt.graph.states[id];let d=state.definition.as_ref().ok_or("DOC_FAMILY: expected derive")?;
        if let Expr::MapInts(list,body)=&d.expr{
            let types=d.premises.iter().map(|&p|rt.graph.states[p].kind).collect::<Vec<_>>();
            let (expr,captures)=prepare(body,&types)?;
            let args=d.premises.iter().map(|&p|rt.value(p).ok_or_else(||"DOC_FAMILY: unsettled input".to_owned())).collect::<Result<Vec<_>>>()?;
            let xs=input(list,&args)?;
            lanes=lanes.checked_add(xs.len()).ok_or("DOC_FAMILY: lane count overflow")?;
            if lanes>MAX_EXPANDED_STATES/2{return Err("DOC_FAMILY: expanded frontier lane budget".into());}
            let mut captures_local=Vec::new();
            for i in captures{
                captures_local.push(if i==d.premises.len(){None}else{Some(premise(rt,&mut states,&mut sources,d.premises[i])?)});
            }
            let mut ids=Vec::new();
            for (index,x) in xs.into_iter().enumerate(){
                let mut local=Vec::new();
                for capture in &captures_local{
                    let p=if let Some(p)=capture{*p}else{
                        let p=states.len();states.push(State::source(format!("item_{id}_{index}"),Value::Int(x)));p};
                    local.push(p);
                }
                ids.push(states.len());
                states.push(State::derived(format!("lane_{id}_{index}"),Type::Int,local,expr.clone()));
            }
            outputs.push((id,true,ids));
        }else{
            let premises=d.premises.iter().map(|&p|premise(rt,&mut states,&mut sources,p)).collect::<Result<Vec<_>>>()?;
            let local=states.len();states.push(State::derived(format!("derive_{id}"),state.kind,premises,d.expr.clone()));
            outputs.push((id,false,vec![local]));
        }
        if states.len()>MAX_EXPANDED_STATES{return Err("DOC_FAMILY: expanded frontier state budget".into());}
    }
    eprintln!("DOC_FAMILY_EXPANDED: parent_candidates={} lanes={lanes} states={}",ready.len(),states.len());
    Ok(Expanded{graph:Graph::new(states)?,outputs})
}
impl Expanded{
    pub(crate) fn gather(self,child:&Runtime)->Result<Vec<(StateId,Value)>>{
        let mut out=Vec::new();
        for (id,list,local) in self.outputs{
            let value=if list{
                let mut xs=Vec::with_capacity(local.len());
                for lane in local{
                    let Some(Value::Int(n))=child.value(lane)else{return Err("DOC_FAMILY: missing completed lane".into())};
                    xs.push(n);
                }Value::Ints(xs)
            }else{child.value(local[0]).ok_or("DOC_FAMILY: missing completed derive")?};
            out.push((id,value));
        }Ok(out)
    }
}
