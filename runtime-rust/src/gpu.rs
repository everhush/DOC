//! Fail-closed, program-defined DOC Boolean/integer DAG GPU evaluator.
//!
//! Every derived state is dispatched through Rust wgpu. The host is allowed
//! to parse inputs, upload values, order graph stages, read back and publish;
//! it never computes a claimed GPU-derived state on CPU. The implementation
//! deliberately refuses DOC constructs it cannot yet evaluate faithfully:
//! i64 outside portable i32, unproved arithmetic, effects, recurrence,
//! graph replacement, non-Boolean outputs and non-total expressions.
//!
//! This is an incremental general-source GPU path, not complete DOC GPU
//! coverage and not a substitute for the independent Goose SDL3 backend.
use crate::{wgsl, Graph, Result, StateId, Type, Value,gpu_health::DeviceHealth};
use std::sync::Mutex;
use std::collections::VecDeque;
use std::collections::HashSet;
use wgpu::util::DeviceExt;

#[derive(Debug)]
struct Prepared {
    values: Vec<Option<Value>>,
    stages: Vec<StateId>,
}

/// Check every possible failure of source eligibility before device dispatch.
/// No candidate state is published until all GPU stages complete.
fn prepare(graph: &Graph, changes: &[(StateId, Value)]) -> Result<Prepared> {
    prepare_with_policy(graph,changes,true)
}

/// The automatic executor submits only a single antichain with materialized
/// source premises. Strict standalone GPU admission remains unchanged.
/// Unlike the whole-graph strict policy, an unrelated wide premise for a
/// comparison must not disqualify a separate, bounded arithmetic definition.
fn prepare_with_policy(graph: &Graph, changes: &[(StateId, Value)], strict_all_sources:bool) -> Result<Prepared> {
    let mut values: Vec<Option<Value>> = graph.states.iter().map(|state| {
        if state.definition.is_none() { state.initial.clone() } else { None }
    }).collect();
    let mut updated = HashSet::new();
    for (id, value) in changes {
        let state = graph.states.get(*id).ok_or("DOC_GPU_UNSUPPORTED: unknown source id")?;
        if state.definition.is_some() {
            return Err("DOC_GPU_UNSUPPORTED: cannot set a derived state".into());
        }
        if state.kind != value.kind() {
            return Err("DOC_GPU_UNSUPPORTED: source type mismatch".into());
        }
        if !updated.insert(*id) {
            return Err("DOC_GPU_UNSUPPORTED: duplicate source update".into());
        }
        values[*id] = Some(value.clone());
    }
    for (state, value) in graph.states.iter().zip(values.iter()) {
        if state.definition.is_none() {
            let value = value.as_ref().ok_or("DOC_GPU_UNSUPPORTED: missing source value")?;
            match value {
                Value::Bool(_) => {}
                Value::Int(n) if i32::try_from(*n).is_ok() => {}
                Value::Int(_) => return Err(
                    "DOC_GPU_UNSUPPORTED: full DOC i64 source requires wide-integer GPU transport".into()),
                _ => return Err(
                    "DOC_GPU_UNSUPPORTED: GPU Boolean-DAG path currently supports only bool/i32 source types".into()),
            }
        }
    }
    let has_integer_computation = graph.states.iter().any(|s|
        s.definition.is_some() && s.kind == Type::Int);
    let has_nested_integer_computation = graph.states.iter().any(|s|
        s.kind == Type::Int && s.definition.as_ref().is_some_and(|d|
            wgsl::arithmetic_operation_count(&d.expr) > 1));
    // Ahead of all GPU dispatch, source admission must be conservative if
    // the authored program contains any derived arithmetic. Dependent
    // intermediate values are checked again before *their* GPU stages.
    if strict_all_sources && has_integer_computation {
        for (state, candidate) in graph.states.iter().zip(values.iter()) {
            if state.definition.is_none() {
                if let Some(Value::Int(value)) = candidate {
                    // Validate all source inputs before dispatch; nested
                    // expressions require the stronger 4^13 proof bound.
                    let bound = if has_nested_integer_computation {4} else {32767};
                    if !(-bound..=bound).contains(value) {
                        return Err("DOC_GPU_UNSUPPORTED: safe i32 arithmetic source range exceeded".into());
                    }
                }
            }
        }
    }
    let mut stages = Vec::new();
    for &id in &graph.topo {
        let state = graph.states.get(id).ok_or("DOC_GPU_UNSUPPORTED: invalid topological state")?;
        if let Some(definition)=&state.definition {
            if !strict_all_sources {
                // The projected graph must really be ONE ready frontier, not
                // an arbitrary graph requesting relaxed source-range admission.
                for &premise in &definition.premises{
                    if graph.states[premise].definition.is_some(){
                        return Err("DOC_GPU_UNSUPPORTED: automatic projection has a derived premise".into());
                    }
                    if state.kind==Type::Int{
                        if let Some(Value::Int(n))=&values[premise]{
                            let bound=if wgsl::arithmetic_operation_count(&definition.expr)>1{4}else{32767};
                            if !(-bound..=bound).contains(n){
                                return Err("DOC_GPU_UNSUPPORTED: automatic integer premise exceeds proved range".into());
                            }
                        }
                    }
                }
            }
            // Strict admission: no unsupported stages are silently run on CPU.
            wgsl::validate_gpu_derived(graph,id)
                .map_err(|e|format!("DOC_GPU_UNSUPPORTED: {}: {e}",state.name))?;
            stages.push(id);
        }
    }
    if stages.is_empty() {
        return Err("DOC_GPU_UNSUPPORTED: no DOC derived computation to dispatch".into());
    }
    Ok(Prepared { values, stages })
}

/// Evaluate an eligible, acyclic and strictly pure DOC Boolean graph on a
/// physically identified GPU adapter. Returns a private complete snapshot;
/// the CLI prints it only after successful final GPU readback.
/// Separate the actual physical WebGPU class from optional correctness
/// testing. The latter can NEVER be used to sign physical device evidence.
fn adapter_admission(device_type:wgpu::DeviceType,allow_software:bool)->(bool,bool){
    let physical=matches!(device_type,
        wgpu::DeviceType::DiscreteGpu | wgpu::DeviceType::IntegratedGpu);
    let software_test=device_type==wgpu::DeviceType::Cpu && allow_software;
    (physical,software_test)
}

/// Reusable device/pipeline across successive automatically placed game epochs.
/// A fresh private buffer set is created for each independent ready frontier.
pub struct GpuSession {
    device:wgpu::Device,
    queue:wgpu::Queue,
    pipelines:Mutex<VecDeque<(String,wgpu::ComputePipeline)>>,
    kernel_threads:u32,
    kind:&'static str,
    health:DeviceHealth,
}
impl std::fmt::Debug for GpuSession {
    fn fmt(&self,f:&mut std::fmt::Formatter<'_>)->std::fmt::Result{
        f.write_str("GpuSession(WebGPU resource ownership)")
    }
}
impl GpuSession {
    pub fn new()->Result<Self>{pollster::block_on(Self::init_async())}
    pub fn evaluate(&self,graph:&Graph,changes:&[(StateId,Value)])->Result<Vec<Value>>{
        let candidate=prepare(graph,changes)?;
        pollster::block_on(self.evaluate_prepared_async(graph,candidate))
    }
    pub(crate) fn evaluate_frontier(&self,graph:&Graph)->Result<Vec<Value>>{
        let candidate=prepare_with_policy(graph,&[],false)?;
        pollster::block_on(self.evaluate_prepared_async(graph,candidate))
    }
    pub(crate) fn kind(&self)->&'static str{self.kind}
    #[cfg(test)]
    pub(crate) fn destroy_device_for_test(&self){self.device.destroy();self.device.poll(wgpu::Maintain::Wait);}
    async fn init_async()->Result<Self>{
    // WebGPU owns native graphics API selection. DOC neither names nor
    // requires a particular backend API: only the requested GPU capability,
    // adapter class and device limits are part of the execution contract.
    let instance=wgpu::Instance::default();
    // Ask wgpu itself for the adapters it can use, without selecting or
    // inspecting any of its native graphics APIs. A CPU adapter must not mask
    // a real GPU when the user explicitly selected --backend=gpu.
    let adapters = instance.enumerate_adapters(wgpu::Backends::all());
    let allow_software=std::env::var("DOC_GPU_ALLOW_SOFTWARE").as_deref()==Ok("1");
    for candidate in &adapters {
        let info=candidate.get_info();
        eprintln!("DOC_WEBGPU_AVAILABLE_ADAPTER: name={} type={:?}",
            info.name,info.device_type);
    }
    let adapter=adapters.iter().position(|candidate|matches!(
        candidate.get_info().device_type,
        wgpu::DeviceType::DiscreteGpu | wgpu::DeviceType::IntegratedGpu
    )).or_else(|| if allow_software {
        adapters.iter().position(|candidate|
            candidate.get_info().device_type==wgpu::DeviceType::Cpu)
    } else {None})
        .and_then(|index|adapters.into_iter().nth(index))
        .ok_or("DOC_GPU_HARDWARE_UNAVAILABLE: wgpu exposes no eligible physical GPU adapter")?;
    let info = adapter.get_info();
    // Physical GPU admission is derived ONLY from the WebGPU adapter class,
    // never vendor IDs, native backend strings, external environment or driver
    // installation. Software execution is a separately labeled CI-only path.
    let (physical,software_test)=adapter_admission(
        info.device_type,
        std::env::var("DOC_GPU_ALLOW_SOFTWARE").as_deref()==Ok("1"));
    if !physical && !software_test {
        return Err(format!(
            "DOC_GPU_HARDWARE_UNAVAILABLE: software or unverified adapter: {:?}",
            info.device_type
        ));
    }
    if software_test {
        eprintln!("DOC_GPU_SOFTWARE_TEST_ONLY: WebGPU CPU adapter; not physical GPU evidence");
    }
    let (device, queue) = adapter
        .request_device(&wgpu::DeviceDescriptor::default(), None).await
        .map_err(|e| format!("DOC_GPU_DEVICE_FAILURE: {e}"))?;
    let limits = device.limits();
    if limits.max_storage_buffer_binding_size < 4 {
        return Err("DOC_GPU_UNSUPPORTED: device does not support four-byte storage bindings".into());
    }
    eprintln!(
        "DOC_GPU_SELECTED_DEVICE: name={} type={:?} vendor={} device={}",
        info.name, info.device_type, info.vendor, info.device
    );
    // Device-specific workgroup width; compile only the typed ready
    // frontiers actually used. No instruction interpreter on the GPU.
    let max_threads=limits.max_compute_invocations_per_workgroup.min(limits.max_compute_workgroup_size_x);
    if max_threads==0||limits.max_compute_workgroups_per_dimension==0{
        return Err("DOC_GPU_UNSUPPORTED: device has no compute workgroup capacity".into());
    }
    let kernel_threads=max_threads.min(64);
    eprintln!("DOC_GPU_GENERATED_SESSION_CREATED: cache_capacity=32");
    let health=DeviceHealth::attach(&device);
    Ok(Self{device,queue,pipelines:Mutex::new(VecDeque::new()),kernel_threads,kind:if physical{"physical"}else{"software-test-only"},health})
    }
    async fn evaluate_prepared_async(&self,graph:&Graph,mut candidate:Prepared)->Result<Vec<Value>>{
        self.health.check()?;
        let device=&self.device;
        let queue=&self.queue;
        let kernel_threads=self.kernel_threads;
        let limits=self.device.limits();
    // A ready frontier may be scheduled as GPU lanes because its premises
    // were committed by earlier frontiers. Never calculate derived results
    // on the host. All values stay private until every GPU pass succeeds.
    let injected_stage=std::env::var("DOC_GPU_INJECT_FAILURE_STAGE")
        .ok().map(|value|value.parse::<usize>()).transpose()
        .map_err(|_|"DOC_GPU_INJECTION_INVALID: expected nonnegative stage index")?;
    // Reuse the validated dynamic GPU workgroup width for all frontier
    // chunks and enforce the actual per-dimension dispatch limit.
    // Bound generated shader size and packed premise/result buffers.
    // Chunking is a resource policy, not a cap on total ready work.
    let max_ready=(u64::from(limits.max_storage_buffer_binding_size)/16)
        .min(u64::from(limits.max_compute_workgroups_per_dimension)
            .saturating_mul(u64::from(kernel_threads)))
        .min(256) as usize;
    if max_ready==0 {
        return Err("DOC_GPU_UNSUPPORTED: insufficient device frontier capacity".into());
    }
    let mut pending=candidate.stages;
    let mut stage_index=0usize;
    while !pending.is_empty() {
        let ready:Vec<_>=pending.iter().filter_map(|id| {
            let d=graph.states[*id].definition.as_ref()?;
            d.premises.iter().all(|p|candidate.values[*p].is_some()).then_some(*id)
        }).collect();
        if ready.is_empty() {
            return Err("DOC_GPU_UNSUPPORTED: no dependency-ready GPU frontier".into());
        }
        for ids in ready.chunks(max_ready) {
            self.health.check()?;
            if injected_stage.is_some_and(|n|
                n>=stage_index && n<stage_index+ids.len()) {
                let n=injected_stage.expect("checked");
                return Err(format!(
                    "DOC_GPU_INJECTED_STAGE_FAILURE: stage={n}; no graph publication"));
            }
            let mut inputs:Vec<i32>=Vec::new();
            for &id in ids {
                let state=&graph.states[id];
                let definition=state.definition.as_ref().ok_or("DOC_GPU_UNSUPPORTED: missing derived-state definition")?;
                wgsl::validate_gpu_derived(graph,id)?;
                for &premise in &definition.premises {
                    let value=candidate.values.get(premise)
                        .and_then(Option::as_ref).ok_or(
                        "DOC_GPU_UNSUPPORTED: unsatisfied dependent frontier")?;
                    let word=match value {
                        Value::Bool(b)=>i32::from(*b),
                        Value::Int(n)=>{
                            if state.kind==Type::Int {
                                let ops=wgsl::arithmetic_operation_count(&definition.expr);
                                let bound=if ops>1 {4}else{32767};
                                if !(-bound..=bound).contains(n) {
                                    return Err("DOC_GPU_UNSUPPORTED: dependent numeric premise exceeds proved range".into());
                                }
                            }
                            i32::try_from(*n).map_err(|_|
                                "DOC_GPU_UNSUPPORTED: full i64 is not portable in WGSL")?
                        }
                        _=>return Err("DOC_GPU_UNSUPPORTED: non-scalar frontier premise".into()),
                    };
                    inputs.push(word);
                }
                if definition.premises.is_empty() {inputs.push(0);}
            }
            let inputs=inputs.iter().flat_map(|v|v.to_le_bytes()).collect::<Vec<_>>();
            let max_binding=u64::from(limits.max_storage_buffer_binding_size);
            if inputs.is_empty()||inputs.len() as u64>max_binding||(ids.len() as u64).saturating_mul(4)>max_binding{
                return Err("DOC_GPU_UNSUPPORTED: device storage-buffer binding limit exceeded".into());
            }
            let workgroup_size=kernel_threads;
            let workgroups=(u32::try_from(ids.len()).map_err(|_|
                "DOC_GPU_UNSUPPORTED: too many GPU-ready lanes")?)
                .div_ceil(workgroup_size);
            if workgroups>limits.max_compute_workgroups_per_dimension {
                return Err("DOC_GPU_UNSUPPORTED: GPU ready frontier exceeds workgroup limit".into());
            }
            let shader=wgsl::lower_parallel_frontier(graph,ids,kernel_threads)?;
            if shader.len()>1024*1024{return Err("DOC_GPU_UNSUPPORTED: generated shader budget exceeded".into());}
            // Full source equality is the cache key: no hash collision,
            // graph identity, or runtime-value specialization can reuse the
            // wrong program. Hold the device-local owner until readback ends.
            let output={
                let mut cache=self.pipelines.lock().map_err(|_|"DOC_GPU_PIPELINE_FAILURE: poisoned cache")?;
                let entry=if let Some(index)=cache.iter().position(|(source,_)|source==&shader){
                    eprintln!("DOC_GPU_GENERATED_PIPELINE_REUSED: lanes={}",ids.len());
                    cache.remove(index).expect("located cache entry")
                }else{
                    device.push_error_scope(wgpu::ErrorFilter::Validation);
                    let module=device.create_shader_module(wgpu::ShaderModuleDescriptor{
                        label:Some("Generated DOC typed frontier"),source:wgpu::ShaderSource::Wgsl(shader.as_str().into()),
                    });
                    let pipeline=device.create_compute_pipeline(&wgpu::ComputePipelineDescriptor{
                        label:Some("Generated DOC compute"),layout:None,module:&module,entry_point:Some("main"),
                        compilation_options:Default::default(),cache:None,
                    });
                    if let Some(error)=device.pop_error_scope().await{return Err(format!("DOC_GPU_PIPELINE_FAILURE: {error}"));}
                    self.health.check()?;
                    eprintln!("DOC_GPU_GENERATED_PIPELINE_CREATED: lanes={} source_bytes={}",ids.len(),shader.len());
                    (shader,pipeline)
                };
                let result=dispatch_frontier(device,queue,&entry.1,&inputs,ids.len(),workgroups,&self.health).await;
                if cache.len()==32{cache.pop_front();}
                cache.push_back(entry);
                result?
            };
            if output.len()!=ids.len() {
                return Err("DOC_GPU_READBACK_FAILURE: incomplete frontier readback".into());
            }
            // Validate ALL typed GPU results before this frontier is made
            // available to subsequent dependency levels.
            let mut typed=Vec::with_capacity(ids.len());
            for (&id,&word) in ids.iter().zip(output.iter()) {
                let v=match graph.states[id].kind {
                    Type::Bool=>match word {
                        0=>Value::Bool(false),
                        1=>Value::Bool(true),
                        _=>return Err("DOC_GPU_RESULT_INVALID: noncanonical Boolean".into()),
                    },
                    Type::Int=>Value::Int(i64::from(word as i32)),
                    _=>return Err("DOC_GPU_UNSUPPORTED: unsupported result kind".into()),
                };
                typed.push(v);
            }
            for (&id,value) in ids.iter().zip(typed.into_iter()) {
                candidate.values[id]=Some(value);
            }
            eprintln!("DOC_RUST_GPU_FRONTIER_DISPATCH: states={} workgroups={} workgroup_size={}",
                ids.len(),workgroups,workgroup_size);
            stage_index+=ids.len();
        }
        let complete:HashSet<_>=ready.into_iter().collect();
        pending.retain(|id|!complete.contains(id));
    }
    self.health.check()?;
    candidate.values.into_iter().map(|value|value.ok_or_else(|| {
        "DOC_GPU_INCOMPLETE: no partial graph publication".into()
    })).collect()
}
}

/// Strict one-shot GPU evaluation preserves fail-closed explicit backend mode.
pub fn evaluate(graph:&Graph,changes:&[(StateId,Value)])->Result<Vec<Value>> {
    let candidate=prepare(graph,changes)?;
    pollster::block_on(async{
        let session=GpuSession::init_async().await?;
        session.evaluate_prepared_async(graph,candidate).await
    })
}

/// Dispatch specialized generated DOC WGSL through a device-local cached pipeline. A new private bind group owns every frontier:
/// no stale result, graph generation or caller can observe an incomplete
/// output. Device failure returns an error BEFORE publication.
async fn dispatch_frontier(
    device:&wgpu::Device,queue:&wgpu::Queue,pipeline:&wgpu::ComputePipeline,
    inputs:&[u8],
    lanes:usize,workgroups:u32,health:&DeviceHealth,
)->Result<Vec<u32>> {
    health.check()?;
    let nbytes=(lanes as u64).checked_mul(4)
        .ok_or("DOC_GPU_UNSUPPORTED: result buffer overflow")?;
    device.push_error_scope(wgpu::ErrorFilter::Validation);
    let input_buffer=device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
        label:Some("DOC source premises - private frontier"),
        contents:inputs,usage:wgpu::BufferUsages::STORAGE,
    });
    let output=device.create_buffer(&wgpu::BufferDescriptor {
        label:Some("DOC private ready-frontier output"),
        size:nbytes,usage:wgpu::BufferUsages::STORAGE|wgpu::BufferUsages::COPY_SRC,
        mapped_at_creation:false,
    });
    let readback=device.create_buffer(&wgpu::BufferDescriptor {
        label:Some("DOC atomic frontier readback"),
        size:nbytes,usage:wgpu::BufferUsages::COPY_DST|wgpu::BufferUsages::MAP_READ,
        mapped_at_creation:false,
    });
    let input_bind=device.create_bind_group(&wgpu::BindGroupDescriptor{
        label:Some("DOC generated frontier bindings"),layout:&pipeline.get_bind_group_layout(0),
        entries:&[wgpu::BindGroupEntry{binding:0,resource:input_buffer.as_entire_binding()},
                  wgpu::BindGroupEntry{binding:1,resource:output.as_entire_binding()}],
    });
    let mut encoder=device.create_command_encoder(&wgpu::CommandEncoderDescriptor {
        label:Some("DOC generated WGSL frontier dispatch"),
    });
    {
        let mut pass=encoder.begin_compute_pass(&wgpu::ComputePassDescriptor{
            label:Some("DOC generated frontier - GPU only"),
            timestamp_writes:None,
        });
        pass.set_pipeline(pipeline);
        pass.set_bind_group(0,&input_bind,&[]);
        pass.dispatch_workgroups(workgroups,1,1);
    }
    encoder.copy_buffer_to_buffer(&output,0,&readback,0,nbytes);
    queue.submit(Some(encoder.finish()));
    if let Some(error)=device.pop_error_scope().await {
        return Err(format!("DOC_GPU_DISPATCH_FAILURE: {error}"));
    }
    health.check()?;
    let (tx,rx)=std::sync::mpsc::channel();
    readback.slice(..).map_async(wgpu::MapMode::Read,move |result| {
        let _=tx.send(result);
    });
    device.poll(wgpu::Maintain::Wait);
    health.check()?;
    rx.try_recv().map_err(|_|"DOC_GPU_READBACK_FAILURE: missing completed callback")?
        .map_err(|e|format!("DOC_GPU_READBACK_FAILURE: {e}"))?;
    let mapped=readback.slice(..).get_mapped_range();
    let values=mapped.chunks_exact(4).map(|v|
        u32::from_le_bytes(v.try_into().expect("four-byte GPU word"))).collect();
    drop(mapped);
    readback.unmap();
    health.check()?;
    Ok(values)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn physical_webgpu_admission_never_accepts_a_software_or_virtual_device() {
        use wgpu::DeviceType::*;
        for class in [DiscreteGpu,IntegratedGpu] {
            assert_eq!(adapter_admission(class,false),(true,false));
            assert_eq!(adapter_admission(class,true),(true,false));
        }
        for class in [Cpu,VirtualGpu,Other] {
            let (physical,software)=adapter_admission(class,false);
            assert!(!physical && !software);
            let (physical,software)=adapter_admission(class,true);
            assert!(!physical);
            assert_eq!(software,class==Cpu,
                "only a WebGPU CPU adapter may run opt-in software correctness tests");
        }
    }
    #[test]
    fn eligible_multi_stage_boolean_graph_preflights_without_gpu() {
        let graph = Graph::parse(concat!(
            "source a: bool = true\n",
            "source b: bool = false\n",
            "derive chosen: bool (a,b) = if(eq(a,b),true,eq(a,false))\n",
            "derive verified: bool (chosen,b) = eq(chosen,b)\n",
        )).unwrap();
        let plan = prepare(&graph, &[]).unwrap();
        assert_eq!(plan.stages.len(), 2);
        assert_eq!(plan.stages[0], graph.id("chosen").unwrap());
        assert_eq!(plan.stages[1], graph.id("verified").unwrap());
    }
    #[test]
    fn auto_frontier_numeric_proof_is_per_definition_not_whole_graph(){
        let graph=Graph::parse(concat!(
            "source small: int = 2\n",
            "source wide: int = 40000\n",
            "derive small_product: int (small) = mul(add(small,1),2)\n",
            "derive wide_compare: bool (wide) = eq(wide,40000)\n",
        )).unwrap();
        assert!(prepare(&graph,&[]).is_err(),"explicit strict GPU contract must not change");
        assert!(prepare_with_policy(&graph,&[],false).is_ok(),
                "unrelated wide i32 comparison must not poison safe arithmetic");
        assert!(prepare_with_policy(&graph,&[(graph.id("small").unwrap(),Value::Int(5))],false).is_err());
        let dependent=Graph::parse(concat!(
            "source a: int = 2\n",
            "derive sum: int (a) = add(a,1)\n",
            "derive again: int (sum) = add(sum,1)\n",
        )).unwrap();
        assert!(prepare_with_policy(&dependent,&[],false).is_err(),
                "only a materialized single frontier can use the automatic policy");
    }
    #[test]
    fn eligibility_refuses_wide_int_and_derived_arithmetic() {
        let graph = Graph::parse(concat!(
            "source a: int = 0\n",
            "source b: int = 2\n",
            "derive choice: bool (a,b) = lt(a,b)\n",
        )).unwrap();
        assert!(prepare(&graph, &[(graph.id("a").unwrap(), Value::Int(i64::MAX))]).is_err());
        let accepted = prepare(&graph, &[
            (graph.id("a").unwrap(), Value::Int(i32::MIN.into())),
            (graph.id("b").unwrap(), Value::Int(i32::MAX.into())),
        ]).unwrap();
        assert_eq!(accepted.stages.len(), 1);
        assert!(prepare(&graph, &[
            (graph.id("a").unwrap(), Value::Int(1)),
            (graph.id("a").unwrap(), Value::Int(2)),
        ]).is_err());
    }
    #[test]
    fn admits_supported_numeric_computation_without_cpu_fallback() {
        let graph = Graph::parse(include_str!("../examples/gpu_arithmetic_chain.doc")).unwrap();
        let plan=prepare(&graph, &[]).unwrap();
        assert_eq!(plan.stages.len(),4);
        assert_eq!(plan.stages[0],graph.id("sum").unwrap());
        assert_eq!(plan.stages[1],graph.id("twice").unwrap());
        assert_eq!(plan.stages[2],graph.id("diff").unwrap());
        assert_eq!(plan.stages[3],graph.id("chosen").unwrap());
        assert!(prepare(&graph, &[(graph.id("a").unwrap(),Value::Int(32768))]).is_err());
    }
    #[test]
    fn nested_arithmetic_preflight_rejects_unproved_inputs() {
        let graph=Graph::parse(include_str!("../examples/gpu_nested_arithmetic.doc")).unwrap();
        let plan=prepare(&graph,&[]).unwrap();
        assert_eq!(plan.stages.len(),4);
        assert!(prepare(&graph, &[
            (graph.id("a").unwrap(),Value::Int(5))]).is_err());
        assert!(prepare(&graph, &[
            (graph.id("a").unwrap(),Value::Int(-5))]).is_err());
    }
}
