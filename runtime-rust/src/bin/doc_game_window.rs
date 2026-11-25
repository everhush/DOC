//! Linux graphical surface/input effect for DOC-authored Radar Chase and Coin Chase.
//! No Rust game rules: scene and fixed-step transitions are native DOC expressions.
//! Only winit window events, typed DOC source facts and wgpu/WGSL presentation.
use std::{collections::VecDeque,env,process,sync::Arc,time::{Duration,Instant}};
use doc_runtime::{recurrence::Recurrence,Graph,Value};
use winit::{
    application::ApplicationHandler,
    dpi::LogicalSize,
    event::{ElementState,WindowEvent},
    event_loop::{ActiveEventLoop,ControlFlow,EventLoop},
    keyboard::{KeyCode,PhysicalKey},
    window::{Window,WindowId},
};
const STEP:Duration=Duration::from_millis(16);
const MAX_INPUT_EVENTS:usize=256;
const CARRIES:&[(&str,&str)]=&[
    ("frame","next_frame"),("player_x","next_x"),("player_y","next_y"),
    ("coin_x","next_coin_x"),("coin_y","next_coin_y"),
    ("score","next_score"),("paused","next_paused"),("won","next_won"),
    ("animation_phase","next_animation_phase"),
];

const ENTITY_CARRIES:&[(&str,&str)]=&[
    ("entity_ids","next_entity_ids"),("entity_xs","next_entity_xs"),("entity_ys","next_entity_ys"),
    ("next_entity_id","next_next_entity_id"),("issued_high_water","next_issued_high_water"),
    ("prefab_template_xs","template_next_xs"),("prefab_template_ys","template_next_ys"),
];
struct DocGame { graph:Graph, recurrence:Recurrence, action:usize }
impl DocGame{
    fn new(file:&str)->Result<Self,String>{
        let graph=Graph::parse_file(file)?;
        let mut carry=Vec::new();
        for &(source,result) in CARRIES {
            carry.push((graph.id(source).ok_or("DOC window carry source not found")?,
                        graph.id(result).ok_or("DOC window carried output not found")?));
        }
        for &(source,result) in ENTITY_CARRIES{
            match (graph.id(source),graph.id(result)){
                (Some(a),Some(b))=>carry.push((a,b)),
                (None,None)=>{},
                _=>return Err("incomplete DOC entity carry".into()),
            }
        }
        let action=graph.id("action").ok_or("DOC window action input not found")?;
        let workers=std::thread::available_parallelism().map(|n|n.get()).unwrap_or(1);
        let recurrence=Recurrence::new_automatic_with_retention(graph.clone(),carry,&[],workers,2)?;
        Ok(Self{graph,recurrence,action})
    }
    fn number(&self,name:&str)->Result<i32,String>{
        let id=self.graph.id(name).ok_or_else(||format!("missing DOC field {name}"))?;
        match self.recurrence.value(id){
            Some(Value::Int(n))=>i32::try_from(n)
                .map_err(|_|format!("DOC field {name} exceeds renderer capacity")),
            _=>Err(format!("DOC field {name} has invalid type")),
        }
    }
    fn flag(&self,name:&str)->Result<i32,String>{
        let id=self.graph.id(name).ok_or("missing DOC flag")?;
        match self.recurrence.value(id){
            Some(Value::Bool(value))=>Ok(i32::from(value)),
            _=>Err(format!("invalid DOC flag {name}")),
        }
    }
    fn entities(&self)->Result<(Vec<i64>,Vec<i64>,Vec<i64>),String>{
        let ids=["next_entity_ids","next_entity_xs","next_entity_ys"].map(|s|self.graph.id(s));
        match ids{
            [None,None,None]=>Ok((vec![],vec![],vec![])),
            [Some(i),Some(x),Some(y)]=>match (self.recurrence.value(i),self.recurrence.value(x),self.recurrence.value(y)){
                (Some(Value::Ints(i)),Some(Value::Ints(x)),Some(Value::Ints(y))) if i.len()==x.len()&&i.len()==y.len()&&i.len()<=4=>Ok((i,x,y)),
                _=>Err("invalid DOC scene entity columns".into()),
            },
            _=>Err("incomplete DOC scene entity columns".into()),
        }
    }
    fn report(&self)->Result<(),String>{
        println!("DOC_GAME_FRAME: tick={} player=({},{}) score={} paused={} won={} coin=({},{})",
            self.number("next_frame")?,self.number("next_x")?,self.number("next_y")?,
            self.number("next_score")?,self.flag("next_paused")?!=0,self.flag("next_won")?!=0,
            self.number("next_coin_x")?,self.number("next_coin_y")?);
        if self.graph.id("next_entity_ids").is_some(){
            let (ids,xs,ys)=self.entities()?;
            let hazards=xs.into_iter().zip(ys).collect::<Vec<_>>();
            println!("DOC_GAME_ENTITIES: count={} ids={ids:?} hazards={hazards:?}",ids.len());
        }
        if self.graph.id("radar_player_cell").is_some(){
            println!("DOC_GAME_RADAR: pre_action_player_cell={} pre_action_coin_cell={}",
                self.number("radar_player_cell")?,self.number("radar_coin_cell")?);
        }
        Ok(())
    }
    fn scene(&self,size:(u32,u32))->Result<[u8;128],String>{
        let px=i32::try_from(size.0).map_err(|_|"surface width overflow")?;
        let py=i32::try_from(size.1).map_err(|_|"surface height overflow")?;
        let (ids,xs,ys)=self.entities()?;
        let width=self.number("width")?;let height=self.number("height")?;
        if !(1..=200).contains(&width)||!(1..=200).contains(&height){return Err("invalid DOC grid".into());}
        let mut hx=[-1i32;4];let mut hy=[-1i32;4];
        for i in 0..ids.len(){
            hx[i]=i32::try_from(xs[i]).map_err(|_|"entity x overflow")?;
            hy[i]=i32::try_from(ys[i]).map_err(|_|"entity y overflow")?;
            if hx[i]<0||hx[i]>=width||hy[i]<0||hy[i]>=height{return Err("entity outside DOC grid".into());}
        }
        let fields=[
            px,py,self.number("width")?,self.number("height")?,
            self.number("next_x")?,self.number("next_y")?,
            self.number("next_score")?,self.number("next_frame")?,
            self.number("next_coin_x")?,self.number("next_coin_y")?,
            self.flag("next_won")?,self.flag("next_paused")?,
            self.number("wall_x")?,self.number("wall_y")?,
            self.number("next_animation_phase")?,ids.len() as i32,
            hx[0],hx[1],hx[2],hx[3],hy[0],hy[1],hy[2],hy[3],
            0,0,0,0,0,0,0,0,
        ];
        let mut data=[0u8;128];
        for (i,value) in fields.into_iter().enumerate(){
            data[i*4..i*4+4].copy_from_slice(&value.to_le_bytes());
        }
        Ok(data)
    }
    fn tick(&mut self,action:i64)->Result<(),String>{
        self.recurrence.advance(&[(self.action,Value::Int(action))])
    }
    fn title(&self)->Result<String,String>{
        Ok(format!("DOC Radar Chase · score {} · {} · WASD move / E spawn / X remove / P pause / R restart / Esc exit",
            self.number("next_score")?,
            if self.flag("next_won")?!=0{"WON"}else if self.flag("next_paused")?!=0{"PAUSED"}else{"PLAY"}))
    }
}

struct WebGpuView {
    window:Arc<Window>,
    surface:wgpu::Surface<'static>,
    device:wgpu::Device,
    queue:wgpu::Queue,
    configuration:wgpu::SurfaceConfiguration,
    pipeline:wgpu::RenderPipeline,
    bind_group:wgpu::BindGroup,
    uniform:wgpu::Buffer,
}
impl WebGpuView{
    async fn new(window:Arc<Window>)->Result<Self,String>{
        let instance=wgpu::Instance::default();
        let surface=instance.create_surface(Arc::clone(&window))
            .map_err(|e|format!("DOC_WINDOW_SURFACE_FAILURE: {e}"))?;
        let mut adapters=instance.enumerate_adapters(wgpu::Backends::all());
        let hardware=adapters.iter().position(|a|
            a.is_surface_supported(&surface) &&
            matches!(a.get_info().device_type,
                wgpu::DeviceType::IntegratedGpu|wgpu::DeviceType::DiscreteGpu));
        let software=if std::env::var("DOC_GPU_ALLOW_SOFTWARE").as_deref()==Ok("1"){
            adapters.iter().position(|a|a.is_surface_supported(&surface)
                && a.get_info().device_type==wgpu::DeviceType::Cpu)
        }else{None};
        let index=hardware.or(software)
            .ok_or("DOC_WINDOW_GPU_HARDWARE_UNAVAILABLE: no physical WebGPU presentation adapter")?;
        let adapter=adapters.swap_remove(index);
        let info=adapter.get_info();
        if matches!(info.device_type,wgpu::DeviceType::Cpu){
            eprintln!("DOC_GPU_SOFTWARE_TEST_ONLY: window uses software WebGPU");
        }
        eprintln!("DOC_WINDOW_WEBGPU_DEVICE: name={} type={:?}",info.name,info.device_type);
        let (device,queue)=adapter.request_device(&wgpu::DeviceDescriptor::default(),None)
            .await.map_err(|e|format!("DOC_WINDOW_DEVICE_FAILURE: {e}"))?;
        let size=window.inner_size();
        let mut configuration=surface.get_default_config(
            &adapter,size.width.max(1),size.height.max(1))
            .ok_or("DOC_WINDOW_NO_SURFACE_CONFIGURATION")?;
        configuration.present_mode=wgpu::PresentMode::Fifo;
        surface.configure(&device,&configuration);
        let shader=device.create_shader_module(wgpu::ShaderModuleDescriptor{
            label:Some("DOC-authored state 2D visualization"),
            source:wgpu::ShaderSource::Wgsl(include_str!("../../../engine/shaders/coin_chase.wgsl").into()),
        });
        let uniform=device.create_buffer(&wgpu::BufferDescriptor{
            label:Some("DOC snapshot presentation buffer"),size:128,
            usage:wgpu::BufferUsages::UNIFORM|wgpu::BufferUsages::COPY_DST,
            mapped_at_creation:false,
        });
        let layout=device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor{
            label:Some("DOC read-only presentation"),
            entries:&[wgpu::BindGroupLayoutEntry{
                binding:0,visibility:wgpu::ShaderStages::FRAGMENT,
                ty:wgpu::BindingType::Buffer{
                    ty:wgpu::BufferBindingType::Uniform,
                    has_dynamic_offset:false,
                    min_binding_size:None,
                },
                count:None,
            }],
        });
        let bind_group=device.create_bind_group(&wgpu::BindGroupDescriptor{
            label:Some("DOC frame binding"),layout:&layout,
            entries:&[wgpu::BindGroupEntry{binding:0,resource:uniform.as_entire_binding()}],
        });
        let pipeline_layout=device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor{
            label:Some("DOC 2D pipeline layout"),bind_group_layouts:&[&layout],
            push_constant_ranges:&[],
        });
        let pipeline=device.create_render_pipeline(&wgpu::RenderPipelineDescriptor{
            label:Some("DOC screen grid"),
            layout:Some(&pipeline_layout),
            vertex:wgpu::VertexState{
                module:&shader,entry_point:Some("vs_main"),
                buffers:&[],compilation_options:wgpu::PipelineCompilationOptions::default(),
            },
            fragment:Some(wgpu::FragmentState{
                module:&shader,entry_point:Some("fs_main"),
                targets:&[Some(wgpu::ColorTargetState{
                    format:configuration.format,
                    blend:Some(wgpu::BlendState::REPLACE),
                    write_mask:wgpu::ColorWrites::ALL,
                })],
                compilation_options:wgpu::PipelineCompilationOptions::default(),
            }),
            primitive:wgpu::PrimitiveState::default(),
            depth_stencil:None,
            multisample:wgpu::MultisampleState::default(),
            multiview:None,cache:None,
        });
        Ok(Self{window,surface,device,queue,configuration,pipeline,bind_group,uniform})
    }
    fn resize(&mut self,width:u32,height:u32){
        if width==0||height==0{return;}
        self.configuration.width=width;
        self.configuration.height=height;
        self.surface.configure(&self.device,&self.configuration);
    }
    fn render(&self,game:&DocGame,verify:bool)->Result<(),String>{
        let raw=game.scene((self.configuration.width,self.configuration.height))?;
        self.queue.write_buffer(&self.uniform,0,&raw);
        let frame=self.surface.get_current_texture()
            .map_err(|e|format!("DOC_WINDOW_SURFACE_LOSS: {e}"))?;
        let view=frame.texture.create_view(&wgpu::TextureViewDescriptor::default());
        // Render the identical shader/uniform to a copyable texture for verification.
        // Actual window presentation is separately performed below.
        let size=wgpu::Extent3d{width:self.configuration.width,height:self.configuration.height,depth_or_array_layers:1};
        let proof=if verify{
            Some(self.device.create_texture(&wgpu::TextureDescriptor{
                label:Some("DOC graphical pixel proof"),size,mip_level_count:1,sample_count:1,
                dimension:wgpu::TextureDimension::D2,format:self.configuration.format,
                usage:wgpu::TextureUsages::RENDER_ATTACHMENT|wgpu::TextureUsages::COPY_SRC,view_formats:&[],
            }))
        }else{None};
        let proof_view=proof.as_ref().map(|t|t.create_view(&wgpu::TextureViewDescriptor::default()));
        let mut encoder=self.device.create_command_encoder(
            &wgpu::CommandEncoderDescriptor{label:Some("DOC frame effect")});
        for target in std::iter::once(&view).chain(proof_view.iter()){
            let mut pass=encoder.begin_render_pass(&wgpu::RenderPassDescriptor{
                label:Some("DOC frame render"),
                color_attachments:&[Some(wgpu::RenderPassColorAttachment{
                    view:target,resolve_target:None,
                    ops:wgpu::Operations{
                        load:wgpu::LoadOp::Clear(wgpu::Color::BLACK),
                        store:wgpu::StoreOp::Store,
                    },
                })],
                depth_stencil_attachment:None,
                occlusion_query_set:None,timestamp_writes:None,
            });
            pass.set_pipeline(&self.pipeline);
            pass.set_bind_group(0,&self.bind_group,&[]);
            pass.draw(0..3,0..1);
        }
        let readback=if let Some(texture)=&proof{
            let row=(size.width*4).div_ceil(256)*256;
            let buffer=self.device.create_buffer(&wgpu::BufferDescriptor{
                label:Some("DOC pixel readback"),size:u64::from(row)*u64::from(size.height),
                usage:wgpu::BufferUsages::COPY_DST|wgpu::BufferUsages::MAP_READ,mapped_at_creation:false,
            });
            encoder.copy_texture_to_buffer(
                wgpu::TexelCopyTextureInfo{texture,mip_level:0,origin:wgpu::Origin3d::ZERO,aspect:wgpu::TextureAspect::All},
                wgpu::TexelCopyBufferInfo{buffer:&buffer,layout:wgpu::TexelCopyBufferLayout{offset:0,bytes_per_row:Some(row),rows_per_image:Some(size.height)}},size);
            Some((buffer,row))
        }else{None};
        self.queue.submit(Some(encoder.finish()));
        frame.present();
        if let Some((buffer,row))=readback{
            let (tx,rx)=std::sync::mpsc::channel();
            buffer.slice(..).map_async(wgpu::MapMode::Read,move|result|{let _=tx.send(result);});
            self.device.poll(wgpu::Maintain::Wait);
            rx.recv().map_err(|_|"pixel mapping channel closed")?.map_err(|e|format!("pixel mapping: {e}"))?;
            let data=buffer.slice(..).get_mapped_range();
            verify_pixels(game,&data,row as usize,size.width,size.height,self.configuration.format)?;
            drop(data);buffer.unmap();
        }
        Ok(())
    }
}

// Verify visible scene centers from actual GPU bytes, not host-generated pixels.
// Shader uses exact categorical primary colors at entity centers; conversion
// supports the usual linear/sRGB RGBA/BGRA surface formats.
fn verify_pixels(game:&DocGame,raw:&[u8],row:usize,width:u32,height:u32,format:wgpu::TextureFormat)->Result<(),String>{
    let bgra=match format{
        wgpu::TextureFormat::Bgra8Unorm|wgpu::TextureFormat::Bgra8UnormSrgb=>true,
        wgpu::TextureFormat::Rgba8Unorm|wgpu::TextureFormat::Rgba8UnormSrgb=>false,
        _=>return Err(format!("unsupported proof surface format {format:?}")),
    };
    let gw=game.number("width")?;let gh=game.number("height")?;
    let player=(game.number("next_x")?,game.number("next_y")?);
    let coin=(game.number("next_coin_x")?,game.number("next_coin_y")?);
    let wall=(game.number("wall_x")?,game.number("wall_y")?);
    let won=game.flag("next_won")?!=0;
    let (ids,xs,ys)=game.entities()?;
    let hazards=xs.into_iter().zip(ys).map(|(x,y)|(x as i32,y as i32)).collect::<Vec<_>>();
    let mut observed=[0usize;5];
    for y in 0..gh{for x in 0..gw{
        let px=(((x as f64+0.5)/gw as f64)*width as f64) as usize;
        let py=(((y as f64+0.5)/gh as f64)*height as f64) as usize;
        let i=py*row+px*4;
        let p=raw.get(i..i+4).ok_or("pixel readback range")?;
        let (r,g,b)=if bgra{(p[2],p[1],p[0])}else{(p[0],p[1],p[2])};
        let expected=if (x,y)==player{1}else if (x,y)==wall{2}else if hazards.contains(&(x,y)){3}
            else if !won&&(x,y)==coin{4}else{0};
        let valid=match expected{
            1=>r>200&&g>120&&b<110,
            2=>r>160&&g<110&&b<110,
            3=>r>150&&g<110&&b>150,
            4=>r<110&&g>160&&b>120,
            _=>r<100&&g<110&&b<130,
        };
        if !valid||p[3]!=255{return Err(format!("DOC_WINDOW_PIXEL_MISMATCH: cell=({x},{y}) expected={expected} rgba=({r},{g},{b},{})",p[3]));}
        observed[expected]+=1;
    }}
    println!("DOC_WINDOW_PIXEL_PASS: tick={} cells={} player={} wall={} hazards={} coin={} live_entities={}",
        game.number("next_frame")?,gw*gh,observed[1],observed[2],observed[3],observed[4],ids.len());
    Ok(())
}

struct App {
    game:DocGame,
    view:Option<WebGpuView>,
    queued:VecDeque<i64>,
    last:Instant,
    failure:Option<String>,
    replay:Option<VecDeque<i64>>,
    target_steps:Option<usize>,
    steps:usize,
    frames_presented:usize,
    pending:bool,
    verify:bool,
}
impl App {
    fn failed(&mut self,e:String,event_loop:&ActiveEventLoop){
        eprintln!("DOC_GAME_WINDOW_FAILURE: {e}");
        self.failure=Some(e);
        event_loop.exit();
    }
}
impl ApplicationHandler for App {
    fn resumed(&mut self,event_loop:&ActiveEventLoop){
        if self.view.is_some(){return;}
        let attributes=Window::default_attributes()
            .with_title("DOC Radar Chase")
            .with_inner_size(LogicalSize::new(960.0,720.0));
        let result=(||->Result<WebGpuView,String>{
            let window=Arc::new(event_loop.create_window(attributes)
                .map_err(|e|format!("DOC_WINDOW_CREATE_FAILURE: {e}"))?);
            pollster::block_on(WebGpuView::new(window))
        })();
        match result{
            Ok(view)=>{view.window.request_redraw();self.view=Some(view);self.pending=true;},
            Err(e)=>self.failed(e,event_loop),
        }
    }
    fn window_event(&mut self,event_loop:&ActiveEventLoop,window_id:WindowId,event:WindowEvent){
        if self.view.as_ref().is_none_or(|v|v.window.id()!=window_id){return;}
        match event {
            WindowEvent::CloseRequested=>event_loop.exit(),
            WindowEvent::Resized(size)=>{
                if let Some(view)=&mut self.view {view.resize(size.width,size.height);view.window.request_redraw();}
            },
            WindowEvent::KeyboardInput{event,..} if event.state==ElementState::Pressed && self.replay.is_none()=>{
                let action=match event.physical_key {
                    PhysicalKey::Code(KeyCode::Escape)=>{event_loop.exit();return;},
                    PhysicalKey::Code(KeyCode::KeyW|KeyCode::ArrowUp)=>Some(1),
                    PhysicalKey::Code(KeyCode::KeyS|KeyCode::ArrowDown)=>Some(2),
                    PhysicalKey::Code(KeyCode::KeyA|KeyCode::ArrowLeft)=>Some(3),
                    PhysicalKey::Code(KeyCode::KeyD|KeyCode::ArrowRight)=>Some(4),
                    PhysicalKey::Code(KeyCode::KeyP)=>Some(5),
                    PhysicalKey::Code(KeyCode::KeyR)=>Some(6),
                    PhysicalKey::Code(KeyCode::KeyE)=>Some(7),
                    PhysicalKey::Code(KeyCode::KeyX)=>Some(8),
                    _=>None,
                };
                if let Some(value)=action {
                    if self.queued.len()==MAX_INPUT_EVENTS{
                        self.failed("DOC_WINDOW_INPUT_BUDGET_EXHAUSTED".into(),event_loop);
                    }else{self.queued.push_back(value);}
                }
            },
            WindowEvent::RedrawRequested=>{
                if let Some(view)=&self.view {
                    if let Err(e)=view.render(&self.game,self.verify&&self.pending){
                        self.failed(e,event_loop);
                    }else{
                        if !self.pending{return;}
                        self.pending=false;
                        if let Err(e)=self.game.report(){self.failed(e,event_loop);return;}
                        self.frames_presented+=1;
                        if let Ok(frame)=self.game.number("next_frame"){
                            println!("DOC_WINDOW_PRESENTED: count={} tick={frame}",
                                self.frames_presented);
                        }
                        if self.target_steps==Some(self.steps) {
                            event_loop.exit();
                        }
                    }
                }
            },
            _=>{},
        }
    }
    fn about_to_wait(&mut self,event_loop:&ActiveEventLoop){
        if self.view.is_none(){return;}
        if self.pending{event_loop.set_control_flow(ControlFlow::Wait);return;}
        if self.target_steps==Some(self.steps){
            event_loop.set_control_flow(ControlFlow::Wait);
            return;
        }
        let now=Instant::now();
        if now.duration_since(self.last)>=STEP{
            let action=self.replay.as_mut().and_then(|r|r.pop_front())
                .or_else(||self.queued.pop_front()).unwrap_or(0);
            if let Err(e)=self.game.tick(action){
                self.failed(e,event_loop);return;
            }
            self.steps+=1;
            if let Ok(frame)=self.game.number("next_frame"){
                if let Ok(score)=self.game.number("next_score"){
                    println!("DOC_WINDOW_SCENE: tick={frame} score={score}");
                }
            }
            if let Some(view)=&self.view{
                match self.game.title(){
                    Ok(title)=>view.window.set_title(&title),
                    Err(e)=>{self.failed(e,event_loop);return;},
                }
                self.pending=true;view.window.request_redraw();
            }
            self.last=now;
        }
        event_loop.set_control_flow(ControlFlow::WaitUntil(self.last+STEP));
    }
}


fn replay_actions(raw:&str)->Result<VecDeque<i64>,String>{
    if raw.is_empty() || raw.len()>MAX_INPUT_EVENTS{
        return Err("DOC window replay must contain 1..=256 ASCII actions".into());
    }
    raw.chars().map(|action|match action{
        'w'=>Ok(1),'s'=>Ok(2),'a'=>Ok(3),'d'=>Ok(4),
        'p'=>Ok(5),'r'=>Ok(6),'e'=>Ok(7),'x'=>Ok(8),'.'=>Ok(0),
        _=>Err(format!("Unknown DOC window replay action {action:?}")),
    }).collect()
}

fn play()->Result<(),String>{
    let mut args=env::args().skip(1);
    let file=args.next().ok_or("usage: doc-game-window FILE.doc [--replay=wasdpr.]")?;
    let mut replay=None;let mut verify=false;
    for arg in args {
        if let Some(raw)=arg.strip_prefix("--replay="){
            if replay.is_some(){return Err("Duplicate DOC window replay".into());}
            replay=Some(replay_actions(raw)?);
        }else if arg=="--verify-pixels"&&!verify{verify=true;}
        else{return Err(format!("Unknown DOC window option {arg}"));}
    }
    let game=DocGame::new(&file)?;
    let event_loop=EventLoop::new()
        .map_err(|e|format!("DOC_WINDOW_EVENT_LOOP_FAILURE: {e}"))?;
    let target_steps=replay.as_ref().map(VecDeque::len);
    let mut app=App{
        game,view:None,queued:VecDeque::with_capacity(MAX_INPUT_EVENTS),
        last:Instant::now(),failure:None,
        replay,target_steps,steps:0,frames_presented:0,pending:false,verify,
    };
    event_loop.run_app(&mut app)
        .map_err(|e|format!("DOC_WINDOW_EVENT_LOOP_FAILURE: {e}"))?;
    if let Some(failure)=app.failure{ return Err(failure); }
    if let Some(target)=app.target_steps {
        if app.steps!=target || app.frames_presented!=target+1 {
            return Err("DOC_WINDOW_REPLAY_INCOMPLETE: missing ticks or presentation".into());
        }
        println!("DOC_GAME_WINDOW_REPLAY_PASS: ticks={} presented={}",
            app.steps,app.frames_presented);
    }
    if let Some(report)=app.game.recurrence.automatic_report(){eprintln!("{report}");}
    Ok(())
}
fn main(){
    if let Err(e)=play(){eprintln!("DOC_GAME_WINDOW_ERROR: {e}");process::exit(1);}
}

#[cfg(test)]
mod replay_tests {
    use super::*;
    #[test]
    fn bounded_input_actions_are_deterministic(){
        let actions=replay_actions("wasdprex.").unwrap();
        assert_eq!(actions.into_iter().collect::<Vec<_>>(),[1,3,2,4,5,6,7,8,0]);
        for bad in ["","W","q","ws\n","a".repeat(257).as_str()]{
            assert!(replay_actions(bad).is_err());
        }
    }
}
