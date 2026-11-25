//! Native object profile: explicitly authorized, dependency-ordered calls
//! to a target C ABI. The ordinary pure graph never evaluates a native call.
//! Only this module may construct its private graph of typed call placeholders.
use crate::{Graph,Result,Type,StateId,aot,typed_ir::emit_typed_ir_v1};
use std::{collections::{BTreeMap,BTreeSet},fmt::Write};

#[derive(Clone,Copy,Debug,PartialEq,Eq)]
pub(crate) enum Abi{I64,I32,U32,U8,Bool8}
impl Abi{
    fn parse(s:&str)->Result<Self>{match s.trim(){
        "i64"=>Ok(Self::I64),"i32"=>Ok(Self::I32),"u32"=>Ok(Self::U32),
        "u8"=>Ok(Self::U8),"bool8"=>Ok(Self::Bool8),
        _=>Err("DOC_NATIVE: unsupported scalar ABI type".into()),
    }}
    fn name(self)->&'static str{match self{Self::I64=>"i64",Self::I32=>"i32",Self::U32=>"u32",Self::U8=>"u8",Self::Bool8=>"bool8"}}
    fn c(self)->&'static str{match self{Self::I64=>"int64_t",Self::I32=>"int32_t",Self::U32=>"uint32_t",Self::U8|Self::Bool8=>"uint8_t"}}
    fn kind(self)->Type{if matches!(self,Self::Bool8){Type::Bool}else{Type::Int}}
    fn bounds(self)->Option<(&'static str,&'static str)>{match self{
        Self::I64=>None,Self::I32=>Some(("INT32_MIN","INT32_MAX")),
        Self::U32=>Some(("0","UINT32_MAX")),Self::U8=>Some(("0","UINT8_MAX")),
        Self::Bool8=>Some(("0","1")),
    }}
}
// Buffer parameters expand into a target pointer + size_t pair. They are
// never scalar values and cannot be returned or placed in a DOC graph.
#[derive(Clone,Copy,Debug,PartialEq,Eq)]
enum Param{Scalar(Abi),Bytes,ConstBytes}
impl Param{
    fn parse(s:&str)->Result<Self>{match s.trim(){
        "bytes"=>Ok(Self::Bytes),"const_bytes"=>Ok(Self::ConstBytes),
        other=>Ok(Self::Scalar(Abi::parse(other)?)),
    }}
    fn name(self)->&'static str{match self{Self::Scalar(a)=>a.name(),Self::Bytes=>"bytes",Self::ConstBytes=>"const_bytes"}}
    fn c(self)->&'static str{match self{Self::Scalar(a)=>a.c(),Self::Bytes=>"uint8_t *, size_t",Self::ConstBytes=>"const uint8_t *, size_t"}}
    fn source_arity(self)->usize{match self{Self::Scalar(_)=>1,_=>3}}
    fn abi_arity(self)->usize{match self{Self::Scalar(_)=>1,_=>2}}
}
#[derive(Debug)]
struct Import{symbol:String,args:Vec<Param>,result:Abi}

#[derive(Clone,Debug,PartialEq,Eq)]
enum IntrinsicOp{Popcount,LeadingZeros,TrailingZeros,External(String)}
impl IntrinsicOp{
    fn parse(s:&str)->Result<Self>{
        let text=s.trim();
        if let Some(intrinsic_symbol)=text.strip_prefix("external(").and_then(|v|v.strip_suffix(')')){
            if !symbol(intrinsic_symbol){return Err("DOC_NATIVE: invalid external intrinsic symbol".into());}
            return Ok(Self::External(intrinsic_symbol.to_owned()));
        }
        match text{
        "popcount"=>Ok(Self::Popcount),
        "leading_zeros"=>Ok(Self::LeadingZeros),
        "trailing_zeros"=>Ok(Self::TrailingZeros),
        _=>Err("DOC_NATIVE: unsupported target intrinsic".into()),
    }}
    fn name(&self)->&'static str{match self{
        Self::Popcount=>"popcount",Self::LeadingZeros=>"leading_zeros",
        Self::TrailingZeros=>"trailing_zeros",Self::External(_)=>"external",
    }}
    fn descriptor(&self)->String{match self{
        Self::External(symbol)=>format!("external({symbol})"),
        other=>other.name().into(),
    }}
    fn c_expr(&self,value:&str)->String{match self{
        Self::Popcount=>format!("(int64_t)__builtin_popcountll((unsigned long long)(uint64_t)({value}))"),
        Self::LeadingZeros=>format!("((uint64_t)({value})==0 ? INT64_C(64) : (int64_t)__builtin_clzll((unsigned long long)(uint64_t)({value})))"),
        Self::TrailingZeros=>format!("((uint64_t)({value})==0 ? INT64_C(64) : (int64_t)__builtin_ctzll((unsigned long long)(uint64_t)({value})))"),
        Self::External(_)=>unreachable!("external intrinsic uses typed ABI emission"),
    }}
}
#[derive(Debug)]
struct Intrinsic{name:String,args:Vec<Param>,result:Abi,op:IntrinsicOp}
#[derive(Clone,Copy,Debug)]
enum Target{Import(usize),Intrinsic(usize)}
#[derive(Clone,Copy,Debug,PartialEq,Eq)]
enum Access{Plain,Volatile,Atomic}
impl Access{
    fn parse(s:&str)->Result<Self>{match s{
        "plain"=>Ok(Self::Plain),"volatile"=>Ok(Self::Volatile),"atomic"=>Ok(Self::Atomic),
        _=>Err("DOC_NATIVE: region access must be plain, volatile or atomic".into()),
    }}
    fn name(self)->&'static str{match self{Self::Plain=>"plain",Self::Volatile=>"volatile",Self::Atomic=>"atomic"}}
}
#[derive(Debug)]
struct Region{name:String,abi:Abi,access:Access}
impl Region{
    fn c(&self)->String{match self.access{
        Access::Plain=>self.abi.c().into(),Access::Volatile=>format!("volatile {}",self.abi.c()),
        Access::Atomic=>format!("_Atomic({})",self.abi.c()),
    }}
}
#[derive(Clone,Copy,Debug,PartialEq,Eq)]
enum Op{Load,Store,FetchAdd,Fence,Extent}
impl Op{
    fn name(self)->&'static str{match self{Self::Load=>"load",Self::Store=>"store",Self::FetchAdd=>"fetch_add",Self::Fence=>"fence",Self::Extent=>"extent"}}
}
#[derive(Debug)]
struct RawRegionOp{op:Op,call:RawCall}
#[derive(Debug)]
struct RegionOp{op:Op,region:Option<usize>,args:Vec<StateId>}
#[derive(Debug)]
struct RawCall{name:String,symbol:String,args:Vec<String>,condition:Option<(String,String)>}
#[derive(Clone,Copy,Debug)]
enum Argument{Scalar(StateId),Buffer{region:usize,offset:StateId,count:StateId}}
impl Argument{
    fn ir(self)->String{match self{Self::Scalar(id)=>id.to_string(),Self::Buffer{region,offset,count}=>format!("r:{region}:{offset}:{count}")}}
}
#[derive(Debug)]
struct Call{target:Target,args:Vec<Argument>,condition:Option<(StateId,StateId)>}
#[derive(Debug)]
struct Repeat{halt:StateId,carries:Vec<(StateId,StateId)>}
#[derive(Debug)]
pub struct NativeProgram{repeat:Option<Repeat>,graph:Graph,cleanups:BTreeMap<StateId,String>,imports:Vec<Import>,intrinsics:Vec<Intrinsic>,calls:BTreeMap<StateId,Call>,regions:Vec<Region>,operations:BTreeMap<StateId,RegionOp>}
fn ident(s:&str)->bool{
    let mut b=s.bytes();
    s.len()<=80&&b.next().is_some_and(|x|x.is_ascii_alphabetic()||x==b'_')&&
        b.all(|x|x.is_ascii_alphanumeric()||x==b'_')
}
fn symbol(s:&str)->bool{ident(s)&&!s.starts_with("doc_")&&!s.starts_with("__")}
fn fields(s:&str)->Vec<&str>{
    if s.trim().is_empty(){vec![]}else{s.split(',').map(str::trim).collect()}
}
fn signature(s:&str)->Result<(&str,&str)>{
    let (name,args)=s.split_once('(').ok_or("DOC_NATIVE: expected signature")?;
    let name=name.trim();
    let args=args.trim().strip_suffix(')').ok_or("DOC_NATIVE: expected closing parenthesis")?;
    if !ident(name){return Err("DOC_NATIVE: invalid identifier".into());}
    Ok((name,args))
}
pub fn has_native_declarations(source:&str)->bool{
    source.lines().any(|line|line.split('#').next().unwrap_or("").trim().starts_with("native "))
}
fn depends(g:&Graph,node:StateId,ancestor:StateId)->bool{
    let mut seen=BTreeSet::new();let mut stack=vec![node];
    while let Some(id)=stack.pop(){
        if !seen.insert(id){continue;}
        if let Some(d)=&g.states[id].definition{
            if d.premises.contains(&ancestor){return true;}
            stack.extend(d.premises.iter().copied());
        }
    }false
}
impl NativeProgram{
    /// The authority list is supplied by the trusted build caller, not the
    /// source. Each signature is a trusted declaration about the linked
    /// library. This is not a sandbox for foreign machine code.
    pub fn parse(source:&str,grants:&[String])->Result<Self>{Self::parse_with_regions(source,grants,&[])}
    pub fn parse_with_regions(source:&str,grants:&[String],region_grants:&[String])->Result<Self>{
        Self::parse_with_authority(source,grants,region_grants,&[])
    }
    /// External target intrinsics require a distinct grant category. An
    /// import or destructor grant cannot authorize an intrinsic or vice versa.
    pub fn parse_with_authority(source:&str,grants:&[String],region_grants:&[String],intrinsic_grants:&[String])->Result<Self>{
        if source.len()>1_048_576{return Err("DOC_NATIVE: source resource bound".into());}
        let granted=grants.iter().map(String::as_str).collect::<BTreeSet<_>>();
        if grants.len()!=granted.len()||grants.len()>64||granted.iter().any(|s|!symbol(s)){
            return Err("DOC_NATIVE: invalid or duplicate symbol grant".into());
        }
        let granted_intrinsics=intrinsic_grants.iter().map(String::as_str).collect::<BTreeSet<_>>();
        if intrinsic_grants.len()!=granted_intrinsics.len()||
            grants.len().saturating_add(intrinsic_grants.len())>64||
            granted_intrinsics.iter().any(|s|!symbol(s)||granted.contains(s)){
            return Err("DOC_NATIVE: invalid, duplicate or overlapping intrinsic grant".into());
        }
        let granted_regions=region_grants.iter().map(String::as_str).collect::<BTreeSet<_>>();
        if region_grants.len()!=granted_regions.len()||region_grants.len()>16||granted_regions.iter().any(|s|!ident(s)){
            return Err("DOC_NATIVE: invalid or duplicate region grant".into());
        }
        let mut imports=Vec::new();let mut lookup=BTreeMap::new();
        let mut intrinsics=Vec::new();let mut intrinsic_lookup=BTreeMap::new();
        let mut regions=Vec::new();let mut region_lookup=BTreeMap::new();let mut raw_regions=Vec::new();
        let mut scoped = BTreeMap::new();
        let mut cleanup_symbols = BTreeSet::new();
        let mut external_intrinsic_symbols = BTreeSet::new();
        let mut raw=Vec::new();let mut pure=String::new();
        let mut raw_repeat:Option<(String,Vec<(String,String)>)>=None;
        for original in source.lines(){
            let line=original.split('#').next().unwrap_or("").trim();
            if let Some(rest)=line.strip_prefix("native repeat until "){
                if raw_repeat.is_some(){return Err("DOC_NATIVE: duplicate repeat declaration".into());}
                let (halt,assignments)=rest.split_once(" carry ").ok_or("DOC_NATIVE: repeat requires carry")?;
                let halt=halt.trim();
                if !ident(halt){return Err("DOC_NATIVE: repeat requires named halt state".into());}
                let mut carries=Vec::new();let mut destinations=BTreeSet::new();
                for assignment in fields(assignments){
                    let (destination,value)=assignment.split_once('=').ok_or("DOC_NATIVE: repeat carry requires source=derive")?;
                    let (destination,value)=(destination.trim(),value.trim());
                    if !ident(destination)||!ident(value)||!destinations.insert(destination){
                        return Err("DOC_NATIVE: invalid or duplicate repeat carry".into());
                    }
                    carries.push((destination.to_owned(),value.to_owned()));
                }
                if carries.is_empty()||carries.len()>256{return Err("DOC_NATIVE: repeat carry resource bound".into());}
                raw_repeat=Some((halt.to_owned(),carries));
            }else if let Some(rest)=line.strip_prefix("native intrinsic "){
                let (head,builtin)=rest.split_once('=').ok_or("DOC_NATIVE: intrinsic needs =")?;
                let (head,result)=head.rsplit_once("->").ok_or("DOC_NATIVE: intrinsic needs result type")?;
                let (name,args)=signature(head.trim())?;
                if !symbol(name)||lookup.contains_key(name)||intrinsic_lookup.contains_key(name){
                    return Err("DOC_NATIVE: invalid or duplicate intrinsic".into());
                }
                let args=fields(args).into_iter().map(Param::parse).collect::<Result<Vec<_>>>()?;
                if args.iter().map(|a|a.abi_arity()).sum::<usize>()>32{return Err("DOC_NATIVE: argument resource bound".into());}
                let result=Abi::parse(result)?;
                let op=IntrinsicOp::parse(builtin)?;
                if let IntrinsicOp::External(symbol)=&op {
                    if !granted_intrinsics.contains(symbol.as_str())||lookup.contains_key(symbol)||
                        cleanup_symbols.contains(symbol)||!external_intrinsic_symbols.insert(symbol.clone()){
                        return Err(format!("DOC_NATIVE: ungranted or duplicate external intrinsic {symbol}"));
                    }
                }else if args!=vec![Param::Scalar(Abi::I64)]||result!=Abi::I64{
                    return Err("DOC_NATIVE: builtin intrinsic ABI must be (i64) -> i64".into());
                }
                let index=intrinsics.len();
                intrinsic_lookup.insert(name.to_owned(),index);
                intrinsics.push(Intrinsic{name:name.into(),args,result,op});
            }else if let Some(rest)=line.strip_prefix("native import "){
                let (head,result)=rest.split_once("->").ok_or("DOC_NATIVE: import needs result type")?;
                let (name,args)=signature(head.trim())?;
                if !symbol(name)||!granted.contains(name){return Err(format!("DOC_NATIVE: ungranted symbol {name}"));}
                if external_intrinsic_symbols.contains(name){return Err("DOC_NATIVE: duplicate native authority symbol".into());}
                if lookup.contains_key(name)||intrinsic_lookup.contains_key(name)||lookup.insert(name.to_owned(),imports.len()).is_some(){return Err("DOC_NATIVE: duplicate import".into());}
                let args=fields(args).into_iter().map(Param::parse).collect::<Result<Vec<_>>>()?;
                if args.iter().map(|a|a.abi_arity()).sum::<usize>()>32{return Err("DOC_NATIVE: argument resource bound".into());}
                imports.push(Import{symbol:name.into(),args,result:Abi::parse(result)?});
            }else if let Some(rest) = line.strip_prefix("native cleanup ") {
                let (state, destructor) = rest.split_once('=').ok_or("DOC_NATIVE: expected cleanup state = destructor")?;
                let (state, destructor) = (state.trim(), destructor.trim());
                if !ident(state) || !granted.contains(destructor) {
                    return Err("DOC_NATIVE: invalid cleanup state or ungranted destructor".into());
                }
                if scoped.insert(state.to_owned(), destructor.to_owned()).is_some() {
                    return Err("DOC_NATIVE: duplicate cleanup for acquisition".into());
                }
                cleanup_symbols.insert(destructor.to_owned());
            }else if let Some(rest)=line.strip_prefix("native region "){
                let (name,spec)=rest.split_once(':').ok_or("DOC_NATIVE: region needs ABI and access type")?;
                let name=name.trim();let spec=spec.split_whitespace().collect::<Vec<_>>();
                if !ident(name)||!granted_regions.contains(name)||spec.len()!=2{
                    return Err("DOC_NATIVE: ungranted or malformed region".into());
                }
                let abi=Abi::parse(spec[0])?;let access=Access::parse(spec[1])?;
                if matches!(abi,Abi::Bool8)||access==Access::Atomic&&!matches!(abi,Abi::U32){
                    return Err("DOC_NATIVE: atomic regions require u32; bool8 memory unsupported".into());
                }
                if region_lookup.insert(name.to_owned(),regions.len()).is_some(){return Err("DOC_NATIVE: duplicate region".into());}
                regions.push(Region{name:name.into(),abi,access});
            }else if let Some(rest)=line.strip_prefix("native call "){
                let (header,body)=rest.split_once('=').ok_or("DOC_NATIVE: call needs =")?;
                let (name,typed)=header.split_once(':').ok_or("DOC_NATIVE: call needs result type")?;
                let name=name.trim();
                let (kind,premises)=signature(typed.trim())?;
                if !ident(name)||!matches!(kind,"int"|"bool"){return Err("DOC_NATIVE: invalid call name or result type".into());}
                let (invocation,condition)=if let Some((invocation,branch))=body.trim().split_once(" when "){
                    let (guard,fallback)=branch.split_once(" else ").ok_or("DOC_NATIVE: conditional call needs else premise")?;
                    let (guard,fallback)=(guard.trim(),fallback.trim());
                    if !ident(guard)||!ident(fallback){return Err("DOC_NATIVE: conditional call requires named guard and fallback premises".into());}
                    (invocation.trim(),Some((guard.to_owned(),fallback.to_owned())))
                }else{(body.trim(),None)};
                let (callee,args)=signature(invocation)?;
                let args=fields(args);
                if args.iter().any(|s|!ident(s)){return Err("DOC_NATIVE: arguments must be named premises".into());}
                raw.push(RawCall{name:name.into(),symbol:callee.into(),args:args.into_iter().map(str::to_owned).collect(),condition});
                if raw.len()>64{return Err("DOC_NATIVE: call resource bound".into());}
                // Use the existing parser and graph checker for dependency
                // validation; the private typed placeholder is NEVER evaluated
                // or exposed as a pure program or serialized as a pure derive.
                writeln!(pure,"derive {name}: {kind} ({premises}) = {}",if kind=="int"{"0"}else{"false"}).unwrap();
            }else if let Some((op,rest))=[
                ("native load ",Op::Load),("native store ",Op::Store),
                ("native fetch_add ",Op::FetchAdd),("native fence ",Op::Fence),("native extent ",Op::Extent)
            ].iter().find_map(|(prefix,op)|line.strip_prefix(*prefix).map(|rest|(*op,rest))){
                let (header,body)=rest.split_once('=').ok_or("DOC_NATIVE: region operation needs =")?;
                let (name,typed)=header.split_once(':').ok_or("DOC_NATIVE: region operation needs result type")?;
                let name=name.trim();let (kind,premises)=signature(typed.trim())?;
                let expected=if matches!(op,Op::Load|Op::FetchAdd|Op::Extent){"int"}else{"bool"};
                if !ident(name)||kind!=expected{return Err("DOC_NATIVE: wrong region operation result type".into());}
                let (callee,args)=signature(body.trim())?;let args=fields(args);
                if args.iter().any(|s|!ident(s)){return Err("DOC_NATIVE: region operands must be named premises".into());}
                raw_regions.push(RawRegionOp{op,call:RawCall{name:name.into(),symbol:callee.into(),args:args.into_iter().map(str::to_owned).collect(),condition:None}});
                if raw_regions.len()>64{return Err("DOC_NATIVE: region operation resource bound".into());}
                writeln!(pure,"derive {name}: {kind} ({premises}) = {}",if kind=="int"{"0"}else{"false"}).unwrap();
            }else if line.starts_with("native ")||line.starts_with("effect ")||line.starts_with("import "){
                return Err("DOC_NATIVE: unsupported declaration in native object profile".into());
            }else{writeln!(pure,"{original}").unwrap();}
        }
        if (raw.is_empty()&&raw_regions.is_empty())||
            imports.len()+cleanup_symbols.len()!=grants.len()||
            external_intrinsic_symbols.len()!=intrinsic_grants.len()||
            cleanup_symbols.iter().any(|name|lookup.contains_key(name)||external_intrinsic_symbols.contains(name))||
            regions.len()!=region_grants.len(){
            return Err("DOC_NATIVE: declared effects and authority grants must agree".into());
        }
        let graph=Graph::parse(&pure)?;
        let mut calls=BTreeMap::new();let mut used=BTreeSet::new();let mut used_intrinsics=BTreeSet::new();let mut used_regions=BTreeSet::new();
        for r in raw{
            let id=graph.id(&r.name).ok_or("DOC_NATIVE: missing call state")?;
            let state=&graph.states[id];let d=state.definition.as_ref().ok_or("DOC_NATIVE: call must be derived")?;
            let target=if let Some(&index)=lookup.get(&r.symbol){
                Target::Import(index)
            }else if let Some(&index)=intrinsic_lookup.get(&r.symbol){
                Target::Intrinsic(index)
            }else{return Err("DOC_NATIVE: undeclared call symbol".into());};
            let (spec_args,spec_result):(&[Param],Abi)=match target{
                Target::Import(index)=>(&imports[index].args,imports[index].result),
                Target::Intrinsic(index)=>(&intrinsics[index].args,intrinsics[index].result),
            };
            if state.kind!=spec_result.kind()||r.args.len()!=spec_args.iter().map(|p|p.source_arity()).sum::<usize>(){return Err("DOC_NATIVE: call ABI signature mismatch".into());}
            let premise=|name:&str,kind:Type|->Result<StateId>{
                let p=graph.id(name).ok_or("DOC_NATIVE: unknown argument")?;
                if !d.premises.contains(&p)||graph.states[p].kind!=kind{
                    return Err("DOC_NATIVE: argument must be a typed declared premise".into());
                }Ok(p)
            };
            let mut args=Vec::new();let mut pos=0;
            let mut borrowed=BTreeSet::new();
            for param in spec_args{
                match param{
                    Param::Scalar(abi)=>args.push(Argument::Scalar(premise(&r.args[pos],abi.kind())?)),
                    Param::Bytes|Param::ConstBytes=>{
                        let region=*region_lookup.get(&r.args[pos]).ok_or("DOC_NATIVE: unknown buffer region")?;
                        if regions[region].abi!=Abi::U8||regions[region].access!=Access::Plain{
                            return Err("DOC_NATIVE: byte buffer requires a plain u8 region".into());
                        }
                        // Conservative no-alias contract, even for two const views.
                        if !borrowed.insert(region){return Err("DOC_NATIVE: duplicate buffer region in call".into());}
                        let offset=premise(&r.args[pos+1],Type::Int)?;
                        let count=premise(&r.args[pos+2],Type::Int)?;
                        used_regions.insert(region);
                        args.push(Argument::Buffer{region,offset,count});
                    }
                }
                pos+=param.source_arity();
            }
            let condition=if let Some((guard,fallback))=r.condition{
                let guard=graph.id(&guard).ok_or("DOC_NATIVE: unknown conditional guard")?;
                let fallback=graph.id(&fallback).ok_or("DOC_NATIVE: unknown conditional fallback")?;
                if !d.premises.contains(&guard)||graph.states[guard].kind!=Type::Bool||
                    !d.premises.contains(&fallback)||graph.states[fallback].kind!=state.kind{
                    return Err("DOC_NATIVE: conditional guard/fallback must be typed declared premises".into());
                }
                Some((guard,fallback))
            }else{None};
            if calls.insert(id,Call{target,args,condition}).is_some(){return Err("DOC_NATIVE: duplicate call".into());}
            match target{Target::Import(index)=>{used.insert(index);},Target::Intrinsic(index)=>{used_intrinsics.insert(index);}}
        }
        let mut cleanups = BTreeMap::new();
        for (state, destructor) in scoped {
            let id = graph.id(&state).ok_or("DOC_NATIVE: unknown acquisition state")?;
            let call = calls.get(&id).ok_or("DOC_NATIVE: cleanup requires an imported acquisition")?;
            let Target::Import(import)=call.target else {
                return Err("DOC_NATIVE: cleanup requires an imported acquisition".into());
            };
            if !matches!(imports[import].result, Abi::I32) {
                return Err("DOC_NATIVE: scoped acquisition must return i32".into());
            }
            cleanups.insert(id, destructor);
        }
        if used.len()!=imports.len(){return Err("DOC_NATIVE: unused imported symbol".into());}
        if used_intrinsics.len()!=intrinsics.len(){return Err("DOC_NATIVE: unused target intrinsic".into());}
        let mut operations=BTreeMap::new();
        for RawRegionOp{op,call:r} in raw_regions{
            let id=graph.id(&r.name).ok_or("DOC_NATIVE: missing region operation state")?;
            let d=graph.states[id].definition.as_ref().ok_or("DOC_NATIVE: region operation must be derived")?;
            let region=if op==Op::Fence{
                if r.symbol!="seq_cst"||!r.args.is_empty()||!regions.iter().any(|r|r.access==Access::Atomic){
                    return Err("DOC_NATIVE: seq_cst fence requires atomic region authority and no arguments".into());
                }None
            }else{
                let index=*region_lookup.get(&r.symbol).ok_or("DOC_NATIVE: undeclared region")?;
                let spec=&regions[index];
                if op==Op::FetchAdd&&spec.access!=Access::Atomic{return Err("DOC_NATIVE: fetch_add requires atomic u32 region".into());}
                let argc=match op{Op::Extent=>0,Op::Load=>1,_=>2};
                if r.args.len()!=argc{return Err("DOC_NATIVE: wrong region operation arity".into());}
                used_regions.insert(index);Some(index)
            };
            let args=r.args.iter().map(|name|{
                let p=graph.id(name).ok_or("DOC_NATIVE: unknown region operand")?;
                if !d.premises.contains(&p)||graph.states[p].kind!=Type::Int{
                    return Err("DOC_NATIVE: region operands must be integer premises".into());
                }Ok(p)
            }).collect::<Result<Vec<_>>>()?;
            if operations.insert(id,RegionOp{op,region,args}).is_some()||calls.contains_key(&id){
                return Err("DOC_NATIVE: duplicate effect state".into());
            }
        }
        if used_regions.len()!=regions.len(){return Err("DOC_NATIVE: unused region authority".into());}
        // The first effect profile conservatively requires one causal chain.
        // An extra premise can be an explicit completion dependency without
        // being an ABI argument. No implicit source-order effect sequencing.
        let mut previous=None;
        for &id in &graph.topo{
            if calls.contains_key(&id)||operations.contains_key(&id){
                if let Some(p)=previous{if !depends(&graph,id,p){return Err("DOC_NATIVE: unordered native effects".into());}}
                previous=Some(id);
            }
        }
        let repeat=if let Some((halt,raw_carries))=raw_repeat{
            let halt=graph.id(&halt).ok_or("DOC_NATIVE: unknown repeat halt state")?;
            if graph.states[halt].kind!=Type::Bool||graph.states[halt].definition.is_none(){
                return Err("DOC_NATIVE: repeat halt must be a derived bool".into());
            }
            let mut carries=Vec::new();
            for (destination,value) in raw_carries{
                let destination=graph.id(&destination).ok_or("DOC_NATIVE: unknown repeat carry destination")?;
                let value=graph.id(&value).ok_or("DOC_NATIVE: unknown repeat carry value")?;
                if graph.states[destination].definition.is_some()||graph.states[value].definition.is_none()||
                    graph.states[destination].kind!=graph.states[value].kind||
                    !matches!(graph.states[value].kind,Type::Int|Type::Bool)||cleanups.contains_key(&value){
                    return Err("DOC_NATIVE: repeat carry must transfer a matching derived scalar to a source, not a scoped acquisition".into());
                }
                carries.push((destination,value));
            }
            Some(Repeat{halt,carries})
        }else{None};
        Ok(Self{repeat,graph,cleanups,imports,intrinsics,calls,regions,operations})
    }
    pub fn emit(&self,export:&str)->Result<(String,String,String)>{
        let (c,h)=aot::emit_scalar_object_impl(&self.graph,export,Some(self))?;
        Ok((c,h,self.ir()?))
    }
    fn ir(&self)->Result<String>{
        let pure=emit_typed_ir_v1(&self.graph,&[])?;
        let mut out=String::from("DOC-NATIVE-IR/1\n");
        for (i,import) in self.imports.iter().enumerate(){
            let args=import.args.iter().map(|a|a.name()).collect::<Vec<_>>().join(",");
            writeln!(out,"import\t{i}\t{}\t{}\t{}",import.symbol,args,import.result.name()).unwrap();
        }
        for intrinsic in &self.intrinsics{
            let args=intrinsic.args.iter().map(|a|a.name()).collect::<Vec<_>>().join(",");
            writeln!(out,"intrinsic\t{}\t{}\t{}\t{}",intrinsic.name,args,intrinsic.result.name(),intrinsic.op.descriptor()).unwrap();
        }
        for (i,region) in self.regions.iter().enumerate(){
            writeln!(out,"region\t{i}\t{}\t{}\t{}",region.name,region.abi.name(),region.access.name()).unwrap();
        }
        for (id, destructor) in &self.cleanups {
            writeln!(out, "cleanup-i32\t{id}\t{destructor}").unwrap();
        }
        if let Some(repeat)=&self.repeat{
            let carries=repeat.carries.iter().map(|(d,v)|format!("{d}:{v}")).collect::<Vec<_>>().join(",");
            writeln!(out,"repeat\t{}\t{carries}",repeat.halt).unwrap();
        }
        for line in pure.lines().skip(1){
            if line.starts_with("derive\t"){
                let f=line.split('\t').collect::<Vec<_>>();
                let id=f[1].parse::<usize>().map_err(|_|"DOC_NATIVE: internal IR state")?;
                if let Some(op)=self.operations.get(&id){
                    let region=op.region.map(|r|r.to_string()).unwrap_or_else(||"-".into());
                    let args=op.args.iter().map(|p|p.to_string()).collect::<Vec<_>>().join(",");
                    writeln!(out,"region-op\t{id}\t{}\t{}\t{}\t{}\t{region}\t{args}",f[2],f[3],f[4],op.op.name()).unwrap();
                    continue;
                }
                if let Some(call)=self.calls.get(&id){
                    let args=call.args.iter().map(|p|p.ir()).collect::<Vec<_>>().join(",");
                    match (call.target,call.condition){
                        (Target::Import(import),Some((guard,fallback)))=>
                            writeln!(out,"call-if\t{id}\t{}\t{}\t{}\t{}\t{args}\t{guard}\t{fallback}",f[2],f[3],f[4],import).unwrap(),
                        (Target::Import(import),None)=>
                            writeln!(out,"call\t{id}\t{}\t{}\t{}\t{}\t{args}",f[2],f[3],f[4],import).unwrap(),
                        (Target::Intrinsic(intrinsic),Some((guard,fallback)))=>
                            writeln!(out,"intrinsic-call-if\t{id}\t{}\t{}\t{}\t{}\t{}\t{args}\t{guard}\t{fallback}",self.intrinsics[intrinsic].name,f[2],f[3],f[4],self.intrinsics[intrinsic].op.descriptor()).unwrap(),
                        (Target::Intrinsic(intrinsic),None)=>
                            writeln!(out,"intrinsic-call\t{id}\t{}\t{}\t{}\t{}\t{}\t{args}",self.intrinsics[intrinsic].name,f[2],f[3],f[4],self.intrinsics[intrinsic].op.descriptor()).unwrap(),
                    }
                    continue;
                }
            }
            writeln!(out,"{line}").unwrap();
        }
        Ok(out)
    }
    pub(crate) fn parameters(&self,params:&mut Vec<String>){
        for r in &self.regions{
            params.push(format!("void *region_ptr_{}",r.name));
            params.push(format!("size_t region_count_{}",r.name));
        }
    }
    pub(crate) fn validate_regions(&self,out:&mut String){
        if self.regions.is_empty(){return;}
        // The enclosing scalar export validates the result address range.
        out.push_str("    uintptr_t output_start=(uintptr_t)out;\n    uintptr_t output_end=output_start+sizeof(*out);\n");
        for (i,r) in self.regions.iter().enumerate(){
            let name=&r.name;let ty=r.c();
            writeln!(out,"    uintptr_t region_start_{i}=(uintptr_t)region_ptr_{name};").unwrap();
            writeln!(out,"    if(region_count_{name}>SIZE_MAX/sizeof({ty}) || region_count_{name}>UINTPTR_MAX/sizeof({ty})) return 0;").unwrap();
            writeln!(out,"    uintptr_t region_size_{i}=(uintptr_t)region_count_{name}*sizeof({ty});").unwrap();
            writeln!(out,"    if(region_size_{i} && (!region_ptr_{name} || region_start_{i}%_Alignof({ty}) || region_start_{i}>UINTPTR_MAX-region_size_{i})) return 0;").unwrap();
            writeln!(out,"    uintptr_t region_end_{i}=region_start_{i}+region_size_{i};").unwrap();
            writeln!(out,"    if(region_size_{i} && region_start_{i}<output_end && output_start<region_end_{i}) return 0;").unwrap();
            for j in 0..i{
                writeln!(out,"    if(region_size_{i} && region_size_{j} && region_start_{i}<region_end_{j} && region_start_{j}<region_end_{i}) return 0;").unwrap();
            }
        }
    }
    pub(crate) fn declarations(&self,out:&mut String){
        if self.regions.iter().any(|r|r.access==Access::Atomic){
            out.push_str("#include <stdatomic.h>\n_Static_assert(__atomic_always_lock_free(sizeof(uint32_t),0),\"DOC target requires lock-free u32 atomics\");\n");
        }
        for (id, symbol) in &self.cleanups {
            writeln!(out, "extern void doc_cleanup_{id}(int32_t) __asm__(\"{symbol}\");").unwrap();
        }
        // GNU C symbol aliases avoid lexical shadowing and built-in
        // prototypes. Only restricted identifier bytes enter asm labels.
        for (i,s) in self.imports.iter().enumerate(){
            let args=if s.args.is_empty(){"void".into()}else{s.args.iter().map(|a|a.c()).collect::<Vec<_>>().join(", ")};
            writeln!(out,"extern {} doc_import_{i}({args}) __asm__(\"{}\");",s.result.c(),s.symbol).unwrap();
        }
        for (i,s) in self.intrinsics.iter().enumerate(){
            let IntrinsicOp::External(symbol)=&s.op else{continue;};
            let args=if s.args.is_empty(){"void".into()}else{s.args.iter().map(|a|a.c()).collect::<Vec<_>>().join(", ")};
            writeln!(out,"extern {} doc_intrinsic_{i}({args}) __asm__(\"{}\");",s.result.c(),symbol).unwrap();
        }
    }
    pub(crate) fn declare_owned_handles(&self, out: &mut String) {
        for id in self.cleanups.keys() {
            writeln!(out, "    int32_t owned_{id} = -1;").unwrap();
        }
    }
    pub(crate) fn release_owned_handles(&self, out: &mut String) {
        for id in self.graph.topo.iter().rev().filter(|id| self.cleanups.contains_key(*id)) {
            writeln!(out, "    if (owned_{id} >= 0) {{ doc_cleanup_{id}(owned_{id}); owned_{id}=-1; }}").unwrap();
        }
    }
    pub(crate) fn begin_repeat(&self,out:&mut String){
        if self.repeat.is_some(){out.push_str("    for (size_t doc_step=0;;doc_step++) {\n");}
    }
    pub(crate) fn end_repeat(&self,out:&mut String){
        if let Some(repeat)=&self.repeat{
            writeln!(out,"    if (v[{}].scalar) break;",repeat.halt).unwrap();
            // Completed effects and cleanup are not replayed or rolled back.
            // Bound the total number of evaluated native epochs, not just transitions.
            out.push_str("    if (doc_step==65535) return 0;\n");
            for (destination,value) in &repeat.carries{
                writeln!(out,"    v[{destination}]=v[{value}];").unwrap();
            }
            out.push_str("    }\n");
        }
    }
    pub(crate) fn emit_call(&self,id:StateId,out:&mut String)->bool{
        if let Some(op)=self.operations.get(&id){
            self.emit_region(id,op,out);return true;
        }
        let Some(call)=self.calls.get(&id)else{return false;};
        if let Target::Intrinsic(index)=call.target{
            let intrinsic=&self.intrinsics[index];
            if let IntrinsicOp::External(_) = &intrinsic.op {
                if let Some((guard,fallback))=call.condition{
                    writeln!(out,"    if (!v[{guard}].scalar) {{ v[{id}]=v[{fallback}]; }} else {{").unwrap();
                }
                let args=self.emit_arguments(call,&intrinsic.args,out);
                writeln!(out,"    {{ {} result = doc_intrinsic_{index}({args});",intrinsic.result.c()).unwrap();
                if matches!(intrinsic.result,Abi::Bool8){out.push_str("    if (result>1) goto failed;\n");}
                let kind=if intrinsic.result.kind()==Type::Bool{"DOC_BOOL"}else{"DOC_INT"};
                writeln!(out,"    v[{id}]=(doc_value){{.kind={kind},.scalar=(int64_t)result}}; }}").unwrap();
                if call.condition.is_some(){out.push_str("    }\n");}
                return true;
            }
            let Some(&Argument::Scalar(input))=call.args.first()else{return false;};
            if let Some((guard,fallback))=call.condition{
                writeln!(out,"    if (!v[{guard}].scalar) {{ v[{id}]=v[{fallback}]; }} else {{").unwrap();
            }
            let value=intrinsic.op.c_expr(&format!("v[{input}].scalar"));
            writeln!(out,"    v[{id}]=(doc_value){{.kind=DOC_INT,.scalar={value}}};").unwrap();
            if call.condition.is_some(){out.push_str("    }\n");}
            return true;
        }
        let Target::Import(import)=call.target else{return false;};
        let s=&self.imports[import];
        if let Some((guard,fallback))=call.condition{
            writeln!(out,"    if (!v[{guard}].scalar) {{ v[{id}]=v[{fallback}]; }} else {{").unwrap();
        }
        let args=self.emit_arguments(call,&s.args,out);
        writeln!(out,"    {{ {} result = doc_import_{}({args});",s.result.c(),import).unwrap();
        if matches!(s.result,Abi::Bool8){out.push_str("    if (result>1) goto failed;\n");}
        if self.cleanups.contains_key(&id) {
            writeln!(out, "    owned_{id} = result;").unwrap();
        }
        let kind=if s.result.kind()==Type::Bool{"DOC_BOOL"}else{"DOC_INT"};
        writeln!(out,"    v[{id}]=(doc_value){{.kind={kind},.scalar=(int64_t)result}}; }}").unwrap();
        if call.condition.is_some(){out.push_str("    }\n");}
        true
    }
    fn emit_arguments(&self,call:&Call,params:&[Param],out:&mut String)->String{
        let mut args=Vec::new();
        for (&arg,&param) in call.args.iter().zip(params){
            match (arg,param){
                (Argument::Scalar(p),Param::Scalar(abi))=>{
                    if let Some((min,max))=abi.bounds(){
                        writeln!(out,"    if (v[{p}].scalar < {min} || v[{p}].scalar > {max}) goto failed;").unwrap();
                    }
                    args.push(format!("({})v[{p}].scalar",abi.c()));
                }
                (Argument::Buffer{region,offset,count},Param::Bytes|Param::ConstBytes)=>{
                    let name=&self.regions[region].name;
                    // Subtract only after checking the offset; avoid signed overflow
                    // and null pointer arithmetic for empty regions.
                    writeln!(out,"    if (v[{offset}].scalar<0 || v[{count}].scalar<0 || (uint64_t)v[{offset}].scalar>region_count_{name} || (uint64_t)v[{count}].scalar>region_count_{name}-(size_t)v[{offset}].scalar) goto failed;").unwrap();
                    let ty=if param==Param::ConstBytes{"const uint8_t"}else{"uint8_t"};
                    args.push(format!("(v[{offset}].scalar ? ({ty}*)region_ptr_{name}+(size_t)v[{offset}].scalar : ({ty}*)region_ptr_{name})"));
                    args.push(format!("(size_t)v[{count}].scalar"));
                }
                _=>unreachable!("validated native argument"),
            }
        }
        args.join(", ")
    }
    fn emit_region(&self,id:StateId,op:&RegionOp,out:&mut String){
        if op.op==Op::Fence{
            writeln!(out,"    atomic_thread_fence(memory_order_seq_cst); v[{id}]=(doc_value){{.kind=DOC_BOOL,.scalar=1}};").unwrap();
            return;
        }
        let r=&self.regions[op.region.expect("checked region")];let name=&r.name;let ty=r.c();
        if op.op==Op::Extent{
            writeln!(out,"    if (region_count_{name}>INT64_MAX) goto failed;").unwrap();
            writeln!(out,"    v[{id}]=(doc_value){{.kind=DOC_INT,.scalar=(int64_t)region_count_{name}}};").unwrap();
            return;
        }
        let index=op.args[0];
        writeln!(out,"    if(v[{index}].scalar<0 || (uint64_t)v[{index}].scalar>=region_count_{name}) goto failed;").unwrap();
        let ptr=format!("(({}*)region_ptr_{name})+(size_t)v[{index}].scalar",ty);
        if op.op==Op::Load{
            let value=if r.access==Access::Atomic{format!("atomic_load_explicit({ptr},memory_order_seq_cst)")}else{format!("*({ptr})")};
            writeln!(out,"    v[{id}]=(doc_value){{.kind=DOC_INT,.scalar=(int64_t)({value})}};").unwrap();
        }else{
            let value=op.args[1];
            if let Some((min,max))=r.abi.bounds(){
                writeln!(out,"    if(v[{value}].scalar<{min} || v[{value}].scalar>{max}) goto failed;").unwrap();
            }
            let x=format!("({})v[{value}].scalar",r.abi.c());
            if op.op==Op::FetchAdd{
                writeln!(out,"    v[{id}]=(doc_value){{.kind=DOC_INT,.scalar=(int64_t)atomic_fetch_add_explicit({ptr},{x},memory_order_seq_cst)}};").unwrap();
            }else{
                if r.access==Access::Atomic{writeln!(out,"    atomic_store_explicit({ptr},{x},memory_order_seq_cst);").unwrap();}
                else{writeln!(out,"    *({ptr})={x};").unwrap();}
                writeln!(out,"    v[{id}]=(doc_value){{.kind=DOC_BOOL,.scalar=1}};").unwrap();
            }
        }
    }

}

#[cfg(test)]
mod region_identifier_tests {
    use super::NativeProgram;

    #[test]
    #[cfg(all(target_os="linux",target_arch="x86_64"))]
    fn native_region_names_do_not_collide_with_generated_count_parameters() {
        use std::{io::Write, process::{Command,Stdio}};
        let source=concat!(
            "native region buf: u8 plain\n",
            "native region buf_count: u8 plain\n",
            "source index: int = 0\n",
            "native load first: int (index) = buf(index)\n",
            "native load second: int (index,first) = buf_count(index)\n");
        let grants=vec!["buf".into(),"buf_count".into()];
        let (c,h,ir)=NativeProgram::parse_with_regions(source,&[],&grants)
            .unwrap().emit("distinct_regions").unwrap();
        assert!(h.contains("void *region_ptr_buf, size_t region_count_buf, void *region_ptr_buf_count, size_t region_count_buf_count"));
        assert!(ir.contains("region\t0\tbuf\tu8\tplain"));
        assert!(ir.contains("region\t1\tbuf_count\tu8\tplain"));
        // Check both generated translation units with the actual native
        // toolchain: distinct Rust strings alone do not prove valid C.
        for unit in [&c,&h] {
            let mut child=Command::new("cc").args(["-std=c11","-fsyntax-only","-x","c","-"])
                .stdin(Stdio::piped()).stderr(Stdio::piped()).spawn().unwrap();
            child.stdin.take().unwrap().write_all(unit.as_bytes()).unwrap();
            let result=child.wait_with_output().unwrap();
            assert!(result.status.success(),"{}",String::from_utf8_lossy(&result.stderr));
        }
    }
}
