// Independently authored Goose-owned WGSL stack interpreter proposal.
// This is NOT yet embedded by the native Goose SDL3 gfx compiler.
// Host-side ABI is common, but Goose frontend and evaluator remain native.
struct SourceWords { data: array<i32>, };
struct Instructions { code: array<vec2<i32>>, };
struct WorkItems { tasks: array<vec4<i32>>, };
struct ResultWords { data: array<u32>, };
@group(0) @binding(0) var<storage,read> arguments:SourceWords;
@group(0) @binding(1) var<storage,read> instructions:Instructions;
@group(0) @binding(2) var<storage,read> work_items:WorkItems;
@group(1) @binding(0) var<storage,read_write> result_words:ResultWords;

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid:vec3<u32>) {
    let index=gid.x;
    if(index>=arrayLength(&result_words.data)){return;}
    let task=work_items.tasks[index];
    var cells:array<i32,128>;
    var length:u32=0u;
    for(var step:i32=0;step<task.y;step=step+1){
        let inst=instructions.code[u32(task.x+step)];
        if(inst.x==1){
            cells[length]=arguments.data[u32(task.z+inst.y)];
            length=length+1u;
        } else if(inst.x==2) {
            cells[length]=inst.y;length=length+1u;
        } else if(inst.x==6){
            let alternative=cells[length-1u];
            let affirmative=cells[length-2u];
            let test=cells[length-3u]!=0;
            length=length-2u;
            cells[length-1u]=select(alternative,affirmative,test);
        } else {
            let right=cells[length-1u];
            let left=cells[length-2u];
            length=length-1u;
            var value:i32=0;
            if(inst.x==3){value=select(0,1,left==right);}
            else if(inst.x==4){value=select(0,1,left<right);}
            else if(inst.x==5){value=select(0,1,left<=right);}
            else if(inst.x==7){value=left+right;}
            else if(inst.x==8){value=left-right;}
            else if(inst.x==9){value=left*right;}
            else {return;}
            cells[length-1u]=value;
        }
    }
    let raw=cells[0];
    if(task.w==1){result_words.data[index]=bitcast<u32>(raw);}
    else {result_words.data[index]=select(0u,1u,raw!=0);}
}
