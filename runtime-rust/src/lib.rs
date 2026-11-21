//! Executable finite DOC calculus and bounded-value forward recurrence.
//! The finite-core proof excludes recurrence, placement and effects.
pub mod recurrence;
pub mod wgsl;
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
                let mut parser=Parser{tokens:&tokens,pos:0,args:&args,depth:0};
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
#[derive(Debug)]
pub struct Runtime {
    pub graph:Graph,values:Vec<Option<Value>>,active:Vec<bool>,
    pub cutoff:Cutoff,pub workers:usize,pub stats:Stats,pub generation:u64,
    pub source_epoch:u64,
}
impl Runtime {
    pub fn new(graph:Graph,workers:usize,cutoff:Cutoff)->Self{
        let values=graph.states.iter().map(|s|s.initial).collect();
        let active=graph.states.iter().map(|s|s.definition.is_some()).collect();
        Self{graph,values,active,cutoff,workers:workers.max(1),stats:Stats::default(),generation:0,source_epoch:0}
    }
    pub fn value(&self,id:StateId)->Option<Value>{self.values.get(id).copied().flatten()}
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
                    state.initial=Some(self.values[old_id].ok_or("missing source fact")?);
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
        for &(id,v) in changes{
            let s=self.graph.states.get(id).ok_or("unknown state")?;
            if s.definition.is_some(){return Err("cannot update derived state".into());}
            if s.kind!=v.kind(){return Err("source update type mismatch".into());}
            if !ids.insert(id){return Err("duplicate source assignment".into());}
        }
        // One atomic source batch advances exactly one source epoch, not
        // one epoch per updated state. Validate epoch overflow before writes.
        let changed=changes.iter().any(|&(id,v)|
            self.cutoff!=Cutoff::Exact || self.values[id]!=Some(v));
        let next=if changed {
            self.source_epoch.checked_add(1).ok_or("source epoch overflow")?
        }else{self.source_epoch};
        for &(id,v) in changes{
            if self.cutoff==Cutoff::Exact && self.values[id]==Some(v){continue;}
            self.values[id]=Some(v);self.stats.updates+=1;
            for &u in &self.graph.users[id]{self.active[u]=true;}
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
