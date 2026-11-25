// Independent Rust-owned reusable DOC GPU stack kernel, ABI v1 prototype.
// This is a candidate until strict selected-GPU source parity is executed.
struct Inputs { words: array<i32>, };
struct Program { instructions: array<vec2<i32>>, };
struct Stages { descriptors: array<vec4<i32>>, };
struct Outputs { results: array<u32>, };
@group(0) @binding(0) var<storage, read> inputs: Inputs;
@group(0) @binding(1) var<storage, read> program: Program;
@group(0) @binding(2) var<storage, read> stages: Stages;
@group(1) @binding(0) var<storage, read_write> outputs: Outputs;

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) invocation: vec3<u32>) {
    let lane=invocation.x;
    if (lane>=arrayLength(&outputs.results)) {return;}
    let desc=stages.descriptors[lane];
    var stack: array<i32,128>;
    var top:u32=0u;
    for (var pc:i32=0;pc<desc.y;pc=pc+1) {
        let op=program.instructions[u32(desc.x+pc)];
        switch(op.x) {
            case 1: {stack[top]=inputs.words[u32(desc.z+op.y)];top=top+1u;}
            case 2: {stack[top]=op.y;top=top+1u;}
            case 3: {
                let b=stack[top-1u];let a=stack[top-2u];top=top-1u;
                stack[top-1u]=select(0,1,a==b);
            }
            case 4: {
                let b=stack[top-1u];let a=stack[top-2u];top=top-1u;
                stack[top-1u]=select(0,1,a<b);
            }
            case 5: {
                let b=stack[top-1u];let a=stack[top-2u];top=top-1u;
                stack[top-1u]=select(0,1,a<=b);
            }
            case 6: {
                let no=stack[top-1u];let yes=stack[top-2u];
                let pred=stack[top-3u];top=top-2u;
                stack[top-1u]=select(no,yes,pred!=0);
            }
            case 7: {
                let b=stack[top-1u];let a=stack[top-2u];top=top-1u;
                stack[top-1u]=a+b;
            }
            case 8: {
                let b=stack[top-1u];let a=stack[top-2u];top=top-1u;
                stack[top-1u]=a-b;
            }
            case 9: {
                let b=stack[top-1u];let a=stack[top-2u];top=top-1u;
                stack[top-1u]=a*b;
            }
            default: {return;}
        }
    }
    let result=stack[0];
    outputs.results[lane]=select(select(0u,1u,result!=0),bitcast<u32>(result),desc.w==1);
}
