//! Executable finite DOC calculus. Extensions (recurrence, placement, effects)
//! are deliberately outside this crate's proof and runtime contract.
use std::collections::{HashMap, HashSet, VecDeque};
use std::thread;

pub type StateId = usize;
pub type Result<T> = std::result::Result<T,String>;

#[derive(Clone,Copy,Debug,PartialEq,Eq)]
pub enum Value { Int(i64), Bool(bool) }
#[derive(Clone,Copy,Debug,PartialEq,Eq)]
pub enum Type { Int, Bool }
impl Value {
    pub fn kind(self)->Type { match self {Self::Int(_)=>Type::Int,Self::Bool(_)=>Type::Bool} }
    pub fn parse(s:&str)->Result<Self>{
        match s.trim() {
            "true"=>Ok(Self::Bool(true)), "false"=>Ok(Self::Bool(false)),
            v=>v.parse::<i64>().map(Self::Int).map_err(|_|format!("invalid literal: {v}"))
        }
    }
}
impl Type { pub fn parse(s:&str)->Result<Self>{
    match s.trim() {"int"=>Ok(Self::Int),"bool"=>Ok(Self::Bool),_=>Err(format!("invalid type: {s}"))}
}}
impl std::fmt::Display for Value {
    fn fmt(&self,f:&mut std::fmt::Formatter<'_>)->std::fmt::Result {
        match self {Self::Int(x)=>write!(f,"{x}"),Self::Bool(x)=>write!(f,"{x}")}
    }
}
#[derive(Clone,Debug)]
pub enum Expr {
    Lit(Value),Arg(usize),
    Add(Box<Self>,Box<Self>), Sub(Box<Self>,Box<Self>),
    Mul(Box<Self>,Box<Self>), Eq(Box<Self>,Box<Self>),
    If(Box<Self>,Box<Self>,Box<Self>),
}
impl Expr {
    pub fn kind(&self,args:&[Type])->Result<Type>{
        use Expr::*;
        match self {
            Lit(v)=>Ok(v.kind()),
            Arg(i)=>args.get(*i).copied().ok_or_else(||"missing formal parameter".into()),
            Add(a,b)|Sub(a,b)|Mul(a,b)=>{
                if a.kind(args)?==Type::Int && b.kind(args)?==Type::Int {Ok(Type::Int)}
                else {Err("arithmetic expects integers".into())}
            }
            Eq(a,b)=>{
                if a.kind(args)?==b.kind(args)? {Ok(Type::Bool)}
                else {Err("incompatible equality types".into())}
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
            Lit(v)=>Ok(*v),
            Arg(i)=>args.get(*i).copied().ok_or_else(||"missing parameter".into()),
            Add(a,b)|Sub(a,b)|Mul(a,b)=>{
                let x=match a.eval(args)? {Value::Int(x)=>x,_=>return Err("integer expected".into())};
                let y=match b.eval(args)? {Value::Int(y)=>y,_=>return Err("integer expected".into())};
                let v=match self {
                    Add(_,_)=>x.checked_add(y),
                    Sub(_,_)=>x.checked_sub(y),
                    _=>x.checked_mul(y)
                };
                v.map(Value::Int).ok_or_else(||"integer overflow; no frontier publication".into())
            }
            Eq(a,b)=>Ok(Value::Bool(a.eval(args)?==b.eval(args)?)),
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
    pub fn parse(src:&str)->Result<Self>{
        let mut states=Vec::new();
        let mut names=HashMap::new();
        for (line_no,original) in src.lines().enumerate(){
            let line=original.split('#').next().unwrap_or("").trim();
            if line.is_empty(){continue;}
            let parsed=if let Some(rest)=line.strip_prefix("source "){
                let (header,v)=rest.split_once('=').ok_or("source requires =")?;
                let (name,t)=header.split_once(':').ok_or("source requires type")?;
                let value=Value::parse(v)?;
                if Type::parse(t)?!=value.kind(){return Err("source value type mismatch".into());}
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
                let mut parser=Parser{tokens:&tokens,pos:0,args:&args};
                let expr=parser.expr()?;
                if parser.pos!=tokens.len(){return Err("trailing tokens".into());}
                State::derived(name.trim(),Type::parse(t)?,premises,expr)
            }else{return Err(format!("line {}: expected source or derive",line_no+1));};
            if names.insert(parsed.name.clone(),states.len()).is_some(){
                return Err(format!("duplicate name {}",parsed.name));
            }
            states.push(parsed);
        }
        Self::new(states)
    }
}
fn lex(text:&str)->Result<Vec<String>>{
    let mut tokens=Vec::new();let mut word=String::new();
    for ch in text.chars(){
        if ch.is_ascii_alphanumeric()||ch=='_'||(ch=='-'&&word.is_empty()){
            word.push(ch);
        }else{
            if !word.is_empty(){tokens.push(std::mem::take(&mut word));}
            if "(),".contains(ch){tokens.push(ch.to_string());}
            else if !ch.is_whitespace(){return Err(format!("illegal token {ch}"));}
        }
    }
    if !word.is_empty(){tokens.push(word);}
    Ok(tokens)
}
struct Parser<'a>{tokens:&'a[String],pos:usize,args:&'a HashMap<String,usize>}
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
        let token=self.next()?;
        if self.tokens.get(self.pos).map(String::as_str)==Some("("){
            self.eat("(")?;
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
#[derive(Clone,Copy,Debug,Default,PartialEq,Eq)]
pub struct Stats {
    pub frontiers:u64,pub evaluations:u64,pub publications:u64,
    pub cutoffs:u64,pub updates:u64
}
#[derive(Debug)]
pub struct Runtime {
    pub graph:Graph,values:Vec<Option<Value>>,active:Vec<bool>,
    pub cutoff:Cutoff,pub workers:usize,pub stats:Stats,
}
impl Runtime {
    pub fn new(graph:Graph,workers:usize,cutoff:Cutoff)->Self{
        let values=graph.states.iter().map(|s|s.initial).collect();
        let active=graph.states.iter().map(|s|s.definition.is_some()).collect();
        Self{graph,values,active,cutoff,workers:workers.max(1),stats:Stats::default()}
    }
    pub fn value(&self,id:StateId)->Option<Value>{self.values.get(id).copied().flatten()}
    pub fn snapshot(&self)->Vec<Option<Value>>{self.values.clone()}
    pub fn stable(&self)->bool{!self.active.iter().any(|v|*v)}
    pub fn update(&mut self,changes:&[(StateId,Value)])->Result<()>{
        let mut ids=HashSet::new();
        for &(id,v) in changes{
            let s=self.graph.states.get(id).ok_or("unknown state")?;
            if s.definition.is_some(){return Err("cannot update derived state".into());}
            if s.kind!=v.kind(){return Err("source update type mismatch".into());}
            if !ids.insert(id){return Err("duplicate source assignment".into());}
        }
        for &(id,v) in changes{
            if self.cutoff==Cutoff::Exact && self.values[id]==Some(v){continue;}
            self.values[id]=Some(v);self.stats.updates+=1;
            for &u in &self.graph.users[id]{self.active[u]=true;}
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
        let args:Result<Vec<Value>>=d.premises.iter().map(|p|self.values[*p].ok_or("missing premise".into())).collect();
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
        for &(id,v) in &candidates{
            if self.cutoff==Cutoff::Exact && self.values[id]==Some(v){
                self.stats.cutoffs+=1;
            }else{
                self.values[id]=Some(v);
                self.stats.publications+=1;
                for &u in &self.graph.users[id]{self.active[u]=true;}
            }
        }
        for &(id,_) in &candidates{self.active[id]=false;}
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
        self.values[id].ok_or("missing stable value".into())
    }
    pub fn oracle(&self)->Result<Vec<Value>>{
        let mut vals=vec![None;self.graph.states.len()];
        for &id in &self.graph.topo{
            if let Some(d)=&self.graph.states[id].definition{
                let inputs:Result<Vec<Value>>=d.premises.iter()
                    .map(|p|vals[*p].ok_or("missing oracle premise".into())).collect();
                vals[id]=Some(d.expr.eval(&inputs?)?);
            }else{vals[id]=self.values[id];}
        }
        vals.into_iter().map(|v|v.ok_or("missing oracle result".into())).collect()
    }
}
