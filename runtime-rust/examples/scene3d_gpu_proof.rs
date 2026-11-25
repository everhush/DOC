//! Test-only physical or software WebGPU conformance using the actual game scene.
//! Game/runtime code contains no special material, camera or mesh oracle.
use doc_runtime::{scene3d::Scene3d,scene_gpu::{adapter,MeshRenderer},Value};
use std::{path::{Path,PathBuf},fs};

struct Scratch(PathBuf);
impl Drop for Scratch{fn drop(&mut self){let _=fs::remove_dir_all(&self.0);}}

fn main(){
    let file=std::env::args().nth(1).expect("usage: scene3d_gpu_proof FILE.doc");
    let mut scene=Scene3d::open(&file,2,false).unwrap();
    let instance=wgpu::Instance::default();
    let a=adapter(&instance,None).expect("admitted WebGPU device");
    let renderer=MeshRenderer::new(&a,scene.program.clone(),wgpu::TextureFormat::Rgba8Unorm).unwrap();
    let frame=scene.frame().unwrap();
    let (w,h)=(640,480);
    let initial=renderer.offscreen(&frame,w,h).unwrap();
    assert!(initial.proof().0>=7,"actual 3D arena must display distinct materials and directional lighting");
    // For the authored isometric projection, offset (12,8,12) preserves
    // screen x/y exactly and decreases depth by 32 fixed-point units.
    // Use the actual player mesh, not synthetic clip-space triangles.
    let far=frame.draws.last().unwrap().clone();
    let mut near=far.clone();
    near.params[0]+=12;near.params[1]+=8;near.params[2]+=12;
    near.params[3]=100;near.params[4]=130;near.params[5]=160;
    let mut only=frame.clone();only.draws=vec![near.clone()];
    let nearer=renderer.offscreen(&only,w,h).unwrap();
    only.draws=vec![far.clone()];
    let farther=renderer.offscreen(&only,w,h).unwrap();
    let covered=nearer.rgba.chunks_exact(4).filter(|p|*p!=frame.clear.as_slice()).count();
    let far_covered=farther.rgba.chunks_exact(4).filter(|p|*p!=frame.clear.as_slice()).count();
    assert!(covered>200 && covered==far_covered && nearer.rgba!=farther.rgba);
    for color in [[100,130,160,255],[70,100,130,255],[40,70,100,255]]{
        assert!(nearer.rgba.chunks_exact(4).any(|p|p==color.as_slice()),"missing lit face {color:?}");
    }
    only.draws=vec![near.clone(),far.clone()];
    let near_first=renderer.offscreen(&only,w,h).unwrap();
    only.draws.reverse();
    let near_last=renderer.offscreen(&only,w,h).unwrap();
    assert_eq!(near_first.rgba,nearer.rgba,"later farther draw must not overwrite");
    assert_eq!(near_last.rgba,nearer.rgba,"nearer geometry must win regardless of order");
    // A source edit, not a host or shader-text mutation, changes only red.
    let root=Scratch(std::env::temp_dir().join(format!("doc-scene-proof-{}-{}",std::process::id(),
        std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos())));
    fs::create_dir(&root.0).unwrap();
    let src=Path::new(&file).parent().unwrap();
    for name in ["radar_chase_3d.doc","engine_math.doc","entity_pool.doc","graphics/arena_vertex.doc","graphics/mesh_fragment.doc","levels/coin_chase.txt","levels/showcase_xs.txt","levels/showcase_ys.txt","levels/arena_vertices.txt","levels/arena_indices.txt"]{
        let dst=root.0.join(name);fs::create_dir_all(dst.parent().unwrap()).unwrap();
        fs::copy(src.join(name),dst).unwrap();
    }
    let fragment=root.0.join("graphics/mesh_fragment.doc");
    let old=fs::read_to_string(&fragment).unwrap();
    let changed=old.replace("= light_r","= if(eq(light_r,0),0,0)");
    assert_ne!(old,changed);
    fs::write(&fragment,changed).unwrap();
    let mutated=Scene3d::open(root.0.join("radar_chase_3d.doc").to_str().unwrap(),2,false).unwrap();
    assert_ne!(scene.program.wgsl,mutated.program.wgsl);
    let other=MeshRenderer::new(&a,mutated.program.clone(),wgpu::TextureFormat::Rgba8Unorm).unwrap();
    let image=other.offscreen(&mutated.frame().unwrap(),w,h).unwrap();
    let mut changed_pixels=0;
    for (p,q) in initial.rgba.chunks_exact(4).zip(image.rgba.chunks_exact(4)){
        if p==frame.clear.as_slice(){assert_eq!(p,q);}
        else{assert_eq!(q[0],0);assert_eq!(&p[1..],&q[1..]);changed_pixels+=usize::from(p[0]!=0);}
    }
    assert!(changed_pixels>1000);
    scene.advance('j').unwrap();
    assert_eq!(scene.value("next_elevation").unwrap(),Value::Int(24));
    let jump=renderer.offscreen(&scene.frame().unwrap(),w,h).unwrap();
    assert_ne!(jump.rgba,initial.rgba);
    for _ in 0..8{scene.advance('.').unwrap();}
    assert_eq!(scene.value("next_elevation").unwrap(),Value::Int(0));
    // Test rejection and repeatable render/resource completion without
    // claiming asynchronous GPU lifetimes or a general graphics API.
    let mut bad=frame.clone();let i=bad.draws[0].first as usize;
    bad.indices[i]=u32::MAX;
    assert!(renderer.offscreen(&bad,w,h).is_err());
    assert!(renderer.offscreen(&frame,0,h).is_err());
    for _ in 0..16{assert_eq!(renderer.offscreen(&frame,w,h).unwrap().rgba,initial.rgba);}
    println!("DOC_SCENE_GPU_PROOF_PASS: covered={covered} mutated={changed_pixels} lighting=3 depth_orders=2 jump=24 landed=0 repeats=16 rejected=2");
}
