//! Native WebGPU platform adapter for the generic DOC scene ABI.
//! Authored geometry, materials, camera, light and physics remain in DOC.
use crate::{graphics::MeshProgram,scene3d::SceneFrame,Result,gpu_health::DeviceHealth};
use wgpu::util::DeviceExt;
use std::{collections::BTreeSet,path::Path,io::Write};

pub fn adapter(instance:&wgpu::Instance,surface:Option<&wgpu::Surface<'_>>)->Result<wgpu::Adapter>{
    let allow=std::env::var("DOC_GPU_ALLOW_SOFTWARE").as_deref()==Ok("1");
    let mut adapters=instance.enumerate_adapters(wgpu::Backends::all());
    let compatible=|a:&wgpu::Adapter|surface.is_none_or(|s|a.is_surface_supported(s));
    let idx=adapters.iter().position(|a|compatible(a)&&matches!(a.get_info().device_type,wgpu::DeviceType::DiscreteGpu|wgpu::DeviceType::IntegratedGpu))
        .or_else(||if allow{adapters.iter().position(|a|compatible(a)&&a.get_info().device_type==wgpu::DeviceType::Cpu)}else{None})
        .ok_or("DOC_SCENE_GPU_HARDWARE_UNAVAILABLE: no admitted WebGPU adapter")?;
    let a=adapters.swap_remove(idx);let info=a.get_info();
    println!("DOC_SCENE_RENDER_DEVICE: name={} type={:?}",info.name,info.device_type);
    if info.device_type==wgpu::DeviceType::Cpu{eprintln!("DOC_SCENE_RENDER_SOFTWARE_TEST_ONLY");}
    Ok(a)
}
pub struct MeshRenderer{
    device:wgpu::Device,queue:wgpu::Queue,pipeline:wgpu::RenderPipeline,
    layout:wgpu::BindGroupLayout,format:wgpu::TextureFormat,program:MeshProgram,health:DeviceHealth,
}
pub struct Pixels{pub width:u32,pub height:u32,pub rgba:Vec<u8>}
impl Pixels{
    pub fn proof(&self)->(usize,u64){
        let mut unique=BTreeSet::new();let mut hash=0xcbf29ce484222325u64;
        for p in self.rgba.chunks_exact(4){unique.insert(u32::from_le_bytes(p.try_into().unwrap()));for b in p{hash=(hash^u64::from(*b)).wrapping_mul(0x100000001b3);}}
        (unique.len(),hash)
    }
    pub fn save_ppm(&self,path:&Path)->Result<()>{
        let mut file=std::fs::OpenOptions::new().write(true).create_new(true).open(path).map_err(|e|e.to_string())?;
        write!(file,"P6\n{} {}\n255\n",self.width,self.height).map_err(|e|e.to_string())?;
        for pixel in self.rgba.chunks_exact(4){file.write_all(&pixel[..3]).map_err(|e|e.to_string())?;}
        Ok(())
    }
}
impl MeshRenderer{
    pub fn new(adapter:&wgpu::Adapter,program:MeshProgram,format:wgpu::TextureFormat)->Result<Self>{
        if !matches!(format,wgpu::TextureFormat::Rgba8Unorm|wgpu::TextureFormat::Rgba8UnormSrgb|wgpu::TextureFormat::Bgra8Unorm|wgpu::TextureFormat::Bgra8UnormSrgb){
            return Err("DOC_SCENE: unsupported target color format".into());
        }
        let(device,queue)=pollster::block_on(adapter.request_device(&wgpu::DeviceDescriptor::default(),None)).map_err(|e|e.to_string())?;
        let health=DeviceHealth::attach(&device);
        device.push_error_scope(wgpu::ErrorFilter::Validation);
        let shader=device.create_shader_module(wgpu::ShaderModuleDescriptor{label:Some("DOC generated mesh"),source:wgpu::ShaderSource::Wgsl(program.wgsl.as_str().into())});
        let layout=device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor{label:Some("DOC draw facts"),entries:&[wgpu::BindGroupLayoutEntry{
            binding:0,visibility:wgpu::ShaderStages::VERTEX_FRAGMENT,ty:wgpu::BindingType::Buffer{ty:wgpu::BufferBindingType::Uniform,has_dynamic_offset:false,min_binding_size:None},count:None}]});
        let pl=device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor{label:None,bind_group_layouts:&[&layout],push_constant_ranges:&[]});
        let attrs=wgpu::vertex_attr_array![0=>Sint32x4,1=>Sint32x4,2=>Sint32x4];
        let pipeline=device.create_render_pipeline(&wgpu::RenderPipelineDescriptor{
            label:Some("DOC generated 3D render pipeline"),layout:Some(&pl),
            vertex:wgpu::VertexState{module:&shader,entry_point:Some("vs_main"),buffers:&[wgpu::VertexBufferLayout{array_stride:48,step_mode:wgpu::VertexStepMode::Vertex,attributes:&attrs}],compilation_options:Default::default()},
            fragment:Some(wgpu::FragmentState{module:&shader,entry_point:Some("fs_main"),targets:&[Some(wgpu::ColorTargetState{format,blend:None,write_mask:wgpu::ColorWrites::ALL})],compilation_options:Default::default()}),
            primitive:Default::default(),depth_stencil:Some(wgpu::DepthStencilState{format:wgpu::TextureFormat::Depth32Float,depth_write_enabled:true,depth_compare:wgpu::CompareFunction::Less,stencil:Default::default(),bias:Default::default()}),
            multisample:Default::default(),multiview:None,cache:None});
        if let Some(e)=pollster::block_on(device.pop_error_scope()){return Err(format!("DOC_SCENE_PIPELINE_FAILURE: {e}"));}
        health.check()?;
        println!("DOC_SCENE_GENERATED_PIPELINE: source_bytes={}",program.wgsl.len());
        Ok(Self{device,queue,pipeline,layout,format,program,health})
    }
    pub fn device(&self)->&wgpu::Device{&self.device}
    fn extent(&self,width:u32,height:u32)->Result<wgpu::Extent3d>{
        self.health.check()?;
        let max=self.device.limits().max_texture_dimension_2d.min(4096);
        if width==0||height==0||width>max||height>max{return Err("DOC_SCENE: invalid framebuffer dimensions".into());}
        Ok(wgpu::Extent3d{width,height,depth_or_array_layers:1})
    }
    pub fn render(&self,frame:&SceneFrame,target:&wgpu::TextureView,width:u32,height:u32)->Result<()>{
        let size=self.extent(width,height)?;
        if frame.draws.is_empty()||frame.draws.len()>128||frame.vertices.is_empty()||frame.vertices.len()>65536||frame.indices.is_empty()||frame.indices.len()>196608{return Err("DOC_SCENE: draw/mesh budget".into());}
        // Revalidate public snapshot values at this device boundary.
        for d in &frame.draws{
            let end=d.first.checked_add(d.count).ok_or("DOC_SCENE: index span")?;
            self.program.validate(&frame.vertices,&d.params,frame.indices.get(d.first as usize..end as usize).ok_or("DOC_SCENE: index range")?)?;
        }
        let v=frame.vertices.iter().flat_map(|v|v.iter().flat_map(|x|x.to_le_bytes())).collect::<Vec<_>>();
        let i=frame.indices.iter().flat_map(|x|x.to_le_bytes()).collect::<Vec<_>>();
        self.device.push_error_scope(wgpu::ErrorFilter::Validation);
        let vb=self.device.create_buffer_init(&wgpu::util::BufferInitDescriptor{label:None,contents:&v,usage:wgpu::BufferUsages::VERTEX});
        let ib=self.device.create_buffer_init(&wgpu::util::BufferInitDescriptor{label:None,contents:&i,usage:wgpu::BufferUsages::INDEX});
        let uniforms=frame.draws.iter().map(|d|{
            let b=d.params.iter().flat_map(|x|x.to_le_bytes()).collect::<Vec<_>>();
            self.device.create_buffer_init(&wgpu::util::BufferInitDescriptor{label:None,contents:&b,usage:wgpu::BufferUsages::UNIFORM})
        }).collect::<Vec<_>>();
        let groups=uniforms.iter().map(|b|self.device.create_bind_group(&wgpu::BindGroupDescriptor{label:None,layout:&self.layout,entries:&[wgpu::BindGroupEntry{binding:0,resource:b.as_entire_binding()}]})).collect::<Vec<_>>();
        let depth=self.device.create_texture(&wgpu::TextureDescriptor{label:None,size,mip_level_count:1,sample_count:1,dimension:wgpu::TextureDimension::D2,format:wgpu::TextureFormat::Depth32Float,usage:wgpu::TextureUsages::RENDER_ATTACHMENT,view_formats:&[]});
        let dv=depth.create_view(&Default::default());
        let mut enc=self.device.create_command_encoder(&Default::default());
        {
            let c=frame.clear.map(|n|f64::from(n)/255.0);
            let mut pass=enc.begin_render_pass(&wgpu::RenderPassDescriptor{label:Some("DOC scene"),color_attachments:&[Some(wgpu::RenderPassColorAttachment{view:target,resolve_target:None,ops:wgpu::Operations{load:wgpu::LoadOp::Clear(wgpu::Color{r:c[0],g:c[1],b:c[2],a:c[3]}),store:wgpu::StoreOp::Store}})],
                depth_stencil_attachment:Some(wgpu::RenderPassDepthStencilAttachment{view:&dv,depth_ops:Some(wgpu::Operations{load:wgpu::LoadOp::Clear(1.0),store:wgpu::StoreOp::Store}),stencil_ops:None}),timestamp_writes:None,occlusion_query_set:None});
            pass.set_pipeline(&self.pipeline);pass.set_vertex_buffer(0,vb.slice(..));pass.set_index_buffer(ib.slice(..),wgpu::IndexFormat::Uint32);
            for(d,b)in frame.draws.iter().zip(&groups){pass.set_bind_group(0,b,&[]);pass.draw_indexed(d.first..d.first+d.count,0,0..1);}
        }
        self.queue.submit(Some(enc.finish()));
        // Wait for device work before retiring this frame's buffers. This first
        // implementation is synchronous; later measured reuse may remove stalls.
        self.device.poll(wgpu::Maintain::Wait);
        if let Some(e)=pollster::block_on(self.device.pop_error_scope()){return Err(format!("DOC_SCENE_RENDER_FAILURE: {e}"));}
        self.health.check()
    }
    pub fn offscreen(&self,frame:&SceneFrame,width:u32,height:u32)->Result<Pixels>{
        let size=self.extent(width,height)?;
        let texture=self.device.create_texture(&wgpu::TextureDescriptor{label:None,size,mip_level_count:1,sample_count:1,dimension:wgpu::TextureDimension::D2,format:self.format,usage:wgpu::TextureUsages::RENDER_ATTACHMENT|wgpu::TextureUsages::COPY_SRC,view_formats:&[]});
        self.health.check()?;
        self.render(frame,&texture.create_view(&Default::default()),width,height)?;
        let row=(width*4).div_ceil(256)*256;
        let read=self.device.create_buffer(&wgpu::BufferDescriptor{label:None,size:u64::from(row)*u64::from(height),usage:wgpu::BufferUsages::COPY_DST|wgpu::BufferUsages::MAP_READ,mapped_at_creation:false});
        let mut enc=self.device.create_command_encoder(&Default::default());
        enc.copy_texture_to_buffer(wgpu::TexelCopyTextureInfo{texture:&texture,mip_level:0,origin:wgpu::Origin3d::ZERO,aspect:wgpu::TextureAspect::All},wgpu::TexelCopyBufferInfo{buffer:&read,layout:wgpu::TexelCopyBufferLayout{offset:0,bytes_per_row:Some(row),rows_per_image:Some(height)}},size);
        self.device.push_error_scope(wgpu::ErrorFilter::Validation);
        self.queue.submit(Some(enc.finish()));
        if let Some(e)=pollster::block_on(self.device.pop_error_scope()){return Err(format!("DOC_SCENE_READBACK_FAILURE: {e}"));}
        let(tx,rx)=std::sync::mpsc::channel();read.slice(..).map_async(wgpu::MapMode::Read,move|x|{let _=tx.send(x);});
        self.device.poll(wgpu::Maintain::Wait);
        self.health.check()?;
        rx.try_recv().map_err(|_|"DOC_SCENE: missing completed readback callback")?.map_err(|e|e.to_string())?;
        let mapped=read.slice(..).get_mapped_range();
        let mut rgba=Vec::with_capacity(width as usize*height as usize*4);
        for src in mapped.chunks_exact(row as usize){rgba.extend_from_slice(&src[..width as usize*4]);}
        drop(mapped);read.unmap();
        self.health.check()?;
        if matches!(self.format,wgpu::TextureFormat::Bgra8Unorm|wgpu::TextureFormat::Bgra8UnormSrgb){for p in rgba.chunks_exact_mut(4){p.swap(0,2);}}
        Ok(Pixels{width,height,rgba})
    }
}
