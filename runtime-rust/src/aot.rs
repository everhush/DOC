//! Stage-0 native C lowering from the validated DOC typed graph.
//! Generated derive functions operate on immutable typed values, not opcodes.
use crate::{typed_ir::emit_typed_ir_v1, Expr, Graph, Result, Type, Value};
use std::fmt::Write;
const MAX_STATES:usize=4096;
const MAX_LIST:usize=65536;
fn number(i:i64)->String {
    if i==i64::MIN {"INT64_MIN".into()}
    else if i<0 {format!("(-INT64_C({}))",i.unsigned_abs())}
    else {format!("INT64_C({i})")}
}
fn kind(t:Type)->Result<&'static str>{
    match t {
        Type::Int=>Ok("DOC_INT"),Type::Bool=>Ok("DOC_BOOL"),Type::Ints=>Ok("DOC_LIST"),
        Type::MaybeInt=>Ok("DOC_MAYBE"),
        Type::Text=>Ok("DOC_TEXT"),Type::Nat=>Ok("DOC_NAT"),
    }
}
// Octal escapes preserve UTF-8 bytes and avoid C source injection/escape ambiguity.
fn c_bytes(s:&str)->String{
    format!("\"{}\"",s.bytes().map(|b|format!("\\{b:03o}")).collect::<Vec<_>>().join(""))
}
fn literal(v:&Value)->Result<String>{
    Ok(match v {
        Value::Int(x)=>format!("{{.kind=DOC_INT,.scalar={}}}",number(*x)),
        Value::Bool(b)=>format!("{{.kind=DOC_BOOL,.scalar={}}}",*b as u8),
        Value::MaybeInt(x)=>format!("{{.kind=DOC_MAYBE,.len={},.scalar={}}}",x.is_some() as u8,number(x.unwrap_or(0))),
        Value::Text(s)|Value::Nat(s) if s.len()<=MAX_LIST=>{
            let k=if matches!(v,Value::Text(_)){"DOC_TEXT"}else{"DOC_NAT"};
            format!("{{.kind={k},.len={},.bytes=(const unsigned char*){}}}",s.len(),c_bytes(s))
        },
        Value::Ints(xs) if xs.len()<=MAX_LIST=>{
            if xs.is_empty() {"{.kind=DOC_LIST}".into()}
            else {format!("{{.kind=DOC_LIST,.len={},.data=(const int64_t[]){{{}}}}}",xs.len(),xs.iter().map(|&x|number(x)).collect::<Vec<_>>().join(","))}
        },
        _=>return Err("DOC_AOT_UNSUPPORTED: value type or list resource bound".into()),
    })
}
struct Lower<'a>{out:&'a mut String,premises:&'a [usize],next:usize,bound:Option<&'static str>,scalar_only:bool}
impl Lower<'_>{
    fn temp(&mut self)->String{let n=self.next;self.next+=1;format!("t{n}")}
    fn expression(&mut self,e:&Expr)->Result<String>{
        use Expr::*;
        match e{
            Lit(v)=>{
                // Static local literal storage is valid even when an if branch ends.
                let t=self.temp();
                if let Value::Ints(xs)=v{
                    if xs.len()>MAX_LIST{return Err("DOC_AOT_UNSUPPORTED: list literal resource bound".into());}
                    if xs.is_empty(){writeln!(self.out,"    const doc_value {t}={{.kind=DOC_LIST}};").unwrap();}
                    else{
                        writeln!(self.out,"    static const int64_t {t}_data[] = {{{}}};",xs.iter().map(|&x|number(x)).collect::<Vec<_>>().join(",")).unwrap();
                        writeln!(self.out,"    const doc_value {t}={{.kind=DOC_LIST,.len={},.data={t}_data}};",xs.len()).unwrap();
                    }
                }else{writeln!(self.out,"    const doc_value {t} = {};",literal(v)?).unwrap();}
                Ok(t)
            },
            Arg(i) if self.bound.is_some()&&*i==self.premises.len()=>Ok(self.bound.unwrap().into()),
            Arg(i)=>Ok(format!("v[{}]",self.premises.get(*i).ok_or("invalid AOT premise")?)),
            MapInts(..)|Recur(..)=>Err("DOC_AOT: dynamic computation requires a named derive".into()),
            WordBinary(op,a,b)=>{
                let x=self.expression(a)?;let y=self.expression(b)?;let t=self.temp();
                writeln!(self.out,"    doc_value {t}; if(!doc_word_{}({x},{y},&{t})) goto failed;",op.name()).unwrap();
                Ok(t)
            },
            BitNot(a)=>{
                let x=self.expression(a)?;let t=self.temp();
                writeln!(self.out,"    doc_value {t}=doc_word_bits(~(uint64_t)({x}).scalar);").unwrap();Ok(t)
            },
            Utf8Bytes(a)|Utf8Text(a)=>{
                let x=self.expression(a)?;let t=self.temp();
                let op=if matches!(e,Utf8Bytes(..)){"bytes"}else{"text"};
                writeln!(self.out,"    doc_value {t}; if(!doc_utf8_{op}(&arena,{x},&{t})) goto failed;").unwrap();Ok(t)
            },
            Empty=>Ok("((doc_value){.kind=DOC_LIST})".into()),
            NoInt=>Ok("((doc_value){.kind=DOC_MAYBE})".into()),
            If(c,a,b)=>{
                let cond=self.expression(c)?;let t=self.temp();
                writeln!(self.out,"    doc_value {t}; if (({cond}).scalar) {{").unwrap();
                let x=self.expression(a)?;
                writeln!(self.out,"    {t} = {x}; }} else {{").unwrap();
                let y=self.expression(b)?;
                writeln!(self.out,"    {t} = {y}; }}").unwrap();
                Ok(t)
            },
            Add(a,b)|Sub(a,b)|Mul(a,b)|Eq(a,b)|Lt(a,b)|Le(a,b)
                |Append(a,b)|RemoveAt(a,b)|Get(a,b)|TryGet(a,b)|UnwrapOr(a,b)|Concat(a,b)|StartsWith(a,b)=>{
                let x=self.expression(a)?;let y=self.expression(b)?;let t=self.temp();
                match e{
                    Add(..)|Sub(..)|Mul(..)=>{
                        let op=match e{Add(..)=>"add",Sub(..)=>"sub",_=>"mul"};
                        if self.scalar_only{
                            writeln!(self.out,"    doc_value {t}={{.kind=DOC_INT}}; if (__builtin_{op}_overflow(({x}).scalar, ({y}).scalar, &{t}.scalar)) goto failed;").unwrap();
                        }else{writeln!(self.out,"    doc_value {t}; if (({x}).kind==DOC_NAT) {{ if(!doc_nat_{op}(&arena,{x},{y},&{t})) goto failed; }} else {{ {t}=(doc_value){{.kind=DOC_INT}}; if (__builtin_{op}_overflow(({x}).scalar, ({y}).scalar, &{t}.scalar)) goto failed; }}").unwrap();}
                    },
                    Eq(..)=>writeln!(self.out,"    doc_value {t} = {{.kind=DOC_BOOL,.scalar=doc_equal({x},{y})}};").unwrap(),
                    Lt(..)|Le(..)=>{
                        let op=if matches!(e,Lt(..)){"<"}else{"<="};
                        writeln!(self.out,"    doc_value {t} = {{.kind=DOC_BOOL,.scalar=(doc_order({x},{y}) {op} 0)}};").unwrap();
                    },
                    Concat(..)=>writeln!(self.out,"    doc_value {t}; if(!doc_concat(&arena,{x},{y},&{t})) goto failed;").unwrap(),
                    StartsWith(..)=>writeln!(self.out,"    doc_value {t}={{.kind=DOC_BOOL,.scalar=doc_prefix({x},{y})}};").unwrap(),
                    TryGet(..)=>writeln!(self.out,"    doc_value {t}=doc_try_get({x},{y});").unwrap(),
                    UnwrapOr(..)=>writeln!(self.out,"    doc_value {t}={{.kind=DOC_INT,.scalar=(({x}).len ? ({x}).scalar : ({y}).scalar)}};").unwrap(),
                    _=>{
                        let op=match e{Append(..)=>"append",RemoveAt(..)=>"remove",_=>"get"};
                        writeln!(self.out,"    doc_value {t}; if(!doc_{op}(&arena,{x},{y},&{t})) goto failed;").unwrap();
                    },
                }
                Ok(t)
            },
            SomeInt(a)|Length(a)|Tail(a)=>{
                let x=self.expression(a)?;let t=self.temp();
                match e{
                    SomeInt(..)=>writeln!(self.out,"    doc_value {t}={{.kind=DOC_MAYBE,.len=1,.scalar=({x}).scalar}};").unwrap(),
                    Length(..)=>writeln!(self.out,"    doc_value {t}={{.kind=DOC_INT,.scalar=(int64_t)({x}).len}};").unwrap(),
                    _=>writeln!(self.out,"    doc_value {t}=doc_tail({x});").unwrap(),
                }
                Ok(t)
            },
            ReplaceAt(a,b,c)|Slice(a,b,c)=>{
                let x=self.expression(a)?;let y=self.expression(b)?;let z=self.expression(c)?;let t=self.temp();
                let op=if matches!(e,Slice(..)){"slice"}else{"replace"};
                writeln!(self.out,"    doc_value {t}; if(!doc_{op}(&arena,{x},{y},{z},&{t})) goto failed;").unwrap();
                Ok(t)
            },
        }
    }
}
fn list(values:impl IntoIterator<Item=String>)->String{
    let xs=values.into_iter().collect::<Vec<_>>();
    if xs.is_empty(){"0".into()}else{xs.join(",")}
}
pub fn emit_c(graph:&Graph)->Result<String>{
    emit_c_with_assets(graph,&[])
}
pub fn emit_c_with_assets(graph:&Graph,assets:&[(String,String)])->Result<String>{
    emit_c_options(graph,assets,false)
}
/// Select the terminal-game platform protocol, never a compute placement.
pub fn emit_c_options(graph:&Graph,assets:&[(String,String)],game:bool)->Result<String>{
    let g=Graph::new(graph.states.clone())?;let n=g.states.len();
    if n==0||n>MAX_STATES{return Err("DOC_AOT_UNSUPPORTED: graph size must be 1..4096".into());}
    let _canonical=emit_typed_ir_v1(&g,&[])?;
    let kinds=g.states.iter().map(|s|kind(s.kind)).collect::<Result<Vec<_>>>()?;
    let mut asset_paths=vec!["NULL".to_string();n];
    if assets.len()>64{return Err("DOC_AOT_UNSUPPORTED: asset count".into());}
    for (name,path) in assets{
        let id=g.id(name).ok_or("unknown startup asset source")?;
        if g.states[id].definition.is_some()||asset_paths[id]!="NULL"||!crate::confined::safe_path(path){
            return Err("DOC_AOT: invalid startup asset authority".into());
        }
        asset_paths[id]=c_bytes(path);
    }
    let mut out=String::from("/* DOC-AOT-C/2: specialized typed DAG; no evaluator. */\n#define _GNU_SOURCE\n#include <stdint.h>\n#include <stddef.h>\n#include <inttypes.h>\n#include <stdlib.h>\n#include <stdio.h>\n#include <string.h>\n#include <errno.h>\n#include <ctype.h>\n#include <pthread.h>\n#include <sched.h>\n#include <unistd.h>\n#include <fcntl.h>\n#include <sys/stat.h>\n");
    writeln!(out,"#define DOC_N {n}").unwrap();
    if game{out.push_str("#define DOC_GAME_HOST 1\n#include <time.h>\n#include <math.h>\n#include <sys/resource.h>\n");}
    out.push_str(include_str!("aot_memory.c"));
    out.push_str(include_str!("aot_values.c"));
    out.push_str(include_str!("aot_word.c"));
    out.push_str(include_str!("aot_family.c"));
    let mut level=vec![0usize;n];
    for &id in &g.topo{
        if let Some(d)=&g.states[id].definition{
            level[id]=1+d.premises.iter().map(|&p|level[p]).max().unwrap_or(0);
            if let Expr::MapInts(list,body)=&d.expr{
                let Expr::Arg(input)=list.as_ref()else{return Err("DOC_AOT: invalid family input".into());};
                let source=d.premises.get(*input).ok_or("DOC_AOT: invalid family premise")?;
                writeln!(out,"static int doc_lane_{id}(const doc_value *v,int64_t item,int64_t *out) {{ (void)v; (void)item; doc_arena arena={{0}};").unwrap();
                let mut lower=Lower{out:&mut out,premises:&d.premises,next:0,scalar_only:false,bound:Some("((doc_value){.kind=DOC_INT,.scalar=item})")};
                let value=lower.expression(body)?;
                writeln!(out,"    *out=({value}).scalar; doc_arena_clear(&arena); return 1;\nfailed: doc_arena_clear(&arena); return 0;\n}}").unwrap();
                writeln!(out,"static int doc_f_{id}(const doc_value *v,doc_value *out) {{ return doc_map_ints(v,v[{source}],doc_lane_{id},out); }}").unwrap();
            }else if let Expr::Recur(seed,done,next)=&d.expr{
                let Expr::Arg(input)=seed.as_ref()else{return Err("DOC_AOT: invalid recurrence seed".into());};
                let source=d.premises.get(*input).ok_or("DOC_AOT: invalid recurrence premise")?;
                writeln!(out,"static int doc_f_{id}(const doc_value *v,doc_value *out) {{\n    doc_value state; if(!doc_clone(v[{source}],&state)) return 0;\n    for(size_t transitions=0;;transitions++) {{ doc_arena arena={{0}};").unwrap();
                let mut lower=Lower{out:&mut out,premises:&d.premises,next:0,scalar_only:false,bound:Some("state")};
                let predicate=lower.expression(done)?;
                writeln!(lower.out,"    if (({predicate}).scalar) {{ doc_arena_clear(&arena); *out=state; return 1; }}\n    if(transitions>={}) goto failed;",crate::causal::MAX_TRANSITIONS).unwrap();
                let successor=lower.expression(next)?;
                writeln!(lower.out,"    doc_value successor; if(!doc_clone({successor},&successor)) goto failed;\n    doc_arena_clear(&arena); doc_drop(&state); state=successor; continue;\nfailed: doc_arena_clear(&arena); doc_drop(&state); return 0;\n    }}\n}}").unwrap();
            }else{
                writeln!(out,"static int doc_f_{id}(const doc_value *v,doc_value *out) {{ (void)v; doc_arena arena={{0}};").unwrap();
                let mut lower=Lower{out:&mut out,premises:&d.premises,next:0,scalar_only:false,bound:None};
                let value=lower.expression(&d.expr)?;
                writeln!(out,"    if(!doc_clone({value},out)) goto failed; doc_arena_clear(&arena); return 1;\nfailed: doc_arena_clear(&arena); return 0;\n}}").unwrap();
            }
        }
    }
    writeln!(out,"static const char *const doc_names[DOC_N] = {{{}}};",list(g.states.iter().map(|s|format!("\"{}\"",s.name)))).unwrap();
    writeln!(out,"static const unsigned char doc_source[DOC_N] = {{{}}};",list(g.states.iter().map(|s|(s.definition.is_none() as u8).to_string()))).unwrap();
    writeln!(out,"static const unsigned char doc_kind[DOC_N] = {{{}}};",list(kinds.iter().map(|s|s.to_string()))).unwrap();
    writeln!(out,"static const char *const doc_asset_paths[DOC_N] = {{{}}};",list(asset_paths)).unwrap();
    let initial=g.states.iter().zip(kinds.iter()).map(|(s,k)|s.initial.as_ref().map(literal).unwrap_or(Ok(format!("{{.kind={k}}}")))).collect::<Result<Vec<_>>>()?;
    writeln!(out,"static const doc_value doc_initial[DOC_N] = {{{}}};",list(initial)).unwrap();
    writeln!(out,"typedef int (*doc_fn)(const doc_value*,doc_value*);\nstatic const doc_fn doc_functions[DOC_N] = {{{}}};",list(g.states.iter().enumerate().map(|(i,s)|if s.definition.is_some(){format!("doc_f_{i}")}else{"NULL".into()}))).unwrap();
    let max=level.iter().copied().max().unwrap_or(0);
    let mut ids=Vec::new();let mut offsets=vec![0usize];
    for k in 1..=max{ids.extend((0..n).filter(|&id|level[id]==k));offsets.push(ids.len());}
    writeln!(out,"#define DOC_LEVELS {max}\nstatic const size_t doc_ids[DOC_N] = {{{}}};\nstatic const size_t doc_offsets[DOC_LEVELS+1] = {{{}}};",list(ids.iter().map(ToString::to_string)),list(offsets.iter().map(ToString::to_string))).unwrap();
    out.push_str("static void doc_mark(size_t id,unsigned char *dirty) { (void)dirty; switch(id) {\n");
    for (id,users) in g.users.iter().enumerate(){if !users.is_empty(){write!(out,"case {id}:").unwrap();for u in users{write!(out," dirty[{u}]=1;").unwrap();}out.push_str(" break;\n");}}
    out.push_str("default: break; }}\nstatic void doc_need(size_t target,unsigned char *need) {\n memset(need,0,DOC_N); need[target]=1;\n");
    for &id in g.topo.iter().rev(){if let Some(d)=&g.states[id].definition{if !d.premises.is_empty(){write!(out," if(need[{id}]) {{").unwrap();for p in &d.premises{write!(out," need[{p}]=1;").unwrap();}out.push_str(" }\n");}}}
    out.push_str("}\n");
    out.push_str(include_str!("aot_support.c"));
    if game{out.push_str(include_str!("aot_game.c"));}
    if out.len()>32*1024*1024{return Err("DOC_AOT_UNSUPPORTED: generated C resource bound".into());}
    Ok(out)
}


// Shared typed expression lowering, with an explicitly limited freestanding
// profile: scalar facts only, bounded local storage, no hosted scheduler or
// dynamic allocation. This is a callable ABI foundation, not a full OS target.
fn scalar_expression(e:&Expr)->bool{
    use Expr::*;
    match e{
        Lit(Value::Int(_)|Value::Bool(_))|Arg(_)=>true,
        Add(a,b)|Sub(a,b)|Mul(a,b)|Eq(a,b)|Lt(a,b)|Le(a,b)|WordBinary(_,a,b)=>
            scalar_expression(a)&&scalar_expression(b),
        BitNot(a)=>scalar_expression(a),
        If(c,a,b)=>scalar_expression(c)&&scalar_expression(a)&&scalar_expression(b),
        _=>false,
    }
}
fn abi_identifier(s:&str)->bool{
    let mut b=s.bytes();
    s.len()<=80&&b.next().is_some_and(|x|x.is_ascii_alphabetic()||x==b'_')&&
        b.all(|x|x.is_ascii_alphanumeric()||x==b'_')
}
fn abi_scalar(t:Type)->Result<&'static str>{
    match t{Type::Int=>Ok("int64_t"),Type::Bool=>Ok("uint8_t"),
        _=>Err("DOC_OBJECT_UNSUPPORTED: scalar int/bool ABI only".into())}
}
/// Return generated C and its matching C ABI header. The native caller owns
/// the result region, provides valid aligned storage, and must not access
/// it concurrently during the call. No result writes occur on failed input
/// or calculation. Native callers need not use C as their implementation
/// language: the header describes a platform C calling convention.
pub fn emit_scalar_object(graph:&Graph,symbol:&str)->Result<(String,String)>{
    emit_scalar_object_impl(graph,symbol,None)
}
pub(crate) fn emit_scalar_object_impl(graph:&Graph,symbol:&str,native:Option<&crate::native_abi::NativeProgram>)->Result<(String,String)>{
    if !abi_identifier(symbol){return Err("DOC_OBJECT: invalid export identifier".into());}
    let g=Graph::new(graph.states.clone())?;
    if g.states.is_empty()||g.states.len()>256{return Err("DOC_OBJECT: scalar graph state budget".into());}
    let _canonical=emit_typed_ir_v1(&g,&[])?;
    for s in &g.states{
        abi_scalar(s.kind)?;
        if !abi_identifier(&s.name){return Err("DOC_OBJECT: invalid ABI field identifier".into());}
        if let Some(d)=&s.definition{if !scalar_expression(&d.expr){
            return Err("DOC_OBJECT_UNSUPPORTED: expression requires a hosted or dynamic target".into());
        }}
    }
    let result=format!("doc_result_{symbol}");
    let function=format!("doc_export_{symbol}");
    let guard=format!("DOC_ABI_{symbol}_H");
    let mut header=format!("#ifndef {guard}\n#define {guard}\n#include <stdint.h>\n#include <stddef.h>\n#ifdef __cplusplus\nextern \"C\" {{\n#endif\nstruct {result} {{\n");
    for s in &g.states{
        writeln!(header,"    {} s_{};",abi_scalar(s.kind)?,s.name).unwrap();
    }
    header.push_str("};\n");
    let mut params=g.states.iter().filter(|s|s.definition.is_none())
        .map(|s|Ok(format!("{} in_{}",abi_scalar(s.kind)?,s.name))).collect::<Result<Vec<_>>>()?;
    if let Some(native)=native{native.parameters(&mut params);}
    params.push(format!("struct {result} *out"));
    let signature=format!("int {function}({})",params.join(", "));
    writeln!(header,"{signature};\n#ifdef __cplusplus\n}}\n#endif\n#endif").unwrap();
    let mut c=String::from("/* DOC native scalar object: generated from checked dependency graph. */\n");
    c.push_str(&header);
    c.push_str("enum { DOC_INT, DOC_BOOL }; typedef struct { int kind; int64_t scalar; } doc_value;\n");
    c.push_str("static inline int doc_equal(doc_value a,doc_value b){return a.kind==b.kind&&a.scalar==b.scalar;}\nstatic inline int doc_order(doc_value a,doc_value b){return (a.scalar>b.scalar)-(a.scalar<b.scalar);}\n");
    c.push_str(include_str!("aot_word.c"));
    if let Some(native)=native{native.declarations(&mut c);}
    writeln!(c,"{signature} {{\n    if (!out || (uintptr_t)out%_Alignof(struct {result}) || (uintptr_t)out>UINTPTR_MAX-sizeof(*out)) return 0;\n    doc_value v[{}];",g.states.len()).unwrap();
    // Validate and capture every external source before any native effect,
    // irrespective of the topological ordering of independent graph nodes.
    for (id,s) in g.states.iter().enumerate().filter(|(_,s)|s.definition.is_none()){
        if s.kind==Type::Bool{writeln!(c,"    if (in_{}>1) return 0;",s.name).unwrap();}
        writeln!(c,"    v[{id}]=(doc_value){{.kind={},.scalar=in_{}}};",kind(s.kind)?,s.name).unwrap();
    }
    if let Some(native)=native{native.validate_regions(&mut c);native.declare_owned_handles(&mut c);native.begin_repeat(&mut c);}
    for &id in &g.topo{
        let s=&g.states[id];
        if native.is_some_and(|n|n.emit_call(id,&mut c)){continue;}
        if let Some(d)=&s.definition{
            c.push_str("    {\n");
            let mut lower=Lower{out:&mut c,premises:&d.premises,next:0,bound:None,scalar_only:true};
            let v=lower.expression(&d.expr)?;
            writeln!(c,"    v[{id}]={v};\n    }}").unwrap();
        }
    }
    if let Some(native)=native{native.release_owned_handles(&mut c);native.end_repeat(&mut c);}
    // The output region is external, not part of ordinary DOC-managed
    // memory. Publish only after every checked derive succeeds.
    for (id,s) in g.states.iter().enumerate(){
        writeln!(c,"    out->s_{}=({})v[{id}].scalar;",s.name,abi_scalar(s.kind)?).unwrap();
    }
    c.push_str("    return 1;\nfailed:\n");
    if let Some(native)=native{native.release_owned_handles(&mut c);}
    c.push_str("    return 0;\n}\n");
    Ok((c,header))
}
