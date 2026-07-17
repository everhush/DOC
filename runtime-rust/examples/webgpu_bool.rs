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

fn main() -> Result<(), Box<dyn Error>> {
    pollster::block_on(run())
}

async fn run() -> Result<(), Box<dyn Error>> {
    let _ = env_logger::try_init();
    let source = "source a: bool = true\nsource b: bool = false\nderive equal: bool (a,b) = eq(a,b)\n";
    let graph = Graph::parse(source)?;
    let target = graph.id("equal").ok_or("missing derived target")?;
    let shader_source = wgsl::lower_bool_derived(&graph, target)?;

    // Exercise multiple workgroups and the out-of-range tail guard.
    // Inputs are deterministic canonical Boolean words, not a hardcoded result.
    const LANES: usize = 130;
    let a: Vec<u32> = (0..LANES).map(|i| u32::from(i % 3 == 0)).collect();
    let b: Vec<u32> = (0..LANES).map(|i| u32::from(i % 5 < 2)).collect();
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

    let instance = wgpu::Instance::new(wgpu::InstanceDescriptor {
        backends: wgpu::Backends::VULKAN | wgpu::Backends::GL,
        ..Default::default()
    });
    let listed = instance.enumerate_adapters(wgpu::Backends::VULKAN | wgpu::Backends::GL);
    println!("WebGPU Vulkan/GLES adapters enumerated: {}", listed.len());
    for item in &listed {
        println!("Candidate: {:?}", item.get_info());
    }
    let mut adapter = None;
    for fallback in [true, false] {
        adapter = instance.request_adapter(&wgpu::RequestAdapterOptions {
            power_preference: wgpu::PowerPreference::LowPower,
            compatible_surface: None,
            force_fallback_adapter: fallback,
        }).await;
        if adapter.is_some() { break; }
    }
    let adapter = adapter.ok_or("No conforming Vulkan or GLES WebGPU adapter available")?;
    let info = adapter.get_info();
    println!("WebGPU adapter: {} ({:?}, {:?})", info.name, info.device_type, info.backend);
    let (device, queue) = adapter
        .request_device(&wgpu::DeviceDescriptor::default(), None)
        .await?;
    let nbytes = (a.len() * std::mem::size_of::<u32>()) as u64;
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
        pass.dispatch_workgroups((LANES as u32).div_ceil(64), 1, 1);
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
