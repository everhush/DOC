// DOC game visualization: no gameplay or compute placement rules.
struct Scene {
    viewport: vec4<i32>,
    actor: vec4<i32>,
    coin: vec4<i32>,
    wall: vec4<i32>,
    hazard_x: vec4<i32>,
    hazard_y: vec4<i32>,
    reserved_a: vec4<i32>,
    reserved_b: vec4<i32>,
}
@group(0) @binding(0) var<uniform> scene: Scene;
@vertex fn vs_main(@builtin(vertex_index) vertex_id: u32) -> @builtin(position) vec4<f32> {
    let corners = array<vec2<f32>,3>(vec2<f32>(-1.0,-3.0),vec2<f32>(3.0,1.0),vec2<f32>(-1.0,1.0));
    return vec4<f32>(corners[vertex_id],0.0,1.0);
}
@fragment fn fs_main(@builtin(position) position: vec4<f32>) -> @location(0) vec4<f32> {
    let vp=vec2<f32>(f32(max(scene.viewport.x,1)),f32(max(scene.viewport.y,1)));
    let grid=vec2<f32>(f32(scene.viewport.z),f32(scene.viewport.w));
    let uv=position.xy/vp*grid;
    let cell=vec2<i32>(floor(uv));
    let f=fract(uv);
    let d=abs(f-vec2<f32>(0.5));
    var color=vec3<f32>(0.025,0.04,0.06);
    if (min(f.x,f.y)<0.025 || max(f.x,f.y)>0.975){color=vec3<f32>(0.07,0.10,0.14);}
    if (all(cell==scene.wall.xy) && max(d.x,d.y)<0.40){color=vec3<f32>(0.9,0.035,0.035);}
    for(var i=0u;i<u32(clamp(scene.wall.w,0,4));i++){
        if(!all(cell==scene.wall.xy) && all(cell==vec2<i32>(scene.hazard_x[i],scene.hazard_y[i])) && d.x+d.y<0.46){
            color=vec3<f32>(0.75,0.025,0.85);
        }
    }
    var blocked=all(cell==scene.wall.xy);
    for(var i=0u;i<u32(clamp(scene.wall.w,0,4));i++){blocked=blocked||all(cell==vec2<i32>(scene.hazard_x[i],scene.hazard_y[i]));}
    if(!blocked && scene.coin.z==0 && all(cell==scene.coin.xy)){
        let radius=0.27+0.06*f32(scene.wall.z)/15.0;
        if(length(d)<radius){color=vec3<f32>(0.02,0.95,0.68);}
    }
    // Top-priority published player position, as in terminal presentation.
    if(all(cell==scene.actor.xy)&&max(d.x,d.y)<0.35){color=vec3<f32>(1.0,0.67,0.025);}
    // Status/score border leaves cell centers unchanged.
    if(position.y<5.0){
        if(scene.coin.z!=0){color=vec3<f32>(0.15,0.95,0.35);}
        else if(scene.coin.w!=0){color=vec3<f32>(0.35,0.45,1.0);}
        else if(position.x<min(f32(scene.actor.z)*vp.x/2.0,vp.x)){color=vec3<f32>(0.9,0.65,0.12);}
    }
    return vec4<f32>(color,1.0);
}
