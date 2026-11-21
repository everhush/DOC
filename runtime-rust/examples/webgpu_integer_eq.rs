//! Executes a DOC-derived signed-integer equality on WebGPU.
//! DOC Int is i64. The host MUST prove every input fits portable WGSL i32.
//! This example checks CPU and GPU results over two source-repair episodes.
//! A software Vulkan adapter validates dispatch, NOT physical acceleration.
use doc_runtime::{wgsl, Cutoff, Graph, Runtime, Value};
use std::{error::Error, time::Instant};
use wgpu::util::DeviceExt;

fn checked_i32_words(input: &[i64]) -> Result<Vec<u32>, Box<dyn Error>> {
    if input.is_empty() { return Err("signed GPU batch cannot be empty".into()); }
    input.iter().map(|&value| {
        let narrow = i32::try_from(value)
            .map_err(|_| "DOC i64 outside i32 WebGPU eligibility range")?;
        Ok(narrow as u32)
    }).collect()
}
fn bytes(input: &[u32]) -> Vec<u8> {
    input.iter().flat_map(|v| v.to_le_bytes()).collect()
}
fn input_for(index: usize, epoch: usize) -> (i64, i64) {
    let a = match index % 9 {
        0 => i64::from(i32::MIN),
        1 => i64::from(i32::MAX),
        2 => -1,
        3 => 0,
        4 => 1,
        5 => 5,
        6 => -934,
        7 => 65_536,
        _ => -19_000,
    };
    let a = if epoch == 0 { a } else {
        match index % 3 {
            0 => 0, 1 => a, _ => a.saturating_neg()
        }
    };
    let b = match index % 4 {
        0 => a,
        1 => a.checked_add(1).filter(|v| i32::try_from(*v).is_ok()).unwrap_or(-1),
        2 => a.checked_sub(1).filter(|v| i32::try_from(*v).is_ok()).unwrap_or(1),
        _ => if a == i64::from(i32::MIN) { i64::from(i32::MAX) } else { -a },
    };
    (a,b)
}
fn main() -> Result<(), Box<dyn Error>> {
    pollster::block_on(run())
}
async fn run() -> Result<(), Box<dyn Error>> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let file = match args.as_slice() {
        [] => None,
        [flag, path] if flag == "--shader" => Some(path.as_str()),
        _ => return Err("usage: webgpu_integer_eq [--shader GENERATED.wgsl]".into()),
    };
    let count: usize = std::env::var("DOC_GPU_LANES")
        .unwrap_or_else(|_| "130".into()).parse()?;
    if !(1..=4096).contains(&count) { return Err("invalid signed GPU batch size".into()); }
    let forced_cpu = std::env::var("DOC_GPU_EXECUTION").unwrap_or_else(|_| "gpu".into());
    if forced_cpu != "gpu" && forced_cpu != "cpu" {
        return Err("DOC_GPU_EXECUTION must be gpu or cpu".into());
    }
    let require_hardware = std::env::var("DOC_GPU_REQUIRE_HARDWARE")
        .unwrap_or_else(|_| "0".into()) == "1";
    if require_hardware && forced_cpu != "gpu" {
        return Err("hardware-GPU requirement excludes CPU fallback".into());
    }
    let graph = Graph::parse(include_str!("integer_equality.doc"))?;
    let target = graph.id("equal").ok_or("missing integer equality")?;
    let a_id = graph.id("a").ok_or("missing a")?;
    let b_id = graph.id("b").ok_or("missing b")?;
    let shader = match file {
        Some(path) => std::fs::read_to_string(path)?,
        None => wgsl::lower_bool_derived(&graph, target)?,
    };
    let mut cpus: Vec<Runtime> = (0..count)
        .map(|_| Runtime::new(graph.clone(), 1, Cutoff::Exact))
        .collect();
    let mut epochs = Vec::new();
    for epoch in 0..2 {
        let started=Instant::now();
        let mut aa=Vec::with_capacity(count);
        let mut bb=Vec::with_capacity(count);
        let mut expected=Vec::with_capacity(count);
        for (lane,runtime) in cpus.iter_mut().enumerate() {
            let (a,b)=input_for(lane,epoch);
            aa.push(a);bb.push(b);
            runtime.update(&[(a_id,Value::Int(a)),(b_id,Value::Int(b))])?;
            runtime.stabilize()?;
            expected.push(u32::from(runtime.value(target)==Some(Value::Bool(true))));
        }
        if std::env::var("DOC_GPU_INJECT_INT_OUT_OF_RANGE").as_deref()==Ok("1") {
            aa[0]=i64::from(i32::MAX)+1;
        }
        // Refuse malformed host values BEFORE allocating GPU buffers or
        // claiming any eligible GPU result.
        let aa=checked_i32_words(&aa)?;
        let bb=checked_i32_words(&bb)?;
        println!("DOC_SIGNED_CPU_REFERENCE_MS: epoch={epoch} value_ms={:.3}",
            started.elapsed().as_secs_f64()*1000.0);
        epochs.push((aa,bb,expected));
    }
    if forced_cpu == "cpu" {
        for (epoch,(_,_,expected)) in epochs.iter().enumerate() {
            println!("DOC_SIGNED_CPU_ONLY_PASS: epoch={epoch} lanes={count} equals={}",
                expected.iter().sum::<u32>());
        }
        return Ok(());
    }
    let instance=wgpu::Instance::new(&wgpu::InstanceDescriptor {
        backends:wgpu::Backends::VULKAN,..Default::default()
    });
    let adapter=instance.request_adapter(&wgpu::RequestAdapterOptions {
        power_preference:wgpu::PowerPreference::HighPerformance,
        ..Default::default()
    }).await.ok_or("No WebGPU Vulkan device for signed integer test")?;
    let info=adapter.get_info();
    if require_hardware && !matches!(info.device_type,
        wgpu::DeviceType::DiscreteGpu | wgpu::DeviceType::IntegratedGpu) {
        return Err("signed DOC hardware gate rejected software adapter".into());
    }
    println!("DOC_SIGNED_WEBGPU_ADAPTER: {} type={:?} backend={:?} driver={}",
        info.name,info.device_type,info.backend,info.driver);
    let (device,queue)=adapter.request_device(&wgpu::DeviceDescriptor::default(),None).await?;
    let nbytes=u64::try_from(count)?.checked_mul(4).ok_or("input byte count overflow")?;
    let limits=device.limits();
    if nbytes>u64::from(limits.max_storage_buffer_binding_size) ||
        (count.div_ceil(64) as u32)>limits.max_compute_workgroups_per_dimension {
        return Err("signed DOC batch exceeds WebGPU device limits".into());
    }
    let workgroups=u32::try_from(count.div_ceil(64))?;
    device.push_error_scope(wgpu::ErrorFilter::Validation);
    let module=device.create_shader_module(wgpu::ShaderModuleDescriptor {
        label:Some("DOC independently lowered signed equality"),
        source:wgpu::ShaderSource::Wgsl(shader.into()),
    });
    let pipeline=device.create_compute_pipeline(&wgpu::ComputePipelineDescriptor {
        label:Some("DOC signed i32 equality compute"),
        layout:None,module:&module,entry_point:Some("main"),
        compilation_options:wgpu::PipelineCompilationOptions::default(),cache:None,
    });
    if let Some(error)=device.pop_error_scope().await {
        return Err(format!("DOC signed WebGPU shader rejected: {error}").into());
    }
    for (epoch,(a,b,expected)) in epochs.into_iter().enumerate() {
        let started=Instant::now();
        let a_buf=device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label:Some("DOC signed lhs"),contents:&bytes(&a),usage:wgpu::BufferUsages::STORAGE,
        });
        let b_buf=device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label:Some("DOC signed rhs"),contents:&bytes(&b),usage:wgpu::BufferUsages::STORAGE,
        });
        let output=device.create_buffer(&wgpu::BufferDescriptor {
            label:Some("DOC signed comparison candidate"),size:nbytes,
            usage:wgpu::BufferUsages::STORAGE|wgpu::BufferUsages::COPY_SRC,
            mapped_at_creation:false,
        });
        let readback=device.create_buffer(&wgpu::BufferDescriptor {
            label:Some("DOC signed comparison readback"),size:nbytes,
            usage:wgpu::BufferUsages::COPY_DST|wgpu::BufferUsages::MAP_READ,
            mapped_at_creation:false,
        });
        let bind=device.create_bind_group(&wgpu::BindGroupDescriptor {
            label:Some("DOC signed premises"),
            layout:&pipeline.get_bind_group_layout(0),
            entries:&[
                wgpu::BindGroupEntry{binding:0,resource:a_buf.as_entire_binding()},
                wgpu::BindGroupEntry{binding:1,resource:b_buf.as_entire_binding()},
                wgpu::BindGroupEntry{binding:2,resource:output.as_entire_binding()},
            ],
        });
        let mut encoder=device.create_command_encoder(&wgpu::CommandEncoderDescriptor {
            label:Some("DOC signed private batch"),
        });
        let mut pass=encoder.begin_compute_pass(&wgpu::ComputePassDescriptor {
            label:Some("DOC signed equality pass"),timestamp_writes:None,
        });
        pass.set_pipeline(&pipeline);
        pass.set_bind_group(0,&bind,&[]);
        pass.dispatch_workgroups(workgroups,1,1);
        drop(pass);
        encoder.copy_buffer_to_buffer(&output,0,&readback,0,nbytes);
        device.push_error_scope(wgpu::ErrorFilter::Validation);
        queue.submit(Some(encoder.finish()));
        if let Some(error)=device.pop_error_scope().await {
            return Err(format!("DOC signed dispatch failed: {error}").into());
        }
        let (tx,rx)=std::sync::mpsc::channel();
        readback.slice(..).map_async(wgpu::MapMode::Read,move|res|{
            let _=tx.send(res);
        });
        device.poll(wgpu::Maintain::Wait);
        rx.recv()?.map_err(|e|format!("DOC signed readback failed: {e}"))?;
        let mapped=readback.slice(..).get_mapped_range();
        let observed:Vec<u32>=mapped.chunks_exact(4)
            .map(|v|u32::from_le_bytes(v.try_into().expect("4-byte chunk"))).collect();
        drop(mapped);
        readback.unmap();
        if observed!=expected {
            return Err(format!("DOC signed GPU/CPU mismatch epoch={epoch}").into());
        }
        // Only a COMPLETE and independently verified candidate is observable.
        println!("DOC_SIGNED_WEBGPU_COMPUTE_PASS: epoch={epoch} lanes={count} equals={}",
            observed.iter().sum::<u32>());
        println!("DOC_SIGNED_WEBGPU_HOST_MS: epoch={epoch} elapsed_ms={:.3}",
            started.elapsed().as_secs_f64()*1000.0);
    }
    Ok(())
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn host_validation_refuses_wide_i64_and_empty_batches() {
        assert!(checked_i32_words(&[]).is_err());
        assert!(checked_i32_words(&[i64::MAX]).is_err());
        assert!(checked_i32_words(&[i64::MIN]).is_err());
        assert_eq!(checked_i32_words(&[i64::from(i32::MIN),i64::from(i32::MAX)]).unwrap(),
            vec![i32::MIN as u32,i32::MAX as u32]);
    }
    #[test]
    fn unsigned_transport_preserves_signed_i32_extremes() {
        for epoch in 0..2 {
            for lane in 0..4096 {
                let (a,b)=input_for(lane,epoch);
                assert_eq!((a as i32) as i64,a);
                assert_eq!((b as i32) as i64,b);
            }
        }
    }
}
