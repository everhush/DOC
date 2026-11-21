//! Safe lock/ownership-only publication of fully stabilized DOC generations.
//! A reader owns an Arc<PublishedSnapshot>, so no writer, graph replacement,
//! eviction, or pool compaction can invalidate a value captured by a reader.
//! This does not promise distributed coherency or wait-free reader progress.
use std::sync::{Arc,Mutex,RwLock};
use crate::{Cutoff,Graph,ObservationToken,Result,Runtime,StateId,Value};

#[derive(Clone,Debug,PartialEq,Eq)]
pub struct PublishedSnapshot {
    pub token: ObservationToken,
    pub states: Vec<(String,Value)>,
}
impl PublishedSnapshot {
    pub fn value(&self,name:&str)->Option<&Value> {
        self.states.iter().find(|(key,_)|key==name).map(|(_,value)|value)
    }
    fn capture(rt:&Runtime)->Result<Self>{
        if !rt.stable(){return Err("cannot publish unstable DOC graph".into());}
        let mut states=Vec::with_capacity(rt.graph.states.len());
        for (id,s) in rt.graph.states.iter().enumerate(){
            states.push((s.name.clone(),rt.value(id).ok_or("missing published value")?));
        }
        Ok(Self{token:rt.observation_token(),states})
    }
}

/// Exactly one authoritative host writer; arbitrary owned immutable readers.
/// Failed candidates and stale worker tokens never change the published Arc.
pub struct PublishedRuntime {
    writer:Mutex<Runtime>,
    current:RwLock<Arc<PublishedSnapshot>>,
}
impl PublishedRuntime {
    pub fn new(graph:Graph,workers:usize,cutoff:Cutoff)->Result<Self>{
        let mut rt=Runtime::new(graph,workers,cutoff);
        rt.stabilize()?;
        let snapshot=Arc::new(PublishedSnapshot::capture(&rt)?);
        Ok(Self{writer:Mutex::new(rt),current:RwLock::new(snapshot)})
    }
    pub fn read(&self)->Result<Arc<PublishedSnapshot>>{
        Ok(Arc::clone(&self.current.read()
            .map_err(|_|"published reader lock poisoned")?))
    }
    fn transact(&self,expected:ObservationToken,
        action:impl FnOnce(&mut Runtime)->Result<()>
    )->Result<ObservationToken>{
        let mut writer=self.writer.lock()
            .map_err(|_|"published writer lock poisoned")?;
        if writer.observation_token()!=expected{
            return Err("stale DOC candidate or writer token".into());
        }
        let mut candidate=writer.clone();
        action(&mut candidate)?;
        if !candidate.stable(){candidate.stabilize()?;}
        // Every result is independently owned and complete before any
        // publication lock is taken. A failure leaves BOTH structures intact.
        let next=Arc::new(PublishedSnapshot::capture(&candidate)?);
        let mut published=self.current.write()
            .map_err(|_|"published publication lock poisoned")?;
        *writer=candidate;
        *published=next;
        Ok(published.token)
    }
    pub fn update(&self,expected:ObservationToken,changes:&[(StateId,Value)])
        ->Result<ObservationToken>{
        self.transact(expected,|candidate|{
            candidate.update(changes)?;
            candidate.stabilize()
        })
    }
    pub fn replace_graph(&self,expected:ObservationToken,graph:Graph)
        ->Result<ObservationToken>{
        self.transact(expected,|candidate|candidate.replace_graph(graph))
    }
}
