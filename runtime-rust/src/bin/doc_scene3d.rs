//! Generic DOC scene input, replay and native presentation host.
use doc_runtime::{scene3d::Scene3d,scene_gpu::{MeshRenderer,Pixels,adapter},Result};
use std::{path::Path,env,collections::VecDeque};
fn report_pixels(epoch:u64,p:&Pixels)->Result<()>{
    let(unique,digest)=p.proof();
    if p.rgba.len()!=p.width as usize*p.height as usize*4{return Err("DOC_SCENE: incomplete pixel data".into());}
    println!("DOC_SCENE_PIXELS: epoch={epoch} distinct={unique} digest={digest:016x}");
    Ok(())
}
fn run()->Result<()>{
    let mut args=env::args().skip(1);let file=args.next().ok_or("usage: doc-scene3d FILE.doc [--headless|--offscreen|--window] [--replay=...] [--verify-pixels] [--snapshot=FILE.ppm]")?;
    let mut mode="window";let mut replay=None;let mut verify=false;let mut snapshot=None;let mut save=None;let mut load=None;let mut audio=None;
    let mut workers=std::thread::available_parallelism().map_or(1,|n|n.get());
    for a in args{
        match a.as_str(){"--headless"=>mode="headless","--offscreen"=>mode="offscreen","--window"=>mode="window","--verify-pixels"=>verify=true,
            _=>if let Some(s)=a.strip_prefix("--replay="){if s.is_empty()||s.len()>256||!s.is_ascii(){return Err("DOC_SCENE: invalid replay".into());}replay=Some(s.chars().collect::<VecDeque<_>>());}
            else if let Some(s)=a.strip_prefix("--snapshot="){snapshot=Some(s.to_string());}
            else if let Some(s)=a.strip_prefix("--save="){save=Some(s.to_string());}
            else if let Some(s)=a.strip_prefix("--load="){load=Some(s.to_string());}
            else if let Some(s)=a.strip_prefix("--audio-dir="){audio=Some(s.to_string());}
            else if let Some(s)=a.strip_prefix("--workers="){workers=s.parse().map_err(|_|"DOC_SCENE: invalid workers")?;if workers==0{return Err("DOC_SCENE: zero workers".into());}}
            else{return Err(format!("DOC_SCENE: unknown option {a}"));}
        }
    }
    let mut scene=Scene3d::open(&file,workers,mode!="headless")?;
    if let Some(path)=load{let epoch=scene.restore(&path)?;println!("DOC_SCENE_RESTORED: saved_epoch={epoch} new_epoch=0");}
    if replay.as_ref().is_some_and(|r|r.iter().any(|&key|!scene.accepts(key))){return Err("DOC_SCENE: replay action not declared".into());}
    if mode=="window"{
        #[cfg(feature="window")]
        {return window::run(scene,replay,verify,snapshot,save,audio);}
        #[cfg(not(feature="window"))]
        {return Err("DOC_SCENE: build with window feature".into());}
    }
    if verify&&mode=="headless"{return Err("DOC_SCENE: pixel verification requires rendering".into());}
    let replay=replay.ok_or("DOC_SCENE: headless and offscreen require replay")?;
    let renderer=if mode=="offscreen"{
        let instance=wgpu::Instance::default();let a=adapter(&instance,None)?;
        Some(MeshRenderer::new(&a,scene.program.clone(),wgpu::TextureFormat::Rgba8Unorm)?)
    }else{None};
    if snapshot.is_some()&&renderer.is_none(){return Err("DOC_SCENE: snapshot requires rendering".into());}
    let count=replay.len();
    for(index,key) in std::iter::once(None).chain(replay.into_iter().map(Some)).enumerate(){
        if let Some(key)=key{scene.advance(key)?;}
        let frame=scene.frame()?;
        if let Some(renderer)=&renderer{
            let pixels=renderer.offscreen(&frame,640,480)?;
            if verify&&pixels.proof().0<2{return Err("DOC_SCENE: rendered image lacks visible variation".into());}
            report_pixels(scene.epoch(),&pixels)?;
            if index==count{if let Some(path)=&snapshot{pixels.save_ppm(Path::new(path))?;}}
        }
        println!("{}",scene.report()?);
        if index>0{if let Some(dir)=&audio{scene.emit_audio(dir)?;}}
    }
    if let Some(path)=save{scene.save(&path)?;println!("DOC_SCENE_SAVED: path={path}");}
    if let Some(report)=scene.automatic_report(){eprintln!("{report}");}
    println!("DOC_SCENE_REPLAY_PASS: mode={mode} actions={count} frames={}",count+1);
    Ok(())
}
fn main(){if let Err(e)=run(){eprintln!("DOC_SCENE_ERROR: {e}");std::process::exit(1);}}

#[cfg(feature="window")]
mod window{
    use super::*;
    use std::{sync::Arc,time::{Duration,Instant}};
    use winit::{application::ApplicationHandler,event::{WindowEvent,ElementState},event_loop::{ActiveEventLoop,EventLoop,ControlFlow},keyboard::{Key,NamedKey},window::{Window,WindowId},dpi::LogicalSize};
    struct View{window:Arc<Window>,surface:wgpu::Surface<'static>,config:wgpu::SurfaceConfiguration,renderer:MeshRenderer}
    impl View{
        fn new(loop_:&ActiveEventLoop,scene:&Scene3d)->Result<Self>{
            let window=Arc::new(loop_.create_window(Window::default_attributes().with_title("DOC 3D scene").with_inner_size(LogicalSize::new(800.,600.))).map_err(|e|e.to_string())?);
            let instance=wgpu::Instance::default();
            let surface=instance.create_surface(window.clone()).map_err(|e|e.to_string())?;
            let a=adapter(&instance,Some(&surface))?;let size=window.inner_size();
            let mut config=surface.get_default_config(&a,size.width.max(1),size.height.max(1)).ok_or("DOC_SCENE: no surface configuration")?;
            config.present_mode=wgpu::PresentMode::Fifo;
            let renderer=MeshRenderer::new(&a,scene.program.clone(),config.format)?;
            surface.configure(renderer.device(),&config);
            Ok(Self{window,surface,config,renderer})
        }
        fn resize(&mut self,w:u32,h:u32){
            if w==0||h==0{return;}
            self.config.width=w;self.config.height=h;self.surface.configure(self.renderer.device(),&self.config);
        }
        fn present(&self,scene:&Scene3d,verify:bool,snapshot:Option<&str>)->Result<()>{
            let frame=scene.frame()?;
            let pixels=if verify||snapshot.is_some(){Some(self.renderer.offscreen(&frame,self.config.width,self.config.height)?)}else{None};
            let texture=self.surface.get_current_texture().map_err(|e|format!("DOC_SCENE_SURFACE_FAILURE: {e}"))?;
            self.renderer.render(&frame,&texture.texture.create_view(&Default::default()),self.config.width,self.config.height)?;
            texture.present();
            if let Some(p)=pixels{report_pixels(scene.epoch(),&p)?;if let Some(path)=snapshot{p.save_ppm(Path::new(path))?;}}
            Ok(())
        }
    }
    struct App{scene:Scene3d,view:Option<View>,replay:Option<VecDeque<char>>,keys:VecDeque<char>,pending:bool,last:Instant,frames:usize,total:Option<usize>,verify:bool,snapshot:Option<String>,audio:Option<String>,error:Option<String>}
    impl App{
        fn fail(&mut self,l:&ActiveEventLoop,e:String){self.error=Some(e);l.exit();}
    }
    impl ApplicationHandler for App{
        fn resumed(&mut self,l:&ActiveEventLoop){
            if self.view.is_some(){return;}
            match View::new(l,&self.scene){Ok(view)=>{view.window.request_redraw();self.view=Some(view);self.pending=true;},Err(e)=>self.fail(l,e)}
        }
        fn window_event(&mut self,l:&ActiveEventLoop,id:WindowId,event:WindowEvent){
            if self.view.as_ref().is_none_or(|v|v.window.id()!=id){return;}
            match event{
                WindowEvent::CloseRequested=>l.exit(),
                WindowEvent::Resized(s)=>{if let Some(v)=&mut self.view{v.resize(s.width,s.height);v.window.request_redraw();}println!("DOC_SCENE_RESIZE: {}x{}",s.width,s.height);},
                WindowEvent::KeyboardInput{event,..} if event.state==ElementState::Pressed&&self.replay.is_none()=>{
                    let key=match event.logical_key{
                        Key::Named(NamedKey::Escape)=>{l.exit();return;},
                        Key::Named(NamedKey::Space)=>Some('j'),
                        Key::Character(s)=>{let mut it=s.chars();let c=it.next();if it.next().is_none(){c.map(|c|c.to_ascii_lowercase())}else{None}},
                        _=>None};
                    if let Some(c)=key{if self.scene.accepts(c){if self.keys.len()>=256{self.fail(l,"DOC_SCENE: input budget".into());}else{self.keys.push_back(c);println!("DOC_SCENE_INPUT: key={c}");}}}
                },
                WindowEvent::RedrawRequested=>{
                    let done=self.total==Some(self.frames+1);
                    let snap=if self.pending&&done{self.snapshot.as_deref()}else{None};
                    let result=self.view.as_ref().unwrap().present(&self.scene,self.pending&&self.verify,snap);
                    if let Err(e)=result{self.fail(l,e);return;}
                    if self.pending{
                        self.pending=false;self.frames+=1;
                        match self.scene.report(){Ok(report)=>{println!("{report}");self.view.as_ref().unwrap().window.set_title(&report);},Err(e)=>{self.fail(l,e);return;}}
                        println!("DOC_SCENE_PRESENTED: epoch={}",self.scene.epoch());
                        if self.scene.epoch()>0{if let Some(dir)=&self.audio{if let Err(e)=self.scene.emit_audio(dir){self.fail(l,e);return;}}}
                        if done{l.exit();}
                    }
                },
                _=>{}
            }
        }
        fn about_to_wait(&mut self,l:&ActiveEventLoop){
            if self.view.is_none()||self.pending||self.total==Some(self.frames){l.set_control_flow(ControlFlow::Wait);return;}
            let now=Instant::now();let step=Duration::from_millis(80);
            if now.duration_since(self.last)>=step{
                let key=self.replay.as_mut().and_then(|r|r.pop_front()).or_else(||self.keys.pop_front()).unwrap_or('.');
                if let Err(e)=self.scene.advance(key){self.fail(l,e);return;}
                self.pending=true;self.last=now;self.view.as_ref().unwrap().window.request_redraw();
            }
            l.set_control_flow(ControlFlow::WaitUntil(self.last+step));
        }
    }
    pub fn run(scene:Scene3d,replay:Option<VecDeque<char>>,verify:bool,snapshot:Option<String>,save:Option<String>,audio:Option<String>)->Result<()>{
        let total=replay.as_ref().map(|r|r.len()+1);
        if snapshot.is_some()&&total.is_none(){return Err("DOC_SCENE: snapshot requires replay".into());}
        let l=EventLoop::new().map_err(|e|e.to_string())?;
        let mut app=App{scene,view:None,replay,keys:VecDeque::new(),pending:false,last:Instant::now(),frames:0,total,verify,snapshot,audio,error:None};
        l.run_app(&mut app).map_err(|e|e.to_string())?;
        if let Some(e)=app.error{return Err(e);}
        if let Some(t)=total{if app.frames!=t{return Err("DOC_SCENE: incomplete surface replay".into());}println!("DOC_SCENE_REPLAY_PASS: mode=window actions={} frames={t}",t-1);}
        if let Some(path)=save{app.scene.save(&path)?;println!("DOC_SCENE_SAVED: path={path}");}
        if let Some(report)=app.scene.automatic_report(){eprintln!("{report}");}
        Ok(())
    }
}
