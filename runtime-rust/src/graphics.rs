//! First native DOC mesh pipeline: ordinary typed graph -> generated WGSL.
//! Vertex facts and draw parameters have proved i32 domains. Clip coordinates
//! use signed fixed-point units (1024 = 1), and fragment channels are 0..255.
//! The renderer owns rasterization/depth, not authored transformation/lighting.
use crate::{Expr,Graph,Result,Type,Value};
use std::fmt::Write;

#[derive(Clone,Copy,Debug)]
pub struct Domain {pub min:i32,pub max:i32}
#[derive(Clone,Copy,Debug)]
pub enum Input {Vertex(usize),Draw(usize),Varying(usize)}
#[derive(Clone,Copy,Debug)]
pub struct Binding<'a>{pub name:&'a str,pub input:Input,pub domain:Domain}
#[derive(Clone,Copy,Debug)]
enum Range{Int(i64,i64),Bool}
fn range(a:i64,b:i64)->Result<Range>{
    if a>b||a<i64::from(i32::MIN)||b>i64::from(i32::MAX){
        return Err("DOC_MESH_UNSUPPORTED: portable integer range not proved".into());
    }Ok(Range::Int(a,b))
}
fn ints(r:Range)->Result<(i64,i64)>{
    if let Range::Int(a,b)=r{Ok((a,b))}else{Err("DOC_MESH: integer output required".into())}
}
fn literal(v:&Value)->Result<(String,Range)>{
    match v{
        Value::Bool(b)=>Ok((b.to_string(),Range::Bool)),
        Value::Int(n)=>Ok((if *n==i64::from(i32::MIN){"(-2147483647i - 1i)".into()}else{format!("{n}i")},range(*n,*n)?)),
        _=>Err("DOC_MESH_UNSUPPORTED: scalar int/bool graph only".into()),
    }
}
fn expr(e:&Expr,args:&[(String,Range)],depth:usize)->Result<(String,Range)>{
    if depth>128{return Err("DOC_MESH: expression depth bound".into());}
    let lower=|e:&Expr|expr(e,args,depth+1);
    use Expr::*;
    match e{
        Lit(v)=>literal(v),Arg(i)=>args.get(*i).cloned().ok_or("DOC_MESH: missing premise".into()),
        If(c,a,b)=>{
            let(c,cr)=lower(c)?;let(a,ar)=lower(a)?;let(b,br)=lower(b)?;
            if !matches!(cr,Range::Bool){return Err("DOC_MESH: invalid condition".into());}
            let r=match(ar,br){
                (Range::Bool,Range::Bool)=>Range::Bool,
                (Range::Int(a,b),Range::Int(c,d))=>range(a.min(c),b.max(d))?,
                _=>return Err("DOC_MESH: branch kind mismatch".into())
            };
            // Eager select is safe because every admitted operand is total
            // and interval-checked, including unchosen branches.
            Ok((format!("select({b},{a},{c})"),r))
        },
        Add(a,b)|Sub(a,b)|Mul(a,b)|Eq(a,b)|Lt(a,b)|Le(a,b)=>{
            let(x,xr)=lower(a)?;let(y,yr)=lower(b)?;
            let(op,r)=match e{
                Eq(..)=>("==",Range::Bool),Lt(..)=>{ints(xr)?;ints(yr)?;("<",Range::Bool)},
                Le(..)=>{ints(xr)?;ints(yr)?;("<=",Range::Bool)},
                _=>{
                    let(a,b)=ints(xr)?;let(c,d)=ints(yr)?;
                    match e{
                        Add(..)=>("+",range(a+c,b+d)?),
                        Sub(..)=>("-",range(a-d,b-c)?),
                        _=>{let p=[a*c,a*d,b*c,b*d];("*",range(*p.iter().min().unwrap(),*p.iter().max().unwrap())?)}
                    }
                }
            };Ok((format!("({x} {op} {y})"),r))
        },
        _=>Err("DOC_MESH_UNSUPPORTED: effectful, partial or non-scalar expression".into()),
    }
}
#[derive(Clone,Debug)]
pub struct MeshProgram{
    pub wgsl:String,
    vertex:[Option<Domain>;12],
    draw:[Option<Domain>;8],
}
impl MeshProgram{
    /// Called before upload. Bounds are checked per draw and per vertex;
    /// invalid geometry may not silently narrow or overflow.
    pub fn validate(&self,vertices:&[[i32;12]],draw:&[i32;8],indices:&[u32])->Result<()>{
        if vertices.is_empty()||vertices.len()>65536||indices.is_empty()||indices.len()>196608||
           indices.len()%3!=0||indices.iter().any(|&i|i as usize>=vertices.len()){
            return Err("DOC_MESH: invalid mesh capacity/index".into());
        }
        for v in vertices{for (i,d) in self.vertex.iter().enumerate(){
            if let Some(d)=d{if !(d.min..=d.max).contains(&v[i]){return Err("DOC_MESH: vertex outside domain".into());}}
        }}
        for(i,d)in self.draw.iter().enumerate(){
            if let Some(d)=d{if !(d.min..=d.max).contains(&draw[i]){return Err("DOC_MESH: draw outside domain".into());}}
        }
        Ok(())
    }
}
fn stage(graph:&Graph,bindings:&[Binding<'_>],vertex:bool,vr:[Option<Domain>;3],out:&mut String,
         vd:&mut[Option<Domain>;12],dd:&mut[Option<Domain>;8])->Result<Vec<Range>>{
    let mut sources=vec![None;graph.states.len()];
    for b in bindings{
        let id=graph.id(b.name).ok_or("DOC_MESH: unknown input binding")?;
        if graph.states[id].kind!=Type::Int||graph.states[id].definition.is_some()||sources[id].is_some(){
            return Err("DOC_MESH: invalid input authority".into());
        }
        let d=b.domain;range(d.min.into(),d.max.into())?;
        let slot=match b.input{
            Input::Vertex(i) if vertex&&i<12=>&mut vd[i],
            Input::Draw(i) if i<8=>&mut dd[i],
            Input::Varying(i) if !vertex&&i<3=>{
                let proven=vr[i].ok_or("DOC_MESH: unproved varying")?;
                if d.min>proven.min||d.max<proven.max{return Err("DOC_MESH: varying domain too narrow".into());}
                sources[id]=Some(b.input);continue;
            },
            _=>return Err("DOC_MESH: input unavailable in stage".into()),
        };
        if let Some(old)=*slot{if old.min!=d.min||old.max!=d.max{return Err("DOC_MESH: conflicting domain".into());}}
        *slot=Some(d);sources[id]=Some(b.input);
    }
    let mut ranges=vec![None;graph.states.len()];
    for &i in &graph.topo{
        let state=&graph.states[i];
        let(s,r)=if let Some(input)=sources[i]{
            let (s,d)=match input{
                Input::Vertex(j)=>(format!("input.a{}[{}]",j/4,j%4),vd[j].unwrap()),
                Input::Draw(j)=>(format!("params.words[{}][{}]",j/4,j%4),dd[j].unwrap()),
                Input::Varying(j)=>(format!("input.shade[{j}]"),vr[j].unwrap()),
            };(s,range(d.min.into(),d.max.into())?)
        }else if let Some(v)=&state.initial{literal(v)?}
        else{
            let d=state.definition.as_ref().ok_or("DOC_MESH: missing definition")?;
            let args=d.premises.iter().map(|&p|Ok((format!("v{p}"),ranges[p].ok_or("DOC_MESH: missing ordered premise")?))).collect::<Result<Vec<_>>>()?;
            expr(&d.expr,&args,0)?
        };
        ranges[i]=Some(r);writeln!(out,"    let v{i} = {s};").unwrap();
        if out.len()>1024*1024{return Err("DOC_MESH: shader size budget".into());}
    }
    ranges.into_iter().map(|x|x.ok_or("DOC_MESH: unresolved state".into())).collect()
}
fn output(graph:&Graph,ranges:&[Range],name:&str,min:i64,max:i64)->Result<(usize,Domain)>{
    let id=graph.id(name).ok_or("DOC_MESH: missing stage output")?;
    let(a,b)=ints(ranges[id])?;
    if a<min||b>max{return Err(format!("DOC_MESH: output {name} range not proved"));}
    Ok((id,Domain{min:a as i32,max:b as i32}))
}
/// Reusable pipeline contract. Source authors write graph definitions; only
/// host ABI maps vertex/draw/varying data. No shader syntax, resource binding,
/// stage entry point, clip scaling or pixel encoding is authored in DOC.
pub fn compile_mesh(vertex:&Graph,fragment:&Graph,vb:&[Binding<'_>],fb:&[Binding<'_>],
                    clip:[&str;4],varying:[&str;3],color:[&str;3])->Result<MeshProgram>{
    let vertex=Graph::new(vertex.states.clone())?;let fragment=Graph::new(fragment.states.clone())?;
    if vertex.states.len()>512||fragment.states.len()>512||vb.len()>64||fb.len()>64{return Err("DOC_MESH: graph budget".into());}
    let mut vd=[None;12];let mut dd=[None;8];let mut vr=[None;3];
    let mut out=String::from(r#"// Generated from ordinary typed DOC graphs.
struct Params { words: array<vec4<i32>,2>, }
@group(0) @binding(0) var<uniform> params: Params;
struct Vertex { @location(0) a0:vec4<i32>, @location(1) a1:vec4<i32>, @location(2) a2:vec4<i32>, }
struct Varyings { @builtin(position) position:vec4<f32>, @location(0) @interpolate(flat) shade:vec3<i32>, }
@vertex fn vs_main(input:Vertex)->Varyings {
"#);
    let r=stage(&vertex,vb,true,vr,&mut out,&mut vd,&mut dd)?;
    let mut ids=[0;4];for i in 0..4{
        ids[i]=output(&vertex,&r,clip[i],if i==3{1}else{-16777216},16777216)?.0;
    }
    let mut vi=[0;3];for i in 0..3{
        let(id,d)=output(&vertex,&r,varying[i],-16777216,16777216)?;vi[i]=id;vr[i]=Some(d);
    }
    writeln!(out,"    var result:Varyings;\n    result.position=vec4<f32>(f32(v{}),f32(v{}),f32(v{}),f32(v{}))/1024.0;\n    result.shade=vec3<i32>(v{},v{},v{});\n    return result;\n}}",ids[0],ids[1],ids[2],ids[3],vi[0],vi[1],vi[2]).unwrap();
    out.push_str("@fragment fn fs_main(input:Varyings)->@location(0) vec4<f32> {\n");
    let r=stage(&fragment,fb,false,vr,&mut out,&mut vd,&mut dd)?;
    let mut ci=[0;3];for i in 0..3{ci[i]=output(&fragment,&r,color[i],0,255)?.0;}
    writeln!(out,"    return vec4<f32>(f32(v{})/255.0,f32(v{})/255.0,f32(v{})/255.0,1.0);\n}}",ci[0],ci[1],ci[2]).unwrap();
    Ok(MeshProgram{wgsl:out,vertex:vd,draw:dd})
}
