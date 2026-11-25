//! Native DOC independence-driven CPU/GPU placement. Game source has NO
//! placement directives. Each ready frontier is partitioned by typed purity,
//! dynamic numeric range and a bounded GPU crossover grain. CPU is always
//! available. Software wgpu is strictly test-only via DOC_GPU_ALLOW_SOFTWARE.
//!
//! Current auto GPU computes only approved scalar expression *frontiers*;
//! non-scalar game logic and effect sources remain on CPU. Never claim a shader
//! used for presentation as GPU DOC computation.
use crate::{cpu_frontier_workers,Runtime};
#[cfg(feature="webgpu")]
use crate::{Graph,Result,State,StateId,Type,Value};
#[cfg(feature="webgpu")]
use crate::wgsl;
#[cfg(feature="webgpu")]
use std::collections::{HashMap,HashSet};

/// The minimum independent scalar lane batch for speculative GPU placement.
/// This is a fixed conservative crossover policy, not a GPU speed guarantee.
pub const AUTO_GPU_MIN_LANES:usize=64;

#[derive(Debug,Clone,Default,PartialEq,Eq)]
pub struct AutomaticStats {
    pub cpu_nodes:u64,
    pub gpu_nodes:u64,
    pub cpu_parallel_frontiers:u64,
    pub gpu_frontiers:u64,
    pub mixed_frontiers:u64,
    pub cpu_only_frontiers:u64,
}
#[derive(Debug)]
pub struct AutomaticScheduler {
    stats:AutomaticStats,
    gpu_kind:&'static str,
    #[cfg(feature="webgpu")]
    session:Option<crate::gpu::GpuSession>,
}
#[cfg(feature="webgpu")]
pub struct SelectedGpuFrontier {
    pub graph:Graph,
    pub outputs:Vec<(StateId,StateId)>,
    pub cpu:Vec<StateId>,
}
impl AutomaticScheduler {
    pub fn new()->Self {
        #[cfg(feature="webgpu")]
        let kind=if std::env::var("DOC_AUTO_DISABLE_GPU").as_deref()==Ok("1"){
            "none"
        }else{
            let instance=wgpu::Instance::default();
            let adapters=instance.enumerate_adapters(wgpu::Backends::all());
            if adapters.iter().any(|a|matches!(a.get_info().device_type,
                wgpu::DeviceType::DiscreteGpu|wgpu::DeviceType::IntegratedGpu)){
                "physical"
            }else if std::env::var("DOC_GPU_ALLOW_SOFTWARE").as_deref()==Ok("1") &&
                adapters.iter().any(|a|a.get_info().device_type==wgpu::DeviceType::Cpu){
                "software-test-only"
            }else{"none"}
        };
        #[cfg(not(feature="webgpu"))]
        let kind="none";
        eprintln!("DOC_AUTO_ADAPTER: gpu_kind={kind} policy=typed-independent-frontiers min_gpu_lanes={AUTO_GPU_MIN_LANES}");
        Self{stats:AutomaticStats::default(),gpu_kind:kind,
            #[cfg(feature="webgpu")]
            session:None,
        }
    }
    /// Initialize before scheduling work. A missing/unusable device at startup
    /// permits an explicitly reported CPU-only path; after dispatch starts,
    /// all failures remain fatal to the candidate frontier.
    #[cfg(feature="webgpu")]
    pub(crate) fn ensure_gpu(&mut self)->bool{
        if self.gpu_kind=="none"{return false;}
        if self.session.is_some(){return true;}
        match crate::gpu::GpuSession::new(){
            Ok(session)=>{
                self.gpu_kind=session.kind();
                eprintln!("DOC_AUTO_GPU_SESSION_CREATED: gpu_kind={} pipelines=0 cache=generated",self.gpu_kind);
                self.session=Some(session);
                true
            },
            Err(error)=>{
                eprintln!("DOC_AUTO_GPU_UNAVAILABLE: cpu-only reason={error}");
                self.gpu_kind="none";
                false
            }
        }
    }
    #[cfg(feature="webgpu")]
    pub(crate) fn run_gpu(&mut self,graph:&Graph)->Result<Vec<Value>>{
        let session=self.session.as_ref().ok_or("automatic GPU session missing")?;
        eprintln!("DOC_AUTO_GPU_SESSION_USED: gpu_kind={}",self.gpu_kind);
        if self.stats.gpu_frontiers>0{
            eprintln!("DOC_AUTO_GPU_SESSION_REUSED: gpu_kind={}",self.gpu_kind);
        }
        session.evaluate_frontier(graph)
    }
    pub fn stats(&self)->AutomaticStats{self.stats.clone()}
    pub fn gpu_kind(&self)->&'static str{self.gpu_kind}
    pub fn report(&self)->String {
        format!("DOC_AUTO_SUMMARY: gpu_kind={} cpu_nodes={} gpu_nodes={} cpu_parallel_frontiers={} cpu_only_frontiers={} gpu_frontiers={} mixed_frontiers={}",
            self.gpu_kind,self.stats.cpu_nodes,self.stats.gpu_nodes,
            self.stats.cpu_parallel_frontiers,self.stats.cpu_only_frontiers,
            self.stats.gpu_frontiers,self.stats.mixed_frontiers)
    }
    pub(crate) fn cpu_completed(&mut self,runtime:&Runtime,frontier:usize){
        self.stats.cpu_nodes+=frontier as u64;
        self.stats.cpu_only_frontiers+=1;
        let hardware=std::thread::available_parallelism().map_or(1,|x|x.get());
        let workers=cpu_frontier_workers(runtime.workers,hardware,frontier);
        if workers>1{self.stats.cpu_parallel_frontiers+=1;}
        eprintln!("DOC_AUTO_FRONTIER: cpu={} gpu=0 cpu_workers={} gpu_kind={} reason=small_or_ineligible",frontier,workers,self.gpu_kind);
    }
    pub(crate) fn mixed_completed(&mut self,cpu:usize,gpu:usize,cpu_parallel:bool){
        self.stats.cpu_nodes+=cpu as u64;
        self.stats.gpu_nodes+=gpu as u64;
        self.stats.gpu_frontiers+=1;
        if cpu_parallel{self.stats.cpu_parallel_frontiers+=1;}
        if cpu>0{self.stats.mixed_frontiers+=1;}
        eprintln!("DOC_AUTO_FRONTIER: cpu={cpu} gpu={gpu} gpu_kind={} placement=typed-independent",self.gpu_kind);
    }
    #[cfg(feature="webgpu")]
    fn scalar_eligible(&self,rt:&Runtime,id:StateId)->bool{
        let Some(state)=rt.graph.states.get(id) else {return false};
        let Some(def)=state.definition.as_ref() else{return false};
        if !matches!(state.kind,Type::Int|Type::Bool){return false;}
        if wgsl::validate_gpu_derived(&rt.graph,id).is_err() {return false;}
        let operations=wgsl::arithmetic_operation_count(&def.expr);
        let bound=if operations>1 {4}else{32767};
        // Full i64 cannot be transported through the portable i32 ABI.
        // Total scalar arithmetic requires even tighter pre-proved bounds.
        def.premises.iter().all(|&p|match rt.value(p){
            Some(Value::Bool(_))=>true,
            Some(Value::Int(n))=>i32::try_from(n).is_ok() &&
                (state.kind!=Type::Int || (-bound..=bound).contains(&n)),
            _=>false,
        })
    }
    #[cfg(feature="webgpu")]
    pub fn plan(&self,rt:&Runtime,ready:&[StateId])->Result<Option<SelectedGpuFrontier>>{
        if self.gpu_kind=="none" || ready.len()<AUTO_GPU_MIN_LANES{
            return Ok(None);
        }
        let selected=ready.iter().copied().filter(|&id|self.scalar_eligible(rt,id))
            .collect::<Vec<_>>();
        if selected.len()<AUTO_GPU_MIN_LANES{return Ok(None);}
        let gpu_ids:HashSet<_>=selected.iter().copied().collect();
        let cpu=ready.iter().copied().filter(|id|!gpu_ids.contains(id)).collect();
        let mut inputs=HashMap::<StateId,StateId>::new();
        let mut states=Vec::<State>::new();
        for &id in &selected{
            let d=rt.graph.states[id].definition.as_ref()
                .ok_or("automatic placement requires a derived state")?;
            for &premise in &d.premises{
                if !inputs.contains_key(&premise){
                    let value=rt.value(premise).ok_or("automatic placement missing settled premise")?;
                    let local=states.len();
                    states.push(State::source(format!("auto_premise_{premise}"),value));
                    inputs.insert(premise,local);
                }
            }
        }
        let mut outputs=Vec::with_capacity(selected.len());
        for id in selected{
            let s=&rt.graph.states[id];
            let d=s.definition.as_ref().ok_or("automatic placement missing definition")?;
            let premises=d.premises.iter().map(|p|inputs[p]).collect();
            let local=states.len();
            states.push(State::derived(format!("auto_derived_{id}"),s.kind,premises,d.expr.clone()));
            outputs.push((id,local));
        }
        let graph=Graph::new(states)?;
        Ok(Some(SelectedGpuFrontier{graph,outputs,cpu}))
    }
}
impl Default for AutomaticScheduler {fn default()->Self{Self::new()}}


#[cfg(all(test,feature="webgpu"))]
mod device_loss_tests{
    use super::*;
    use crate::Cutoff;
    #[test]
    fn real_webgpu_device_invalidation_rejects_mixed_frontier(){
        if std::env::var("DOC_GPU_DEVICE_LOSS_TEST").as_deref()!=Ok("1"){return;}
        let mut source=String::from("source x: int = 1\nsource xs: ints = [1]\nderive cpu_len: int (xs) = len(xs)\n");
        for i in 0..128{source.push_str(&format!("derive lane_{i}: int (x) = add(x,1)\n"));}
        let graph=Graph::parse(&source).unwrap();
        let mut runtime=Runtime::new(graph,4,Cutoff::Exact);
        let mut scheduler=AutomaticScheduler::new();
        runtime.stabilize_automatic(&mut scheduler).unwrap();
        assert_eq!(scheduler.stats().gpu_nodes,128,"actual initial GPU dispatch required");
        assert_eq!(scheduler.stats().mixed_frontiers,1);
        let kind=scheduler.gpu_kind();
        let x=runtime.graph.id("x").unwrap();
        let xs=runtime.graph.id("xs").unwrap();
        runtime.update(&[(x,Value::Int(2)),(xs,Value::Ints(vec![1,2]))]).unwrap();
        let before=runtime.snapshot();
        let ready=runtime.ready();
        let stats=scheduler.stats();
        scheduler.session.as_ref().expect("live admitted session").destroy_device_for_test();
        let error=runtime.step_automatic(&mut scheduler).unwrap_err();
        assert!(error.contains("DOC_GPU_DEVICE_LOST"),"{error}");
        assert_eq!(runtime.snapshot(),before);
        assert_eq!(runtime.ready(),ready);
        assert_eq!(scheduler.stats(),stats);
        assert_eq!(scheduler.gpu_kind(),kind,"no CPU fallback on a selected lost device");
        println!("DOC_WEBGPU_DEVICE_INVALIDATION_PASS: adapter={kind} prior_gpu_lanes=128 no_publication=true");
    }
}
