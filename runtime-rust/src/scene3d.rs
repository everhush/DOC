//! Reusable typed DOC scene ABI. No game rules, geometry, camera or material
//! decisions live here. DOC defines carry, action, mesh, draw and shader facts.
use crate::{graphics::{compile_mesh,Binding,Domain,Input,MeshProgram},recurrence::Recurrence,Graph,Result,Value};
use std::{collections::BTreeMap,path::Path};

#[derive(Clone,Debug)]
pub struct Draw {pub first:u32,pub count:u32,pub params:[i32;8]}
#[derive(Clone,Debug)]
pub struct SceneFrame {
    pub vertices:Vec<[i32;12]>,pub indices:Vec<u32>,pub draws:Vec<Draw>,
    pub clear:[u8;4],
}
pub struct Scene3d {
    pub program:MeshProgram,
    recurrence:Recurrence,
    actions:BTreeMap<char,i64>,
    report:Vec<usize>,
    action:usize,
    clear:[u8;4],
    file:String,
    workers:usize,
    automatic:bool,
    audio:Option<(usize,usize)>,
}
fn constant(graph:&Graph,name:&str)->Result<Value>{
    let id=graph.id(name).ok_or_else(||format!("DOC_SCENE: missing {name}"))?;
    graph.states[id].initial.clone().ok_or_else(||format!("DOC_SCENE: {name} must be a static source"))
}
fn text(graph:&Graph,name:&str)->Result<String>{
    if let Value::Text(s)=constant(graph,name)?{Ok(s)}else{Err(format!("DOC_SCENE: {name} must be text"))}
}
fn names(s:&str)->Result<Vec<&str>>{
    let v=s.split(',').map(str::trim).collect::<Vec<_>>();
    if v.is_empty()||v.iter().any(|x|x.is_empty()){return Err("DOC_SCENE: empty interface name".into());}
    Ok(v)
}
fn bindings(s:&str)->Result<Vec<Binding<'_>>>{
    let mut out=Vec::new();
    for item in names(s)?{
        let a=item.split(':').collect::<Vec<_>>();
        if a.len()!=5{return Err("DOC_SCENE: binding requires name:domain:slot:min:max".into());}
        let slot=a[2].parse::<usize>().map_err(|_|"DOC_SCENE: invalid slot")?;
        let input=match a[1]{"vertex"=>Input::Vertex(slot),"draw"=>Input::Draw(slot),"varying"=>Input::Varying(slot),_=>return Err("DOC_SCENE: unknown input domain".into())};
        let min=a[3].parse::<i32>().map_err(|_|"DOC_SCENE: invalid lower bound")?;
        let max=a[4].parse::<i32>().map_err(|_|"DOC_SCENE: invalid upper bound")?;
        out.push(Binding{name:a[0],input,domain:Domain{min,max}});
    }Ok(out)
}
fn stage_file(root:&Path,raw:&str)->Result<Graph>{
    // The same descriptor-relative, bounded read as ordinary DOC child
    // sources; shader stage text is pure, never an effectful file frontend.
    let source=crate::confined::read(root,raw,65_536)?;
    Graph::parse(&source)
}
impl Scene3d {
    pub fn open(file:&str,workers:usize,automatic:bool)->Result<Self>{
        let graph=Graph::parse_file(file)?;
        let root=crate::confined::source_directory(Path::new(file));
        let vertex=stage_file(root,&text(&graph,"render_vertex_stage")?)?;
        let fragment=stage_file(root,&text(&graph,"render_fragment_stage")?)?;
        let vb=text(&graph,"render_vertex_bindings")?;let fb=text(&graph,"render_fragment_bindings")?;
        let clip=text(&graph,"render_clip")?;let varying=text(&graph,"render_varying")?;let color=text(&graph,"render_color")?;
        let program=compile_mesh(&vertex,&fragment,&bindings(&vb)?,&bindings(&fb)?,
            names(&clip)?.try_into().map_err(|_|"DOC_SCENE: expected four clip outputs")?,
            names(&varying)?.try_into().map_err(|_|"DOC_SCENE: expected three varying outputs")?,
            names(&color)?.try_into().map_err(|_|"DOC_SCENE: expected three color outputs")?)?;
        let action=graph.id("action").ok_or("DOC_SCENE: missing input action")?;
        if graph.states[action].definition.is_some()||graph.states[action].kind!=crate::Type::Int{
            return Err("DOC_SCENE: action must be integer source".into());
        }
        let mut carries=Vec::new();
        for item in names(&text(&graph,"render_carries")?)?{
            let(a,b)=item.split_once(':').ok_or("DOC_SCENE: carry requires source:result")?;
            if a.starts_with("render_")||a=="action"{return Err("DOC_SCENE: immutable interface or input carry".into());}
            carries.push((graph.id(a).ok_or("DOC_SCENE: unknown carry source")?,graph.id(b).ok_or("DOC_SCENE: unknown carry result")?));
        }
        let mut actions=BTreeMap::new();
        for item in names(&text(&graph,"render_actions")?)?{
            let(a,b)=item.split_once(':').ok_or("DOC_SCENE: action requires key:value")?;
            let mut chars=a.chars();let ch=chars.next().ok_or("DOC_SCENE: empty action key")?;
            if chars.next().is_some()||!ch.is_ascii()||actions.insert(ch,b.parse().map_err(|_|"DOC_SCENE: invalid action")?).is_some(){
                return Err("DOC_SCENE: invalid or duplicate action key".into());
            }
        }
        if !actions.contains_key(&'.'){return Err("DOC_SCENE: idle action missing".into());}
        let report=names(&text(&graph,"render_report")?)?.iter().map(|s|graph.id(s).ok_or_else(||format!("DOC_SCENE: unknown report state {s}"))).collect::<Result<Vec<_>>>()?;
        let clear=match constant(&graph,"render_clear")?{
            Value::Ints(xs) if xs.len()==4=>xs.into_iter().map(|n|u8::try_from(n).map_err(|_|"DOC_SCENE: clear channel outside byte".into())).collect::<Result<Vec<_>>>()?.try_into().map_err(|_|"DOC_SCENE: clear size")?,
            _=>return Err("DOC_SCENE: clear must be four bytes".into()),
        };
        let audio=if graph.id("render_audio").is_some(){
            let fields=text(&graph,"render_audio")?;
            let names=names(&fields)?;
            if names.len()!=2{return Err("DOC_SCENE: audio needs frequency,duration state names".into());}
            let hz=graph.id(names[0]).ok_or("DOC_SCENE: missing audio frequency")?;
            let ms=graph.id(names[1]).ok_or("DOC_SCENE: missing audio duration")?;
            if graph.states[hz].kind!=crate::Type::Int||graph.states[ms].kind!=crate::Type::Int{return Err("DOC_SCENE: audio values must be ints".into());}
            Some((hz,ms))
        }else{None};
        let recurrence=if automatic{Recurrence::new_automatic_with_retention(graph,carries,&[],workers,2)?}
            else{Recurrence::new_with_retention(graph,carries,&[],workers,2)?};
        let result=Self{program,recurrence,actions,report,action,clear,file:file.into(),workers,automatic,audio};
        result.frame()?;Ok(result)
    }
    pub fn epoch(&self)->u64{self.recurrence.epoch()}
    pub fn value(&self,name:&str)->Result<Value>{
        self.recurrence.graph().id(name).and_then(|id|self.recurrence.value(id)).ok_or_else(||format!("DOC_SCENE: missing value {name}"))
    }
    pub fn advance(&mut self,key:char)->Result<()>{
        let value=*self.actions.get(&key).ok_or("DOC_SCENE: unknown action")?;
        let program=&self.program;let clear=self.clear;
        self.recurrence.advance_validated(&[(self.action,Value::Int(value))],|candidate|{
            decode_frame(program,clear,|name|candidate.graph.id(name).and_then(|id|candidate.value(id)).ok_or_else(||format!("DOC_SCENE: missing candidate {name}")))?;
            Ok(())
        })
    }
    pub fn save(&self,relative:&str)->Result<()>{
        crate::checkpoint::save_checkpoint(&self.file,relative,&self.recurrence)
    }
    pub fn restore(&mut self,relative:&str)->Result<u64>{
        let mut loaded=crate::checkpoint::load_checkpoint(&self.file,relative,self.recurrence.graph().clone(),self.recurrence.carries().to_vec(),self.workers,2)?;
        // A persisted source may not replace the static shader/interface
        // authority used to construct this native renderer.
        for name in ["render_vertex_stage","render_fragment_stage","render_vertex_bindings","render_fragment_bindings","render_clip","render_varying","render_color","render_carries","render_actions","render_report","render_clear","render_audio"]{
            if let Some(id)=loaded.recurrence.graph().id(name){
                if loaded.recurrence.value(id)!=Some(constant(self.recurrence.graph(),name)?){
                    return Err(format!("DOC_SCENE: checkpoint changed static interface {name}"));
                }
            }
        }
        decode_frame(&self.program,self.clear,|name|loaded.recurrence.graph().id(name).and_then(|id|loaded.recurrence.value(id)).ok_or_else(||format!("DOC_SCENE: missing restored {name}")))?;
        if self.automatic{loaded.recurrence.enable_automatic();}
        let epoch=loaded.saved_epoch;self.recurrence=loaded.recurrence;Ok(epoch)
    }
    /// Optional confined WAV effect after a successful logical frame.
    pub fn emit_audio(&self,dir:&str)->Result<()>{
        let(hz,ms)=self.audio.ok_or("DOC_SCENE: no authored audio interface")?;
        let read=|id|->Result<u32>{match self.recurrence.value(id){Some(Value::Int(n))=>u32::try_from(n).map_err(|_|"DOC_SCENE: invalid audio value".into()),_=>Err("DOC_SCENE: invalid audio state".into())}};
        let frequency=read(hz)?;let duration=read(ms)?;
        if frequency==0&&duration==0{return Ok(());}
        let path=format!("{dir}/cue_{}.wav",self.epoch());
        crate::audio::write_tone_wav(&self.file,&path,frequency,duration)?;
        println!("DOC_SCENE_AUDIO_WAV: epoch={} path={path}",self.epoch());
        Ok(())
    }
    pub fn accepts(&self,key:char)->bool{self.actions.contains_key(&key)}
    pub fn automatic_report(&self)->Option<String>{self.recurrence.automatic_report()}
    pub fn report(&self)->Result<String>{
        let mut out=format!("DOC_SCENE_FRAME: epoch={}",self.epoch());
        for &id in &self.report{
            let value=self.recurrence.value(id).ok_or("DOC_SCENE: report not stable")?;
            out.push_str(&format!(" {}={}",self.recurrence.graph().states[id].name,value));
        }Ok(out)
    }
    pub fn frame(&self)->Result<SceneFrame>{
        decode_frame(&self.program,self.clear,|name|self.value(name))
    }
}
fn decode_frame(program:&MeshProgram,clear:[u8;4],get:impl Fn(&str)->Result<Value>)->Result<SceneFrame>{
        let ints=|name:&str|match get(name)?{Value::Ints(v)=>Ok(v),_=>Err(format!("DOC_SCENE: {name} must be ints"))};
        let v=ints("render_vertices")?;let i=ints("render_indices")?;let d=ints("render_draws")?;
        if v.is_empty()||v.len()%12!=0||v.len()>65536*12||i.is_empty()||i.len()>196608||
            d.is_empty()||d.len()%10!=0||d.len()>128*10{
            return Err("DOC_SCENE: invalid scene column size".into());
        }
        let vertices=v.chunks_exact(12).map(|row|{
            let mut a=[0;12];for(i,n)in row.iter().enumerate(){a[i]=i32::try_from(*n).map_err(|_|"DOC_SCENE: vertex overflow")?;}Ok(a)
        }).collect::<Result<Vec<_>>>()?;
        let indices=i.into_iter().map(|n|u32::try_from(n).map_err(|_|"DOC_SCENE: index overflow".into())).collect::<Result<Vec<_>>>()?;
        let mut draws=Vec::new();
        for row in d.chunks_exact(10){
            let first=u32::try_from(row[0]).map_err(|_|"DOC_SCENE: first index overflow")?;
            let count=u32::try_from(row[1]).map_err(|_|"DOC_SCENE: count overflow")?;
            let end=first.checked_add(count).ok_or("DOC_SCENE: index span overflow")?;
            let span=indices.get(first as usize..end as usize).ok_or("DOC_SCENE: draw outside index data")?;
            let mut params=[0;8];
            for (p,n) in params.iter_mut().zip(&row[2..]){*p=i32::try_from(*n).map_err(|_|"DOC_SCENE: parameter overflow")?;}
            program.validate(&vertices,&params,span)?;
            draws.push(Draw{first,count,params});
        }
        Ok(SceneFrame{vertices,indices,draws,clear})
}
