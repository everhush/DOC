//! Executes a DOC-derived Boolean computation through WebGPU compute.
//! This is an experimental native host example, not general-purpose offloading.
//! Linux CI's lavapipe adapter is software Vulkan; it validates functionality,
//! not hardware acceleration or CPU/GPU speedup.
use doc_runtime::{wgsl, Cutoff, Graph, Runtime, Value};
use std::error::Error;
use wgpu::util::DeviceExt;

fn bytes(data: &[u32]) -> Vec<u8> {
    data.iter().flat_map(|word| word.to_le_bytes()).collect()
}

fn validate_boolean_batch(inputs: &[&[u32]]) -> Result<usize, Box<dyn Error>> {
    let len = inputs.first().ok_or("DOC GPU batch requires inputs")?.len();
    if len == 0 { return Err("DOC GPU batch must not be empty".into()); }
    if inputs.iter().any(|input| input.len() != len) {
        return Err("DOC GPU premise buffers must have identical lengths".into());
    }
    if inputs.iter().flat_map(|input| input.iter()).any(|word| *word > 1) {
        return Err("DOC GPU boolean words must be canonical (0 or 1)".into());
    }
    Ok(len)
}

fn main() -> Result<(), Box<dyn Error>> {
    pollster::block_on(run())
}

async fn run() -> Result<(), Box<dyn Error>> {
    let _ = env_logger::try_init();
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    let (staged, repair, paths) = match args.as_slice() {
        [] => (false, false, &args[..]),
        [flag, _] if flag == "--shader" => (false, false, &args[1..]),
        [flag, _] if flag == "--repair-shader" => (false, true, &args[1..]),
        [flag] if flag == "--repair" => (false, true, &args[1..]),
        [flag] if flag == "--staged" => (true, false, &args[1..]),
        [flag] if flag == "--staged-repair" => (true, true, &args[1..]),
        [flag, _, _] if flag == "--staged-shaders" => (true, false, &args[1..]),
        [flag, _, _] if flag == "--staged-shaders-repair" => (true, true, &args[1..]),
        _ => return Err("usage: webgpu_bool [--repair | --staged | --staged-repair | --shader FILE | --repair-shader FILE | --staged-shaders FIRST SECOND | --staged-shaders-repair FIRST SECOND]".into()),
    };
    let graph = Graph::parse(if staged {
        include_str!("boolean_staged.doc")
    } else {
        include_str!("boolean_conditional.doc")
    })?;
    let stages: &[&str] = if staged { &["chosen", "verified"] } else { &["chosen"] };
    let target = graph.id(stages[stages.len() - 1]).ok_or("missing derived target")?;
    let shaders = if paths.is_empty() {
        stages.iter().map(|name| {
            let id = graph.id(name).ok_or("missing derived stage")?;
            wgsl::lower_bool_derived(&graph, id)
        }).collect::<Result<Vec<_>, _>>()?
    } else {
        paths.iter().map(std::fs::read_to_string).collect::<Result<Vec<_>, _>>()?
    };

    let lane_count = match std::env::var("DOC_GPU_LANES") {
        Ok(raw) => raw.parse::<usize>().map_err(|_| "invalid DOC_GPU_LANES")?,
        Err(std::env::VarError::NotPresent) => 130,
        Err(_) => return Err("DOC_GPU_LANES must be valid UTF-8".into()),
    };
    if !(1..=4096).contains(&lane_count) {
        return Err("DOC_GPU_LANES must be within 1..=4096".into());
    }
    // The default is strict GPU execution. 'auto' is an opt-in fallback
    // only for GPU-admission failure, never for a failed or stale dispatch.
    // 'cpu' is a deterministic fallback test without any GPU dependency.
    let execution = std::env::var("DOC_GPU_EXECUTION").unwrap_or_else(|_| "gpu".into());
    if !["gpu", "auto", "cpu"].contains(&execution.as_str()) {
        return Err("DOC_GPU_EXECUTION must be gpu, auto, or cpu".into());
    }

    // Keep independent DOC CPU runtimes alive across BOTH source revisions.
    // This exercises actual incremental source repair rather than rebuilding
    // from scratch for the second episode.
    let source_a = graph.id("a").ok_or("missing DOC source a")?;
    let source_b = graph.id("b").ok_or("missing DOC source b")?;
    let mut cpu: Vec<Runtime> = (0..lane_count)
        .map(|_| Runtime::new(graph.clone(), 1, Cutoff::Exact))
        .collect();
    let episodes = if repair { 2 } else { 1 };
    let mut cases = Vec::with_capacity(episodes);
    for episode in 0..episodes {
        let a: Vec<u32> = (0..lane_count)
            .map(|i| u32::from(if episode == 0 { i % 3 == 0 } else { i % 7 < 3 }))
            .collect();
        let b: Vec<u32> = (0..lane_count)
            .map(|i| u32::from(if episode == 0 { i % 5 < 2 } else { i % 11 == 0 }))
            .collect();
        validate_boolean_batch(&[&a, &b])?;
        let mut expected = Vec::with_capacity(lane_count);
        for (index, (&lhs, &rhs)) in a.iter().zip(&b).enumerate() {
            cpu[index].update(&[
                (source_a, Value::Bool(lhs != 0)),
                (source_b, Value::Bool(rhs != 0)),
            ])?;
            cpu[index].stabilize()?;
            expected.push(u32::from(cpu[index].value(target) == Some(Value::Bool(true))));
        }
        cases.push((a, b, expected));
    }

    // The forced CPU path does not even initialize a GPU backend.
    let adapter = if execution == "cpu" {
        None
    } else {
        let instance = wgpu::Instance::new(&wgpu::InstanceDescriptor {
            backends: wgpu::Backends::VULKAN,
            ..Default::default()
        });
        instance.request_adapter(&wgpu::RequestAdapterOptions {
            power_preference: wgpu::PowerPreference::LowPower,
            ..Default::default()
        }).await
    };
    let Some(adapter) = adapter else {
        if execution == "gpu" {
            return Err("No conforming Vulkan WebGPU adapter available".into());
        }
        for (episode, (_, _, expected)) in cases.iter().enumerate() {
            println!("DOC_CPU_FALLBACK_PASS: episode={episode} lanes={lane_count} output={expected:?}");
        }
        return Ok(());
    };
    let info = adapter.get_info();
    println!("WebGPU adapter: {} ({:?}, {:?})", info.name, info.device_type, info.backend);
    let (device, queue) = match adapter
        .request_device(&wgpu::DeviceDescriptor::default(), None)
        .await
    {
        Ok(pair) => pair,
        Err(_) if execution == "auto" => {
            for (episode, (_, _, expected)) in cases.iter().enumerate() {
                println!("DOC_CPU_FALLBACK_PASS: episode={episode} lanes={lane_count} output={expected:?}");
            }
            return Ok(());
        }
        Err(error) => return Err(format!("DOC WebGPU device admission failed: {error}").into()),
    };

    let nbytes = u64::try_from(lane_count)?
        .checked_mul(4).ok_or("DOC GPU buffer size overflow")?;
    let limits = device.limits();
    if nbytes > u64::from(limits.max_storage_buffer_binding_size) {
        return Err("DOC GPU batch exceeds storage buffer binding limit".into());
    }
    let workgroups = u32::try_from(lane_count.div_ceil(64))?;
    if workgroups > limits.max_compute_workgroups_per_dimension {
        return Err("DOC GPU batch exceeds workgroup dispatch limit".into());
    }
    for (episode, (a, b, expected)) in cases.into_iter().enumerate() {
        // All buffers are private to this source revision. Never rebind the
        // prior episode's output as a candidate for the newer source epoch.
        let buffer_a = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("DOC premises a"),
            contents: &bytes(&a),
            usage: wgpu::BufferUsages::STORAGE,
        });
        let buffer_b = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("DOC premises b"),
            contents: &bytes(&b),
            usage: wgpu::BufferUsages::STORAGE,
        });
        let output_buffers: Vec<_> = stages.iter()
            .map(|stage| device.create_buffer(&wgpu::BufferDescriptor {
                label: Some(stage),
                size: nbytes,
                usage: wgpu::BufferUsages::STORAGE | wgpu::BufferUsages::COPY_SRC,
                mapped_at_creation: false,
            })).collect();
        let readback = device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("DOC candidate readback"),
            size: nbytes,
            usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ,
            mapped_at_creation: false,
        });
        let mut encoder = device.create_command_encoder(&wgpu::CommandEncoderDescriptor {
            label: Some("DOC ordered Boolean stages"),
        });
        device.push_error_scope(wgpu::ErrorFilter::Validation);
        for (index, shader_source) in shaders.iter().enumerate() {
            let first_input = if index == 0 { &buffer_a } else { &output_buffers[index - 1] };
            let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
                label: Some("DOC generated WGSL"),
                source: wgpu::ShaderSource::Wgsl(shader_source.as_str().into()),
            });
            let pipeline = device.create_compute_pipeline(&wgpu::ComputePipelineDescriptor {
                label: Some("DOC Boolean frontier batch"),
                layout: None,
                module: &shader,
                entry_point: Some("main"),
                compilation_options: wgpu::PipelineCompilationOptions::default(),
                cache: None,
            });
            let bind_group = device.create_bind_group(&wgpu::BindGroupDescriptor {
                label: Some("DOC Boolean inputs and output"),
                layout: &pipeline.get_bind_group_layout(0),
                entries: &[
                    wgpu::BindGroupEntry { binding: 0, resource: first_input.as_entire_binding() },
                    wgpu::BindGroupEntry { binding: 1, resource: buffer_b.as_entire_binding() },
                    wgpu::BindGroupEntry {
                        binding: 2, resource: output_buffers[index].as_entire_binding(),
                    },
                ],
            });
            let mut pass = encoder.begin_compute_pass(&wgpu::ComputePassDescriptor {
                label: Some("DOC compute"),
                timestamp_writes: None,
            });
            pass.set_pipeline(&pipeline);
            pass.set_bind_group(0, &bind_group, &[]);
            pass.dispatch_workgroups(workgroups, 1, 1);
        }
        encoder.copy_buffer_to_buffer(
            output_buffers.last().ok_or("missing output buffer")?,
            0, &readback, 0, nbytes,
        );
        queue.submit(Some(encoder.finish()));
        if let Some(error) = device.pop_error_scope().await {
            return Err(format!("DOC WebGPU validation failure at episode {episode}: {error}").into());
        }
        let slice = readback.slice(..);
        let (tx, rx) = std::sync::mpsc::channel();
        slice.map_async(wgpu::MapMode::Read, move |res| {
            let _ = tx.send(res);
        });
        device.poll(wgpu::Maintain::Wait);
        rx.recv()?.map_err(|e| format!("DOC WebGPU readback failure: {e}"))?;
        let mapped = slice.get_mapped_range();
        let got: Vec<u32> = mapped
            .chunks_exact(4)
            .map(|data| u32::from_le_bytes(data.try_into().unwrap()))
            .collect();
        drop(mapped);
        readback.unmap();
        if got != expected {
            return Err(format!(
                "GPU/CPU DOC differential mismatch at episode {episode}: \
                GPU {got:?}, CPU {expected:?}"
            ).into());
        }
        // Only successful complete readback and CPU equivalence are observable.
        if repair { println!("DOC_WEBGPU_EPISODE: {episode}"); }
        println!("DOC_WEBGPU_COMPUTE_PASS: {got:?}");
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::validate_boolean_batch;

    #[test]
    fn validates_batch_shape_and_canonical_words() {
        assert_eq!(validate_boolean_batch(&[&[0, 1], &[1, 0]]).unwrap(), 2);
        assert!(validate_boolean_batch(&[&[0, 1], &[1]]).is_err());
        assert!(validate_boolean_batch(&[&[0, 2], &[1, 0]]).is_err());
        assert!(validate_boolean_batch(&[&[], &[]]).is_err());
        assert!(validate_boolean_batch(&[]).is_err());
        assert_eq!(validate_boolean_batch(&[&[1], &[0]]).unwrap(), 1);
        assert_eq!(validate_boolean_batch(&[&vec![0; 129], &vec![1; 129]]).unwrap(), 129);
    }
}
