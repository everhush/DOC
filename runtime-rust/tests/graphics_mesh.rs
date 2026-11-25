use doc_runtime::{Graph,graphics::{compile_mesh,Binding,Domain,Input,MeshProgram}};
fn b(name:&str,input:Input,min:i32,max:i32)->Binding<'_>{Binding{name,input,domain:Domain{min,max}}}
fn program(vertex:&str,fragment:&str)->Result<MeshProgram,String>{
    use Input::*;
    let v=Graph::parse(vertex)?;let f=Graph::parse(fragment)?;
    compile_mesh(&v,&f,&[
        b("x",Vertex(0),-1024,1024),b("y",Vertex(1),-1024,1024),b("z",Vertex(2),0,1024),
        b("normal_z",Vertex(3),-1,1),b("red",Vertex(4),0,255),
        b("green",Vertex(5),0,255),b("blue",Vertex(6),0,255),
        b("shift_x",Draw(0),-512,512),b("shift_y",Draw(1),-512,512),
        b("depth_shift",Draw(2),-512,512),b("camera_w",Draw(3),1,2048),
    ],&[b("light_r",Varying(0),0,255),b("light_g",Varying(1),0,255),b("light_b",Varying(2),0,255)],
    ["clip_x","clip_y","clip_z","clip_w"],["lit_r","lit_g","lit_b"],["color_r","color_g","color_b"])
}
const V:&str=include_str!("../../engine/graphics/mesh_vertex.doc");
const F:&str=include_str!("../../engine/graphics/mesh_fragment.doc");
fn validate(s:&str){
    let m=naga::front::wgsl::parse_str(s).unwrap();
    naga::valid::Validator::new(naga::valid::ValidationFlags::all(),naga::valid::Capabilities::all()).validate(&m).unwrap();
}
#[test]
fn ordinary_doc_mesh_graphs_generate_valid_deterministic_wgsl(){
    let p=program(V,F).unwrap();validate(&p.wgsl);assert_eq!(p.wgsl,program(V,F).unwrap().wgsl);
    let changed=program(V,&F.replace("= light_r","= if(eq(light_r,0),0,255)")).unwrap();
    validate(&changed.wgsl);assert_ne!(p.wgsl,changed.wgsl);
    assert!(program(&V.replace("add(x,shift_x)","mul(x,2147483647)"),F).is_err());
    assert!(program(&V.replace("= camera_w","= 0"),F).is_err());
    assert!(program(V,&F.replace("= light_r","= 256")).is_err());
    let v=[[0;12];3];let mut draw=[0;8];draw[3]=1024;
    p.validate(&v,&draw,&[0,1,2]).unwrap();
    assert!(p.validate(&v,&draw,&[0,1,3]).is_err());
    draw[3]=0;assert!(p.validate(&v,&draw,&[0,1,2]).is_err());
}
#[cfg(feature="webgpu")]
#[test]
fn generated_doc_mesh_depth_lighting_and_source_mutation_on_real_webgpu(){
    use wgpu::util::DeviceExt;
    pollster::block_on(async{
        let instance=wgpu::Instance::default();
        let allow=std::env::var("DOC_GPU_ALLOW_SOFTWARE").as_deref()==Ok("1");
        let mut adapters=instance.enumerate_adapters(wgpu::Backends::all());
        let idx=adapters.iter().position(|a|matches!(a.get_info().device_type,wgpu::DeviceType::DiscreteGpu|wgpu::DeviceType::IntegratedGpu))
            .or_else(||if allow{adapters.iter().position(|a|a.get_info().device_type==wgpu::DeviceType::Cpu)}else{None}).expect("admitted GPU required");
        let adapter=adapters.swap_remove(idx);let info=adapter.get_info();
        println!("DOC_MESH_DEVICE: name={} type={:?}",info.name,info.device_type);
        let(device,queue)=adapter.request_device(&wgpu::DeviceDescriptor::default(),None).await.unwrap();
        // Three independent triangles: near red over far green, and a
        // separate dark back-facing triangle. Positions/normals are mesh data.
        let make=|x,y,z,n,r,g,b|[x,y,z,n,r,g,b,0,0,0,0,0];
        let vertices=[
            make(-900,-850,200,1,240,20,10),make(100,-850,200,1,240,20,10),make(-400,800,200,1,240,20,10),
            make(-900,-850,800,1,10,240,20),make(100,-850,800,1,10,240,20),make(-400,800,800,1,10,240,20),
            make(200,-850,300,-1,240,200,50),make(950,-850,300,-1,240,200,50),make(600,800,300,-1,240,200,50),
        ];
        let indices=[0u32,1,2,3,4,5,6,7,8];
        let draw=[0,0,0,1024,0,0,0,0];
        let bytes=vertices.iter().flat_map(|v|v.iter().flat_map(|x|i32::to_le_bytes(*x))).collect::<Vec<_>>();
        let ix=indices.iter().flat_map(|x|x.to_le_bytes()).collect::<Vec<_>>();
        let uniform=draw.iter().flat_map(|x|i32::to_le_bytes(*x)).collect::<Vec<_>>();
        let vb=device.create_buffer_init(&wgpu::util::BufferInitDescriptor{label:None,contents:&bytes,usage:wgpu::BufferUsages::VERTEX});
        let ib=device.create_buffer_init(&wgpu::util::BufferInitDescriptor{label:None,contents:&ix,usage:wgpu::BufferUsages::INDEX});
        let ub=device.create_buffer_init(&wgpu::util::BufferInitDescriptor{label:None,contents:&uniform,usage:wgpu::BufferUsages::UNIFORM});
        for (source,expect) in [(F,[240,20,10,255]),("source light_r: int = 0\nsource light_g: int = 0\nsource light_b: int = 0\nderive color_r: int (light_r) = 0\nderive color_g: int (light_g) = light_g\nderive color_b: int (light_b) = light_b\n",[0,20,10,255])]{
            let program=program(V,source).unwrap();program.validate(&vertices,&draw,&indices).unwrap();
            let shader=device.create_shader_module(wgpu::ShaderModuleDescriptor{label:None,source:wgpu::ShaderSource::Wgsl(program.wgsl.into())});
            let layout=device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor{label:None,entries:&[wgpu::BindGroupLayoutEntry{
                binding:0,visibility:wgpu::ShaderStages::VERTEX_FRAGMENT,ty:wgpu::BindingType::Buffer{ty:wgpu::BufferBindingType::Uniform,has_dynamic_offset:false,min_binding_size:None},count:None}]});
            let bind=device.create_bind_group(&wgpu::BindGroupDescriptor{label:None,layout:&layout,entries:&[wgpu::BindGroupEntry{binding:0,resource:ub.as_entire_binding()}]});
            let pl=device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor{label:None,bind_group_layouts:&[&layout],push_constant_ranges:&[]});
            let attrs=wgpu::vertex_attr_array![0=>Sint32x4,1=>Sint32x4,2=>Sint32x4];
            let pipeline=device.create_render_pipeline(&wgpu::RenderPipelineDescriptor{
                label:None,layout:Some(&pl),vertex:wgpu::VertexState{module:&shader,entry_point:Some("vs_main"),
                    buffers:&[wgpu::VertexBufferLayout{array_stride:48,step_mode:wgpu::VertexStepMode::Vertex,attributes:&attrs}],compilation_options:Default::default()},
                fragment:Some(wgpu::FragmentState{module:&shader,entry_point:Some("fs_main"),targets:&[Some(wgpu::ColorTargetState{format:wgpu::TextureFormat::Rgba8Unorm,blend:None,write_mask:wgpu::ColorWrites::ALL})],compilation_options:Default::default()}),
                primitive:Default::default(),depth_stencil:Some(wgpu::DepthStencilState{format:wgpu::TextureFormat::Depth32Float,depth_write_enabled:true,depth_compare:wgpu::CompareFunction::Less,stencil:Default::default(),bias:Default::default()}),
                multisample:Default::default(),multiview:None,cache:None});
            let size=wgpu::Extent3d{width:64,height:64,depth_or_array_layers:1};
            let color=device.create_texture(&wgpu::TextureDescriptor{label:None,size,mip_level_count:1,sample_count:1,dimension:wgpu::TextureDimension::D2,format:wgpu::TextureFormat::Rgba8Unorm,usage:wgpu::TextureUsages::RENDER_ATTACHMENT|wgpu::TextureUsages::COPY_SRC,view_formats:&[]});
            let depth=device.create_texture(&wgpu::TextureDescriptor{label:None,size,mip_level_count:1,sample_count:1,dimension:wgpu::TextureDimension::D2,format:wgpu::TextureFormat::Depth32Float,usage:wgpu::TextureUsages::RENDER_ATTACHMENT,view_formats:&[]});
            let cv=color.create_view(&Default::default());let dv=depth.create_view(&Default::default());
            let read=device.create_buffer(&wgpu::BufferDescriptor{label:None,size:16384,usage:wgpu::BufferUsages::MAP_READ|wgpu::BufferUsages::COPY_DST,mapped_at_creation:false});
            let mut enc=device.create_command_encoder(&Default::default());
            {
                let mut pass=enc.begin_render_pass(&wgpu::RenderPassDescriptor{label:None,color_attachments:&[Some(wgpu::RenderPassColorAttachment{view:&cv,resolve_target:None,ops:wgpu::Operations{load:wgpu::LoadOp::Clear(wgpu::Color{r:0.0,g:0.0,b:1.0,a:1.0}),store:wgpu::StoreOp::Store}})],
                    depth_stencil_attachment:Some(wgpu::RenderPassDepthStencilAttachment{view:&dv,depth_ops:Some(wgpu::Operations{load:wgpu::LoadOp::Clear(1.0),store:wgpu::StoreOp::Store}),stencil_ops:None}),timestamp_writes:None,occlusion_query_set:None});
                pass.set_pipeline(&pipeline);pass.set_bind_group(0,&bind,&[]);pass.set_vertex_buffer(0,vb.slice(..));pass.set_index_buffer(ib.slice(..),wgpu::IndexFormat::Uint32);pass.draw_indexed(0..9,0,0..1);
            }
            enc.copy_texture_to_buffer(wgpu::TexelCopyTextureInfo{texture:&color,mip_level:0,origin:wgpu::Origin3d::ZERO,aspect:wgpu::TextureAspect::All},wgpu::TexelCopyBufferInfo{buffer:&read,layout:wgpu::TexelCopyBufferLayout{offset:0,bytes_per_row:Some(256),rows_per_image:Some(64)}},size);
            queue.submit(Some(enc.finish()));
            let(tx,rx)=std::sync::mpsc::channel();read.slice(..).map_async(wgpu::MapMode::Read,move|x|{let _=tx.send(x);});device.poll(wgpu::Maintain::Wait);rx.recv().unwrap().unwrap();
            let data=read.slice(..).get_mapped_range();
            let pixel=|x:usize,y:usize|&data[(y*64+x)*4..(y*64+x+1)*4];
            assert_eq!(pixel(19,32),expect,"near triangle must hide later far triangle");
            assert_eq!(pixel(50,32),[0,0,0,255],"DOC normal-dependent lighting");
            assert_eq!(pixel(0,0),[0,0,255,255],"background");
            drop(data);read.unmap();
        }
        println!("DOC_GENERATED_MESH_GPU_PASS: depth occlusion, DOC lighting, source mutation, actual readback");
    });
}
