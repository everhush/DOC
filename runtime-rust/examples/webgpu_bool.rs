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
    let source = include_str!("boolean_conditional.doc");
    let graph = Graph::parse(source)?;
    let target = graph.id("chosen").ok_or("missing derived target")?;
    let shader_source = wgsl::lower_bool_derived(&graph, target)?;

    // Exercise multiple workgroups and the out-of-range tail guard.
    // Inputs are deterministic canonical Boolean words, not a hardcoded result.
    const LANES: usize = 130;
    let a: Vec<u32> = (0..LANES).map(|i| u32::from(i % 3 == 0)).collect();
    let b: Vec<u32> = (0..LANES).map(|i| u32::from(i % 5 < 2)).collect();
    let lane_count = validate_boolean_batch(&[&a, &b])?;
    let mut expected = Vec::new();
    for (&lhs, &rhs) in a.iter().zip(b.iter()) {
        let mut rt = Runtime::new(graph.clone(), 1, Cutoff::Exact);
        rt.update(&[
            (graph.id("a").unwrap(), Value::Bool(lhs != 0)),
            (graph.id("b").unwrap(), Value::Bool(rhs != 0)),
        ])?;
        rt.stabilize()?;
        expected.push(u32::from(rt.value(target) == Some(Value::Bool(true))));
    }

    let instance = wgpu::Instance::new(&wgpu::InstanceDescriptor {
        backends: wgpu::Backends::VULKAN,
        ..Default::default()
    });
    let adapter = instance
        .request_adapter(&wgpu::RequestAdapterOptions {
            power_preference: wgpu::PowerPreference::LowPower,
            ..Default::default()
        })
        .await
        .ok_or("No conforming Vulkan WebGPU adapter available")?;
    let info = adapter.get_info();
    println!("WebGPU adapter: {} ({:?}, {:?})", info.name, info.device_type, info.backend);
    let (device, queue) = adapter
        .request_device(&wgpu::DeviceDescriptor::default(), None)
        .await?;
    let nbytes = u64::try_from(lane_count)?.checked_mul(4).ok_or("DOC GPU buffer size overflow")?;
    let limits = device.limits();
    if nbytes > u64::from(limits.max_storage_buffer_binding_size) {
        return Err("DOC GPU batch exceeds storage buffer binding limit".into());
    }
    let workgroups = u32::try_from(lane_count.div_ceil(64))?;
    if workgroups > limits.max_compute_workgroups_per_dimension {
        return Err("DOC GPU batch exceeds workgroup dispatch limit".into());
    }
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
    let output = device.create_buffer(&wgpu::BufferDescriptor {
        label: Some("DOC private candidates"),
        size: nbytes,
        usage: wgpu::BufferUsages::STORAGE | wgpu::BufferUsages::COPY_SRC,
        mapped_at_creation: false,
    });
    let readback = device.create_buffer(&wgpu::BufferDescriptor {
        label: Some("DOC candidate readback"),
        size: nbytes,
        usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ,
        mapped_at_creation: false,
    });
    let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
        label: Some("DOC generated WGSL"),
        source: wgpu::ShaderSource::Wgsl(shader_source.into()),
    });
    let pipeline = device.create_compute_pipeline(&wgpu::ComputePipelineDescriptor {
        label: Some("DOC Boolean frontier batch"),
        layout: None,
        module: &shader,
        entry_point: Some("main"),
        compilation_options: wgpu::PipelineCompilationOptions::default(),
        cache: None,
    });
    let layout = pipeline.get_bind_group_layout(0);
    let bind_group = device.create_bind_group(&wgpu::BindGroupDescriptor {
        label: Some("DOC Boolean inputs and output"),
        layout: &layout,
        entries: &[
            wgpu::BindGroupEntry { binding: 0, resource: buffer_a.as_entire_binding() },
            wgpu::BindGroupEntry { binding: 1, resource: buffer_b.as_entire_binding() },
            wgpu::BindGroupEntry { binding: 2, resource: output.as_entire_binding() },
        ],
    });
    let mut encoder = device.create_command_encoder(&wgpu::CommandEncoderDescriptor {
        label: Some("DOC frontier compute and complete readback"),
    });
    {
        let mut pass = encoder.begin_compute_pass(&wgpu::ComputePassDescriptor {
            label: Some("DOC compute"),
            timestamp_writes: None,
        });
        pass.set_pipeline(&pipeline);
        pass.set_bind_group(0, &bind_group, &[]);
        // The shader declares 64 invocations per workgroup and checks idx.
        pass.dispatch_workgroups(workgroups, 1, 1);
    }
    encoder.copy_buffer_to_buffer(&output, 0, &readback, 0, nbytes);
    queue.submit(Some(encoder.finish()));
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
        return Err(format!("GPU/CPU DOC differential mismatch: GPU {got:?}, CPU {expected:?}").into());
    }
    // Only after successful readback and complete equivalence checking may
    // a production DOC runtime publish the candidates into a logical frontier.
    println!("DOC_WEBGPU_COMPUTE_PASS: {got:?}");
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
    }
}
