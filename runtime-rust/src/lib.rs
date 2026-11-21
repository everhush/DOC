//! Executable finite DOC calculus and bounded-value forward recurrence.
//! The finite-core proof excludes recurrence, placement and effects.
pub mod recurrence;
pub mod wgsl;
pub mod nat;
pub mod publication;
use std::collections::{HashMap, HashSet, VecDeque};
use std::thread;

pub type StateId = usize;
pub type Result<T> = std::result::Result<T,String>;

#[derive(Clone,Debug,PartialEq,Eq)]
pub enum Value { Int(i64), Bool(bool), Nat(String), Ints(Vec<i64>),
    MaybeInt(Option<i64>), Text(String) }
#[derive(Clone,Copy,Debug,PartialEq,Eq)]
pub enum Type { Int, Bool, Nat, Ints, MaybeInt, Text }
impl Value {
    pub fn kind(&self)->Type {
        match self {Self::Int(_)=>Type::Int,Self::Bool(_)=>Type::Bool,
            Self::Nat(_)=>Type::Nat,Self::Ints(_)=>Type::Ints,
            Self::MaybeInt(_)=>Type::MaybeInt,Self::Text(_)=>Type::Text}
    }
    pub fn parse_for_type(s:&str,kind:Type)->Result<Self>{
        if kind==Type::Nat {return Ok(Self::Nat(nat::canonical(s.trim())?));}
        if kind==Type::Text {
            let source=s.trim();
            let literal=source.strip_prefix('"').and_then(|s|s.strip_suffix('"'))
                .ok_or("text source requires a quoted UTF-8 value")?;
            if literal.len()>16384 || literal.chars().any(|ch|matches!(ch,'\n'|'\r'|'"'|'\\')) {
                return Err("unsupported text source literal/control sequence".into());
            }
            return Ok(Self::Text(literal.to_string()));
        }
        if kind==Type::MaybeInt {
            let raw=s.trim();
            if raw=="none" {return Ok(Self::MaybeInt(None));}
            let contents=raw.strip_prefix("some(").and_then(|s|s.strip_suffix(')'))
                .ok_or("maybe_int requires none or some(i64)")?;
            return Ok(Self::MaybeInt(Some(contents.trim().parse::<i64>()
                .map_err(|_|"invalid maybe_int payload")?)));
        }
        if kind==Type::Ints {
            let raw=s.trim();
            let body=raw.strip_prefix('[').and_then(|r|r.strip_suffix(']'))
                .ok_or("ints source literal must have [..]")?;
            let mut values=Vec::new();
            if !body.trim().is_empty() {
                for item in body.split(',') {
                    values.push(item.trim().parse::<i64>().map_err(|_|
                        format!("invalid ints item: {item}"))?);
                }
            }
            return Ok(Self::Ints(values));
        }
        let value=Self::parse(s)?;
        if value.kind()!=kind{return Err("source value type mismatch".into());}
        Ok(value)
    }
    pub fn parse(s:&str)->Result<Self>{
        match s.trim() {
            "true"=>Ok(Self::Bool(true)), "false"=>Ok(Self::Bool(false)),
            v=>v.parse::<i64>().map(Self::Int).map_err(|_|format!("invalid literal: {v}"))
        }
    }
}
impl Type { pub fn parse(s:&str)->Result<Self>{
    match s.trim() {"int"=>Ok(Self::Int),"bool"=>Ok(Self::Bool),"nat"=>Ok(Self::Nat),"ints"=>Ok(Self::Ints),"maybe_int"=>Ok(Self::MaybeInt),"text"=>Ok(Self::Text),
        _=>Err(format!("invalid type: {s}"))}
}}
impl std::fmt::Display for Value {
    fn fmt(&self,f:&mut std::fmt::Formatter<'_>)->std::fmt::Result {
        match self {
            Self::Int(x)=>write!(f,"{x}"),Self::Bool(x)=>write!(f,"{x}"),
            Self::Nat(x)=>write!(f,"{x}"),
            Self::Text(value)=>write!(f,"{value}"),
            Self::MaybeInt(None)=>write!(f,"none"),
            Self::MaybeInt(Some(n))=>write!(f,"some({n})"),
            Self::Ints(xs)=>{
                write!(f,"[")?;
                for (idx,x) in xs.iter().enumerate(){
                    if idx>0 {write!(f,",")?;}
                    write!(f,"{x}")?;
                }
                write!(f,"]")
            }
        }
    }
}
#[derive(Clone,Debug)]
pub enum Expr {
    Lit(Value),Arg(usize),
    Add(Box<Self>,Box<Self>), Sub(Box<Self>,Box<Self>),
    Mul(Box<Self>,Box<Self>), Eq(Box<Self>,Box<Self>),
    Lt(Box<Self>,Box<Self>), Le(Box<Self>,Box<Self>),
    Empty, Append(Box<Self>,Box<Self>),
    Length(Box<Self>), Get(Box<Self>,Box<Self>), Tail(Box<Self>),
    NoInt, SomeInt(Box<Self>), TryGet(Box<Self>,Box<Self>),
    UnwrapOr(Box<Self>,Box<Self>),
    Concat(Box<Self>,Box<Self>), StartsWith(Box<Self>,Box<Self>),
    If(Box<Self>,Box<Self>,Box<Self>),
}
impl Expr {
    pub fn kind(&self,args:&[Type])->Result<Type>{
        use Expr::*;
        match self {
            Lit(v)=>Ok(v.kind()),
            Arg(i)=>args.get(*i).copied().ok_or_else(||"missing formal parameter".into()),
            Empty=>Ok(Type::Ints),
            NoInt=>Ok(Type::MaybeInt),
            SomeInt(value)=>{
                if value.kind(args)?==Type::Int {Ok(Type::MaybeInt)}
                else{Err("some requires int".into())}
            }
            TryGet(list,index)=>{
                if list.kind(args)?==Type::Ints && index.kind(args)?==Type::Int{
                    Ok(Type::MaybeInt)
                }else{Err("try_get requires (ints,int)".into())}
            }
            UnwrapOr(value,default)=>{
                if value.kind(args)?==Type::MaybeInt &&
                   default.kind(args)?==Type::Int {Ok(Type::Int)}
                else{Err("unwrap_or requires (maybe_int,int)".into())}
            }
            Append(list,value)=>{
                if list.kind(args)?==Type::Ints && value.kind(args)?==Type::Int {
                    Ok(Type::Ints)
                }else{Err("append requires (ints,int)".into())}
            }
            Get(list,index)=>{
                if list.kind(args)?==Type::Ints && index.kind(args)?==Type::Int{
                    Ok(Type::Int)
                }else{Err("get requires (ints,int)".into())}
            }
            Length(list)=>{
                if list.kind(args)?==Type::Ints || list.kind(args)?==Type::Text {
                    Ok(Type::Int)
                }else{Err("len requires ints or text".into())}
            }
            Concat(a,b)=>{
                if a.kind(args)?==Type::Text && b.kind(args)?==Type::Text{
                    Ok(Type::Text)
                }else{Err("concat requires (text,text)".into())}
            }
            StartsWith(a,b)=>{
                if a.kind(args)?==Type::Text && b.kind(args)?==Type::Text{
                    Ok(Type::Bool)
                }else{Err("starts_with requires (text,text)".into())}
            }
            Tail(list)=>{
                if list.kind(args)?==Type::Ints {Ok(Type::Ints)}
                else{Err("tail requires ints".into())}
            }
            Add(a,b)|Sub(a,b)|Mul(a,b)=>{
                let at=a.kind(args)?;let bt=b.kind(args)?;
                if at==bt && (at==Type::Int || at==Type::Nat){Ok(at)}
                else{Err("arithmetic requires matching int or nat operands".into())}
            }
            Eq(a,b)=>{
                if a.kind(args)?==b.kind(args)? {Ok(Type::Bool)}
                else {Err("incompatible equality types".into())}
            }
            Lt(a,b)|Le(a,b)=>{
                let left=a.kind(args)?;let right=b.kind(args)?;
                if left==right && (left==Type::Int || left==Type::Nat) {
                    Ok(Type::Bool)
                }else{
                    Err("ordering requires identical int or nat operand types".into())
                }
            }
            If(c,a,b)=>{
                if c.kind(args)?!=Type::Bool {return Err("if condition must be bool".into());}
                let t=a.kind(args)?;
                if t==b.kind(args)? {Ok(t)}else{Err("if branch types differ".into())}
            }
        }
    }
    pub fn eval(&self,args:&[Value])->Result<Value>{
        use Expr::*;
        match self {
            Lit(v)=>Ok(v.clone()),
            Arg(i)=>args.get(*i).cloned().ok_or_else(||"missing parameter".into()),
            Empty=>Ok(Value::Ints(Vec::new())),
            NoInt=>Ok(Value::MaybeInt(None)),
            SomeInt(e)=>match e.eval(args)?{
                Value::Int(n)=>Ok(Value::MaybeInt(Some(n))),
                _=>Err("some requires int".into())
            },
            TryGet(list,index)=>match (list.eval(args)?,index.eval(args)?) {
                (Value::Ints(xs),Value::Int(i))=>
                    Ok(Value::MaybeInt(usize::try_from(i).ok()
                        .and_then(|offset|xs.get(offset).copied()))),
                _=>Err("try_get requires ints collection and int index".into())
            },
            UnwrapOr(value,default)=>match(value.eval(args)?,default.eval(args)?) {
                (Value::MaybeInt(Some(n)),Value::Int(_))=>Ok(Value::Int(n)),
                (Value::MaybeInt(None),Value::Int(default))=>Ok(Value::Int(default)),
                _=>Err("unwrap_or requires maybe_int and int".into())
            },
            Append(list,value)=>match (list.eval(args)?,value.eval(args)?) {
                (Value::Ints(mut xs),Value::Int(x))=>{
                    xs.push(x);
                    Ok(Value::Ints(xs))
                }
                _=>Err("append expects ints collection and int value".into())
            },
            Get(list,index)=>match (list.eval(args)?,index.eval(args)?) {
                (Value::Ints(xs),Value::Int(index))=>{
                    let index=usize::try_from(index)
                        .map_err(|_|"negative collection index")?;
                    xs.get(index).copied().map(Value::Int)
                        .ok_or_else(||"DOC collection index out of range".into())
                }
                _=>Err("get expects ints collection and int index".into())
            },
            Length(list)=>match list.eval(args)?{
                Value::Ints(xs)=>Ok(Value::Int(xs.len() as i64)),
                Value::Text(s)=>Ok(Value::Int(s.len() as i64)),
                _=>Err("len expects ints collection or text".into())
            },
            Concat(a,b)=>match (a.eval(args)?,b.eval(args)?) {
                (Value::Text(mut lhs),Value::Text(rhs))=>{
                    if lhs.len().checked_add(rhs.len()).is_none_or(|n|n>16384){
                        return Err("DOC text exceeds 16KiB limit".into());
                    }
                    lhs.push_str(&rhs);
                    Ok(Value::Text(lhs))
                }
                _=>Err("concat requires text inputs".into())
            },
            StartsWith(a,b)=>match (a.eval(args)?,b.eval(args)?) {
                (Value::Text(text),Value::Text(prefix))=>
                    Ok(Value::Bool(text.starts_with(&prefix))),
                _=>Err("starts_with requires text inputs".into())
            },
            Tail(list)=>match list.eval(args)?{
                Value::Ints(xs)=>Ok(Value::Ints(xs.into_iter().skip(1).collect())),
                _=>Err("tail expects ints collection".into())
            },
            Add(a,b)|Sub(a,b)|Mul(a,b)=>{
                match (a.eval(args)?,b.eval(args)?) {
                    (Value::Int(x),Value::Int(y))=>{
                        let v=match self{
                            Add(_,_)=>x.checked_add(y),
                            Sub(_,_)=>x.checked_sub(y),
                            _=>x.checked_mul(y)
                        };
                        v.map(Value::Int).ok_or_else(||
                            "integer overflow; no frontier publication".into())
                    }
                    (Value::Nat(x),Value::Nat(y))=>{
                        let result=match self{
                            Add(_,_)=>nat::add(&x,&y),
                            Sub(_,_)=>nat::sub(&x,&y)?,
                            _=>nat::mul(&x,&y)
                        };
                        Ok(Value::Nat(result))
                    }
                    _=>Err("arithmetic requires matching numeric kinds".into())
                }
            }
            Eq(a,b)=>Ok(Value::Bool(a.eval(args)?==b.eval(args)?)),
            Lt(a,b)|Le(a,b)=>{
                let ordered=match (a.eval(args)?,b.eval(args)?) {
                    (Value::Int(x),Value::Int(y))=>x.cmp(&y),
                    (Value::Nat(x),Value::Nat(y))=>
                        x.len().cmp(&y.len()).then_with(||x.cmp(&y)),
                    _=>return Err("ordering requires identical numeric kinds".into())
                };
                Ok(Value::Bool(ordered==std::cmp::Ordering::Less ||
                    (matches!(self,Le(_, _)) && ordered==std::cmp::Ordering::Equal)))
            }
            If(c,a,b)=>match c.eval(args)? {
                Value::Bool(true)=>a.eval(args),Value::Bool(false)=>b.eval(args),
                _=>Err("bool expected".into())
            }
        }
    }
}
#[derive(Clone,Debug)]
pub struct Definition { pub premises:Vec<StateId>,pub expr:Expr }
#[derive(Clone,Debug)]
pub struct State {
    pub name:String,pub kind:Type,pub initial:Option<Value>,pub definition:Option<Definition>
}
impl State {
    pub fn source(name:impl Into<String>,v:Value)->Self{
        Self{name:name.into(),kind:v.kind(),initial:Some(v),definition:None}
    }
    pub fn derived(name:impl Into<String>,kind:Type,premises:Vec<StateId>,expr:Expr)->Self{
        Self{name:name.into(),kind,initial:None,definition:Some(Definition{premises,expr})}
    }
}
#[derive(Clone,Debug)]
pub struct Graph {
    pub states:Vec<State>,pub users:Vec<Vec<StateId>>,pub topo:Vec<StateId>,
    names:HashMap<String,StateId>,
}
// Bounded, compile-time, hygienic-by-name pure DOC functions. Definitions
// may refer to earlier functions; calls are lowered inside the DOC frontend
// to existing typed Expr nodes, NOT handed to a foreign transpiler/runtime.
// Formal replacement only touches full identifier tokens, never substrings.
#[derive(Clone)]
struct UserFn { params: Vec<String>, body: String }
fn valid_user_ident(s:&str)->bool {
    let mut bytes=s.bytes();
    matches!(bytes.next(), Some(c) if c.is_ascii_alphabetic() || c==b'_')
        && bytes.all(|c|c.is_ascii_alphanumeric() || c==b'_')
}
fn reserved_user_ident(s:&str)->bool {
    matches!(s,"add"|"sub"|"mul"|"eq"|"if"|"lt"|"le"|"nat"|
        "empty"|"append"|"get"|"len"|"tail"|
        "none"|"some"|"try_get"|"unwrap_or"|
        "text"|"concat"|"starts_with"|
        "true"|"false"|"source"|"derive"|"fn")
}
fn replace_function_formals(body:&str,params:&[String],args:&[String])->String {
    let bytes=body.as_bytes();
    let mut out=String::new();
    let mut i=0;
    while i<bytes.len() {
        if bytes[i].is_ascii_alphabetic() || bytes[i]==b'_' {
            let mut j=i+1;
            while j<bytes.len() &&
                (bytes[j].is_ascii_alphanumeric() || bytes[j]==b'_') {j+=1;}
            let name=&body[i..j];
            if let Some(idx)=params.iter().position(|s|s==name) {
                out.push_str(&args[idx]);
            }else{out.push_str(name);}
            i=j;
        } else {
            out.push(bytes[i] as char);i+=1;
        }
    }
    out
}
fn expand_function_calls(input:&str,functions:&HashMap<String,UserFn>,depth:usize)
    ->Result<String>
{
    if depth>32 || input.len()>4096 {
        return Err("DOC function expansion exceeded resource bounds".into());
    }
    if !input.is_ascii(){return Err("DOC function expressions must be ASCII".into());}
    let bytes=input.as_bytes();
    let mut out=String::new();
    let mut i=0;
    while i<bytes.len(){
        if bytes[i].is_ascii_alphabetic() || bytes[i]==b'_'{
            let mut end=i+1;
            while end<bytes.len() &&
                (bytes[end].is_ascii_alphanumeric() || bytes[end]==b'_'){end+=1;}
            let name=&input[i..end];
            let mut open=end;
            while open<bytes.len() && bytes[open].is_ascii_whitespace(){open+=1;}
            if let Some(function)=functions.get(name).filter(|_|open<bytes.len()&&bytes[open]==b'('){
                let mut args=Vec::new();let mut cursor=open+1;let mut start=cursor;let mut nesting=0usize;
                let after_close=loop {
                    if cursor>=bytes.len(){return Err("unterminated DOC function call".into());}
                    match bytes[cursor] {
                        b'('=>nesting+=1,
                        b')' if nesting>0=>nesting-=1,
                        b')'=>{
                            if cursor>start {
                                let argument=input[start..cursor].trim();
                                if argument.is_empty(){return Err("empty DOC function argument".into());}
                                args.push(expand_function_calls(argument,functions,depth+1)?);
                            } else if !args.is_empty(){
                                return Err("empty trailing DOC function argument".into());
                            }
                            break cursor+1;
                        }
                        b',' if nesting==0=>{
                            let argument=input[start..cursor].trim();
                            if argument.is_empty(){return Err("empty DOC function argument".into());}
                            args.push(expand_function_calls(argument,functions,depth+1)?);
                            start=cursor+1;
                        }
                        _=>{}
                    }
                    cursor+=1;
                };
                if args.len()!=function.params.len(){
                    return Err(format!("wrong number of DOC function arguments for {name}"));
                }
                let substituted=replace_function_formals(&function.body,&function.params,&args);
                let expanded=expand_function_calls(&substituted,functions,depth+1)?;
                out.push_str(&expanded);
                i=after_close;
            }else{
                out.push_str(name);i=end;
            }
        }else{
            out.push(bytes[i] as char);i+=1;
        }
        if out.len()>512{return Err("expanded DOC expression exceeds 512 bytes".into());}
    }
    Ok(out)
}

/// Portable lexical DOC path policy: no parent/current traversal, absolute,
/// drive, whitespace, or alternate separator tokens. The Rust file boundary
/// also verifies canonical containment to reject symlink escapes.
fn safe_doc_relative_path(path:&str)->bool{
    !path.is_empty() && path.len()<=256 && path.is_ascii() &&
    path.split('/').all(|component|
        !component.is_empty() && component!="." && component!=".." &&
        component.bytes().all(|b|
            b.is_ascii_alphanumeric() || matches!(b,b'_'|b'-'|b'.')))
}
fn confined_doc_path(base:&std::path::Path,raw:&str)->Result<std::path::PathBuf>{
    if !safe_doc_relative_path(raw) {return Err("DOC path rejected by confinement policy".into());}
    let root=std::fs::canonicalize(base)
        .map_err(|e|format!("DOC source directory unavailable: {e}"))?;
    let file=std::fs::canonicalize(base.join(raw))
        .map_err(|e|format!("DOC input path unavailable: {e}"))?;
    if !file.starts_with(&root){
        return Err("DOC path escapes source directory".into());
    }
    Ok(file)
}
/// Explicit fallible, after-stabilization filesystem output effect.
/// This does NOT roll back externally visible effects and is not a claim of
/// exactly-once delivery. Temp-file + same-directory rename avoids half files.
pub fn write_doc_output(
    doc_file:&str,relative:&str,value:&Value
)->Result<()>{
    use std::{fs,io::Write,path::Path};
    if !safe_doc_relative_path(relative){
        return Err("DOC output path must be a confined relative path".into());
    }
    let base=Path::new(doc_file).parent().unwrap_or(Path::new("."));
    let root=fs::canonicalize(base)
        .map_err(|e|format!("DOC output base unavailable: {e}"))?;
    let requested=base.join(relative);
    let parent=requested.parent().ok_or("DOC output has no directory")?;
    let dir=fs::canonicalize(parent)
        .map_err(|e|format!("DOC output directory unavailable: {e}"))?;
    if !dir.starts_with(&root){return Err("DOC output escapes source directory".into());}
    let name=requested.file_name().ok_or("missing DOC output name")?;
    let output=dir.join(name);
    let temporary=dir.join(format!(
        ".doc-write-{}-{}.tmp",std::process::id(),name.to_string_lossy()
    ));
    let mut file=fs::OpenOptions::new().write(true).create_new(true)
        .open(&temporary).map_err(|e|format!("DOC temporary write: {e}"))?;
    let result=(||->Result<()>{
        write!(file,"{value}\n").map_err(|e|format!("DOC write: {e}"))?;
        file.sync_all().map_err(|e|format!("DOC sync: {e}"))?;
        drop(file);
        fs::rename(&temporary,&output).map_err(|e|format!("DOC rename: {e}"))?;
        Ok(())
    })();
    if result.is_err(){let _=fs::remove_file(&temporary);}
    result
}

impl Graph {
    pub fn new(states:Vec<State>)->Result<Self>{
        let n=states.len();
        let mut names=HashMap::new();
        let mut indegree=vec![0usize;n];
        let mut users=vec![Vec::new();n];
        for (id,s) in states.iter().enumerate(){
            if s.name.is_empty()||!s.name.chars().all(|c|c.is_ascii_alphanumeric()||c=='_'){
                return Err("state names must be nonempty ASCII identifiers".into());
            }
            if names.insert(s.name.clone(),id).is_some(){return Err(format!("duplicate name {}",s.name));}
            match (&s.initial,&s.definition){
                (Some(v),None) if v.kind()==s.kind=>{},
                (None,Some(d))=>{
                    let mut kinds=Vec::new();
                    for &p in &d.premises {
                        let ps=states.get(p).ok_or_else(||format!("invalid premise {p}"))?;
                        kinds.push(ps.kind);users[p].push(id);indegree[id]+=1;
                    }
                    if d.expr.kind(&kinds)?!=s.kind {return Err(format!("wrong result type: {}",s.name));}
                },
                _=>return Err(format!("invalid source/definition: {}",s.name))
            }
        }
        let mut q=VecDeque::new();
        for (i,degree) in indegree.iter().enumerate(){if *degree==0{q.push_back(i);}}
        let mut topo=Vec::new();
        while let Some(id)=q.pop_front(){
            topo.push(id);
            for &u in &users[id]{
                indegree[u]-=1;
                if indegree[u]==0 {q.push_back(u);}
            }
        }
        if topo.len()!=n {return Err("dependency cycle".into());}
        for u in &mut users {u.sort_unstable();u.dedup();}
        Ok(Self{states,users,topo,names})
    }
    pub fn id(&self,name:&str)->Option<StateId>{self.names.get(name).copied()}
    /// Resolve explicit compile-time imports of pure function-only DOC
    /// modules. All modules run through this same native Rust DOC frontend.
    /// Imported files may not contain sources, derivations or further imports:
    /// this prevents hidden effects, source injection and import cycles.
    pub fn parse_file(file:&str)->Result<Self>{
        use std::path::Path;
        let source=std::fs::read_to_string(file)
            .map_err(|e|format!("cannot read DOC file {file}: {e}"))?;
        let base=Path::new(file).parent().unwrap_or(Path::new("."));
        let mut assembled=String::new();
        let mut modules=0usize;
        let mut effects=0usize;
        for original in source.lines(){
            let line=original.split('#').next().unwrap_or("").trim();
            if let Some(path)=line.strip_prefix("import "){
                let path=path.trim();
                if !safe_doc_relative_path(path) || !path.ends_with(".doc"){
                    return Err("DOC module import requires one relative .doc path".into());
                }
                modules+=1;
                if modules>64{return Err("DOC module import limit exceeded".into());}
                let module=confined_doc_path(base,path)?;
                let body=std::fs::read_to_string(&module)
                    .map_err(|e|format!("DOC module {}: {e}",module.display()))?;
                if body.len()>65_536{return Err("DOC module exceeds 64KiB".into());}
                for declaration in body.lines(){
                    let trimmed=declaration.split('#').next().unwrap_or("").trim();
                    if !trimmed.is_empty() && !trimmed.starts_with("fn "){
                        return Err(format!("DOC module {} may only declare pure functions",
                            module.display()));
                    }
                }
                assembled.push_str(&body);
                assembled.push('\n');
            }else if let Some(effect)=line.strip_prefix("effect "){
                // The named read is explicitly effectful; it is sampled once
                // at the program boundary into an immutable DOC source fact.
                // No filesystem operation runs inside a pure ready-frontier.
                effects+=1;
                if effects>64{return Err("DOC effect source limit exceeded".into());}
                let (header,operation)=effect.split_once('=')
                    .ok_or("effect source requires = read(\"path\")")?;
                let (name,ty)=header.split_once(':')
                    .ok_or("effect source requires a declared type")?;
                let name=name.trim();
                let ty=ty.trim();
                let kind=Type::parse(ty)?;
                let operand=operation.trim().strip_prefix("read(")
                    .and_then(|s|s.strip_suffix(')'))
                    .ok_or("effect requires read(\"relative-path\")")?;
                let relative=operand.trim().strip_prefix('"')
                    .and_then(|s|s.strip_suffix('"'))
                    .ok_or("effect read path must be quoted")?;
                if !safe_doc_relative_path(relative) {
                    return Err("DOC effect read requires a confined relative path".into());
                }
                let file_path=confined_doc_path(base,relative)?;
                let raw=std::fs::read_to_string(&file_path)
                    .map_err(|e|format!("DOC read effect {}: {e}",file_path.display()))?;
                if raw.len()>8_192{return Err("DOC read effect exceeds 8KiB".into());}
                let typed=if kind==Type::Text {
                    let data=raw.trim_end_matches(['\r','\n']);
                    if data.len()>16384 || data.chars().any(|ch|matches!(ch,'\r'|'\n'|'"'|'\\')) {
                        return Err("DOC text effect exceeds simple literal contract".into());
                    }
                    Value::Text(data.into())
                }else{Value::parse_for_type(raw.trim(),kind)?};
                let source_text=if kind==Type::Text {
                    format!("source {name}: {ty} = \"{typed}\"\n")
                }else{format!("source {name}: {ty} = {typed}\n")};
                assembled.push_str(&source_text);
            }else{
                assembled.push_str(original);
                assembled.push('\n');
            }
            if assembled.len()>1_048_576{return Err("DOC file exceeds parse limit".into());}
        }
        Self::parse(&assembled)
    }

    pub fn parse(src:&str)->Result<Self>{
        let mut states=Vec::new();
        let mut names=HashMap::new();
        let mut functions:HashMap<String,UserFn>=HashMap::new();
        for (line_no,original) in src.lines().enumerate(){
            let line=original.split('#').next().unwrap_or("").trim();
            if line.is_empty(){continue;}
            if let Some(rest)=line.strip_prefix("fn "){
                let (signature,body)=rest.split_once('=').ok_or("function requires =")?;
                let (name,arguments)=signature.split_once('(')
                    .ok_or("function requires arguments")?;
                let name=name.trim();
                let arguments=arguments.trim().strip_suffix(')')
                    .ok_or("function signature requires )")?;
                if !valid_user_ident(name) || reserved_user_ident(name) ||
                    names.contains_key(name) || functions.contains_key(name) {
                    return Err(format!("invalid or duplicate DOC function: {name}"));
                }
                if body.trim().is_empty() || body.len()>512 {
                    return Err("DOC function body must have 1..=512 bytes".into());
                }
                let mut params=Vec::new();
                if !arguments.trim().is_empty() {
                    for raw in arguments.split(','){
                        let param=raw.trim();
                        if !valid_user_ident(param) || reserved_user_ident(param) ||
                           params.iter().any(|p|p==param) {
                            return Err("invalid or duplicate function formal".into());
                        }
                        params.push(param.to_string());
                    }
                }
                if params.len()>4 {
                    return Err("DOC function arity exceeds four".into());
                }
                let _=lex(body)?;
                functions.insert(name.to_string(),UserFn{params,body:body.trim().into()});
                continue;
            }
            let parsed=if let Some(rest)=line.strip_prefix("source "){
                let (header,v)=rest.split_once('=').ok_or("source requires =")?;
                let (name,t)=header.split_once(':').ok_or("source requires type")?;
                let value=Value::parse_for_type(v,Type::parse(t)?)?;
                State::source(name.trim(),value)
            }else if let Some(rest)=line.strip_prefix("derive "){
                let (header,body)=rest.split_once('=').ok_or("definition requires =")?;
                let (name,signature)=header.split_once(':').ok_or("definition requires type")?;
                let (t,formals)=signature.split_once('(').ok_or("definition requires (premises)")?;
                let formals=formals.trim().strip_suffix(')').ok_or("missing )")?;
                let mut premises=Vec::new();
                let mut args=HashMap::new();
                if !formals.trim().is_empty(){
                    for formal in formals.split(','){
                        let formal=formal.trim();
                        let id=*names.get(formal).ok_or_else(||format!("unknown premise: {formal}"))?;
                        if args.insert(formal.to_string(),premises.len()).is_some(){
                            return Err("duplicate formal parameter".into());
                        }
                        premises.push(id);
                    }
                }
                // Preserve the original finite-core nesting diagnostic for
                // programs not using user functions. Expanded functions have
                // a separate bounded-size policy shared with native Goose.
                let expanded=if functions.is_empty() {
                    body.to_string()
                }else{expand_function_calls(body,&functions,0)?};
                let tokens=lex(&expanded)?;
                let mut parser=Parser{tokens:&tokens,pos:0,args:&args,depth:0};
                let expr=parser.expr()?;
                if parser.pos!=tokens.len(){return Err("trailing tokens".into());}
                State::derived(name.trim(),Type::parse(t)?,premises,expr)
            }else{return Err(format!("line {}: expected source or derive",line_no+1));};
            if functions.contains_key(&parsed.name) ||
               names.insert(parsed.name.clone(),states.len()).is_some(){
                return Err(format!("duplicate name {}",parsed.name));
            }
            states.push(parsed);
        }
        Self::new(states)
    }
}
fn lex(text:&str)->Result<Vec<String>>{
    let mut tokens=Vec::new();
    let mut word=String::new();
    let mut quoted=false;
    for ch in text.chars(){
        if quoted{
            if matches!(ch,'\n'|'\r'|'\\'){
                return Err("DOC literal disallows unescaped controls and backslashes".into());
            }
            word.push(ch);
            if ch=='"'{
                tokens.push(std::mem::take(&mut word));
                quoted=false;
            }
        }else if ch=='"'{
            if !word.is_empty(){tokens.push(std::mem::take(&mut word));}
            word.push('"');
            quoted=true;
        }else if ch.is_ascii_alphanumeric() || ch=='_' ||
                 (ch=='-' && word.is_empty()){
            word.push(ch);
        }else{
            if !word.is_empty(){tokens.push(std::mem::take(&mut word));}
            if "(),".contains(ch){tokens.push(ch.to_string());}
            else if !ch.is_whitespace(){return Err(format!("illegal token {ch}"));}
        }
    }
    if quoted{return Err("unterminated DOC text literal".into());}
    if !word.is_empty(){tokens.push(word);}
    Ok(tokens)
}
struct Parser<'a>{tokens:&'a[String],pos:usize,args:&'a HashMap<String,usize>,depth:usize}
impl Parser<'_>{
    fn next(&mut self)->Result<String>{
        let tok=self.tokens.get(self.pos).cloned().ok_or("unexpected end")?;
        self.pos+=1;Ok(tok)
    }
    fn eat(&mut self,expected:&str)->Result<()>{
        let found=self.next()?;
        if found==expected {Ok(())}else{Err(format!("expected {expected}, found {found}"))}
    }
    fn expr(&mut self)->Result<Expr>{
        // Bound untrusted source nesting before recursive descent can exhaust the host stack.
        if self.depth >= 128 { return Err("expression nesting exceeds 128".into()); }
        self.depth += 1;
        let result=self.parse_expr_inner();
        self.depth -= 1;
        result
    }
    fn parse_expr_inner(&mut self)->Result<Expr>{
        let token=self.next()?;
        if self.tokens.get(self.pos).map(String::as_str)==Some("("){
            self.eat("(")?;
            if token=="nat"{
                let digits=self.next()?;
                self.eat(")")?;
                return Ok(Expr::Lit(Value::Nat(nat::canonical(&digits)?)));
            }
            if token=="text"{
                let literal=self.next()?;
                let value=Value::parse_for_type(&literal,Type::Text)?;
                self.eat(")")?;
                return Ok(Expr::Lit(value));
            }
            if token=="empty" || token=="none" {
                self.eat(")")?;
                return Ok(if token=="empty"{Expr::Empty}else{Expr::NoInt});
            }
            if token=="some" {
                let value=Box::new(self.expr()?);
                self.eat(")")?;
                return Ok(Expr::SomeInt(value));
            }
            if token=="len" || token=="tail"{
                let argument=Box::new(self.expr()?);
                self.eat(")")?;
                return Ok(if token=="len"{Expr::Length(argument)}
                    else{Expr::Tail(argument)});
            }
            let expr=if token=="if"{
                let c=Box::new(self.expr()?);self.eat(",")?;
                let a=Box::new(self.expr()?);self.eat(",")?;
                let b=Box::new(self.expr()?);Expr::If(c,a,b)
            }else{
                let a=Box::new(self.expr()?);self.eat(",")?;
                let b=Box::new(self.expr()?);
                match token.as_str(){
                    "add"=>Expr::Add(a,b),"sub"=>Expr::Sub(a,b),
                    "mul"=>Expr::Mul(a,b),"eq"=>Expr::Eq(a,b),
                    "lt"=>Expr::Lt(a,b),"le"=>Expr::Le(a,b),
                    "append"=>Expr::Append(a,b),"get"=>Expr::Get(a,b),
                    "try_get"=>Expr::TryGet(a,b),
                    "unwrap_or"=>Expr::UnwrapOr(a,b),
                    "concat"=>Expr::Concat(a,b),
                    "starts_with"=>Expr::StartsWith(a,b),
                    _=>return Err(format!("unknown operator {token}"))
                }
            };
            self.eat(")")?;Ok(expr)
        }else if token=="true"||token=="false"||token.parse::<i64>().is_ok(){
            Ok(Expr::Lit(Value::parse(&token)?))
        }else{
            self.args.get(&token).copied().map(Expr::Arg)
                .ok_or_else(||format!("unknown variable {token}"))
        }
    }
}
#[derive(Clone,Copy,Debug,PartialEq,Eq)]
pub enum Cutoff { Exact, Conservative }
/// An external/WebGPU result is admissible only for this exact source episode
/// and immutable graph generation. This token authorizes checking, not a
/// bypass of the ordinary DOC frontier publication rule.
#[derive(Clone,Copy,Debug,PartialEq,Eq)]
pub struct ObservationToken {
    pub graph_generation:u64,
    pub source_epoch:u64,
}
#[derive(Clone,Copy,Debug,Default,PartialEq,Eq)]
pub struct Stats {
    pub frontiers:u64,pub evaluations:u64,pub publications:u64,
    pub cutoffs:u64,pub updates:u64
}
#[derive(Clone,Debug)]
pub struct Runtime {
    pub graph:Graph,values:Vec<Option<Value>>,active:Vec<bool>,
    pub cutoff:Cutoff,pub workers:usize,pub stats:Stats,pub generation:u64,
    pub source_epoch:u64,
}
impl Runtime {
    pub fn new(graph:Graph,workers:usize,cutoff:Cutoff)->Self{
        let values=graph.states.iter().map(|s|s.initial.clone()).collect();
        let active=graph.states.iter().map(|s|s.definition.is_some()).collect();
        Self{graph,values,active,cutoff,workers:workers.max(1),stats:Stats::default(),generation:0,source_epoch:0}
    }
    pub fn value(&self,id:StateId)->Option<Value>{self.values.get(id).cloned().flatten()}
    pub fn snapshot(&self)->Vec<Option<Value>>{self.values.clone()}
    pub fn stable(&self)->bool{!self.active.iter().any(|v|*v)}
    pub fn observation_token(&self)->ObservationToken{
        ObservationToken{graph_generation:self.generation,source_epoch:self.source_epoch}
    }
    /// Reject a device/worker result from an obsolete source or graph
    /// generation before it can participate in any DOC logical publication.
    pub fn validate_observation_token(&self,token:ObservationToken)->Result<()>{
        if token.graph_generation!=self.generation || token.source_epoch!=self.source_epoch{
            Err("stale DOC observation token".into())
        }else{Ok(())}
    }


    /// Conservatively replace a stable immutable graph generation.
    ///
    /// Only source facts with the same name, source role and type are carried.
    /// All derived values are rebuilt under the candidate's definitions; thus
    /// semantic-key equivalence is never guessed. Candidate stabilization is
    /// private, and a failing candidate leaves this generation untouched.
    ///
    /// This finite, owned-runtime operation does not implement asynchronous
    /// reader pinning, graph-version reuse, or distributed generation fences.
    pub fn replace_graph(&mut self,candidate:Graph)->Result<()>{
        if !self.stable(){
            return Err("replace_graph requires a stable current graph".into());
        }
        // A caller can mutate public Graph fields after construction. Revalidate
        // the complete candidate and rebuild its topology before any state carry.
        let mut candidate=Graph::new(candidate.states)?;
        let next=self.generation.checked_add(1).ok_or("graph generation overflow")?;
        let source_next=self.source_epoch.checked_add(1).ok_or("source epoch overflow")?;
        for state in &mut candidate.states {
            if state.definition.is_some(){continue;}
            if let Some(old_id)=self.graph.id(&state.name){
                let old=&self.graph.states[old_id];
                if old.definition.is_none() && old.kind==state.kind {
                    state.initial=Some(self.values[old_id].clone().ok_or("missing source fact")?);
                }
            }
        }
        let mut pending=Runtime::new(candidate,self.workers,self.cutoff);
        pending.stabilize()?;
        self.graph=pending.graph;
        self.values=pending.values;
        self.active=pending.active;
        self.stats=pending.stats;
        self.generation=next;
        self.source_epoch=source_next;
        Ok(())
    }
    /// A stale scheduler token is rejected without inspecting or publishing work.
    pub fn step_for_generation(&mut self,generation:u64,selected:&[StateId])->Result<()>{
        if generation!=self.generation{
            return Err("stale graph generation".into());
        }
        self.step(selected)
    }
    /// Owned scalar snapshots remain valid across later source/graph changes.
    pub fn snapshot_for_generation(&self,generation:u64)->Option<Vec<Option<Value>>>{
        if generation==self.generation{Some(self.snapshot())}else{None}
    }

    pub fn update(&mut self,changes:&[(StateId,Value)])->Result<()>{
        let mut ids=HashSet::new();
        for (id,v) in changes{
            let s=self.graph.states.get(*id).ok_or("unknown state")?;
            if s.definition.is_some(){return Err("cannot update derived state".into());}
            if s.kind!=v.kind(){return Err("source update type mismatch".into());}
            if !ids.insert(*id){return Err("duplicate source assignment".into());}
        }
        // One atomic source batch advances exactly one source epoch, not
        // one epoch per updated state. Validate epoch overflow before writes.
        let changed=changes.iter().any(|(id,v)|
            self.cutoff!=Cutoff::Exact || self.values[*id].as_ref()!=Some(v));
        let next=if changed {
            self.source_epoch.checked_add(1).ok_or("source epoch overflow")?
        }else{self.source_epoch};
        for (id,v) in changes{
            if self.cutoff==Cutoff::Exact && self.values[*id].as_ref()==Some(v){continue;}
            self.values[*id]=Some(v.clone());self.stats.updates+=1;
            for &u in &self.graph.users[*id]{self.active[u]=true;}
        }
        self.source_epoch=next;
        Ok(())
    }
    /// Materialize only the ancestor-closed finite subgraph necessary for
    /// `requested`. Unrelated active definitions remain pending, so even
    /// a failing unrelated computation cannot poison a demanded observation.
    /// The selected tasks are ordinary legal finite DOC frontier subsets.
    pub fn stabilize_requested(&mut self, requested: &[StateId]) -> Result<()> {
        if requested.is_empty() {
            return Err("demand requires at least one requested state".into());
        }
        let mut needed = vec![false; self.graph.states.len()];
        let mut queue = Vec::from(requested);
        while let Some(id) = queue.pop() {
            let state = self.graph.states.get(id).ok_or("invalid demand target")?;
            if needed[id] { continue; }
            needed[id] = true;
            if let Some(definition) = &state.definition {
                queue.extend_from_slice(&definition.premises);
            }
        }
        loop {
            let selected: Vec<_> = self.ready().into_iter()
                .filter(|id| needed[*id])
                .collect();
            if selected.is_empty() { break; }
            self.step(&selected)?;
        }
        if needed.iter().enumerate().any(|(id, selected)|
            *selected && (self.active[id] || self.value(id).is_none())) {
            return Err("demanded subgraph failed to reach stability".into());
        }
        Ok(())
    }

    /// Finds the active antichain of states lacking active strict ancestors.
    pub fn ready(&self)->Vec<StateId>{
        let mut has_active_ancestor=vec![false;self.graph.states.len()];
        let mut out=Vec::new();
        for &id in &self.graph.topo{
            if let Some(d)=&self.graph.states[id].definition{
                let blocked=d.premises.iter().any(|p|has_active_ancestor[*p]||self.active[*p]);
                has_active_ancestor[id]=blocked;
                if self.active[id]&&!blocked{out.push(id);}
            }
        }
        out
    }
    fn eval(&self,id:StateId)->Result<Value>{
        let d=self.graph.states[id].definition.as_ref().ok_or("not derived")?;
        let args:Result<Vec<Value>>=d.premises.iter().map(|p|self.values[*p].clone().ok_or("missing premise".into())).collect();
        d.expr.eval(&args?)
    }
    /// Evaluate selected ready definitions against one settled pre-valuation.
    /// Validation or evaluation errors leave ALL selected states and values intact.
    pub fn step(&mut self,selected:&[StateId])->Result<()>{
        if selected.is_empty(){return Err("empty frontier subset".into());}
        let ready:HashSet<StateId>=self.ready().into_iter().collect();
        let mut seen=HashSet::new();
        for id in selected{
            if !ready.contains(id)||!seen.insert(*id){return Err("illegal frontier subset".into());}
        }
        let candidates:Result<Vec<(StateId,Value)>>=
        if self.workers<2||selected.len()<64{
            selected.iter().map(|&id|self.eval(id).map(|v|(id,v))).collect()
        }else{
            let count=self.workers.min(selected.len());
            let chunk=selected.len().div_ceil(count);
            let runtime:&Runtime=self;
            thread::scope(|scope|{
                let mut handles=Vec::new();
                for ids in selected.chunks(chunk){
                    handles.push(scope.spawn(move||ids.iter()
                        .map(|&id|runtime.eval(id).map(|v|(id,v)))
                        .collect::<Result<Vec<_>>>()));
                }
                let mut results=Vec::new();
                let mut error=None;
                for handle in handles{
                    match handle.join(){
                        Ok(Ok(mut part))=>results.append(&mut part),
                        Ok(Err(e))=>{if error.is_none(){error=Some(e);}},
                        Err(_)=>{if error.is_none(){error=Some("worker panic".into());}}
                    }
                }
                match error {Some(e)=>Err(e),None=>Ok(results)}
            })
        };
        let candidates=candidates?;
        self.stats.frontiers+=1;
        self.stats.evaluations+=candidates.len() as u64;
        // Apply the logical publication barrier only after all candidates succeed.
        for (id,v) in &candidates{
            if self.cutoff==Cutoff::Exact && self.values[*id].as_ref()==Some(v){
                self.stats.cutoffs+=1;
            }else{
                self.values[*id]=Some(v.clone());
                self.stats.publications+=1;
                for &u in &self.graph.users[*id]{self.active[u]=true;}
            }
        }
        for (id,_) in &candidates{self.active[*id]=false;}
        Ok(())
    }
    pub fn stabilize(&mut self)->Result<()>{
        while !self.stable(){
            let front=self.ready();
            if front.is_empty(){return Err("nonempty active set has no frontier".into());}
            self.step(&front)?;
        }
        Ok(())
    }
    pub fn observe(&mut self,id:StateId)->Result<Value>{
        if id>=self.graph.states.len(){return Err("unknown state".into());}
        self.stabilize()?;
        self.values[id].clone().ok_or("missing stable value".into())
    }
    pub fn oracle(&self)->Result<Vec<Value>>{
        let mut vals=vec![None;self.graph.states.len()];
        for &id in &self.graph.topo{
            if let Some(d)=&self.graph.states[id].definition{
                let inputs:Result<Vec<Value>>=d.premises.iter()
                    .map(|p|vals[*p].clone().ok_or("missing oracle premise".into())).collect();
                vals[id]=Some(d.expr.eval(&inputs?)?);
            }else{vals[id]=self.values[id].clone();}
        }
        vals.into_iter().map(|v|v.ok_or("missing oracle result".into())).collect()
    }
}

#[cfg(test)]
mod source_depth_regression {
    use super::Graph;

    #[test]
    fn deeply_nested_untrusted_doc_is_rejected_without_host_stack_overflow() {
        let mut expression = "a".to_string();
        for _ in 0..129 { expression = format!("eq(a,{expression})"); }
        let source = format!("source a: bool = true\nderive chosen: bool (a) = {expression}\n");
        let error = Graph::parse(&source).expect_err("deep source must fail safely");
        assert!(error.contains("nesting"), "unexpected error: {error}");
    }

    #[test]
    fn ordinary_nested_doc_source_still_elaborates() {
        let source = "source a: bool = true\nderive chosen: bool (a) = eq(eq(a,true),true)\n";
        assert!(Graph::parse(source).is_ok());
    }
}
