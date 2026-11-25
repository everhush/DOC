//! Executable finite DOC calculus and bounded-value forward recurrence.
//! The finite-core proof excludes recurrence, placement and effects.
pub mod recurrence;
pub mod automatic;
pub mod checkpoint;
mod confined;
pub mod resources;
pub mod audio;
pub mod typed_ir;
pub mod aot;
pub mod native_abi;
pub mod wgsl;
pub mod graphics;
pub mod scene3d;
pub mod family;
pub mod causal;
pub mod word;
mod pure_fn;
#[cfg(feature = "webgpu")]
pub mod scene_gpu;
pub mod gpu_abi;
#[cfg(feature = "webgpu")]
pub mod gpu;
#[cfg(feature = "webgpu")]
mod gpu_health;
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
    /// Public host constructors can bypass parsing. Check the value-domain
    /// invariant before admitting a value as a source, literal or resource.
    pub(crate) fn validate(&self)->Result<()> {
        if let Self::Nat(digits)=self {
            if digits.is_empty() || !digits.bytes().all(|b|b.is_ascii_digit())
                || (digits.len()>1 && digits.starts_with('0')) {
                return Err("DOC_VALUE: natural must be canonical decimal".into());
            }
        }
        Ok(())
    }
    pub fn parse_for_type(s:&str,kind:Type)->Result<Self>{
        if kind==Type::Nat {return Ok(Self::Nat(nat::canonical(s.trim())?));}
        if kind==Type::Text {
            let source=s.trim();
            let literal=source.strip_prefix('"').and_then(|s|s.strip_suffix('"'))
                .ok_or("text source requires a quoted UTF-8 value")?;
            if literal.chars().any(|ch|matches!(ch,'\n'|'\r'|'"'|'\\')) {
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
    RemoveAt(Box<Self>,Box<Self>), ReplaceAt(Box<Self>,Box<Self>,Box<Self>),
    Length(Box<Self>), Get(Box<Self>,Box<Self>), Tail(Box<Self>),
    Slice(Box<Self>,Box<Self>,Box<Self>),
    NoInt, SomeInt(Box<Self>), TryGet(Box<Self>,Box<Self>),
    UnwrapOr(Box<Self>,Box<Self>),
    Concat(Box<Self>,Box<Self>), StartsWith(Box<Self>,Box<Self>),
    MapInts(Box<Self>,Box<Self>),
    Recur(Box<Self>,Box<Self>,Box<Self>),
    WordBinary(word::WordOp,Box<Self>,Box<Self>),
    BitNot(Box<Self>), Utf8Bytes(Box<Self>), Utf8Text(Box<Self>),
    If(Box<Self>,Box<Self>,Box<Self>),
}
impl Expr {
    pub fn kind(&self,args:&[Type])->Result<Type>{
        use Expr::*;
        match self {
            Lit(v)=>{v.validate()?;Ok(v.kind())},
            Arg(i)=>args.get(*i).copied().ok_or_else(||"missing formal parameter".into()),
            MapInts(list,body)=>family::kind(list,body,args),
            Recur(seed,done,next)=>causal::kind(seed,done,next,args),
            WordBinary(_,a,b)=>{
                if a.kind(args)?==Type::Int&&b.kind(args)?==Type::Int{Ok(Type::Int)}
                else{Err("DOC_WORD: binary word operands must be int".into())}
            },
            BitNot(a)=>if a.kind(args)?==Type::Int{Ok(Type::Int)}else{Err("DOC_WORD: bit_not requires int".into())},
            Utf8Bytes(a)=>if a.kind(args)?==Type::Text{Ok(Type::Ints)}else{Err("DOC_BYTES: utf8_bytes requires text".into())},
            Utf8Text(a)=>if a.kind(args)?==Type::Ints{Ok(Type::Text)}else{Err("DOC_BYTES: utf8_text requires ints".into())},
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
            RemoveAt(list,index)=>{
                if list.kind(args)?==Type::Ints && index.kind(args)?==Type::Int {
                    Ok(Type::Ints)
                }else{Err("remove_at requires (ints,int)".into())}
            }
            ReplaceAt(list,index,value)=>{
                if list.kind(args)?==Type::Ints && index.kind(args)?==Type::Int
                    && value.kind(args)?==Type::Int {
                    Ok(Type::Ints)
                }else{Err("replace_at requires (ints,int,int)".into())}
            }
            Slice(list,start,count)=>{
                if list.kind(args)?==Type::Ints && start.kind(args)?==Type::Int && count.kind(args)?==Type::Int {
                    Ok(Type::Ints)
                }else{Err("slice requires (ints,int,int)".into())}
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
            Lit(v)=>{v.validate()?;Ok(v.clone())},
            Arg(i)=>{
                let value=args.get(*i).ok_or("missing parameter")?;
                value.validate()?;
                Ok(value.clone())
            },
            MapInts(list,body)=>family::evaluate(list,body,args),
            Recur(seed,done,next)=>causal::evaluate(seed,done,next,args),
            WordBinary(op,a,b)=>match(a.eval(args)?,b.eval(args)?){
                (Value::Int(x),Value::Int(y))=>op.eval(x,y).map(Value::Int),
                _=>Err("DOC_WORD: binary word operands must be int".into()),
            },
            BitNot(a)=>match a.eval(args)?{Value::Int(x)=>Ok(Value::Int(!x)),_=>Err("DOC_WORD: bit_not requires int".into())},
            Utf8Bytes(a)=>word::utf8_bytes(a.eval(args)?),
            Utf8Text(a)=>word::utf8_text(a.eval(args)?),
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
                    if lhs.len().checked_add(rhs.len()).is_none(){
                        return Err("DOC text byte-length overflow".into());
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
            RemoveAt(list,index)=>match (list.eval(args)?,index.eval(args)?) {
                (Value::Ints(mut xs),Value::Int(index))=>{
                    let index=usize::try_from(index)
                        .map_err(|_|"negative collection index")?;
                    if index>=xs.len(){
                        return Err("DOC collection index out of range".into());
                    }
                    xs.remove(index);
                    Ok(Value::Ints(xs))
                }
                _=>Err("remove_at expects ints collection and int index".into())
            },
            ReplaceAt(list,index,value)=>match (list.eval(args)?,index.eval(args)?,value.eval(args)?) {
                (Value::Ints(mut xs),Value::Int(index),Value::Int(value))=>{
                    let index=usize::try_from(index)
                        .map_err(|_|"negative collection index")?;
                    let target=xs.get_mut(index)
                        .ok_or("DOC collection index out of range")?;
                    *target=value;
                    Ok(Value::Ints(xs))
                }
                _=>Err("replace_at expects ints collection, int index and int value".into())
            },
            Slice(list,start,count)=>match (list.eval(args)?,start.eval(args)?,count.eval(args)?) {
                (Value::Ints(xs),Value::Int(start),Value::Int(count))=>{
                    let start=usize::try_from(start).map_err(|_|"DOC slice negative start")?;
                    let count=usize::try_from(count).map_err(|_|"DOC slice negative count")?;
                    let end=start.checked_add(count).ok_or("DOC slice range overflow")?;
                    Ok(Value::Ints(xs.get(start..end).ok_or("DOC slice range out of bounds")?.to_vec()))
                }
                _=>Err("slice expects ints collection, int start and int count".into())
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
// Pure function definitions are lexical typed-expression templates, parsed
// once against earlier declarations and specialized at the call site.
struct UserFn { arity: usize, body: Expr }
fn valid_user_ident(s:&str)->bool {
    let mut bytes=s.bytes();
    matches!(bytes.next(), Some(c) if c.is_ascii_alphabetic() || c==b'_')
        && bytes.all(|c|c.is_ascii_alphanumeric() || c==b'_')
}
fn reserved_user_ident(s:&str)->bool {
    matches!(s,"add"|"sub"|"mul"|"eq"|"if"|"lt"|"le"|"nat"|
        "empty"|"append"|"get"|"len"|"tail"|"remove_at"|"replace_at"|"slice"|
        "none"|"some"|"try_get"|"unwrap_or"|
        "text"|"concat"|"starts_with"|"map_ints"|"recur"|
        "quot"|"rem"|"bit_and"|"bit_or"|"bit_xor"|"bit_not"|"shift_left"|"shift_right"|"utf8_bytes"|"utf8_text"|
        "true"|"false"|"source"|"derive"|"fn")
}
/// Explicit fallible filesystem output after stabilization. Descriptor-relative
/// replacement publishes complete bytes; irreversible effects are not replayed.
pub fn write_doc_output(doc_file:&str,relative:&str,value:&Value)->Result<()> {
    value.validate()?;
    confined::write(doc_file,relative,format!("{value}\n").as_bytes())
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
                (Some(v),None) if v.kind()==s.kind=>{v.validate()?;},
                (None,Some(d))=>{
                    let mut kinds=Vec::new();
                    for &p in &d.premises {
                        let ps=states.get(p).ok_or_else(||format!("invalid premise {p}"))?;
                        kinds.push(ps.kind);users[p].push(id);indegree[id]+=1;
                    }
                    family::placement(&d.expr,true)?;
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
        let source=Self::read_source_file(file)?;
        Self::parse_file_snapshot(file,&source,None)
    }

    /// Read one bounded, regular UTF-8 source snapshot. The host-selected
    /// top-level filename is trusted; child effect paths remain confined.
    pub fn read_source_file(file:&str)->Result<String>{
        confined::read_source(std::path::Path::new(file),1_048_576)
    }

    /// Strict selected-GPU source admission and parsing of the SAME bytes.
    /// Never reopen a checked source or invoke the effectful file frontend.
    pub fn parse_pure_gpu_file(file:&str)->Result<Self>{
        let source=Self::read_source_file(file)?;
        for line in source.lines(){
            if matches!(line.split_whitespace().next(),Some("effect"|"import")){
                return Err("DOC_GPU_UNSUPPORTED: source imports and effects must be rejected before execution".into());
            }
        }
        Self::parse(&source)
    }

    /// AOT frontend: validate and elaborate imports and effect declarations,
    /// without reading startup assets at build time. The placeholders are
    /// typed, not actual source facts; the generated host must replace them
    /// all before initial stabilization.
    pub fn parse_file_deferred(file:&str)->Result<(Self,Vec<(String,String)>)>{
        let source=Self::read_source_file(file)?;
        Self::parse_aot_snapshot(file,&source,false)
    }

    /// Bootstrap driver already inspected this source snapshot for native
    /// declarations. Elaborate the identical bytes, not a second file read.
    pub fn parse_aot_snapshot(file:&str,source:&str,freeze:bool)->Result<(Self,Vec<(String,String)>)>{
        let mut assets=Vec::new();
        let graph=Self::parse_file_snapshot(file,source,if freeze{None}else{Some(&mut assets)})?;
        Ok((graph,assets))
    }

    fn parse_file_snapshot(file:&str,source:&str,mut deferred:Option<&mut Vec<(String,String)>>)->Result<Self>{
        use std::path::Path;
        if source.len()>1_048_576{return Err("DOC source exceeds parse resource bound".into());}
        let base=confined::source_directory(Path::new(file));
        let mut assembled=String::new();
        let mut modules=0usize;
        let mut effects=0usize;
        for original in source.lines(){
            let line=original.split('#').next().unwrap_or("").trim();
            if let Some(path)=line.strip_prefix("import "){
                let path=path.trim();
                if !confined::safe_path(path) || !path.ends_with(".doc"){
                    return Err("DOC module import requires one relative .doc path".into());
                }
                modules+=1;
                if modules>64{return Err("DOC module import limit exceeded".into());}
                let body=confined::read(base,path,65_536)?;
                for declaration in body.lines(){
                    let trimmed=declaration.split('#').next().unwrap_or("").trim();
                    if !trimmed.is_empty() && !trimmed.starts_with("fn "){
                        return Err(format!("DOC module {path} may only declare pure functions"));
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
                if !confined::safe_path(relative) {
                    return Err("DOC effect read requires a confined relative path".into());
                }
                if let Some(assets)=deferred.as_deref_mut(){
                    let placeholder=match kind{
                        Type::Int=>"0",Type::Bool=>"false",Type::Nat=>"0",
                        Type::Ints=>"[]",Type::MaybeInt=>"none",Type::Text=>"\"\"",
                    };
                    assets.push((name.to_owned(),relative.to_owned()));
                    assembled.push_str(&format!("source {name}: {ty} = {placeholder}\n"));
                    if assembled.len()>1_048_576{return Err("DOC file exceeds parse limit".into());}
                    continue;
                }
                let raw=confined::read(base,relative,1_048_576)?;
                let typed=if kind==Type::Text {
                    let data=raw.trim_end_matches(['\r','\n']);
                    if data.chars().any(|ch|matches!(ch,'\r'|'\n'|'"'|'\\')) {
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
        if src.len()>1_048_576{return Err("DOC source exceeds parse resource bound".into());}
        let mut expression_budget=1_048_576usize;
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
                if body.trim().is_empty() || body.len()>65536 {
                    return Err("DOC function body source resource bound".into());
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
                if params.len()>pure_fn::MAX_FORMALS{return Err("DOC function formal resource bound".into());}
                let args=params.iter().enumerate().map(|(i,s)|(s.clone(),i)).collect::<HashMap<_,_>>();
                let tokens=lex(body)?;
                let budget=expression_budget.min(pure_fn::MAX_EXPR_NODES);
                let mut parser=Parser{tokens:&tokens,pos:0,args:&args,functions:&functions,depth:0,remaining:budget,allow_dynamic:false};
                let expr=parser.expr()?;
                if parser.pos!=tokens.len(){return Err("trailing function body tokens".into());}
                expression_budget-=budget-parser.remaining;
                functions.insert(name.to_string(),UserFn{arity:params.len(),body:expr});
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
                let tokens=lex(body)?;
                let budget=expression_budget.min(pure_fn::MAX_EXPR_NODES);
                let mut parser=Parser{tokens:&tokens,pos:0,args:&args,functions:&functions,depth:0,remaining:budget,allow_dynamic:true};
                let expr=parser.expr()?;
                if parser.pos!=tokens.len(){return Err("trailing tokens".into());}
                expression_budget-=budget-parser.remaining;
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
struct Parser<'a>{tokens:&'a[String],pos:usize,args:&'a HashMap<String,usize>,functions:&'a HashMap<String,UserFn>,depth:usize,remaining:usize,allow_dynamic:bool}
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
        if self.remaining==0{return Err("DOC expression node resource bound".into());}
        self.remaining-=1;
        self.depth += 1;
        let result=self.parse_expr_inner();
        self.depth -= 1;
        result
    }
    fn parse_expr_inner(&mut self)->Result<Expr>{
        let token=self.next()?;
        if self.tokens.get(self.pos).map(String::as_str)==Some("("){
            self.eat("(")?;
            let functions=self.functions;
            if let Some(function)=functions.get(&token){
                let mut actuals=Vec::new();
                if self.tokens.get(self.pos).map(String::as_str)!=Some(")"){
                    loop{
                        if actuals.len()>=function.arity{return Err(format!("wrong number of DOC function arguments for {token}"));}
                        actuals.push(self.expr()?);
                        if self.tokens.get(self.pos).map(String::as_str)==Some(")"){break;}
                        self.eat(",")?;
                    }
                }
                self.eat(")")?;
                if actuals.len()!=function.arity{return Err(format!("wrong number of DOC function arguments for {token}"));}
                return pure_fn::instantiate(&function.body,Some(&actuals),self.depth,&mut self.remaining);
            }
            if token=="recur"{
                if !self.allow_dynamic||self.depth!=1{return Err("DOC_RECUR: use a named top-level derive".into());}
                let seed=Box::new(self.expr()?);self.eat(",")?;
                let binder=self.next()?;
                if !valid_user_ident(&binder)||reserved_user_ident(&binder)||self.args.contains_key(&binder){
                    return Err("DOC_RECUR: invalid or shadowing state binder".into());
                }
                self.eat(",")?;
                let mut scoped=self.args.clone();scoped.insert(binder,self.args.len());
                let mut parser=Parser{tokens:self.tokens,pos:self.pos,args:&scoped,functions:self.functions,depth:self.depth,remaining:self.remaining,allow_dynamic:self.allow_dynamic};
                let done=Box::new(parser.expr()?);parser.eat(",")?;
                let next=Box::new(parser.expr()?);self.pos=parser.pos;self.remaining=parser.remaining;self.eat(")")?;
                return Ok(Expr::Recur(seed,done,next));
            }
            if token=="map_ints"{
                if !self.allow_dynamic||self.depth!=1{return Err("DOC_FAMILY: map_ints needs a named top-level derive".into());}
                let input=Box::new(self.expr()?);self.eat(",")?;
                let binder=self.next()?;
                if !valid_user_ident(&binder)||reserved_user_ident(&binder)||self.args.contains_key(&binder){
                    return Err("DOC_FAMILY: invalid or shadowing lane binder".into());
                }
                self.eat(",")?;
                let mut scoped=self.args.clone();scoped.insert(binder,self.args.len());
                let mut parser=Parser{tokens:self.tokens,pos:self.pos,args:&scoped,functions:self.functions,depth:self.depth,remaining:self.remaining,allow_dynamic:self.allow_dynamic};
                let body=Box::new(parser.expr()?);self.pos=parser.pos;self.remaining=parser.remaining;self.eat(")")?;
                return Ok(Expr::MapInts(input,body));
            }
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
            if matches!(token.as_str(),"bit_not"|"utf8_bytes"|"utf8_text"){
                let argument=Box::new(self.expr()?);self.eat(")")?;
                return Ok(match token.as_str(){"bit_not"=>Expr::BitNot(argument),"utf8_bytes"=>Expr::Utf8Bytes(argument),_=>Expr::Utf8Text(argument)});
            }
            if token=="len" || token=="tail"{
                let argument=Box::new(self.expr()?);
                self.eat(")")?;
                return Ok(if token=="len"{Expr::Length(argument)}
                    else{Expr::Tail(argument)});
            }
            if token=="replace_at" || token=="slice" {
                let list=Box::new(self.expr()?);self.eat(",")?;
                let index=Box::new(self.expr()?);self.eat(",")?;
                let value=Box::new(self.expr()?);self.eat(")")?;
                return Ok(if token=="slice"{Expr::Slice(list,index,value)}else{Expr::ReplaceAt(list,index,value)});
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
                    "remove_at"=>Expr::RemoveAt(a,b),
                    "try_get"=>Expr::TryGet(a,b),
                    "unwrap_or"=>Expr::UnwrapOr(a,b),
                    "concat"=>Expr::Concat(a,b),
                    "starts_with"=>Expr::StartsWith(a,b),
                    other=>if let Some(op)=word::WordOp::parse(other){Expr::WordBinary(op,a,b)}else{return Err(format!("unknown operator {token}"))}
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
/// Hardware-aware bounded task grain for ready DOC frontiers. No CPU cap.
pub fn cpu_frontier_workers(requested:usize,hardware:usize,ready:usize)->usize{
    if ready<64 {return 1;}
    requested.max(1).min(hardware.max(1)).min((ready/32).max(1))
}
impl Runtime {
    pub fn new(graph:Graph,workers:usize,cutoff:Cutoff)->Self{
        let values=graph.states.iter().map(|s|s.initial.clone()).collect();
        let active=graph.states.iter().map(|s|s.definition.is_some()).collect();
        let detected=thread::available_parallelism().map_or(1,|n|n.get());
        let requested=if workers==0 {detected} else {workers};
        Self{graph,values,active,cutoff,workers:requested.max(1),stats:Stats::default(),generation:0,source_epoch:0}
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
            v.validate()?;
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
    /// Evaluate a ready CPU subset privately, using the same bounded worker
    /// grain in CPU-only and mixed CPU/GPU frontiers.
    fn eval_many(&self,selected:&[StateId])->Result<Vec<(StateId,Value)>> {
        let hardware=thread::available_parallelism().map_or(1,|n|n.get());
        let count=cpu_frontier_workers(self.workers,hardware,selected.len());
        let candidates:Result<Vec<(StateId,Value)>>=
        if count<2{
            selected.iter().map(|&id|self.eval(id).map(|v|(id,v))).collect()
        }else{
            let chunk=selected.len().div_ceil(count);
            let runtime:&Runtime=self;
            eprintln!("DOC_RUST_PARALLEL_FRONTIER: workers={count} candidates={} hardware={hardware}",selected.len());
            thread::scope(|scope|{
                let mut handles=Vec::new();
                let mut error=None;
                for ids in selected.chunks(chunk){
                    match thread::Builder::new().spawn_scoped(scope,move||ids.iter()
                        .map(|&id|runtime.eval(id).map(|v|(id,v)))
                        .collect::<Result<Vec<_>>>()){
                        Ok(handle)=>handles.push(handle),
                        Err(e)=>{error=Some(format!("DOC worker admission failed: {e}"));break;}
                    }
                }
                let mut results=Vec::new();
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
        Ok(candidates)
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
        let candidates=if family::has_map(self,selected){
            let expanded=family::expand(self,selected)?;
            let mut child=Runtime::new(expanded.graph.clone(),self.workers,self.cutoff);
            child.stabilize()?;
            expanded.gather(&child)?
        }else{self.eval_many(selected)?};
        self.commit_frontier(candidates);
        Ok(())
    }
    /// Commit one validated ready frontier from CPU or jointly completed CPU/GPU candidates.
    /// All effectful/device/CPU candidate errors are checked BEFORE entering this barrier.
    fn commit_frontier(&mut self,candidates:Vec<(StateId,Value)>){
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
    }

    /// Automatically schedule one dependency-ready frontier on CPU workers
    /// and (if proved eligible and available) real WebGPU compute. No authored
    /// placement hints, and no GPU publication before CPU AND GPU succeed.
    pub fn step_automatic(&mut self,scheduler:&mut automatic::AutomaticScheduler)->Result<()>{
        let ready=self.ready();
        if ready.is_empty(){return Err("automatic scheduler has no ready DOC frontier".into());}
        if family::has_map(self,&ready){
            let expanded=family::expand(self,&ready)?;
            let mut child=Runtime::new(expanded.graph.clone(),self.workers,self.cutoff);
            child.stabilize_automatic(scheduler)?;
            let candidates=expanded.gather(&child)?;
            self.commit_frontier(candidates);
            return Ok(());
        }
        #[cfg(feature="webgpu")]
        if let Some(plan)=scheduler.plan(self,&ready)?{
            // Device initialization precedes selection/dispatch commitment.
            // If no usable adapter is present, choose the ordinary CPU path.
            if !scheduler.ensure_gpu(){
                self.step(&ready)?;
                scheduler.cpu_completed(self,ready.len());
                return Ok(());
            }
            let automatic::SelectedGpuFrontier{graph,outputs,cpu}=plan;
            let cpu_count=cpu.len();
            let gpu_count=outputs.len();
            let (cpu_values,gpu_values)=thread::scope(|scope|{
                // CPU and persistent WebGPU execute from the same immutable,
                // dependency-ready values. No partial result can publish.
                let current:&Runtime=&*self;
                let cpu_thread=thread::Builder::new().spawn_scoped(scope,move||current.eval_many(&cpu))
                    .map_err(|e|format!("DOC automatic CPU worker admission failed: {e}"))?;
                let gpu_result=scheduler.run_gpu(&graph);
                let cpu_values=cpu_thread.join()
                    .map_err(|_|"DOC automatic CPU worker panicked")??;
                Ok::<_,String>((cpu_values,gpu_result?))
            })?;
            let mut results=HashMap::<StateId,Value>::new();
            for (id,value) in cpu_values{results.insert(id,value);}
            for (original,local) in outputs{
                let value=gpu_values.get(local).cloned()
                    .ok_or("DOC automatic GPU missing a fully read-back result")?;
                if results.insert(original,value).is_some(){
                    return Err("DOC automatic duplicate frontier candidate".into());
                }
            }
            let candidates:Result<Vec<_>>=ready.iter().map(|id|
                results.remove(id).map(|v|(*id,v))
                    .ok_or_else(||"DOC automatic frontier lost a candidate".into())).collect();
            self.commit_frontier(candidates?);
            let hardware=thread::available_parallelism().map_or(1,|x|x.get());
            let cpu_parallel=cpu_frontier_workers(self.workers,hardware,cpu_count)>1;
            scheduler.mixed_completed(cpu_count,gpu_count,cpu_parallel);
            return Ok(());
        }
        let count=ready.len();
        self.step(&ready)?;
        scheduler.cpu_completed(self,count);
        Ok(())
    }
    pub fn stabilize_automatic(
        &mut self,scheduler:&mut automatic::AutomaticScheduler
    )->Result<()> {
        while !self.stable(){
            self.step_automatic(scheduler)?;
        }
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

#[cfg(test)]
mod scheduler_budget_tests {
    use super::*;
    #[test]
    fn cpu_parallel_budget_tracks_hardware_and_frontier_width() {
        for hardware in [1usize,2,4,8,16,64,128] {
            assert_eq!(cpu_frontier_workers(0,hardware,4096),1);
            assert_eq!(cpu_frontier_workers(usize::MAX,hardware,4096),hardware);
            assert_eq!(cpu_frontier_workers(usize::MAX,hardware,16),1);
            assert_eq!(cpu_frontier_workers(usize::MAX,hardware,64),hardware.min(2));
            assert_eq!(cpu_frontier_workers(usize::MAX,hardware,128),hardware.min(4));
            assert_eq!(cpu_frontier_workers(3,hardware,4096),hardware.min(3));
        }
    }
}
